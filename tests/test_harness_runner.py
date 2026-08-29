"""Testes para o executor do harness (run_harness.py)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from harness.run_harness import main, setup_logging
from src.models import HarnessReport, SearchReport, SearchResult, SearchStatus

if TYPE_CHECKING:
    from pathlib import Path


def _dummy_harness_report(success: bool = True) -> HarnessReport:
    """Gera um HarnessReport para mock."""
    results = [
        SearchResult(
            position=i,
            title=f"Resultado {i}",
            url=f"https://exemplo{i}.com",
            snippet=f"Snippet {i}",
        )
        for i in range(1, 11)
    ] if success else []

    status = SearchStatus.SUCCESS if success else SearchStatus.FAILED
    report = SearchReport(
        term="python",
        status=status,
        results=results,
        results_count=len(results),
        duration_seconds=2.0,
        attempt=1 if success else 3,
        error_message=None if success else "Failed",
    )
    hr = HarnessReport(reports=[report])
    hr.calculate_metrics()
    return hr


class TestHarnessRunner:
    """Testes para o runner principal do harness."""

    def test_setup_logging(self) -> None:
        setup_logging("DEBUG")

    def test_no_args_fails(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code != 0
        assert "Forneça --terms ou --file" in result.output

    def test_empty_terms_fails(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--terms", " , "])
        assert result.exit_code != 0

    @patch("harness.run_harness.SearchOrchestrator.run")
    def test_run_success_with_terms(self, mock_run: AsyncMock, tmp_path: Path) -> None:
        mock_run.return_value = _dummy_harness_report(success=True)
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--terms",
                "python,scraping",
                "--output",
                str(tmp_path / "results"),
            ],
        )
        assert result.exit_code == 0
        assert "Harness concluído com sucesso" in result.output

    @patch("harness.run_harness.SearchOrchestrator.run")
    def test_run_success_with_file(self, mock_run: AsyncMock, tmp_path: Path) -> None:
        terms_file = tmp_path / "terms.json"
        terms_file.write_text(json.dumps({"terms": ["python", "playwright"]}))

        mock_run.return_value = _dummy_harness_report(success=True)
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--file",
                str(terms_file),
                "--output",
                str(tmp_path / "results"),
            ],
        )
        assert result.exit_code == 0

    @patch("harness.run_harness.SearchOrchestrator.run")
    def test_run_failure_exits_1(self, mock_run: AsyncMock, tmp_path: Path) -> None:
        mock_run.return_value = _dummy_harness_report(success=False)
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--terms",
                "falha",
                "--output",
                str(tmp_path / "results"),
            ],
        )
        assert result.exit_code == 1
        assert "Harness concluído com erros" in result.output
