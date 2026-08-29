"""Testes do harness: validator e reporter."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from harness.validator import ResultValidator
from src.models import (
    HarnessReport,
    SearchReport,
    SearchResult,
    SearchStatus,
)

if TYPE_CHECKING:
    from pathlib import Path


def _make_results(count: int) -> list[SearchResult]:
    """Helper para criar N resultados válidos."""
    return [
        SearchResult(
            position=i,
            title=f"Title {i}",
            url=f"https://example{i}.com/page",
            snippet=f"Snippet for result {i}",
        )
        for i in range(1, count + 1)
    ]


def _make_report(
    term: str,
    status: SearchStatus,
    results_count: int = 0,
    error: str | None = None,
) -> SearchReport:
    """Helper para criar um SearchReport."""
    results = _make_results(results_count) if results_count > 0 else []
    return SearchReport(
        term=term,
        status=status,
        results=results,
        results_count=results_count,
        duration_seconds=5.0,
        error_message=error,
    )


class TestResultValidator:
    """Testes do validador de resultados."""

    @pytest.fixture()
    def validator(self) -> ResultValidator:
        return ResultValidator(expected_results=10)

    def test_valid_report_all_success(self, validator: ResultValidator) -> None:
        """Relatório com todos os termos com 10 resultados deve ser válido."""
        harness = HarnessReport(
            reports=[
                _make_report("t1", SearchStatus.SUCCESS, 10),
                _make_report("t2", SearchStatus.SUCCESS, 10),
            ]
        )
        harness.calculate_metrics()

        validation = validator.validate_report(harness)
        assert validation.is_valid
        assert validation.errors == 0

    def test_failed_report(self, validator: ResultValidator) -> None:
        """Relatório com termos falhados deve ter erros."""
        harness = HarnessReport(
            reports=[
                _make_report("t1", SearchStatus.FAILED, error="Timeout"),
            ]
        )
        harness.calculate_metrics()

        validation = validator.validate_report(harness)
        assert not validation.is_valid
        assert validation.errors > 0

    def test_blocked_report(self, validator: ResultValidator) -> None:
        """Relatório com termos bloqueados deve ter erros."""
        harness = HarnessReport(
            reports=[
                _make_report("t1", SearchStatus.BLOCKED),
            ]
        )
        harness.calculate_metrics()

        validation = validator.validate_report(harness)
        assert not validation.is_valid

    def test_partial_results_warning(self, validator: ResultValidator) -> None:
        """Termos com resultado SUCCESS mas < 10 resultados geram warning."""
        report = _make_report("t1", SearchStatus.SUCCESS, 7)
        harness = HarnessReport(reports=[report])
        harness.calculate_metrics()

        validation = validator.validate_report(harness)
        assert validation.warnings > 0

    def test_low_success_rate_warning(self, validator: ResultValidator) -> None:
        """Taxa de sucesso < 90% deve gerar warning."""
        harness = HarnessReport(
            reports=[
                _make_report("t1", SearchStatus.SUCCESS, 10),
                _make_report("t2", SearchStatus.FAILED, error="err"),
                _make_report("t3", SearchStatus.FAILED, error="err"),
            ]
        )
        harness.calculate_metrics()

        validation = validator.validate_report(harness)
        # Verifica que há warning de taxa de sucesso
        rate_warnings = [
            i for i in validation.issues
            if i.field == "success_rate"
        ]
        assert len(rate_warnings) >= 1

    def test_empty_report(self, validator: ResultValidator) -> None:
        """Relatório vazio deve ter erro."""
        harness = HarnessReport()

        validation = validator.validate_report(harness)
        assert not validation.is_valid
        assert validation.errors > 0

    def test_duplicate_urls_warning(self, validator: ResultValidator) -> None:
        """URLs duplicadas devem gerar warning."""
        results = [
            SearchResult(position=1, title="T1", url="https://example.com/a", snippet="s"),
            SearchResult(position=2, title="T2", url="https://example.com/a", snippet="s"),
        ]
        report = SearchReport(
            term="test",
            status=SearchStatus.SUCCESS,
            results=results,
            results_count=2,
            duration_seconds=1.0,
        )
        harness = HarnessReport(reports=[report])
        harness.calculate_metrics()

        validation = validator.validate_report(harness)
        dup_warnings = [
            i for i in validation.issues
            if "duplicada" in i.message
        ]
        assert len(dup_warnings) >= 1

    def test_empty_title_error(self, validator: ResultValidator) -> None:
        """Resultado com título vazio deve gerar erro."""
        results = [
            SearchResult(position=1, title=" ", url="https://example.com/a", snippet="s"),
        ]
        report = SearchReport(
            term="test",
            status=SearchStatus.PARTIAL,
            results=results,
            results_count=1,
            duration_seconds=1.0,
        )
        harness = HarnessReport(reports=[report])
        harness.calculate_metrics()

        validation = validator.validate_report(harness)
        title_errors = [
            i for i in validation.issues
            if i.field == "title"
        ]
        assert len(title_errors) >= 1


class TestReporter:
    """Testes do reporter."""

    def test_generate_markdown_report(self, tmp_path: Path) -> None:
        """Deve gerar relatório Markdown."""
        from harness.reporter import Reporter

        harness = HarnessReport(
            reports=[_make_report("t1", SearchStatus.SUCCESS, 10)]
        )
        harness.calculate_metrics()

        validator = ResultValidator(expected_results=10)
        validation = validator.validate_report(harness)

        reporter = Reporter(output_dir=tmp_path)
        md_path = reporter.generate_markdown_report(harness, validation)

        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")
        assert "WebScrapper" in content
        assert "t1" in content

    def test_generate_json_summary(self, tmp_path: Path) -> None:
        """Deve gerar sumário JSON."""
        import json

        from harness.reporter import Reporter

        harness = HarnessReport(
            reports=[_make_report("t1", SearchStatus.SUCCESS, 10)]
        )
        harness.calculate_metrics()

        validator = ResultValidator(expected_results=10)
        validation = validator.validate_report(harness)

        reporter = Reporter(output_dir=tmp_path)
        json_path = reporter.generate_json_summary(harness, validation)

        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data["metrics"]["total_terms"] == 1
        assert data["validation"]["is_valid"] is True
