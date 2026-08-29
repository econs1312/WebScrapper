"""Servidor FastAPI e API REST para a interface Web do WebScrapper."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from harness.reporter import Reporter
from harness.validator import ResultValidator
from src.config import ScrapperConfig
from src.models import (
    HarnessReport,
    SearchStatus,
)
from src.orchestrator import SearchOrchestrator

logger = logging.getLogger(__name__)

# Diretórios
ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
TERMS_FILE = ROOT_DIR / "terms.json"
RESULTS_DIR = ROOT_DIR / "results"

app = FastAPI(
    title="WebScrapper API",
    version="1.0.0",
    description="API para orquestração, monitoramento e visualização de web scraping no Google.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Estado Global da Execução
# ---------------------------------------------------------------------------
class ScraperTaskState:
    """Gerencia o estado e o histórico da tarefa assíncrona de raspagem."""

    def __init__(self) -> None:
        self.is_running: bool = False
        self.status: str = "idle"  # idle, running, completed, failed, cancelled
        self.current_term: str | None = None
        self.current_index: int = 0
        self.total_terms: int = 0
        self.progress_percentage: float = 0.0
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None
        self.logs: list[dict[str, Any]] = []
        self.current_results: list[dict[str, Any]] = []
        self.latest_report: dict[str, Any] | None = None
        self.latest_report_path: str | None = None
        self.task: asyncio.Task[None] | None = None
        self.cancel_requested: bool = False

    def add_log(self, message: str, level: str = "info") -> None:
        """Adiciona uma entrada de log com timestamp."""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "level": level,
            "message": message,
        }
        self.logs.append(entry)
        if len(self.logs) > 300:
            self.logs.pop(0)

    def reset(self, total: int) -> None:
        """Reinicia o estado para uma nova execução."""
        self.is_running = True
        self.status = "running"
        self.current_term = None
        self.current_index = 0
        self.total_terms = total
        self.progress_percentage = 0.0
        self.started_at = datetime.now()
        self.finished_at = None
        self.logs = []
        self.current_results = []
        self.cancel_requested = False


task_state = ScraperTaskState()


# ---------------------------------------------------------------------------
# Modelos de Requisição
# ---------------------------------------------------------------------------
class TermAddRequest(BaseModel):
    term: str = Field(..., min_length=1, description="Novo termo de busca")


class TermsUpdateRequest(BaseModel):
    terms: list[str] = Field(..., min_length=1, description="Lista completa de termos")


class ScrapeStartRequest(BaseModel):
    engine: str = Field(default="duckduckgo", description="Mecanismo de busca: 'duckduckgo' ou 'google'")
    terms: list[str] | None = Field(default=None, description="Termos específicos ou None para terms.json")
    max_results: int = Field(default=10, ge=1, le=10)
    delay_min: float = Field(default=1.0, ge=0.0)
    delay_max: float = Field(default=3.0, ge=0.0)
    headless: bool = Field(default=True)
    max_retries: int = Field(default=3, ge=1, le=5)
    save_html: bool = Field(default=True)


# ---------------------------------------------------------------------------
# Background Worker
# ---------------------------------------------------------------------------
async def _run_scraper_job(config: ScrapperConfig, terms: list[str]) -> None:
    """Executa o processo de scraping emitindo logs e atualizações de progresso."""
    task_state.reset(len(terms))
    task_state.add_log(f"Iniciando raspagem de {len(terms)} termo(s)...", "info")

    harness_report = HarnessReport(started_at=datetime.now())
    orchestrator = SearchOrchestrator(config)
    config.ensure_dirs()

    try:
        async with orchestrator.provider:
            for idx, term in enumerate(terms, start=1):
                if task_state.cancel_requested:
                    task_state.add_log("Cancelamento solicitado pelo usuário.", "warning")
                    task_state.status = "cancelled"
                    break

                task_state.current_term = term
                task_state.current_index = idx
                task_state.progress_percentage = round(((idx - 1) / len(terms)) * 100, 1)
                task_state.add_log(f"[{idx}/{len(terms)}] Buscando: '{term}'...", "info")

                report = await orchestrator.search_term(term)
                harness_report.reports.append(report)

                # Salvar resultados parciais para visualização imediata
                for res in report.results:
                    task_state.current_results.append({
                        "term": term,
                        "position": res.position,
                        "title": res.title,
                        "url": res.url,
                        "snippet": res.snippet,
                        "status": report.status.value,
                    })

                if report.status == SearchStatus.SUCCESS:
                    task_state.add_log(
                        f"✓ '{term}': {report.results_count} resultados em {report.duration_seconds:.1f}s",
                        "success",
                    )
                elif report.status == SearchStatus.PARTIAL:
                    task_state.add_log(
                        f"⚠ '{term}': Resultados parciais ({report.results_count})",
                        "warning",
                    )
                else:
                    task_state.add_log(
                        f"✗ '{term}': Falha ({report.error_message or 'erro desconhecido'})",
                        "error",
                    )

                if idx < len(terms) and not task_state.cancel_requested:
                    delay = config.get_random_delay()
                    task_state.add_log(f"Aguardando {delay:.1f}s antes da próxima consulta...", "debug")
                    await asyncio.sleep(delay)

        harness_report.calculate_metrics()
        task_state.progress_percentage = 100.0

        if not task_state.cancel_requested:
            # Exportar JSON e CSV
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_file = config.output_dir / f"report_{timestamp}.json"
            json_file.write_text(harness_report.model_dump_json(indent=2), encoding="utf-8")
            orchestrator._export_csv(harness_report)

            # Validação e Markdown
            validator = ResultValidator(expected_results=config.max_results)
            validation = validator.validate_report(harness_report)
            reporter = Reporter(output_dir=config.output_dir)
            reporter.generate_markdown_report(harness_report, validation)
            reporter.generate_json_summary(harness_report, validation)

            task_state.latest_report_path = str(json_file)
            task_state.latest_report = json.loads(harness_report.model_dump_json())
            task_state.status = "completed"
            task_state.add_log(
                f"✓ Coleta finalizada com sucesso! Taxa: {harness_report.success_rate:.1%}",
                "success",
            )
        else:
            task_state.status = "cancelled"

    except Exception as exc:
        logger.exception("Erro durante a execução do scraping")
        task_state.status = "failed"
        task_state.add_log(f"Erro crítico durante raspagem: {exc}", "error")
    finally:
        task_state.is_running = False
        task_state.finished_at = datetime.now()


# ---------------------------------------------------------------------------
# Endpoints da API
# ---------------------------------------------------------------------------
@app.get("/api/terms")
def get_terms() -> dict[str, Any]:
    """Retorna os termos atuais configurados em terms.json."""
    if not TERMS_FILE.exists():
        return {"terms": [], "metadata": {}}
    try:
        data = json.loads(TERMS_FILE.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler terms.json: {e}") from e


@app.post("/api/terms")
def add_or_update_terms(payload: TermAddRequest) -> dict[str, Any]:
    """Adiciona um termo ao terms.json."""
    term = payload.term.strip()
    if not term:
        raise HTTPException(status_code=400, detail="Termo não pode ser vazio")

    data = {"terms": [], "metadata": {}}
    if TERMS_FILE.exists():
        with contextlib.suppress(Exception):
            data = json.loads(TERMS_FILE.read_text(encoding="utf-8"))

    terms_list: list[str] = data.get("terms", [])
    if term in terms_list:
        raise HTTPException(status_code=409, detail=f"O termo '{term}' já existe na lista.")

    terms_list.append(term)
    data["terms"] = terms_list
    data.setdefault("metadata", {})["updated_at"] = datetime.now().isoformat()

    TERMS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"message": f"Termo '{term}' adicionado com sucesso.", "terms": terms_list}


@app.delete("/api/terms/{term}")
def delete_term(term: str) -> dict[str, Any]:
    """Remove um termo do terms.json."""
    if not TERMS_FILE.exists():
        raise HTTPException(status_code=404, detail="Arquivo terms.json não encontrado.")

    data = json.loads(TERMS_FILE.read_text(encoding="utf-8"))
    terms_list: list[str] = data.get("terms", [])

    if term not in terms_list:
        raise HTTPException(status_code=404, detail=f"Termo '{term}' não encontrado.")

    terms_list.remove(term)
    data["terms"] = terms_list
    data.setdefault("metadata", {})["updated_at"] = datetime.now().isoformat()

    TERMS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"message": f"Termo '{term}' removido com sucesso.", "terms": terms_list}


@app.post("/api/scrape/start")
async def start_scraping(request: ScrapeStartRequest) -> dict[str, Any]:
    """Inicia uma tarefa de scraping no backend."""
    if task_state.is_running:
        raise HTTPException(status_code=409, detail="Já existe uma tarefa de raspagem em execução.")

    terms = request.terms
    if not terms:
        if not TERMS_FILE.exists():
            raise HTTPException(status_code=400, detail="Nenhum termo fornecido e terms.json inexistente.")
        data = json.loads(TERMS_FILE.read_text(encoding="utf-8"))
        terms = data.get("terms", [])

    if not terms:
        raise HTTPException(status_code=400, detail="A lista de termos está vazia.")

    config = ScrapperConfig(
        search_engine=request.engine,
        max_results=request.max_results,
        search_delay_min=request.delay_min,
        search_delay_max=request.delay_max,
        headless=request.headless,
        max_retries=request.max_retries,
        save_raw_html=request.save_html,
        output_dir=RESULTS_DIR,
        raw_html_dir=RESULTS_DIR / "raw_html",
    )

    task = asyncio.create_task(_run_scraper_job(config, terms))
    task_state.task = task

    return {
        "status": "started",
        "total_terms": len(terms),
        "message": f"Iniciando coleta para {len(terms)} termos.",
    }


@app.get("/api/scrape/status")
def get_scrape_status() -> dict[str, Any]:
    """Retorna o status atual, progresso e logs recentes da raspagem."""
    return {
        "is_running": task_state.is_running,
        "status": task_state.status,
        "current_term": task_state.current_term,
        "current_index": task_state.current_index,
        "total_terms": task_state.total_terms,
        "progress_percentage": task_state.progress_percentage,
        "started_at": task_state.started_at.isoformat() if task_state.started_at else None,
        "finished_at": task_state.finished_at.isoformat() if task_state.finished_at else None,
        "logs": task_state.logs,
        "current_results_count": len(task_state.current_results),
        "results": task_state.current_results,
    }


@app.post("/api/scrape/stop")
def stop_scraping() -> dict[str, Any]:
    """Interrompe a execução atual do scraper."""
    if not task_state.is_running:
        return {"status": "idle", "message": "Nenhuma raspagem em andamento."}

    task_state.cancel_requested = True
    return {"status": "stopping", "message": "Solicitação de parada enviada."}


@app.get("/api/results")
def list_results() -> dict[str, Any]:
    """Lista todos os relatórios e arquivos gerados em results/."""
    if not RESULTS_DIR.exists():
        return {"files": []}

    files_list = []
    for p in sorted(RESULTS_DIR.glob("*.*"), key=lambda f: f.stat().st_mtime, reverse=True):
        if p.is_file() and p.suffix in [".json", ".csv", ".md"]:
            files_list.append({
                "name": p.name,
                "size_bytes": p.stat().st_size,
                "modified_at": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                "type": p.suffix.replace(".", "").upper(),
            })

    return {"files": files_list}


@app.get("/api/results/latest")
def get_latest_results() -> dict[str, Any]:
    """Retorna o último relatório JSON detalhado com resultados."""
    if not RESULTS_DIR.exists():
        raise HTTPException(status_code=404, detail="Diretório de resultados não encontrado.")

    json_reports = sorted(RESULTS_DIR.glob("report_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not json_reports:
        raise HTTPException(status_code=404, detail="Nenhum relatório de resultados encontrado.")

    latest_file = json_reports[0]
    try:
        content = json.loads(latest_file.read_text(encoding="utf-8"))
        return {
            "filename": latest_file.name,
            "data": content,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler relatório: {e}") from e


@app.get("/api/results/download/{filename}")
def download_result_file(filename: str) -> FileResponse:
    """Permite download seguro de relatórios gerados."""
    safe_filename = Path(filename).name
    file_path = RESULTS_DIR / safe_filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="application/octet-stream",
    )


@app.post("/api/validate")
def validate_results(filename: str | None = Query(default=None)) -> dict[str, Any]:
    """Executa a validação de integridade dos resultados via ResultValidator."""
    if not RESULTS_DIR.exists():
        raise HTTPException(status_code=404, detail="Nenhum resultado para validar.")

    target_file: Path | None = None
    if filename:
        target_file = RESULTS_DIR / Path(filename).name
    else:
        reports = sorted(RESULTS_DIR.glob("report_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if reports:
            target_file = reports[0]

    if not target_file or not target_file.exists():
        raise HTTPException(status_code=404, detail="Relatório JSON não encontrado para validação.")

    try:
        raw_data = json.loads(target_file.read_text(encoding="utf-8"))
        harness_report = HarnessReport(**raw_data)
        validator = ResultValidator(expected_results=10)
        validation_report = validator.validate_report(harness_report)

        return {
            "file": target_file.name,
            "is_valid": validation_report.is_valid,
            "total_checks": validation_report.total_checks,
            "passed": validation_report.passed,
            "warnings": validation_report.warnings,
            "errors": validation_report.errors,
            "issues": [
                {
                    "term": issue.term,
                    "severity": issue.severity,
                    "message": issue.message,
                    "field": issue.field,
                }
                for issue in validation_report.issues
            ],
            "metrics": {
                "total_terms": harness_report.total_terms,
                "successful": harness_report.successful,
                "partial": harness_report.partial,
                "failed": harness_report.failed,
                "success_rate": harness_report.success_rate,
                "total_results": harness_report.total_results,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro durante validação: {e}") from e


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    """Retorna as configurações padrão do WebScrapper."""
    cfg = ScrapperConfig()
    return {
        "max_results": cfg.max_results,
        "search_delay_min": cfg.search_delay_min,
        "search_delay_max": cfg.search_delay_max,
        "request_timeout": cfg.request_timeout,
        "max_retries": cfg.max_retries,
        "headless": cfg.headless,
        "save_raw_html": cfg.save_raw_html,
    }


# ---------------------------------------------------------------------------
# Montagem do Frontend Estático
# ---------------------------------------------------------------------------
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
