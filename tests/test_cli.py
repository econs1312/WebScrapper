"""Testes para a interface CLI."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from src.cli import main, setup_logging
from src.models import HarnessReport, SearchReport, SearchResult, SearchStatus

if TYPE_CHECKING:
    from pathlib import Path


def _dummy_harness_report() -> HarnessReport:
    """Gera um HarnessReport para mock."""
    results = [
        SearchResult(
            position=i,
            title=f"Resultado {i}",
            url=f"https://exemplo{i}.com",
            snippet=f"Snippet {i}",
        )
        for i in range(1, 11)
    ]
    report = SearchReport(
        term="python",
        status=SearchStatus.SUCCESS,
        results=results,
        results_count=10,
        duration_seconds=2.5,
        attempt=1,
    )
    hr = HarnessReport(reports=[report])
    hr.calculate_metrics()
    return hr


class TestCli:
    """Testes dos comandos do CLI."""

    def test_setup_logging_with_file(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        setup_logging("DEBUG", log_file)
        assert log_file.parent.exists()

    def test_search_no_args_fails(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["search"])
        assert result.exit_code != 0
        assert "Forneça termos via --terms ou --file" in result.output

    def test_search_empty_terms_string(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["search", "--terms", " , "])
        assert result.exit_code != 0

    @patch("src.cli.SearchOrchestrator.run")
    def test_search_with_terms_success(self, mock_run: AsyncMock, tmp_path: Path) -> None:
        mock_run.return_value = _dummy_harness_report()
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "search",
                "--terms",
                "python,rust",
                "--output",
                str(tmp_path / "results"),
            ],
        )
        assert result.exit_code == 0
        assert "WebScrapper" in result.output

    @patch("src.cli.SearchOrchestrator.run")
    def test_search_with_file_success(self, mock_run: AsyncMock, tmp_path: Path) -> None:
        terms_file = tmp_path / "terms.json"
        terms_file.write_text(json.dumps({"terms": ["python", "playwright"]}))

        mock_run.return_value = _dummy_harness_report()
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "search",
                "--file",
                str(terms_file),
                "--output",
                str(tmp_path / "results"),
            ],
        )
        assert result.exit_code == 0

    @patch("src.cli.SearchOrchestrator.run")
    def test_search_low_success_rate_exits_1(self, mock_run: AsyncMock, tmp_path: Path) -> None:
        report = SearchReport(
            term="fail",
            status=SearchStatus.FAILED,
            results=[],
            results_count=0,
            duration_seconds=1.0,
            attempt=3,
        )
        hr = HarnessReport(reports=[report])
        hr.calculate_metrics()
        mock_run.return_value = hr

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "search",
                "--terms",
                "fail",
                "--output",
                str(tmp_path / "results"),
            ],
        )
        assert result.exit_code == 1

    def test_validate_no_reports(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["validate", "--results-dir", str(tmp_path)])
        assert result.exit_code != 0
        assert "Nenhum relatório encontrado" in result.output

    def test_validate_valid_report(self, tmp_path: Path) -> None:
        report_file = tmp_path / "report_20260101_120000.json"
        hr = _dummy_harness_report()
        report_file.write_text(hr.model_dump_json())

        runner = CliRunner()
        result = runner.invoke(main, ["validate", "--results-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "Total de termos" in result.output

    def test_validate_corrupted_json(self, tmp_path: Path) -> None:
        report_file = tmp_path / "report_20260101_120000.json"
        report_file.write_text("invalid json content")

        runner = CliRunner()
        result = runner.invoke(main, ["validate", "--results-dir", str(tmp_path)])
        assert "Erro ao validar" in result.output
