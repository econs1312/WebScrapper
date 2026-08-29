"""Testes para o servidor FastAPI e endpoints da API REST."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.models import (
    HarnessReport,
    SearchReport,
    SearchResult,
    SearchStatus,
)
from src.server import app, task_state

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def mock_results_dir(tmp_path: Path) -> Path:
    results_dir = tmp_path / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir


def _make_dummy_report() -> HarnessReport:
    results = [
        SearchResult(position=1, title="Google Title", url="https://example.com", snippet="Snippet text")
    ]
    report = SearchReport(
        term="python",
        status=SearchStatus.SUCCESS,
        results=results,
        results_count=1,
        duration_seconds=1.2,
    )
    hr = HarnessReport(reports=[report])
    hr.calculate_metrics()
    return hr


class TestServerEndpoints:
    """Testes dos endpoints da API."""

    def test_get_terms(self, client: TestClient, tmp_path: Path) -> None:
        terms_file = tmp_path / "terms.json"
        terms_file.write_text(json.dumps({"terms": ["python", "playwright"]}))

        with patch("src.server.TERMS_FILE", terms_file):
            response = client.get("/api/terms")
            assert response.status_code == 200
            data = response.json()
            assert "terms" in data
            assert data["terms"] == ["python", "playwright"]

    def test_add_term_success(self, client: TestClient, tmp_path: Path) -> None:
        terms_file = tmp_path / "terms.json"
        terms_file.write_text(json.dumps({"terms": ["python"]}))

        with patch("src.server.TERMS_FILE", terms_file):
            response = client.post("/api/terms", json={"term": "fastapi"})
            assert response.status_code == 200
            data = response.json()
            assert "fastapi" in data["terms"]

    def test_add_term_empty_fails(self, client: TestClient) -> None:
        response = client.post("/api/terms", json={"term": "   "})
        assert response.status_code == 400

    def test_add_term_duplicate_fails(self, client: TestClient, tmp_path: Path) -> None:
        terms_file = tmp_path / "terms.json"
        terms_file.write_text(json.dumps({"terms": ["python"]}))

        with patch("src.server.TERMS_FILE", terms_file):
            response = client.post("/api/terms", json={"term": "python"})
            assert response.status_code == 409

    def test_delete_term_success(self, client: TestClient, tmp_path: Path) -> None:
        terms_file = tmp_path / "terms.json"
        terms_file.write_text(json.dumps({"terms": ["python", "rust"]}))

        with patch("src.server.TERMS_FILE", terms_file):
            response = client.delete("/api/terms/python")
            assert response.status_code == 200
            data = response.json()
            assert "python" not in data["terms"]

    def test_delete_term_not_found(self, client: TestClient, tmp_path: Path) -> None:
        terms_file = tmp_path / "terms.json"
        terms_file.write_text(json.dumps({"terms": ["python"]}))

        with patch("src.server.TERMS_FILE", terms_file):
            response = client.delete("/api/terms/nonexistent")
            assert response.status_code == 404

    def test_get_config(self, client: TestClient) -> None:
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "max_results" in data
        assert "search_delay_min" in data

    def test_scrape_status(self, client: TestClient) -> None:
        response = client.get("/api/scrape/status")
        assert response.status_code == 200
        data = response.json()
        assert "is_running" in data
        assert "status" in data
        assert "logs" in data

    def test_scrape_stop_when_idle(self, client: TestClient) -> None:
        task_state.is_running = False
        response = client.post("/api/scrape/stop")
        assert response.status_code == 200
        assert response.json()["status"] == "idle"

    def test_scrape_stop_when_running(self, client: TestClient) -> None:
        task_state.is_running = True
        response = client.post("/api/scrape/stop")
        assert response.status_code == 200
        assert response.json()["status"] == "stopping"
        assert task_state.cancel_requested is True
        task_state.is_running = False

    def test_start_scrape_already_running(self, client: TestClient) -> None:
        task_state.is_running = True
        response = client.post("/api/scrape/start", json={"terms": ["python"]})
        assert response.status_code == 409
        task_state.is_running = False

    def test_start_scrape_empty_terms(self, client: TestClient, tmp_path: Path) -> None:
        terms_file = tmp_path / "terms.json"
        terms_file.write_text(json.dumps({"terms": []}))
        task_state.is_running = False

        with patch("src.server.TERMS_FILE", terms_file):
            response = client.post("/api/scrape/start", json={"terms": []})
            assert response.status_code == 400

    @patch("src.server._run_scraper_job")
    def test_start_scrape_success(self, mock_job: AsyncMock, client: TestClient) -> None:
        task_state.is_running = False
        response = client.post("/api/scrape/start", json={"terms": ["python", "rust"]})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert data["total_terms"] == 2
        task_state.is_running = False

    def test_list_results_empty(self, client: TestClient, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty_results"
        with patch("src.server.RESULTS_DIR", empty_dir):
            response = client.get("/api/results")
            assert response.status_code == 200
            assert response.json()["files"] == []

    def test_list_results_with_files(self, client: TestClient, tmp_path: Path) -> None:
        res_dir = tmp_path / "results"
        res_dir.mkdir(parents=True, exist_ok=True)
        (res_dir / "report_20260101_120000.json").write_text("{}")
        (res_dir / "results_20260101_120000.csv").write_text("a,b,c")

        with patch("src.server.RESULTS_DIR", res_dir):
            response = client.get("/api/results")
            assert response.status_code == 200
            files = response.json()["files"]
            assert len(files) == 2

    def test_get_latest_results_not_found(self, client: TestClient, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty_dir"
        with patch("src.server.RESULTS_DIR", empty_dir):
            response = client.get("/api/results/latest")
            assert response.status_code == 404

    def test_get_latest_results_success(self, client: TestClient, tmp_path: Path) -> None:
        res_dir = tmp_path / "results"
        res_dir.mkdir(parents=True, exist_ok=True)
        report = _make_dummy_report()
        (res_dir / "report_20260101_120000.json").write_text(report.model_dump_json())

        with patch("src.server.RESULTS_DIR", res_dir):
            response = client.get("/api/results/latest")
            assert response.status_code == 200
            data = response.json()
            assert "filename" in data
            assert data["data"]["total_terms"] == 1

    def test_download_file(self, client: TestClient, tmp_path: Path) -> None:
        res_dir = tmp_path / "results"
        res_dir.mkdir(parents=True, exist_ok=True)
        sample_file = res_dir / "report_sample.json"
        sample_file.write_text('{"sample": "data"}')

        with patch("src.server.RESULTS_DIR", res_dir):
            response = client.get("/api/results/download/report_sample.json")
            assert response.status_code == 200
            assert '{"sample": "data"}' in response.text

    def test_download_file_not_found(self, client: TestClient, tmp_path: Path) -> None:
        res_dir = tmp_path / "results"
        res_dir.mkdir(parents=True, exist_ok=True)
        with patch("src.server.RESULTS_DIR", res_dir):
            response = client.get("/api/results/download/missing.json")
            assert response.status_code == 404

    def test_validate_endpoint_success(self, client: TestClient, tmp_path: Path) -> None:
        res_dir = tmp_path / "results"
        res_dir.mkdir(parents=True, exist_ok=True)
        report = _make_dummy_report()
        (res_dir / "report_20260101_120000.json").write_text(report.model_dump_json())

        with patch("src.server.RESULTS_DIR", res_dir):
            response = client.post("/api/validate")
            assert response.status_code == 200
            data = response.json()
            assert "is_valid" in data
            assert "total_checks" in data

    def test_validate_endpoint_no_results(self, client: TestClient, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty_dir"
        with patch("src.server.RESULTS_DIR", empty_dir):
            response = client.post("/api/validate")
            assert response.status_code == 404

    def test_static_index_html(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "WebScrapper" in response.text

    @pytest.mark.asyncio
    async def test_run_scraper_job_execution(self, tmp_path: Path) -> None:
        from src.config import ScrapperConfig
        from src.server import _run_scraper_job

        config = ScrapperConfig(
            max_results=2,
            search_delay_min=0.01,
            search_delay_max=0.02,
            output_dir=tmp_path / "results",
            raw_html_dir=tmp_path / "results" / "raw_html",
        )

        mock_search_report = SearchReport(
            term="python",
            status=SearchStatus.SUCCESS,
            results=[
                SearchResult(position=1, title="Python", url="https://python.org", snippet="Docs"),
                SearchResult(position=2, title="Learn Python", url="https://learn.org", snippet="Tutorial"),
            ],
            results_count=2,
            duration_seconds=0.5,
        )

        with patch("src.server.SearchOrchestrator.search_term", new_callable=AsyncMock) as mock_search, \
             patch("src.search_provider.GoogleSearchProvider.start", new_callable=AsyncMock), \
             patch("src.search_provider.GoogleSearchProvider.stop", new_callable=AsyncMock):
            mock_search.return_value = mock_search_report

            await _run_scraper_job(config, ["python"])
            assert task_state.status == "completed"
            assert task_state.progress_percentage == 100.0
            assert len(task_state.current_results) == 2
            assert task_state.is_running is False
