"""Provider de busca no Google usando Playwright em modo stealth."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

if TYPE_CHECKING:
    from src.config import ScrapperConfig

logger = logging.getLogger(__name__)


class GoogleSearchProvider:
    """Busca termos no Google usando Playwright com técnicas de stealth."""

    def __init__(self, config: ScrapperConfig) -> None:
        self.config = config
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

        # Injetar scripts stealth para mascarar detecção de automação
        await context.add_init_script("""
            // Remover propriedade webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            // Mascarar plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });

            // Mascarar linguagens
            Object.defineProperty(navigator, 'languages', {
                get: () => ['pt-BR', 'pt', 'en-US', 'en'],
            });

            // Chrome runtime mock
            window.chrome = {
                runtime: {},
            };

            // Permissions mock
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

    async def search(self, term: str) -> str:
        """
        Busca um termo no Google e retorna o HTML da página de resultados.

        Args:
            term: Termo de busca.

        Returns:
            HTML raw da página de resultados do Google.

        Raises:
            RuntimeError: Se o browser não estiver iniciado.
            TimeoutError: Se a página não carregar no tempo limite.
        """
        if not self._context:
            raise RuntimeError("Browser não iniciado. Chame start() primeiro.")

        page: Page = await self._context.new_page()

        try:
            search_url = f"{self.config.google_base_url}?q={term}&num={self.config.max_results}&hl=pt-BR"
            logger.info("Buscando: '%s' → %s", term, search_url)

            # Navegar para a página de busca
            await page.goto(
                search_url,
                wait_until="domcontentloaded",
                timeout=self.config.request_timeout,
            )

            # Esperar pelos resultados orgânicos
            # Tentar múltiplos seletores (o Google muda frequentemente)
            selectors = [
                "#search",
                "#rso",
                "div[data-async-context]",
                "div.g",
            ]

            result_found = False
            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=10000)
                    result_found = True
                    logger.debug("Seletor encontrado: %s", selector)
                    break
                except Exception:
                    continue

            if not result_found:
                logger.warning(
                    "Nenhum seletor de resultados encontrado para '%s'. "
                    "Possível CAPTCHA ou bloqueio.",
                    term,
                )

            # Scroll para carregar todos os resultados (lazy loading)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)

            # Extrair HTML completo
            html_content = await page.content()
            logger.info(
                "HTML extraído para '%s' (%d bytes)",
                term,
                len(html_content),
            )

            return html_content

        finally:
            await page.close()

    async def __aenter__(self) -> GoogleSearchProvider:
        """Suporte a context manager async."""
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Cleanup do context manager."""
        await self.stop()
