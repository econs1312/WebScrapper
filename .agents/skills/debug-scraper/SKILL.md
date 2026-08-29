---
name: debug-scraper
description: >-
  Use this skill when the scraper fails, produces empty results, encounters
  CAPTCHAs, or returns corrupted data. Guides diagnosis through log analysis,
  raw HTML inspection, and selector verification.
---

# Debug de Falhas do Scraper

Skill para diagnosticar e corrigir problemas do WebScrapper.

## Sintomas Comuns

| Sintoma | Causa Provável | Solução |
|---------|----------------|---------|
| Resultados vazios | Seletores CSS desatualizados | Atualizar seletores em `src/parser.py` |
| CAPTCHA detectado | Rate limiting do Google | Aumentar delays, usar proxy |
| Timeout | Página não carregou | Aumentar `request_timeout` |
| Dados corrompidos | Parser extraindo lixo | Revisar HTML raw |

## Steps de Diagnóstico

### 1. Verificar logs
```bash
cat results/scrapper.log | grep -i "error\|warning\|captcha\|timeout"
```

### 2. Analisar HTML raw
Abrir o HTML raw mais recente em `results/raw_html/`:
```bash
ls -la results/raw_html/
```
Abrir no browser para inspeção visual.

### 3. Verificar seletores
Carregar o HTML em Python e testar cada seletor:
```python
from bs4 import BeautifulSoup
from pathlib import Path

html = Path("results/raw_html/<arquivo>.html").read_text()
soup = BeautifulSoup(html, "lxml")

# Testar seletores de container
for sel in ["div.g", "div.MjjYud div.g", "#rso > div > div.g"]:
    results = soup.select(sel)
    print(f"{sel}: {len(results)} resultados")

# Testar seletores de título
for el in soup.select("div.g")[:3]:
    for sel in ["h3", "h3.LC20lb"]:
        h = el.select_one(sel)
        print(f"  {sel}: {h.text if h else 'VAZIO'}")
```

### 4. Identificar novos seletores
Se os seletores existentes não funcionam:
1. Abrir o HTML raw no browser
2. Inspecionar elementos dos resultados orgânicos
3. Identificar os novos seletores CSS
4. Atualizar as constantes em `src/parser.py`

### 5. Validar correção
```bash
python -m pytest tests/test_parser.py -v
python -m harness.run_harness --terms "python tutorial" --output results/test_debug/
```

## Quando Escalar

- Se o Google mudou completamente o layout → usar skill `update-parser`
- Se IP está banido → considerar serviço de proxy
- Se CAPTCHA persistente → considerar SerpAPI como fallback
