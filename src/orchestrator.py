"""Orquestrador principal do WebScrapper com suporte multi-engine."""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

from src.models import (
    HarnessReport,
    SearchReport,
    SearchResult,
    SearchStatus,
    TermsInput,
)
from src.parser import detect_captcha, detect_no_results, parse_serp_html
from src.search_provider import DuckDuckGoSearchProvider, create_search_provider

if TYPE_CHECKING:
    from pathlib import Path

    from src.config import ScrapperConfig

logger = logging.getLogger(__name__)


class SearchOrchestrator:
    """Orquestra a busca de múltiplos termos no Google ou DuckDuckGo."""

    def __init__(self, config: ScrapperConfig) -> None:
        self.config = config
        self.provider = create_search_provider(config)

    def load_terms_from_file(self, file_path: Path) -> list[str]:
        """Carrega termos de um arquivo JSON."""
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        terms_input = TermsInput(**data)
        logger.info("Carregados %d termos de %s", len(terms_input.terms), file_path)
        return terms_input.terms

    @staticmethod
    def parse_terms_string(terms_str: str) -> list[str]:
        """Parseia uma string de termos separados por vírgula."""
        terms = [t.strip() for t in terms_str.split(",") if t.strip()]
        return terms

    async def search_term(self, term: str) -> SearchReport:
        """
        Busca um único termo com retry e backoff.

        Args:
            term: Termo de busca.

        Returns:
            SearchReport com os resultados ou erro.
        """
        last_error: str | None = None

        for attempt in range(1, self.config.max_retries + 1):
            start_time = time.time()

            try:
                logger.info(
                    "[%s] Tentativa %d/%d para '%s'",
                    self.config.search_engine,
                    attempt,
                    self.config.max_retries,
                    term,
                )

                # Buscar HTML da SERP
                html = await self.provider.search_raw(term)
                duration = time.time() - start_time

                # Salvar HTML raw se configurado
                raw_html_path: str | None = None
                if self.config.save_raw_html:
                    raw_html_path = self._save_raw_html(term, html, attempt)

                results: list[SearchResult] = []

                if isinstance(self.provider, DuckDuckGoSearchProvider):
                    results = self.provider.parse_results(html, self.config.max_results)
                else:
                    # Google - Verificar CAPTCHA
                    if detect_captcha(html):
                        logger.warning("CAPTCHA detectado para '%s' na tentativa %d", term, attempt)
                        last_error = "CAPTCHA detectado"
                        if attempt < self.config.max_retries:
                            backoff = self.config.retry_backoff_base ** attempt
                            logger.info("Aguardando %.1fs antes de retry...", backoff)
                            await asyncio.sleep(backoff)
                        continue

                    # Verificar se não há resultados
                    if detect_no_results(html):
                        return SearchReport(
                            term=term,
                            status=SearchStatus.SUCCESS,
                            results=[],
                            results_count=0,
                            duration_seconds=duration,
                            attempt=attempt,
                            raw_html_path=raw_html_path,
                        )

                    results = parse_serp_html(html, self.config.max_results)

                # Determinar status
                if len(results) >= self.config.max_results:
                    status = SearchStatus.SUCCESS
                elif len(results) > 0:
                    status = SearchStatus.PARTIAL
                else:
                    status = SearchStatus.FAILED
                    last_error = "Nenhum resultado extraído da busca"
                    if attempt < self.config.max_retries:
                        backoff = self.config.retry_backoff_base ** attempt
                        await asyncio.sleep(backoff)
                    continue

                return SearchReport(
                    term=term,
                    status=status,
                    results=results,
                    results_count=len(results),
                    duration_seconds=duration,
                    attempt=attempt,
                    raw_html_path=raw_html_path,
                )

            except TimeoutError:
                duration = time.time() - start_time
                last_error = f"Timeout após {duration:.1f}s"
                logger.warning("Timeout na tentativa %d para '%s'", attempt, term)
                if attempt < self.config.max_retries:
                    backoff = self.config.retry_backoff_base ** attempt
                    await asyncio.sleep(backoff)

            except Exception as e:
                duration = time.time() - start_time
                last_error = str(e)
                logger.error(
                    "Erro na tentativa %d para '%s': %s",
                    attempt,
                    term,
                    e,
                )
                if attempt < self.config.max_retries:
                    backoff = self.config.retry_backoff_base ** attempt
                    await asyncio.sleep(backoff)

        # Todas as tentativas falharam
        return SearchReport(
            term=term,
            status=SearchStatus.FAILED,
            results=[],
            results_count=0,
            duration_seconds=time.time() - start_time,
            attempt=self.config.max_retries,
            error_message=last_error,
        )

    async def run(self, terms: list[str]) -> HarnessReport:
        """
        Executa a busca para todos os termos.

        Args:
            terms: Lista de termos de busca.

        Returns:
            HarnessReport com resultados agregados.
        """
        harness_report = HarnessReport(started_at=datetime.now())
        self.config.ensure_dirs()

        async with self.provider:
            for i, term in enumerate(terms, 1):
                logger.info("━━━ Termo %d/%d: '%s' ━━━", i, len(terms), term)

                report = await self.search_term(term)
                harness_report.reports.append(report)

                logger.info(
                    "Resultado: %s (%d resultados em %.1fs)",
                    report.status.value,
                    report.results_count,
                    report.duration_seconds,
                )

                # Delay entre buscas (exceto a última)
                if i < len(terms):
                    delay = self.config.get_random_delay()
                    logger.debug("Delay de %.1fs antes do próximo termo", delay)
                    await asyncio.sleep(delay)

        # Calcular métricas finais
        harness_report.calculate_metrics()

        # Exportar resultados
        self._export_json(harness_report)
        self._export_csv(harness_report)

        return harness_report

    def _save_raw_html(self, term: str, html: str, attempt: int) -> str:
        """Salva o HTML raw de uma SERP."""
        safe_term = "".join(c if c.isalnum() or c == " " else "_" for c in term)
        safe_term = safe_term.replace(" ", "_")[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.config.search_engine}_{safe_term}_{timestamp}_attempt{attempt}.html"
        filepath = self.config.raw_html_dir / filename
        filepath.write_text(html, encoding="utf-8")
        logger.debug("HTML raw salvo em: %s", filepath)
        return str(filepath)

    def _export_json(self, report: HarnessReport) -> None:
        """Exporta relatório completo em JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.config.output_dir / f"report_{timestamp}.json"
        filepath.write_text(
            report.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info("Relatório JSON exportado: %s", filepath)

    def _export_csv(self, report: HarnessReport) -> None:
        """Exporta resultados individuais em CSV."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.config.output_dir / f"results_{timestamp}.csv"

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "term", "position", "title", "url", "snippet",
                "status", "timestamp", "duration_seconds",
            ])

            for search_report in report.reports:
                for result in search_report.results:
                    writer.writerow([
                        search_report.term,
                        result.position,
                        result.title,
                        result.url,
                        result.snippet,
                        search_report.status.value,
                        search_report.timestamp.isoformat(),
                        f"{search_report.duration_seconds:.2f}",
                    ])

        logger.info("Resultados CSV exportados: %s", filepath)
