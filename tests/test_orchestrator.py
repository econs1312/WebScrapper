"""Testes do orquestrador com search provider mockado."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.config import ScrapperConfig
from src.models import SearchStatus
from src.orchestrator import SearchOrchestrator

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestSearchOrchestrator:
    """Testes do orquestrador."""

    @pytest.fixture()
    def config(self, tmp_path: Path) -> ScrapperConfig:
        return ScrapperConfig(
            search_engine="google",
            max_results=10,
            max_retries=2,
            search_delay_min=0.01,
            search_delay_max=0.02,
            headless=True,
            output_dir=tmp_path / "results",
            raw_html_dir=tmp_path / "results" / "raw_html",
            save_raw_html=True,
        )

    @pytest.fixture()
    def orchestrator(self, config: ScrapperConfig) -> SearchOrchestrator:
        return SearchOrchestrator(config)

    @pytest.fixture()
    def serp_html(self) -> str:
        return (FIXTURES_DIR / "google_serp_10_results.html").read_text(encoding="utf-8")

    def test_load_terms_from_file(self, orchestrator: SearchOrchestrator, tmp_path: Path) -> None:
        """Deve carregar termos de um arquivo JSON."""
        terms_data = {
            "terms": ["term1", "term2", "term3"],
            "metadata": {"version": "1.0"},
        }
        terms_file = tmp_path / "terms.json"
        terms_file.write_text(json.dumps(terms_data))

        terms = orchestrator.load_terms_from_file(terms_file)
        assert terms == ["term1", "term2", "term3"]

    def test_parse_terms_string(self) -> None:
        """Deve parsear termos de uma string separada por vírgula."""
        terms = SearchOrchestrator.parse_terms_string("python, javascript, rust")
        assert terms == ["python", "javascript", "rust"]

    def test_parse_terms_string_empty(self) -> None:
        """Deve retornar lista vazia para string vazia."""
        terms = SearchOrchestrator.parse_terms_string("")
        assert terms == []

    def test_parse_terms_string_with_spaces(self) -> None:
        """Deve tratar espaços corretamente."""
        terms = SearchOrchestrator.parse_terms_string("  python  ,  ,  rust  ")
        assert terms == ["python", "rust"]

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_search_term_success(
        self,
        orchestrator: SearchOrchestrator,
        serp_html: str,
    ) -> None:
        """Deve retornar SUCCESS quando encontra 10 resultados."""
        orchestrator.provider.search_raw = AsyncMock(return_value=serp_html)
        orchestrator.provider.start = AsyncMock()
        orchestrator.provider.stop = AsyncMock()
        orchestrator.config.ensure_dirs()

        report = await orchestrator.search_term("python web scraping")

        assert report.status == SearchStatus.SUCCESS
        assert report.results_count == 10
        assert report.term == "python web scraping"
        assert report.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_search_term_captcha(
        self,
        orchestrator: SearchOrchestrator,
    ) -> None:
        """Deve retornar FAILED quando detecta CAPTCHA após todas as tentativas."""
        orchestrator.config.search_engine = "google"
        from src.search_provider import GoogleSearchProvider
        orchestrator.provider = GoogleSearchProvider(orchestrator.config)
        captcha_html = (FIXTURES_DIR / "google_captcha.html").read_text(encoding="utf-8")
        orchestrator.provider.search_raw = AsyncMock(return_value=captcha_html)
        orchestrator.provider.start = AsyncMock()
        orchestrator.provider.stop = AsyncMock()
        orchestrator.config.ensure_dirs()

        report = await orchestrator.search_term("test captcha")

        assert report.status == SearchStatus.FAILED
        assert report.results_count == 0

    @pytest.mark.asyncio
    async def test_search_term_no_results(
        self,
        orchestrator: SearchOrchestrator,
    ) -> None:
        """Deve retornar SUCCESS com 0 resultados quando Google não encontra nada."""
        orchestrator.config.search_engine = "google"
        from src.search_provider import GoogleSearchProvider
        orchestrator.provider = GoogleSearchProvider(orchestrator.config)
        no_results_html = (FIXTURES_DIR / "google_no_results.html").read_text(encoding="utf-8")
        orchestrator.provider.search_raw = AsyncMock(return_value=no_results_html)
        orchestrator.provider.start = AsyncMock()
        orchestrator.provider.stop = AsyncMock()
        orchestrator.config.ensure_dirs()

        report = await orchestrator.search_term("xyznonexistent123")

        assert report.status == SearchStatus.SUCCESS
        assert report.results_count == 0

    @pytest.mark.asyncio
    async def test_run_multiple_terms(
        self,
        orchestrator: SearchOrchestrator,
        serp_html: str,
    ) -> None:
        """Deve processar múltiplos termos e gerar relatório agregado."""
        orchestrator.provider.search_raw = AsyncMock(return_value=serp_html)
        orchestrator.provider.start = AsyncMock()
        orchestrator.provider.stop = AsyncMock()
        orchestrator.config.ensure_dirs()

        report = await orchestrator.run(["term1", "term2"])

        assert report.total_terms == 2
        assert report.successful == 2
        assert report.success_rate == 1.0
        assert report.total_results == 20

    @pytest.mark.asyncio
    async def test_exports_json_and_csv(
        self,
        orchestrator: SearchOrchestrator,
        serp_html: str,
    ) -> None:
        """Deve exportar resultados em JSON e CSV."""
        orchestrator.provider.search_raw = AsyncMock(return_value=serp_html)
        orchestrator.provider.start = AsyncMock()
        orchestrator.provider.stop = AsyncMock()
        orchestrator.config.ensure_dirs()

        await orchestrator.run(["test"])

        json_files = list(orchestrator.config.output_dir.glob("report_*.json"))
        csv_files = list(orchestrator.config.output_dir.glob("results_*.csv"))

        assert len(json_files) >= 1, "JSON report não foi gerado"
        assert len(csv_files) >= 1, "CSV results não foi gerado"


