---
name: update-parser
description: >-
  Use this skill when the Google SERP layout has changed and the parser is no
  longer extracting results correctly. Guides the process of identifying new
  CSS selectors and updating the parser with proper testing.
---

# Atualizar Seletores do Parser

Skill para quando o layout do Google muda e o parser para de funcionar.

## Quando Usar

- Health check (`parser-health.yml`) detectou falha
- Resultados estão consistentemente vazios
- Debug confirmou que seletores CSS estão desatualizados

## Steps

### 1. Obter HTML de referência atualizado
```bash
python -m harness.run_harness --terms "python tutorial" --output results/reference/ --save-html
```

### 2. Analisar a nova estrutura
Abrir `results/reference/raw_html/*.html` no browser e identificar:
- Container dos resultados orgânicos (normalmente `div.g` ou variante)
- Elemento do título (normalmente `h3`)
- Elemento da URL (normalmente `a[href]` dentro de `div.yuRUbf` ou similar)
- Elemento do snippet (normalmente `div.VwiC3b` ou similar)

### 3. Testar novos seletores
```python
from bs4 import BeautifulSoup
from pathlib import Path

html = Path("results/reference/raw_html/<arquivo>.html").read_text()
soup = BeautifulSoup(html, "lxml")

# Testar novo seletor de container
new_selector = "div.NOVO_SELETOR"
results = soup.select(new_selector)
print(f"Encontrados: {len(results)} resultados com '{new_selector}'")

# Verificar conteúdo
for r in results[:3]:
    h3 = r.select_one("h3")
    a = r.select_one("a[href]")
    print(f"  Título: {h3.text if h3 else 'N/A'}")
    print(f"  URL: {a['href'] if a else 'N/A'}")
```

### 4. Atualizar `src/parser.py`
Modificar as constantes de seletores no topo do arquivo:
- `_RESULT_CONTAINER_SELECTORS` — adicionar novo seletor NO INÍCIO da lista
- `_TITLE_SELECTORS` — ajustar se necessário
- `_URL_SELECTORS` — ajustar se necessário
- `_SNIPPET_SELECTORS` — ajustar se necessário

**IMPORTANTE**: Não remover seletores antigos. Adicionar os novos no início
da lista para prioridade, mantendo os antigos como fallback.

### 5. Atualizar fixture de teste
Salvar o novo HTML de referência como fixture:
```bash
cp results/reference/raw_html/<arquivo>.html tests/fixtures/google_serp_updated.html
```

### 6. Rodar testes
```bash
python -m pytest tests/test_parser.py -v
python -m pytest tests/ -v
```

### 7. Verificar integração end-to-end
```bash
python -m harness.run_harness --terms "python tutorial,javascript framework" --output results/test_update/
```

Se taxa de sucesso ≥ 90%, a atualização foi bem-sucedida.

### 8. Commitar e criar PR
```bash
git add src/parser.py tests/fixtures/
git commit -m "fix(parser): atualizar seletores CSS para novo layout Google"
git push
```
