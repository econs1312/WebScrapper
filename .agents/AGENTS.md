# WebScrapper — Regras do Agente

## Ambiente
- Python 3.12+ obrigatório.
- Sempre usar virtual environment (`.venv/`).
- Instalar dependências via `pip install -e ".[dev]"`.

## Padrões de Código
- Todos os dados devem ser validados com **Pydantic models** (`src/models.py`) antes de serem persistidos.
- Nunca fazer requests HTTP diretos ao Google — sempre usar `GoogleSearchProvider` com Playwright stealth.
- Manter seletores CSS do parser em variáveis constantes no topo de `src/parser.py` para fácil manutenção.
- Usar `logging` em vez de `print()`. O projeto usa Rich para formatação.
- Type hints em todas as funções (mypy strict mode).

## Testes
- Rodar `pytest tests/ -v` antes de qualquer commit.
- Testes do parser devem usar HTML mockado em `tests/fixtures/`, nunca fazer requests reais em testes.
- Manter cobertura ≥ 80%.

## Output
- Resultados vão em `results/` — nunca commitar este diretório.
- HTML raw vai em `results/raw_html/` — usar para debug de seletores.

## CI/CD
- Workflows do GitHub Actions ficam em `.github/workflows/`.
- O harness (`harness/run_harness.py`) é o ponto de entrada principal para execução automatizada.
- Exit code 0 = sucesso, 1 = falha (para integração com CI).
