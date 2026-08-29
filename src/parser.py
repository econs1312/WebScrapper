"""Parser de resultados de busca do Google usando BeautifulSoup."""

from __future__ import annotations

import logging
import re
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup, Tag

from src.models import SearchResult

logger = logging.getLogger(__name__)


# Conjuntos de seletores CSS para extrair resultados orgânicos do Google.
# O Google muda frequentemente o layout, então mantemos fallbacks.
_RESULT_CONTAINER_SELECTORS = [
    "div.g:not(.g-blk)",          # Seletor clássico de resultado orgânico
    "div[data-hveid] div.g",       # Wrapper com data attribute
    "div.MjjYud div.g",           # Layout 2024+
    "#rso > div > div.g",         # Filhos diretos do container de resultados
    "div[data-sokoban-container] div.g",  # Variante moderna
]

_TITLE_SELECTORS = [
    "h3",
    "h3.LC20lb",
    "h3.DKV0Md",
    "a h3",
]

_URL_SELECTORS = [
    "a[href][data-ved]",
    "div.yuRUbf > div > span > a",
    "div.yuRUbf > a",
    "a[jsname]",
]

_SNIPPET_SELECTORS = [
    "div.VwiC3b",
    "div[data-sncf]",
    "span.aCOpRe",
    "div.IsZvec",
    "div[style='-webkit-line-clamp:2']",
]


def _extract_text(element: Tag | None, selectors: list[str]) -> str:
    """Extrai texto do primeiro seletor que corresponder."""
    if element is None:
        return ""

    for selector in selectors:
        found = element.select_one(selector)
        if found and found.get_text(strip=True):
            return found.get_text(strip=True)

    return ""


def _extract_url(element: Tag) -> str:
    """Extrai a URL limpa de um elemento de resultado."""
    for selector in _URL_SELECTORS:
        link = element.select_one(selector)
        if link and link.get("href"):
            href = str(link["href"])
            # Limpar URLs de redirecionamento do Google
            if href.startswith("/url?"):
                match = re.search(r"[?&]q=([^&]+)", href)
                if match:
                    return unquote(match.group(1))
            elif href.startswith("http"):
                return href

    # Fallback: primeiro <a> com href http
    for link in element.find_all("a", href=True):
        href = str(link["href"])
        if href.startswith("http") and "google.com" not in href:
            return href

    return ""


def _is_organic_result(url: str) -> bool:
    """Verifica se a URL é de um resultado orgânico (não anúncio/widget)."""
    if not url:
        return False

    parsed = urlparse(url)
    # Excluir domínios do Google (maps, images, books, etc.)
    google_domains = [
        "google.com", "google.com.br", "gstatic.com",
        "googleapis.com", "youtube.com",
    ]
    return all(not parsed.netloc.endswith(domain) for domain in google_domains)


def parse_serp_html(html: str, max_results: int = 10) -> list[SearchResult]:
    """
    Parseia o HTML de uma SERP do Google e extrai os resultados orgânicos.

    Args:
        html: HTML raw da página de resultados do Google.
        max_results: Número máximo de resultados a extrair (padrão: 10).

    Returns:
        Lista de SearchResult com os resultados orgânicos encontrados.
    """
    soup = BeautifulSoup(html, "lxml")
    results: list[SearchResult] = []
    seen_urls: set[str] = set()

    # Tentar cada conjunto de seletores até encontrar resultados
    result_elements: list[Tag] = []
    for selector in _RESULT_CONTAINER_SELECTORS:
        elements = soup.select(selector)
        if elements:
            result_elements = elements
            logger.debug(
                "Seletor '%s' encontrou %d elementos",
                selector,
                len(elements),
            )
            break

    if not result_elements:
        logger.warning(
            "Nenhum resultado encontrado com os seletores conhecidos. "
            "O layout do Google pode ter mudado."
        )
        return results

    position = 0
    for element in result_elements:
        if position >= max_results:
            break

        # Extrair dados
        url = _extract_url(element)
        if not url or not _is_organic_result(url):
            continue

        # Deduplicar por URL
        if url in seen_urls:
            continue
        seen_urls.add(url)

        title = _extract_text(element, _TITLE_SELECTORS)
        snippet = _extract_text(element, _SNIPPET_SELECTORS)

        if not title:
            logger.debug("Resultado sem título ignorado: %s", url)
            continue

        position += 1

        result = SearchResult(
            position=position,
            title=title,
            url=url,
            snippet=snippet,
        )
        results.append(result)
        logger.debug("Resultado #%d: %s — %s", position, title[:50], url[:80])

    logger.info("Extraídos %d resultados orgânicos de %d elementos", len(results), len(result_elements))
    return results


def detect_captcha(html: str) -> bool:
    """Detecta se a página contém um CAPTCHA ou bloqueio."""
    captcha_indicators = [
        "unusual traffic",
        "tráfego incomum",
        "captcha",
        "recaptcha",
        "robot",
        "automated queries",
        "sorry/index",
        "blocked",
    ]
    html_lower = html.lower()
    return any(indicator in html_lower for indicator in captcha_indicators)


def detect_no_results(html: str) -> bool:
    """Detecta se a SERP indica que não há resultados."""
    no_result_indicators = [
        "nenhum resultado encontrado",
        "did not match any documents",
        "não corresponde a nenhum documento",
        "your search -",
    ]
    html_lower = html.lower()
    return any(indicator in html_lower for indicator in no_result_indicators)
