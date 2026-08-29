---
name: validate-results
description: >-
  Use this skill when the user asks to validate, check, or verify the integrity
  and quality of scraped results. Validates schema, completeness, duplicate URLs,
  and compares against baselines.
---

# Validar Resultados

Skill para verificar integridade e qualidade dos dados extraídos.

## Steps

### 1. Validação via CLI
```bash
webscrapper validate --results-dir results/
```

### 2. Validação programática avançada
```python
import json
from pathlib import Path
from src.models import HarnessReport
from harness.validator import ResultValidator

# Carregar relatório mais recente
results_dir = Path("results")
latest = sorted(results_dir.glob("report_*.json"), reverse=True)[0]
data = json.loads(latest.read_text())
report = HarnessReport(**data)

# Validar
validator = ResultValidator(expected_results=10)
validation = validator.validate_report(report)

# Exibir issues
for issue in validation.issues:
    print(f"[{issue.severity}] {issue.term}: {issue.message}")

print(f"\nResultado: {'✅ VÁLIDO' if validation.is_valid else '❌ INVÁLIDO'}")
```

### 3. Comparar com baseline
Se existir um baseline anterior:
```python
import json
from pathlib import Path

baseline_file = Path("results/baseline.json")
latest_file = sorted(Path("results").glob("summary_*.json"), reverse=True)[0]

baseline = json.loads(baseline_file.read_text()) if baseline_file.exists() else None
latest = json.loads(latest_file.read_text())

if baseline:
    baseline_rate = baseline["metrics"]["success_rate"]
    latest_rate = latest["metrics"]["success_rate"]
    diff = latest_rate - baseline_rate
    print(f"Baseline: {baseline_rate:.1%} → Atual: {latest_rate:.1%} (Δ {diff:+.1%})")
```

### 4. Gerar relatório de validação
```bash
python -m harness.run_harness --file terms.json --output results/
# O harness gera automaticamente report_*.md com seção de validação
```

## Critérios de Aprovação
- Taxa de sucesso ≥ 90%
- Zero erros de validação (títulos/URLs vazios)
- Sem URLs duplicadas dentro do mesmo termo
