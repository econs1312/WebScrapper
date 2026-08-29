"""Validador de qualidade dos dados extraídos."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

from src.models import HarnessReport, SearchReport, SearchResult, SearchStatus

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Representa um problema encontrado na validação."""

    term: str
    severity: str  # "error", "warning", "info"
    message: str
    field: str | None = None


@dataclass
class ValidationReport:
    """Relatório de validação dos resultados."""

    is_valid: bool = True
    total_checks: int = 0
    passed: int = 0
    warnings: int = 0
    errors: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    def add_issue(self, issue: ValidationIssue) -> None:
        """Adiciona um issue ao relatório."""
        self.issues.append(issue)
        self.total_checks += 1
        if issue.severity == "error":
            self.errors += 1
            self.is_valid = False
        elif issue.severity == "warning":
            self.warnings += 1
        else:
            self.passed += 1

    def add_pass(self) -> None:
        """Registra uma verificação bem-sucedida."""
        self.total_checks += 1
        self.passed += 1


class ResultValidator:
    """Valida a qualidade e integridade dos resultados de scraping."""

    def __init__(self, expected_results: int = 10) -> None:
        self.expected_results = expected_results

    def validate_report(self, report: HarnessReport) -> ValidationReport:
        """Valida um HarnessReport completo."""
        validation = ValidationReport()

        # Verificar se tem algum relatório
        if not report.reports:
            validation.add_issue(ValidationIssue(
                term="*",
                severity="error",
                message="Nenhum relatório de busca encontrado",
            ))
            return validation

        # Validar cada termo
        for search_report in report.reports:
            self._validate_search_report(search_report, validation)

        # Métricas globais
        if report.success_rate < 0.9:
            validation.add_issue(ValidationIssue(
                term="*",
                severity="warning",
                message=f"Taxa de sucesso abaixo do alvo: {report.success_rate:.1%} (alvo: 90%)",
                field="success_rate",
            ))
        else:
            validation.add_pass()

        logger.info(
            "Validação concluída: %d checks, %d OK, %d warnings, %d errors",
            validation.total_checks,
            validation.passed,
            validation.warnings,
            validation.errors,
        )

        return validation

    def _validate_search_report(
        self,
        report: SearchReport,
        validation: ValidationReport,
    ) -> None:
        """Valida um SearchReport individual."""
        # Verificar contagem de resultados
        if report.status == SearchStatus.SUCCESS:
            if report.results_count < self.expected_results:
                validation.add_issue(ValidationIssue(
                    term=report.term,
                    severity="warning",
                    message=(
                        f"Esperados {self.expected_results} resultados, "
                        f"obtidos {report.results_count}"
                    ),
                    field="results_count",
                ))
            else:
                validation.add_pass()

        elif report.status == SearchStatus.FAILED:
            validation.add_issue(ValidationIssue(
                term=report.term,
                severity="error",
                message=f"Busca falhou: {report.error_message or 'sem detalhes'}",
                field="status",
            ))

        elif report.status == SearchStatus.BLOCKED:
            validation.add_issue(ValidationIssue(
                term=report.term,
                severity="error",
                message="Busca bloqueada (CAPTCHA/ban)",
                field="status",
            ))

        # Validar resultados individuais
        seen_urls: set[str] = set()
        for result in report.results:
            self._validate_result(result, report.term, seen_urls, validation)

    def _validate_result(
        self,
        result: SearchResult,
        term: str,
        seen_urls: set[str],
        validation: ValidationReport,
    ) -> None:
        """Valida um resultado individual."""
        # Título vazio
        if not result.title.strip():
            validation.add_issue(ValidationIssue(
                term=term,
                severity="error",
                message=f"Resultado #{result.position}: título vazio",
                field="title",
            ))
        else:
            validation.add_pass()

        # URL inválida
        if not result.url.strip():
            validation.add_issue(ValidationIssue(
                term=term,
                severity="error",
                message=f"Resultado #{result.position}: URL vazia",
                field="url",
            ))
        else:
            parsed = urlparse(result.url)
            if not parsed.scheme or not parsed.netloc:
                validation.add_issue(ValidationIssue(
                    term=term,
                    severity="error",
                    message=f"Resultado #{result.position}: URL inválida: {result.url}",
                    field="url",
                ))
            else:
                validation.add_pass()

        # URL duplicada
        if result.url in seen_urls:
            validation.add_issue(ValidationIssue(
                term=term,
                severity="warning",
                message=f"Resultado #{result.position}: URL duplicada: {result.url}",
                field="url",
            ))
        else:
            seen_urls.add(result.url)
            validation.add_pass()

        # Snippet vazio (apenas warning)
        if not result.snippet.strip():
            validation.add_issue(ValidationIssue(
                term=term,
                severity="info",
                message=f"Resultado #{result.position}: snippet vazio",
                field="snippet",
            ))
