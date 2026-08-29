"""Testes para o GoogleSearchProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import ScrapperConfig
from src.search_provider import GoogleSearchProvider


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
