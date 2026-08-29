# WebScrapper — Product Requirements Document (PRD)

**Versão**: 1.0  
**Data**: 2026-08-28  
**Status**: Aprovado  

---

## 1. Resumo Executivo

O **WebScrapper** é um serviço de linha de comando que recebe uma lista de termos
de busca, pesquisa cada termo no Google, extrai os **10 primeiros resultados
orgânicos** e retorna os dados estruturados (título, URL, snippet e posição) em
formatos JSON e CSV.

O sistema inclui um **harness de execução** com retry automático, validação de
dados via Pydantic e um **pipeline CI/CD agentic** que monitora a saúde do
parser e se auto-repara quando o layout do Google muda.

---

## 2. Problema

Profissionais de SEO, pesquisadores e desenvolvedores frequentemente precisam
coletar dados dos resultados de busca do Google para:

- Monitorar posicionamento de sites
- Analisar concorrência
- Pesquisar tendências de conteúdo
- Alimentar pipelines de dados com informações de SERP

Fazer isso manualmente é tedioso, propenso a erros e não escalável. Ferramentas
existentes são geralmente pagas, fechadas ou complexas demais para uso simples.

---

## 3. Personas

| Persona | Descrição | Necessidade |
|---------|-----------|-------------|
| **Dev Automatizador** | Desenvolvedor que precisa integrar dados de SERP em pipelines | CLI simples, output JSON, fácil de scripting |
| **Analista de SEO** | Profissional que monitora rankings | Resultados limpos, CSV para Excel, execução agendada |
| **Pesquisador** | Acadêmico ou analista coletando dados | Termos em batch, dados estruturados, reprodutibilidade |

---

## 4. Requisitos Funcionais

### 4.1 Input
| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-01 | Aceitar termos via argumento CLI (`--terms "t1,t2"`) | P0 |
| RF-02 | Aceitar termos via arquivo JSON (`--file terms.json`) | P0 |
| RF-03 | Validar formato dos termos antes de executar | P0 |

### 4.2 Busca
| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-04 | Buscar cada termo no Google (google.com) | P0 |
| RF-05 | Extrair os 10 primeiros resultados orgânicos | P0 |
| RF-06 | Usar navegador headless com stealth para evitar bloqueio | P0 |
| RF-07 | Implementar delay configurável entre buscas | P0 |
| RF-08 | Retry automático com backoff exponencial (max 3) | P0 |

### 4.3 Output
| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-09 | Para cada resultado: título, URL, snippet, posição | P0 |
| RF-10 | Exportar resultados em JSON | P0 |
| RF-11 | Exportar resultados em CSV | P1 |
| RF-12 | Incluir metadados (timestamp, termo, duração) | P0 |

### 4.4 Validação
| ID | Requisito | Prioridade |
|----|-----------|------------|
| RF-13 | Validar schema dos resultados via Pydantic | P0 |
| RF-14 | Detectar e reportar resultados parciais (< 10) | P0 |
| RF-15 | Detectar duplicatas de URL dentro do mesmo termo | P1 |

---

## 5. Requisitos Não-Funcionais

| ID | Requisito | Meta |
|----|-----------|------|
| RNF-01 | **Stealth** — Não ser detectado como bot | User-Agent rotation + Playwright stealth |
| RNF-02 | **Latência** — Tempo por termo | ≤ 15 segundos |
| RNF-03 | **Confiabilidade** — Taxa de sucesso | ≥ 90% dos termos |
| RNF-04 | **Extensibilidade** — Fácil adicionar providers | Interface abstrata de SearchProvider |
| RNF-05 | **Observabilidade** — Logs estruturados | Rich console + arquivo de log |
| RNF-06 | **Resiliência** — Parser auto-reparável | CI/CD agentic com health check |

---

## 6. Métricas de Sucesso

| Métrica | Alvo | Medição |
|---------|------|---------|
| Taxa de sucesso por termo | ≥ 90% | `termos_com_10_resultados / total_termos` |
| Latência média por termo | ≤ 15s | Timestamp end - start por termo |
| Dados corrompidos | 0% | Falhas de validação Pydantic |
| Uptime do parser | ≥ 95%/mês | Health check semanal |
| Tempo de auto-reparo | ≤ 24h | Issue detectada → PR merged |

---

## 7. Arquitetura

```
terms.json ──→ CLI ──→ Orchestrator ──→ SearchProvider (Playwright)
                                │              │
                                │              ▼
                                │         ResultParser (BS4)
                                │              │
                                │              ▼
                                │         DataValidator (Pydantic)
                                │              │
                                ▼              ▼
                           Harness Loop    results/ (JSON + CSV)
                                │
                                ▼
                        CI/CD Agentic Loop
```

---

## 8. Riscos e Mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Bloqueio pelo Google (CAPTCHA) | Alto | Alta | Playwright stealth + delays + proxy (futuro) |
| Mudança no layout da SERP | Alto | Média | Parser health check semanal + seletores fallback |
| Rate limiting | Médio | Alta | Delay configurável entre buscas |
| IP ban | Alto | Média | Rotação de User-Agent + limitar frequência |

---

## 9. Roadmap

| Fase | Escopo | Timeline |
|------|--------|----------|
| **v1.0** (MVP) | CLI + Playwright + 10 resultados + JSON/CSV | Sprint 1 |
| **v1.1** | Harness loop + retry + validação | Sprint 1 |
| **v1.2** | Agent skills + CI/CD workflows | Sprint 1 |
| **v2.0** | API REST + dashboard web | Sprint 2 |
| **v2.1** | Suporte a proxy residencial + SerpAPI fallback | Sprint 2 |
| **v3.0** | Multi-engine (Bing, DuckDuckGo) + análise de tendências | Sprint 3 |

---

## 10. Glossário

| Termo | Definição |
|-------|-----------|
| **SERP** | Search Engine Results Page — página de resultados do Google |
| **Stealth** | Técnicas para evitar detecção como bot automatizado |
| **Harness** | Framework de execução que gerencia o loop de scraping |
| **Agentic Loop** | Pipeline CI/CD onde um agente de IA monitora e corrige o sistema |
| **Health Check** | Verificação periódica de que o parser ainda funciona |
