"""Testes do parser de SERP usando HTML mockado."""

from pathlib import Path

import pytest

from src.parser import detect_captcha, detect_no_results, parse_serp_html

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestParseSerpHtml:
    """Testes do parser principal."""

    @pytest.fixture()
    def serp_html(self) -> str:
        return (FIXTURES_DIR / "google_serp_10_results.html").read_text(encoding="utf-8")

    @pytest.fixture()
    def captcha_html(self) -> str:
        return (FIXTURES_DIR / "google_captcha.html").read_text(encoding="utf-8")

    @pytest.fixture()
    def no_results_html(self) -> str:
        return (FIXTURES_DIR / "google_no_results.html").read_text(encoding="utf-8")

    def test_parse_10_results(self, serp_html: str) -> None:
        """Deve extrair exatamente 10 resultados do mock."""
        results = parse_serp_html(serp_html, max_results=10)
        assert len(results) == 10

    def test_result_positions(self, serp_html: str) -> None:
        """Posições devem ser sequenciais de 1 a 10."""
        results = parse_serp_html(serp_html, max_results=10)
        positions = [r.position for r in results]
        assert positions == list(range(1, 11))

    def test_result_titles_not_empty(self, serp_html: str) -> None:
        """Todos os resultados devem ter título não-vazio."""
        results = parse_serp_html(serp_html, max_results=10)
        for result in results:
            assert result.title.strip(), f"Resultado #{result.position} sem título"

    def test_result_urls_valid(self, serp_html: str) -> None:
        """Todos os resultados devem ter URLs válidas (http/https)."""
        results = parse_serp_html(serp_html, max_results=10)
        for result in results:
            assert result.url.startswith("http"), f"URL inválida: {result.url}"

    def test_result_urls_no_google(self, serp_html: str) -> None:
        """URLs não devem ser de domínios do Google."""
        results = parse_serp_html(serp_html, max_results=10)
        for result in results:
            assert "google.com" not in result.url, f"URL do Google encontrada: {result.url}"

    def test_result_urls_unique(self, serp_html: str) -> None:
        """Não deve haver URLs duplicadas."""
        results = parse_serp_html(serp_html, max_results=10)
        urls = [r.url for r in results]
        assert len(urls) == len(set(urls)), "URLs duplicadas encontradas"

    def test_result_snippets(self, serp_html: str) -> None:
        """A maioria dos resultados deve ter snippet."""
        results = parse_serp_html(serp_html, max_results=10)
        with_snippets = sum(1 for r in results if r.snippet.strip())
        assert with_snippets >= 8, f"Apenas {with_snippets}/10 resultados com snippet"

    def test_max_results_limit(self, serp_html: str) -> None:
        """Deve respeitar o limite de max_results."""
        results = parse_serp_html(serp_html, max_results=5)
        assert len(results) == 5

    def test_first_result_content(self, serp_html: str) -> None:
        """Verificar conteúdo do primeiro resultado."""
        results = parse_serp_html(serp_html, max_results=10)
        first = results[0]
        assert first.position == 1
        assert "Beautiful Soup" in first.title or "Real Python" in first.title
        assert "realpython.com" in first.url

    def test_empty_html(self) -> None:
        """HTML vazio deve retornar lista vazia."""
        results = parse_serp_html("", max_results=10)
        assert results == []

    def test_html_without_results(self) -> None:
        """HTML sem resultados deve retornar lista vazia."""
        html = "<html><body><div>No search results here</div></body></html>"
        results = parse_serp_html(html, max_results=10)
        assert results == []


class TestDetectCaptcha:
    """Testes de detecção de CAPTCHA."""

    @pytest.fixture()
    def captcha_html(self) -> str:
        return (FIXTURES_DIR / "google_captcha.html").read_text(encoding="utf-8")

    def test_detect_captcha(self, captcha_html: str) -> None:
        assert detect_captcha(captcha_html) is True

    def test_no_captcha_in_normal_html(self) -> None:
        html = "<html><body><div>Normal page content</div></body></html>"
        assert detect_captcha(html) is False

    def test_detect_unusual_traffic(self) -> None:
        html = "<html><body>unusual traffic from your computer</body></html>"
        assert detect_captcha(html) is True

    def test_detect_recaptcha(self) -> None:
        html = "<html><body><div class='g-recaptcha'></div></body></html>"
        assert detect_captcha(html) is True


class TestDetectNoResults:
    """Testes de detecção de busca sem resultados."""

    @pytest.fixture()
    def no_results_html(self) -> str:
        return (FIXTURES_DIR / "google_no_results.html").read_text(encoding="utf-8")

    def test_detect_no_results(self, no_results_html: str) -> None:
        assert detect_no_results(no_results_html) is True

    def test_no_detection_in_normal_html(self) -> None:
        html = "<html><body><div>Normal page with results</div></body></html>"
        assert detect_no_results(html) is False

    def test_detect_no_match(self) -> None:
        html = "<html><body>did not match any documents</body></html>"
        assert detect_no_results(html) is True
