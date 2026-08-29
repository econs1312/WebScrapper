"""Modelos Pydantic para dados do WebScrapper."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SearchStatus(StrEnum):
    """Status de uma busca."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    RETRY = "retry"


class SearchResult(BaseModel):
    """Um resultado individual de busca do Google."""

    position: int = Field(..., ge=1, le=10, description="Posição do resultado (1-10)")
    title: str = Field(..., min_length=1, description="Título do resultado")
    url: str = Field(..., min_length=1, description="URL do resultado")
    snippet: str = Field(default="", description="Snippet/descrição do resultado")

    def is_valid(self) -> bool:
        """Verifica se o resultado tem dados mínimos válidos."""
        return bool(self.title.strip() and self.url.strip())


class SearchTerm(BaseModel):
    """Um termo de busca com metadados."""

    term: str = Field(..., min_length=1, description="Termo de busca")
    enabled: bool = Field(default=True, description="Se o termo está ativo")
    tags: list[str] = Field(default_factory=list, description="Tags para categorização")


class SearchReport(BaseModel):
    """Relatório completo de uma busca para um termo."""

    term: str = Field(..., description="Termo buscado")
    status: SearchStatus = Field(..., description="Status da busca")
    results: list[SearchResult] = Field(default_factory=list, description="Resultados encontrados")
    results_count: int = Field(default=0, description="Número de resultados extraídos")
    timestamp: datetime = Field(default_factory=datetime.now, description="Momento da busca")
    duration_seconds: float = Field(default=0.0, description="Duração da busca em segundos")
    attempt: int = Field(default=1, ge=1, description="Número da tentativa")
    error_message: str | None = Field(default=None, description="Mensagem de erro, se houver")
    raw_html_path: str | None = Field(default=None, description="Path do HTML raw salvo")

    def model_post_init(self, __context: object) -> None:
        """Atualiza results_count após inicialização."""
        if not self.results_count and self.results:
            self.results_count = len(self.results)


class TermsInput(BaseModel):
    """Estrutura do arquivo terms.json."""

    terms: list[str] = Field(..., min_length=1, description="Lista de termos de busca")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadados opcionais")


class HarnessReport(BaseModel):
    """Relatório completo do harness."""

    total_terms: int = Field(default=0, description="Total de termos processados")
    successful: int = Field(default=0, description="Termos com sucesso total")
    partial: int = Field(default=0, description="Termos com resultados parciais")
    failed: int = Field(default=0, description="Termos que falharam")
    blocked: int = Field(default=0, description="Termos bloqueados (CAPTCHA/ban)")
    total_results: int = Field(default=0, description="Total de resultados coletados")
    total_duration_seconds: float = Field(default=0.0, description="Duração total em segundos")
    success_rate: float = Field(default=0.0, description="Taxa de sucesso (0-1)")
    reports: list[SearchReport] = Field(default_factory=list, description="Relatórios individuais")
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: datetime | None = Field(default=None)

    def calculate_metrics(self) -> None:
        """Calcula métricas a partir dos relatórios individuais."""
        self.total_terms = len(self.reports)
        self.successful = sum(1 for r in self.reports if r.status == SearchStatus.SUCCESS)
        self.partial = sum(1 for r in self.reports if r.status == SearchStatus.PARTIAL)
        self.failed = sum(1 for r in self.reports if r.status == SearchStatus.FAILED)
        self.blocked = sum(1 for r in self.reports if r.status == SearchStatus.BLOCKED)
        self.total_results = sum(r.results_count for r in self.reports)
        self.total_duration_seconds = sum(r.duration_seconds for r in self.reports)
        self.success_rate = (
            self.successful / self.total_terms if self.total_terms > 0 else 0.0
        )
        self.finished_at = datetime.now()
