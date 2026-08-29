"""Testes para o GoogleSearchProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import ScrapperConfig
from src.search_provider import DuckDuckGoSearchProvider, GoogleSearchProvider


class TestGoogleSearchProvider:
    """Testes para o provedor de busca do Google."""

    @pytest.fixture()
    def config(self) -> ScrapperConfig:
        return ScrapperConfig(request_timeout=5000)

    @pytest.fixture()
    def provider(self, config: ScrapperConfig) -> GoogleSearchProvider:
        return GoogleSearchProvider(config)

    @pytest.mark.asyncio
    async def test_search_without_start_raises_error(self, provider: GoogleSearchProvider) -> None:
        with pytest.raises(RuntimeError, match="Browser não iniciado"):
            await provider.search("python")

    @pytest.mark.asyncio
    async def test_start_and_stop(self, provider: GoogleSearchProvider) -> None:
        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()

        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.add_init_script = AsyncMock()

        with patch("src.search_provider.async_playwright") as mock_ap:
            mock_ap_instance = MagicMock()
            mock_ap_instance.start = AsyncMock(return_value=mock_pw)
            mock_ap.return_value = mock_ap_instance

            await provider.start()
            assert provider._browser is not None
            assert provider._context is not None

            await provider.stop()
            mock_context.close.assert_awaited_once()
            mock_browser.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_success(self, provider: GoogleSearchProvider) -> None:
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.evaluate = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html><body>Mock SERP</body></html>")
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        provider._context = mock_context

        html = await provider.search("python")
        assert "Mock SERP" in html
        mock_page.goto.assert_awaited_once()
        mock_page.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_search_selector_timeout_still_returns_content(self, provider: GoogleSearchProvider) -> None:
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
        mock_page.evaluate = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html><body>Fallback content</body></html>")
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        provider._context = mock_context

        html = await provider.search("python")
        assert "Fallback content" in html
        mock_page.close.assert_awaited_once()


class TestDuckDuckGoSearchProvider:
    """Testes para o provedor DuckDuckGo."""

    @pytest.fixture()
    def config(self) -> ScrapperConfig:
        return ScrapperConfig(search_engine="duckduckgo")

    @pytest.fixture()
    def provider(self, config: ScrapperConfig) -> DuckDuckGoSearchProvider:
        return DuckDuckGoSearchProvider(config)

    @pytest.fixture()
    def ddg_html(self) -> str:
        return """
        <html><body>
        <div class="result results_links">
          <h2><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fpython.org%2F">Python Official Site</a></h2>
          <a class="result__snippet">Python is a programming language that lets you work quickly.</a>
        </div>
        <div class="result results_links">
          <h2><a class="result__a" href="https://realpython.com/tutorials/">Real Python Tutorials</a></h2>
          <a class="result__snippet">Learn Python online with comprehensive tutorials.</a>
        </div>
        </body></html>
        """

    @pytest.mark.asyncio
    async def test_search_without_start_raises_error(self, provider: DuckDuckGoSearchProvider) -> None:
        with pytest.raises(RuntimeError, match="Cliente HTTP não iniciado"):
            await provider.search_raw("python")

    @pytest.mark.asyncio
    async def test_search_raw_success(self, provider: DuckDuckGoSearchProvider, ddg_html: str) -> None:
        mock_response = MagicMock()
        mock_response.text = ddg_html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        provider._client = mock_client

        html = await provider.search_raw("python")
        assert "Python Official Site" in html
        mock_client.post.assert_awaited_once()

    def test_parse_results(self, provider: DuckDuckGoSearchProvider, ddg_html: str) -> None:
        results = provider.parse_results(ddg_html, max_results=10)
        assert len(results) == 2
        assert results[0].position == 1
        assert results[0].title == "Python Official Site"
        assert results[0].url == "https://python.org/"
        assert "programming language" in results[0].snippet

        assert results[1].position == 2
        assert results[1].title == "Real Python Tutorials"
        assert results[1].url == "https://realpython.com/tutorials/"

    def test_extract_clean_url(self) -> None:
        url = DuckDuckGoSearchProvider._extract_clean_url("//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage%3Fid%3D1")
        assert url == "https://example.com/page?id=1"

        direct_url = DuckDuckGoSearchProvider._extract_clean_url("https://example.org")
        assert direct_url == "https://example.org"

        empty_url = DuckDuckGoSearchProvider._extract_clean_url("")
        assert empty_url == ""


class TestFactory:
    """Testes da factory de provedores."""

    def test_create_google_provider(self) -> None:
        from src.search_provider import GoogleSearchProvider, create_search_provider
        cfg = ScrapperConfig(search_engine="google")
        provider = create_search_provider(cfg)
        assert isinstance(provider, GoogleSearchProvider)

    def test_create_duckduckgo_provider(self) -> None:
        from src.search_provider import DuckDuckGoSearchProvider, create_search_provider
        cfg = ScrapperConfig(search_engine="duckduckgo")
        provider = create_search_provider(cfg)
        assert isinstance(provider, DuckDuckGoSearchProvider)
