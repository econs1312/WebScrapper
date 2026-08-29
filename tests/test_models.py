"""Testes dos modelos Pydantic."""

import pytest
from pydantic import ValidationError

from src.models import (
    HarnessReport,
    SearchReport,
    SearchResult,
    SearchStatus,
    SearchTerm,
    TermsInput,
)


class TestSearchResult:
    """Testes para o modelo SearchResult."""

    def test_valid_result(self) -> None:
        result = SearchResult(
            position=1,
            title="Test Title",
            url="https://example.com",
            snippet="Test snippet",
        )
        assert result.position == 1
        assert result.title == "Test Title"
        assert result.url == "https://example.com"
        assert result.snippet == "Test snippet"

    def test_is_valid(self) -> None:
        result = SearchResult(position=1, title="Title", url="https://example.com")
        assert result.is_valid()

    def test_is_invalid_empty_title(self) -> None:
        result = SearchResult(position=1, title="  ", url="https://example.com")
        assert not result.is_valid()

    def test_is_invalid_empty_url(self) -> None:
        result = SearchResult(position=1, title="Title", url="  ")
        assert not result.is_valid()

    def test_position_range(self) -> None:
        # Posição válida
        result = SearchResult(position=10, title="T", url="https://x.com")
        assert result.position == 10

        # Posição inválida (abaixo)
        with pytest.raises(ValidationError):
            SearchResult(position=0, title="T", url="https://x.com")

        # Posição inválida (acima)
        with pytest.raises(ValidationError):
            SearchResult(position=11, title="T", url="https://x.com")

    def test_default_snippet(self) -> None:
        result = SearchResult(position=1, title="T", url="https://x.com")
        assert result.snippet == ""

    def test_empty_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SearchResult(position=1, title="", url="https://x.com")


class TestSearchTerm:
    """Testes para o modelo SearchTerm."""

    def test_valid_term(self) -> None:
        term = SearchTerm(term="python web scraping")
        assert term.term == "python web scraping"
        assert term.enabled is True
        assert term.tags == []

    def test_with_tags(self) -> None:
        term = SearchTerm(term="test", tags=["dev", "tutorial"])
        assert len(term.tags) == 2

    def test_empty_term_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SearchTerm(term="")


class TestSearchReport:
    """Testes para o modelo SearchReport."""

    def test_success_report(self) -> None:
        results = [
            SearchResult(position=i, title=f"Title {i}", url=f"https://example{i}.com")
            for i in range(1, 11)
        ]
        report = SearchReport(
            term="test query",
            status=SearchStatus.SUCCESS,
            results=results,
            duration_seconds=5.0,
        )
        assert report.results_count == 10
        assert report.status == SearchStatus.SUCCESS

    def test_failed_report(self) -> None:
        report = SearchReport(
            term="test",
            status=SearchStatus.FAILED,
            error_message="Timeout",
        )
        assert report.results_count == 0
        assert report.error_message == "Timeout"

    def test_auto_results_count(self) -> None:
        results = [
            SearchResult(position=1, title="T1", url="https://a.com"),
            SearchResult(position=2, title="T2", url="https://b.com"),
        ]
        report = SearchReport(
            term="test",
            status=SearchStatus.PARTIAL,
            results=results,
        )
        assert report.results_count == 2


class TestTermsInput:
    """Testes para o modelo TermsInput."""

    def test_valid_input(self) -> None:
        data = TermsInput(terms=["term1", "term2"])
        assert len(data.terms) == 2

    def test_empty_terms_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TermsInput(terms=[])

    def test_with_metadata(self) -> None:
        data = TermsInput(
            terms=["test"],
            metadata={"version": "1.0"},
        )
        assert data.metadata["version"] == "1.0"


class TestHarnessReport:
    """Testes para o modelo HarnessReport."""

    def test_calculate_metrics(self) -> None:
        reports = [
            SearchReport(
                term="t1",
                status=SearchStatus.SUCCESS,
                results=[
                    SearchResult(position=i, title=f"T{i}", url=f"https://x{i}.com")
                    for i in range(1, 11)
                ],
                results_count=10,
                duration_seconds=5.0,
            ),
            SearchReport(
                term="t2",
                status=SearchStatus.FAILED,
                error_message="erro",
                duration_seconds=3.0,
            ),
        ]

        harness = HarnessReport(reports=reports)
        harness.calculate_metrics()

        assert harness.total_terms == 2
        assert harness.successful == 1
        assert harness.failed == 1
        assert harness.success_rate == 0.5
        assert harness.total_results == 10
        assert harness.total_duration_seconds == 8.0

    def test_empty_report(self) -> None:
        harness = HarnessReport()
        harness.calculate_metrics()
        assert harness.total_terms == 0
        assert harness.success_rate == 0.0
