"""Provedores de busca (Google com Playwright e DuckDuckGo com HTTPX)."""

from __future__ import annotations

import abc
import asyncio
import logging
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.models import SearchResult

if TYPE_CHECKING:
    from src.config import ScrapperConfig

logger = logging.getLogger(__name__)


class BaseSearchProvider(abc.ABC):
    """Interface abstrata para provedores de busca."""

    def __init__(self, config: ScrapperConfig) -> None:
        self.config = config

    @abc.abstractmethod
    async def start(self) -> None:
        """Inicializa conexões ou navegadores necessários."""
        pass

    @abc.abstractmethod
    async def stop(self) -> None:
        """Encerra recursos."""
        pass

    @abc.abstractmethod
    async def search_raw(self, term: str) -> str:
        """Retorna o HTML raw da página de resultados."""
        pass

    async def __aenter__(self) -> BaseSearchProvider:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.stop()


class GoogleSearchProvider(BaseSearchProvider):
    """Busca termos no Google usando Playwright com técnicas de stealth."""

    def __init__(self, config: ScrapperConfig) -> None:
        super().__init__(config)
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def _create_stealth_context(self) -> BrowserContext:
        """Cria um contexto de browser com configurações stealth."""
        assert self._browser is not None

        context = await self._browser.new_context(
            user_agent=self.config.get_random_user_agent(),
            viewport={"width": 1920, "height": 1080},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            geolocation={"latitude": -23.5505, "longitude": -46.6333},
            permissions=["geolocation"],
            java_script_enabled=True,
            has_touch=False,
            is_mobile=False,
            color_scheme="light",
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['pt-BR', 'pt', 'en-US', 'en'],
            });
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);
        """)

        return context

    async def start(self) -> None:
        """Inicia o browser Playwright."""
        pw = await async_playwright().start()
        self._browser = await pw.chromium.launch(
            headless=self.config.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        self._context = await self._create_stealth_context()
        logger.info("Browser Playwright iniciado (headless=%s)", self.config.headless)

    async def stop(self) -> None:
        """Para o browser e limpa recursos."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        logger.info("Browser Playwright encerrado")

    async def search_raw(self, term: str) -> str:
        """Busca um termo no Google e retorna o HTML."""
        if not self._context:
            raise RuntimeError("Browser não iniciado. Chame start() primeiro.")

        page: Page = await self._context.new_page()
        try:
            search_url = f"{self.config.google_base_url}?q={term}&num={self.config.max_results}&hl=pt-BR"
            logger.info("Buscando no Google: '%s' → %s", term, search_url)

            await page.goto(
                search_url,
                wait_until="domcontentloaded",
                timeout=self.config.request_timeout,
            )

            selectors = ["#search", "#rso", "div[data-async-context]", "div.g"]
            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=10000)
                    break
                except Exception:
                    continue

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.5)
            return await page.content()
        finally:
            await page.close()

    async def search(self, term: str) -> str:
        """Alias de compatibilidade."""
        return await self.search_raw(term)


class DuckDuckGoSearchProvider(BaseSearchProvider):
    """
    Busca termos no DuckDuckGo via requisições HTTP diretas (sem CAPTCHAs e super rápido).
    """

    def __init__(self, config: ScrapperConfig) -> None:
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Inicializa o cliente HTTP assíncrono."""
        self._client = httpx.AsyncClient(
            timeout=float(self.config.request_timeout / 1000),
            follow_redirects=True,
            headers={
                "User-Agent": self.config.get_random_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        logger.info("DuckDuckGo HTTP Provider inicializado")

    async def stop(self) -> None:
        """Encerra o cliente HTTP."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("DuckDuckGo HTTP Provider encerrado")

    async def search_raw(self, term: str) -> str:
        """Executa a busca no DuckDuckGo HTML e retorna o HTML raw."""
        if not self._client:
            raise RuntimeError("Cliente HTTP não iniciado. Chame start() primeiro.")

        url = self.config.duckduckgo_base_url
        logger.info("Buscando no DuckDuckGo: '%s' → %s", term, url)

        # O DuckDuckGo HTML aceita POST com form-data
        response = await self._client.post(url, data={"q": term, "b": ""})
        response.raise_for_status()
        return response.text

    def parse_results(self, html: str, max_results: int = 10) -> list[SearchResult]:
        """Extrai os resultados orgânicos do HTML do DuckDuckGo."""
        soup = BeautifulSoup(html, "lxml")
        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        # Selecionar blocos de resultados (ignorando blocos de anúncios)
        result_elements = soup.select("div.result.results_links, div.web-result, div.result")
        position = 0

        for el in result_elements:
            if position >= max_results:
                break

            # Pular anúncios
            classes = el.get("class", [])
            if any("ad" in c.lower() for c in classes) or el.select_one(".badge--ad, .result__badge--ad"):
                continue

            # Link e Título
            link_el = el.select_one("a.result__url, a.result__a, a.result__snippet")
            title_el = el.select_one("a.result__a, h2.result__title, a.result__title")

            if not link_el:
                continue

            raw_href = link_el.get("href", "")
            clean_url = self._extract_clean_url(str(raw_href))

            # Ignorar URLs vazias, duplicadas ou de anúncios (y.js / aclick)
            if not clean_url or clean_url in seen_urls:
                continue
            if "duckduckgo.com/y.js" in clean_url or "bing.com/aclick" in clean_url:
                continue

            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            # Snippet
            snippet_el = el.select_one("a.result__snippet, div.result__snippet")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            position += 1
            seen_urls.add(clean_url)
            results.append(SearchResult(
                position=position,
                title=title,
                url=clean_url,
                snippet=snippet,
            ))

        return results

    @staticmethod
    def _extract_clean_url(href: str) -> str:
        """Limpa links com redirecionamento //duckduckgo.com/l/?uddg=..."""
        if not href:
            return ""

        if href.startswith("//"):
            href = "https:" + href

        if "duckduckgo.com/l/?" in href:
            parsed = urlparse(href)
            query = parse_qs(parsed.query)
            if "uddg" in query and query["uddg"]:
                return unquote(query["uddg"][0])

        if href.startswith("http"):
            # Evitar links diretos de tracking de anúncio
            if "duckduckgo.com/y.js" in href or "bing.com/aclick" in href:
                return ""
            return href

        return ""

    async def search(self, term: str) -> str:
        """Alias de compatibilidade."""
        return await self.search_raw(term)


def create_search_provider(config: ScrapperConfig) -> BaseSearchProvider:
    """Factory para instanciar o provedor de busca configurado."""
    engine = config.search_engine.lower().strip()
    if engine in ["google"]:
        return GoogleSearchProvider(config)
    return DuckDuckGoSearchProvider(config)
