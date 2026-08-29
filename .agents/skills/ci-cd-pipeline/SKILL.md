---
name: ci-cd-pipeline
description: >-
  Use this skill when the user asks about the CI/CD pipeline, deploying,
  running workflows, checking pipeline status, or managing GitHub Actions.
  Covers all 4 workflows: CI, scheduled scraper, parser health, and agentic loop.
---

# Gerenciar Pipeline CI/CD

Skill para operar e manter os workflows do GitHub Actions.

## Visão Geral dos Workflows

| Workflow | Arquivo | Trigger | Função |
|----------|---------|---------|--------|
| CI | `ci.yml` | push/PR | Lint + testes |
| Scraper Run | `scraper-run.yml` | cron diário + dispatch | Execução agendada |
| Parser Health | `parser-health.yml` | cron semanal | Detectar layout changes |
| Agentic Loop | `agentic-loop.yml` | issue labeled | Auto-fix via agente |

## Steps de Operação

### 1. Verificar status dos workflows
```bash
gh workflow list
gh run list --limit 5
```

### 2. Executar workflow manualmente
```bash
# Executar scraper
gh workflow run scraper-run.yml

# Executar CI
gh workflow run ci.yml

# Executar parser health check
gh workflow run parser-health.yml
```

### 3. Verificar resultado de execução
```bash
gh run view <run-id>
gh run view <run-id> --log
```

### 4. Diagnosticar falha no CI
1. Verificar logs: `gh run view <id> --log-failed`
2. Se lint falhou: `ruff check src/ harness/ --fix`
3. Se testes falharam: `pytest tests/ -v --tb=long`
4. Se type check falhou: `mypy src/ harness/`

### 5. Configurar secrets (primeira vez)
```bash
# Se usar proxy
gh secret set PROXY_URL --body "http://user:pass@proxy:port"

# Se usar SerpAPI
gh secret set SERPAPI_KEY --body "your-key-here"
```

## O Loop Agentic

O workflow `agentic-loop.yml` funciona assim:

1. Uma **issue** é criada com label `agent-task`
2. O workflow detecta e classifica a tarefa
3. Seleciona a skill apropriada (debug, update-parser, etc.)
4. Executa em loop: Plan → Code → Test → Validate
5. Se testes passam → cria PR automático
6. Se falha após 3 iterações → alerta no issue

Para acionar manualmente:
```bash
gh issue create --title "Parser quebrado: seletores desatualizados" --label "agent-task"
```
