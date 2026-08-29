---
name: add-search-term
description: >-
  Use this skill when the user wants to add new search terms to the terms list,
  modify existing terms, or manage the terms.json configuration file.
---

# Adicionar Termos de Busca

Skill para gerenciar a lista de termos em `terms.json`.

## Steps

### 1. Validar o termo
- Verificar que o termo não está vazio
- Verificar que não é duplicata de um termo existente
- Termos devem ter entre 2 e 100 caracteres

### 2. Adicionar ao terms.json
```python
import json
from pathlib import Path

terms_file = Path("terms.json")
data = json.loads(terms_file.read_text())

new_terms = ["novo termo 1", "novo termo 2"]

for term in new_terms:
    if term not in data["terms"]:
        data["terms"].append(term)
        print(f"✅ Adicionado: '{term}'")
    else:
        print(f"⚠️ Já existe: '{term}'")

terms_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
```

### 3. Executar scraper incremental (opcional)
Para buscar apenas os novos termos:
```bash
webscrapper search --terms "novo termo 1,novo termo 2" --output results/
```

### 4. Validar
```bash
python -c "
import json
data = json.loads(open('terms.json').read())
print(f'Total de termos: {len(data[\"terms\"])}')
for t in data['terms']:
    print(f'  - {t}')
"
```
