"""Interface CLI do WebScrapper usando Click + Rich."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from src.config import ScrapperConfig
from src.models import SearchStatus
from src.orchestrator import SearchOrchestrator

console = Console()


def setup_logging(level: str, log_file: Path | None = None) -> None:
    """Configura logging com Rich handler."""
    handlers: list[logging.Handler] = [
        RichHandler(
            console=console,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
        )
    ]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=handlers,
        format="%(message)s",
        datefmt="[%X]",
    )


@click.group()
@click.version_option(version="1.0.0", prog_name="WebScrapper")
def main() -> None:
    """🔍 WebScrapper — Busca termos no Google e extrai os 10 primeiros resultados."""
    pass


@main.command()
@click.option(
    "--terms", "-t",
    type=str,
    default=None,
    help="Termos separados por vírgula. Ex: 'python,javascript'",
)
@click.option(
    "--file", "-f",
    "terms_file",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Arquivo JSON com lista de termos.",
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default="results",
    help="Diretório de saída dos resultados.",
)
@click.option(
    "--max-results", "-n",
    type=int,
    default=10,
    help="Número máximo de resultados por termo.",
)
@click.option(
    "--delay-min",
    type=float,
    default=2.0,
    help="Delay mínimo entre buscas (segundos).",
)
@click.option(
    "--delay-max",
    type=float,
    default=5.0,
    help="Delay máximo entre buscas (segundos).",
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="Executar browser em modo headless.",
)
@click.option(
    "--save-html/--no-save-html",
    default=True,
    help="Salvar HTML raw das SERPs.",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Nível de log.",
)
def search(
    terms: str | None,
    terms_file: Path | None,
    output: Path,
    max_results: int,
    delay_min: float,
    delay_max: float,
    headless: bool,
    save_html: bool,
    log_level: str,
) -> None:
    """🔎 Buscar termos no Google e extrair resultados."""
    if not terms and not terms_file:
        console.print(
            "[red]❌ Forneça termos via --terms ou --file[/red]"
        )
        sys.exit(1)

    # Configurar
    config = ScrapperConfig(
        max_results=max_results,
        search_delay_min=delay_min,
        search_delay_max=delay_max,
        headless=headless,
        save_raw_html=save_html,
        output_dir=output,
        raw_html_dir=output / "raw_html",
        log_level=log_level,
    )
    setup_logging(log_level, config.log_file)

    # Carregar termos
    orchestrator = SearchOrchestrator(config)

    if terms_file:
        term_list = orchestrator.load_terms_from_file(terms_file)
    else:
        assert terms is not None
        term_list = orchestrator.parse_terms_string(terms)

    if not term_list:
        console.print("[red]❌ Nenhum termo válido encontrado.[/red]")
        sys.exit(1)

    # Header
    console.print(Panel.fit(
        f"[bold cyan]🔍 WebScrapper[/bold cyan]\n"
        f"Termos: {len(term_list)} | Max resultados: {max_results} | "
        f"Headless: {headless}",
        border_style="cyan",
    ))

    # Executar
    report = asyncio.run(orchestrator.run(term_list))

    # Exibir resultados
    _display_report(report)

    # Exit code baseado na taxa de sucesso
    if report.success_rate < 0.5:
        sys.exit(1)


@main.command()
@click.option(
    "--results-dir", "-r",
    type=click.Path(exists=True, path_type=Path),
    default="results",
    help="Diretório com resultados para validar.",
)
def validate(results_dir: Path) -> None:
    """✅ Validar integridade dos resultados exportados."""
    import json as json_module

    from src.models import HarnessReport

    json_files = list(results_dir.glob("report_*.json"))
    if not json_files:
        console.print(f"[yellow]⚠️  Nenhum relatório encontrado em {results_dir}[/yellow]")
        sys.exit(1)

    for json_file in sorted(json_files, reverse=True):
        console.print(f"\n[bold]📄 {json_file.name}[/bold]")
        try:
            data = json_module.loads(json_file.read_text(encoding="utf-8"))
            report = HarnessReport(**data)

            table = Table(show_header=True, header_style="bold")
            table.add_column("Métrica")
            table.add_column("Valor", justify="right")

            table.add_row("Total de termos", str(report.total_terms))
            table.add_row("Sucesso", f"[green]{report.successful}[/green]")
            table.add_row("Parcial", f"[yellow]{report.partial}[/yellow]")
            table.add_row("Falha", f"[red]{report.failed}[/red]")
            table.add_row("Bloqueado", f"[red]{report.blocked}[/red]")
            table.add_row("Total de resultados", str(report.total_results))
            table.add_row(
                "Taxa de sucesso",
                f"{'[green]' if report.success_rate >= 0.9 else '[red]'}"
                f"{report.success_rate:.1%}[/]",
            )

            console.print(table)

        except Exception as e:
            console.print(f"[red]❌ Erro ao validar {json_file.name}: {e}[/red]")


@main.command()
@click.option(
    "--host",
    "-h",
    type=str,
    default="127.0.0.1",
    help="Host para vinculação do servidor web.",
)
@click.option(
    "--port",
    "-p",
    type=int,
    default=8000,
    help="Porta para o servidor web.",
)
@click.option(
    "--reload/--no-reload",
    default=False,
    help="Habilitar recarga automática (auto-reload) do servidor.",
)
def serve(host: str, port: int, reload: bool) -> None:
    """🌐 Iniciar o servidor e painel web do WebScrapper."""
    import uvicorn

    console.print(
        Panel.fit(
            f"[bold cyan]🌐 WebScrapper Dashboard[/bold cyan]\n"
            f"Interface web disponível em: [bold underline green]http://{host}:{port}[/bold underline green]\n"
            f"Pressione [bold red]Ctrl+C[/bold red] para encerrar.",
            border_style="cyan",
        )
    )
    uvicorn.run("src.server:app", host=host, port=port, reload=reload)


def _display_report(report: object) -> None:
    """Exibe o relatório formatado no terminal."""
    from src.models import HarnessReport

    assert isinstance(report, HarnessReport)

    # Tabela de resultados por termo
    table = Table(
        title="📊 Resultados da Busca",
        show_header=True,
        header_style="bold magenta",
        border_style="bright_black",
    )
    table.add_column("Termo", style="cyan", max_width=40)
    table.add_column("Status", justify="center")
    table.add_column("Resultados", justify="right")
    table.add_column("Tempo", justify="right")
    table.add_column("Tentativa", justify="center")

    status_styles = {
        SearchStatus.SUCCESS: "[green]✅ OK[/green]",
        SearchStatus.PARTIAL: "[yellow]⚠️  Parcial[/yellow]",
        SearchStatus.FAILED: "[red]❌ Falha[/red]",
        SearchStatus.BLOCKED: "[red]🚫 Bloqueado[/red]",
    }

    for r in report.reports:
        table.add_row(
            r.term[:40],
            status_styles.get(r.status, r.status.value),
            str(r.results_count),
            f"{r.duration_seconds:.1f}s",
            str(r.attempt),
        )

    console.print(table)

    # Resumo
    success_color = "green" if report.success_rate >= 0.9 else "yellow" if report.success_rate >= 0.5 else "red"
    console.print(Panel.fit(
        f"[bold]📈 Resumo[/bold]\n"
        f"Total: {report.total_terms} termos | "
        f"Resultados: {report.total_results} | "
        f"Tempo: {report.total_duration_seconds:.1f}s\n"
        f"Taxa de sucesso: [{success_color}]{report.success_rate:.1%}[/{success_color}]",
        border_style=success_color,
    ))


if __name__ == "__main__":
    main()
