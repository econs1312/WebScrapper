"""Gerador de relatórios em JSON e Markdown."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from src.models import HarnessReport, SearchStatus

if TYPE_CHECKING:
    from pathlib import Path

    from harness.validator import ValidationReport

logger = logging.getLogger(__name__)


class Reporter:
    """Gera relatórios de execução do harness."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown_report(
        self,
        harness_report: HarnessReport,
        validation: ValidationReport,
    ) -> Path:
        """Gera relatório completo em Markdown."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.output_dir / f"report_{timestamp}.md"

        lines: list[str] = []
        lines.append("# 📊 WebScrapper — Relatório de Execução\n")
        lines.append(f"**Data**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append("")

        # Resumo
        lines.append("## 📈 Resumo\n")
        lines.append("| Métrica | Valor |")
        lines.append("|---------|-------|")
        lines.append(f"| Total de termos | {harness_report.total_terms} |")
        lines.append(f"| ✅ Sucesso | {harness_report.successful} |")
        lines.append(f"| ⚠️ Parcial | {harness_report.partial} |")
        lines.append(f"| ❌ Falha | {harness_report.failed} |")
        lines.append(f"| 🚫 Bloqueado | {harness_report.blocked} |")
        lines.append(f"| Total de resultados | {harness_report.total_results} |")
        lines.append(f"| Tempo total | {harness_report.total_duration_seconds:.1f}s |")
        lines.append(f"| Taxa de sucesso | {harness_report.success_rate:.1%} |")
        lines.append("")

        # Detalhes por termo
        lines.append("## 🔎 Resultados por Termo\n")
        for report in harness_report.reports:
            status_emoji = {
                SearchStatus.SUCCESS: "✅",
                SearchStatus.PARTIAL: "⚠️",
                SearchStatus.FAILED: "❌",
                SearchStatus.BLOCKED: "🚫",
            }.get(report.status, "❓")

            lines.append(f"### {status_emoji} `{report.term}`\n")
            lines.append(f"- **Status**: {report.status.value}")
            lines.append(f"- **Resultados**: {report.results_count}")
            lines.append(f"- **Tempo**: {report.duration_seconds:.1f}s")
            lines.append(f"- **Tentativa**: {report.attempt}")

            if report.error_message:
                lines.append(f"- **Erro**: {report.error_message}")

            if report.results:
                lines.append("")
                lines.append("| # | Título | URL |")
                lines.append("|---|--------|-----|")
                for result in report.results:
                    title = result.title[:60] + ("..." if len(result.title) > 60 else "")
                    lines.append(f"| {result.position} | {title} | {result.url} |")

            lines.append("")

        # Validação
        lines.append("## ✅ Validação\n")
        lines.append(f"- **Status**: {'APROVADO ✅' if validation.is_valid else 'REPROVADO ❌'}")
        lines.append(f"- **Checks**: {validation.total_checks}")
        lines.append(f"- **Aprovados**: {validation.passed}")
        lines.append(f"- **Warnings**: {validation.warnings}")
        lines.append(f"- **Erros**: {validation.errors}")

        if validation.issues:
            lines.append("")
            lines.append("### Issues Encontrados\n")
            lines.append("| Severidade | Termo | Campo | Mensagem |")
            lines.append("|------------|-------|-------|----------|")
            for issue in validation.issues:
                sev_emoji = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(
                    issue.severity, "❓"
                )
                lines.append(
                    f"| {sev_emoji} {issue.severity} | `{issue.term}` | "
                    f"{issue.field or '-'} | {issue.message} |"
                )

        lines.append("")

        content = "\n".join(lines)
        filepath.write_text(content, encoding="utf-8")
        logger.info("Relatório Markdown gerado: %s", filepath)
        return filepath

    def generate_json_summary(
        self,
        harness_report: HarnessReport,
        validation: ValidationReport,
    ) -> Path:
        """Gera sumário em JSON (sem resultados individuais, para CI/CD)."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.output_dir / f"summary_{timestamp}.json"

        summary = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "total_terms": harness_report.total_terms,
                "successful": harness_report.successful,
                "partial": harness_report.partial,
                "failed": harness_report.failed,
                "blocked": harness_report.blocked,
                "total_results": harness_report.total_results,
                "success_rate": harness_report.success_rate,
                "total_duration_seconds": harness_report.total_duration_seconds,
            },
            "validation": {
                "is_valid": validation.is_valid,
                "total_checks": validation.total_checks,
                "passed": validation.passed,
                "warnings": validation.warnings,
                "errors": validation.errors,
            },
            "terms_status": {
                report.term: {
                    "status": report.status.value,
                    "results_count": report.results_count,
                    "duration_seconds": report.duration_seconds,
                    "attempt": report.attempt,
                    "error": report.error_message,
                }
                for report in harness_report.reports
            },
        }

        filepath.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Sumário JSON gerado: %s", filepath)
        return filepath
