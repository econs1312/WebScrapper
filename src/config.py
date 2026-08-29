"""Configurações centralizadas do WebScrapper."""

from __future__ import annotations

import random
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

# Pool de User-Agents reais para rotação
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
]


class ScrapperConfig(BaseSettings):
    """Configurações do WebScrapper com valores padrão sensatos."""

    # --- Busca ---
    max_results: int = Field(default=10, description="Número máximo de resultados por termo")
    search_delay_min: float = Field(default=2.0, description="Delay mínimo entre buscas (s)")
    search_delay_max: float = Field(default=5.0, description="Delay máximo entre buscas (s)")
    request_timeout: int = Field(default=30000, description="Timeout por requisição (ms)")
    google_base_url: str = Field(
        default="https://www.google.com/search",
        description="URL base do Google Search",
    )

    # --- Retry ---
    max_retries: int = Field(default=3, description="Número máximo de tentativas por termo")
    retry_backoff_base: float = Field(default=2.0, description="Base do backoff exponencial (s)")

    # --- Browser ---
    headless: bool = Field(default=True, description="Executar browser em modo headless")
    browser_type: str = Field(default="chromium", description="Tipo de browser Playwright")

    # --- Output ---
    output_dir: Path = Field(default=Path("results"), description="Diretório de saída")
    save_raw_html: bool = Field(default=True, description="Salvar HTML raw das SERPs")
    raw_html_dir: Path = Field(default=Path("results/raw_html"), description="Dir do HTML raw")

    # --- Logging ---
    log_level: str = Field(default="INFO", description="Nível de log")
    log_file: Path | None = Field(default=Path("results/scrapper.log"), description="Arquivo de log")

    model_config = {"env_prefix": "WEBSCRAPPER_", "env_file": ".env"}

    def get_random_user_agent(self) -> str:
        """Retorna um User-Agent aleatório do pool."""
        return random.choice(_USER_AGENTS)

    def get_random_delay(self) -> float:
        """Retorna um delay aleatório entre min e max."""
        return random.uniform(self.search_delay_min, self.search_delay_max)

    def ensure_dirs(self) -> None:
        """Cria diretórios de output se não existirem."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.save_raw_html:
            self.raw_html_dir.mkdir(parents=True, exist_ok=True)
