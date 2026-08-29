# 🔍 WebScrapper

Serviço de Web Scraping que busca termos específicos no Google e extrai os **10 primeiros resultados orgânicos** de cada busca.

## ✨ Features

- 🔎 **Busca no Google** via Playwright com stealth (evita detecção)
- 📊 **10 resultados por termo** — título, URL, snippet e posição
- 🔄 **Retry automático** com backoff exponencial
- ✅ **Validação Pydantic** de todos os dados
- 📄 **Export JSON + CSV** dos resultados
- 🏗️ **Harness de execução** com loop, validação e reporting
- 🤖 **CI/CD Agentic Loop** — auto-detecção e auto-reparo de falhas
- 🩺 **Health check semanal** do parser com canary tests

## 🚀 Quick Start

### 1. Instalar

```bash
# Clonar
git clone <repo-url>
cd WebScrapper

# Criar virtual environment
python -m venv .venv

# Ativar (Windows)
.venv\Scripts\activate

# Ativar (Linux/Mac)
source .venv/bin/activate

# Instalar dependências
pip install -e ".[dev]"

# Instalar browser do Playwright
playwright install chromium
```

### 2. Buscar termos

```bash
# Via arquivo de termos
webscrapper search --file terms.json

# Via CLI direta
webscrapper search --terms "python tutorial, javascript framework"

# Com opções
webscrapper search --file terms.json --output results/ --max-results 10 --headless
```

### 3. Validar resultados

```bash
webscrapper validate --results-dir results/
```

### 4. Executar via Harness (recomendado)

```bash
python -m harness.run_harness --file terms.json --output results/
```

## 📁 Estrutura do Projeto

```
WebScrapper/
├── src/                          # Código principal
│   ├── cli.py                    # Interface CLI (Click + Rich)
│   ├── config.py                 # Configurações (Pydantic Settings)
│   ├── models.py                 # Modelos de dados (Pydantic)
│   ├── orchestrator.py           # Orquestrador de buscas
│   ├── parser.py                 # Parser de SERP (BeautifulSoup)
│   └── search_provider.py        # Provider Google (Playwright stealth)
├── harness/                      # Framework de execução
│   ├── run_harness.py            # Loop principal
│   ├── validator.py              # Validação de qualidade
│   └── reporter.py               # Geração de relatórios
├── tests/                        # Testes
│   ├── fixtures/                 # HTML mockado de SERPs
│   ├── test_models.py
│   ├── test_parser.py
│   ├── test_orchestrator.py
│   ├── test_harness.py
│   ├── test_cli.py
│   ├── test_harness_runner.py
│   └── test_search_provider.py
├── .agents/                      # Agent Skills & Rules
│   ├── AGENTS.md                 # Regras do agente
│   └── skills/                   # Skills modulares
│       ├── run-scraper/
│       ├── debug-scraper/
│       ├── add-search-term/
│       ├── validate-results/
│       ├── ci-cd-pipeline/
│       └── update-parser/
├── .github/workflows/            # CI/CD Pipelines
│   ├── ci.yml                    # Lint + Testes
│   ├── scraper-run.yml           # Execução agendada
│   ├── parser-health.yml         # Health check semanal
│   └── agentic-loop.yml          # Loop agentic auto-fix
├── docs/
│   └── PRD.md                    # Product Requirements Document
├── terms.json                    # Lista de termos de busca
├── pyproject.toml                # Configuração Python
└── README.md
```

## 🤖 Agent Skills

O projeto inclui 6 skills modulares para o Antigravity:

| Skill | Quando usar |
|-------|-------------|
| `run-scraper` | Executar o scraper, buscar termos |
| `debug-scraper` | Diagnosticar falhas, CAPTCHAs |
| `add-search-term` | Adicionar novos termos |
| `validate-results` | Verificar integridade dos dados |
| `ci-cd-pipeline` | Gerenciar workflows GitHub Actions |
| `update-parser` | Atualizar seletores CSS do parser |

## 🔄 CI/CD Agentic Loop

O pipeline CI/CD funciona em loop contínuo:

```
Cron/Issue → Classificar Tarefa → Selecionar Skill → Executar
    ↑                                                    ↓
    ╰──── Alertar ← Falhou 3x ← Validar ← Testar ←────╯
                                     ↓
                               Sucesso → Criar PR
```

## ⚙️ Configuração

Todas as configurações podem ser definidas via variáveis de ambiente com prefixo `WEBSCRAPPER_`:

```bash
WEBSCRAPPER_MAX_RESULTS=10
WEBSCRAPPER_SEARCH_DELAY_MIN=2.0
WEBSCRAPPER_SEARCH_DELAY_MAX=5.0
WEBSCRAPPER_HEADLESS=true
WEBSCRAPPER_MAX_RETRIES=3
```

Ou via arquivo `.env` na raiz do projeto.

## 🧪 Testes

```bash
# Rodar todos os testes
pytest tests/ -v

# Com cobertura
pytest tests/ -v --cov=src --cov=harness

# Apenas parser
pytest tests/test_parser.py -v

# Apenas modelos
pytest tests/test_models.py -v
```

## 📝 Licença

MIT
