"""
Harness Runner — Loop principal de execução do WebScrapper.

Executa o scraper em loop com retry, validação e reporting.
Pode ser executado standalone ou pelo CI/CD.

Uso:
    python -m harness.run_harness --file terms.json
    python -m harness.run_harness --terms "python,javascript"
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

from harness.reporter import Reporter
from harness.validator import ResultValidator
from src.config import ScrapperConfig
from src.orchestrator import SearchOrchestrator

console = Console()
logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO") -> None:
    """Configura logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[
            RichHandler(console=console, show_path=False, markup=True),
        ],
        format="%(message)s",
        datefmt="[%X]",
    )


@click.command()
@click.option("--terms", "-t", type=str, default=None, help="Termos separados por vírgula.")
@click.option(
    "--file", "-f", "terms_file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Arquivo JSON com termos.",
)
@click.option("--output", "-o", type=click.Path(path_type=Path), default="results")
@click.option("--max-retries", type=int, default=3, help="Tentativas por termo.")
@click.option("--headless/--no-headless", default=True)
@click.option("--log-level", type=str, default="INFO")
def main(
    terms: str | None,
    terms_file: Path | None,
    output: Path,
    max_retries: int,
    headless: bool,
    log_level: str,
) -> None:
    """🏗️ Harness Runner — Executa o scraper com validação e reporting."""
    setup_logging(log_level)

    if not terms and not terms_file:
        console.print("[red]❌ Forneça --terms ou --file[/red]")
        sys.exit(1)

    console.print(Panel.fit(
        "[bold cyan]🏗️ WebScrapper Harness[/bold cyan]\n"
        "Loop de execução com validação e retry",
        border_style="cyan",
    ))

    # Configurar
    config = ScrapperConfig(
        max_retries=max_retries,
        headless=headless,
        output_dir=output,
        raw_html_dir=output / "raw_html",
        log_level=log_level,
    )

    # Carregar termos
    orchestrator = SearchOrchestrator(config)
    if terms_file:
        term_list = orchestrator.load_terms_from_file(terms_file)
    else:
        assert terms is not None
        term_list = orchestrator.parse_terms_string(terms)

    if not term_list:
        console.print("[red]❌ Nenhum termo válido[/red]")
        sys.exit(1)

    logger.info("Iniciando harness com %d termos", len(term_list))

    # ═══════════════════════════════════════════
    # LOOP PRINCIPAL DO HARNESS
    # ═══════════════════════════════════════════
    harness_report = asyncio.run(orchestrator.run(term_list))

    # ═══════════════════════════════════════════
    # VALIDAÇÃO
    # ═══════════════════════════════════════════
    validator = ResultValidator(expected_results=config.max_results)
    validation = validator.validate_report(harness_report)

    # ═══════════════════════════════════════════
    # REPORTING
    # ═══════════════════════════════════════════
    reporter = Reporter(output_dir=config.output_dir)
    md_path = reporter.generate_markdown_report(harness_report, validation)
    json_path = reporter.generate_json_summary(harness_report, validation)

    console.print(f"\n[bold]📄 Relatório Markdown:[/bold] {md_path}")
    console.print(f"[bold]📄 Sumário JSON:[/bold] {json_path}")

    # ═══════════════════════════════════════════
    # RESULTADO
    # ═══════════════════════════════════════════
    if validation.is_valid:
        console.print(Panel.fit(
            f"[bold green]✅ Harness concluído com sucesso[/bold green]\n"
            f"Taxa de sucesso: {harness_report.success_rate:.1%} | "
            f"Resultados: {harness_report.total_results}",
            border_style="green",
        ))
        sys.exit(0)
    else:
        console.print(Panel.fit(
            f"[bold red]❌ Harness concluído com erros[/bold red]\n"
            f"Erros: {validation.errors} | Warnings: {validation.warnings}\n"
            f"Taxa de sucesso: {harness_report.success_rate:.1%}",
            border_style="red",
        ))
        sys.exit(1)


if __name__ == "__main__":
    main()
