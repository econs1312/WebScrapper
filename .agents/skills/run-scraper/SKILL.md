---
name: run-scraper
description: >-
  Use this skill when the user asks to execute the scraper, run a search,
  collect data, or scrape terms from Google. Handles the full execution cycle
  including environment setup, harness execution, validation, and reporting.
---

# Executar o Scraper

Skill para rodar o WebScrapper completo via harness.

## Pré-condições

1. Virtual environment ativa com dependências instaladas.
2. Playwright browsers instalados (`playwright install chromium`).
3. Arquivo `terms.json` presente ou termos fornecidos via CLI.

## Steps

### 1. Verificar ambiente
```bash
python -c "import playwright; import bs4; import pydantic; print('OK')"
```
Se falhar, instalar dependências:
```bash
pip install -e ".[dev]"
playwright install chromium
```

### 2. Executar via harness (recomendado)
```bash
python -m harness.run_harness --file terms.json --output results/ --log-level INFO
```

### 3. Ou executar via CLI diretamente
```bash
webscrapper search --file terms.json --output results/
webscrapper search --terms "termo1,termo2" --output results/
```

### 4. Validar resultados
```bash
webscrapper validate --results-dir results/
```

### 5. Verificar output
- Conferir `results/report_*.json` — relatório completo
- Conferir `results/results_*.csv` — dados tabulares
- Conferir `results/report_*.md` — relatório legível (se via harness)
- Conferir `results/summary_*.json` — sumário para CI/CD (se via harness)

## Troubleshooting

- Se taxa de sucesso < 90%: aumentar delays (`--delay-min 5 --delay-max 10`)
- Se CAPTCHA detectado: verificar logs em `results/scrapper.log`
- Se resultados vazios: verificar HTML raw em `results/raw_html/` — seletores podem ter mudado
