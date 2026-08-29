/**
 * WebScrapper — Frontend Client Application
 * Handles reactive UI, real-time polling, term management, and SERP exploration.
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const btnStartScrape = document.getElementById('btn-start-scrape');
  const btnStopScrape = document.getElementById('btn-stop-scrape');
  const btnValidateNow = document.getElementById('btn-validate-now');
  const btnRefreshResults = document.getElementById('btn-refresh-results');
  const btnClearLogs = document.getElementById('btn-clear-logs');
  
  const formAddTerm = document.getElementById('form-add-term');
  const inputNewTerm = document.getElementById('input-new-term');
  const termsChipsArea = document.getElementById('terms-chips-area');
  const termsCounterBadge = document.getElementById('terms-counter-badge');
  
  const progressBarFill = document.getElementById('progress-bar-fill');
  const progressLabel = document.getElementById('progress-label');
  const progressPercentageText = document.getElementById('progress-percentage-text');
  const activityTerminal = document.getElementById('activity-terminal');
  
  const statTotalTerms = document.getElementById('stat-total-terms');
  const statTotalResults = document.getElementById('stat-total-results');
  const statSuccessRate = document.getElementById('stat-success-rate');
  const statCurrentState = document.getElementById('stat-current-state');
  const systemStatusDot = document.getElementById('system-status-dot');
  const systemStatusText = document.getElementById('system-status-text');
  
  const resultsCardsList = document.getElementById('results-cards-list');
  const inputFilterResults = document.getElementById('input-filter-results');
  const resultsFileList = document.getElementById('results-file-list');
  
  const sectionValidationPanel = document.getElementById('section-validation-panel');
  const validationDetailsContent = document.getElementById('validation-details-content');
  const validationHealthBadge = document.getElementById('validation-health-badge');

  // Application State
  let termsList = [];
  let pollInterval = null;
  let allResults = [];
  let lastLogCount = 0;

  // -------------------------------------------------------------------------
  // Toast Notifications
  // -------------------------------------------------------------------------
  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icon = type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ';
    toast.innerHTML = `<span style="font-weight: 700;">${icon}</span> <span>${message}</span>`;
    
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // -------------------------------------------------------------------------
  // Terminal Logging
  // -------------------------------------------------------------------------
  function appendLog(timestamp, message, level = 'info') {
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    
    let levelClass = 'log-msg-info';
    if (level === 'success') levelClass = 'log-msg-success';
    else if (level === 'warning') levelClass = 'log-msg-warning';
    else if (level === 'error') levelClass = 'log-msg-error';
    else if (level === 'debug') levelClass = 'log-msg-debug';

    entry.innerHTML = `
      <span class="log-time">[${timestamp}]</span>
      <span class="${levelClass}">${message}</span>
    `;
    activityTerminal.appendChild(entry);
    activityTerminal.scrollTop = activityTerminal.scrollHeight;
  }

  btnClearLogs.addEventListener('click', () => {
    activityTerminal.innerHTML = '';
    appendLog(new Date().toLocaleTimeString(), 'Logs limpos pelo usuário.', 'debug');
  });

  // -------------------------------------------------------------------------
  // Terms Management
  // -------------------------------------------------------------------------
  async function loadTerms() {
    try {
      const res = await fetch('/api/terms');
      if (!res.ok) throw new Error('Falha ao carregar termos');
      const data = await res.json();
      termsList = data.terms || [];
      renderTermsChips();
      statTotalTerms.textContent = termsList.length;
    } catch (err) {
      showToast('Erro ao carregar lista de termos', 'error');
    }
  }

  function renderTermsChips() {
    termsChipsArea.innerHTML = '';
    termsCounterBadge.textContent = `${termsList.length} termo${termsList.length === 1 ? '' : 's'}`;

    if (termsList.length === 0) {
      termsChipsArea.innerHTML = '<span style="color: var(--text-dim); font-size: 0.85rem;">Nenhum termo cadastrado.</span>';
      return;
    }

    termsList.forEach(term => {
      const chip = document.createElement('div');
      chip.className = 'term-chip';
      chip.innerHTML = `
        <span>${escapeHtml(term)}</span>
        <button class="term-chip-delete" title="Remover termo" data-term="${escapeHtml(term)}">✕</button>
      `;
      termsChipsArea.appendChild(chip);
    });

    // Attach delete handlers
    document.querySelectorAll('.term-chip-delete').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const termToDelete = e.currentTarget.getAttribute('data-term');
        await deleteTerm(termToDelete);
      });
    });
  }

  async function addTerm(term) {
    if (!term || !term.trim()) return;
    try {
      const res = await fetch('/api/terms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ term: term.trim() }),
      });
      if (res.status === 409) {
        showToast(`O termo "${term}" já existe.`, 'warning');
        return;
      }
      if (!res.ok) throw new Error('Falha ao adicionar termo');
      
      showToast(`Termo "${term}" adicionado!`, 'success');
      inputNewTerm.value = '';
      await loadTerms();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function deleteTerm(term) {
    try {
      const res = await fetch(`/api/terms/${encodeURIComponent(term)}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error('Falha ao remover termo');
      showToast(`Termo "${term}" removido.`, 'info');
      await loadTerms();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  formAddTerm.addEventListener('submit', async (e) => {
    e.preventDefault();
    await addTerm(inputNewTerm.value);
  });

  // -------------------------------------------------------------------------
  // Scraping Controls & Real-time Polling
  // -------------------------------------------------------------------------
  const cfgEngineSelect = document.getElementById('cfg-engine');
  const badgeEngineType = document.getElementById('badge-engine-type');

  if (cfgEngineSelect && badgeEngineType) {
    cfgEngineSelect.addEventListener('change', (e) => {
      badgeEngineType.textContent = e.target.value === 'duckduckgo' ? 'DuckDuckGo Engine' : 'Playwright Stealth';
    });
    badgeEngineType.textContent = cfgEngineSelect.value === 'duckduckgo' ? 'DuckDuckGo Engine' : 'Playwright Stealth';
  }

  btnStartScrape.addEventListener('click', async () => {
    const engine = cfgEngineSelect ? cfgEngineSelect.value : 'duckduckgo';
    const maxResults = parseInt(document.getElementById('cfg-max-results').value, 10) || 10;
    const delayMin = parseFloat(document.getElementById('cfg-delay-min').value) || 1.0;
    const delayMax = parseFloat(document.getElementById('cfg-delay-max').value) || 3.0;
    const maxRetries = parseInt(document.getElementById('cfg-max-retries').value, 10) || 3;
    const headless = document.getElementById('cfg-headless').checked;

    try {
      btnStartScrape.disabled = true;
      const res = await fetch('/api/scrape/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          engine: engine,
          max_results: maxResults,
          delay_min: delayMin,
          delay_max: delayMax,
          max_retries: maxRetries,
          headless: headless,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Erro ao iniciar raspagem');
      }

      showToast('Raspagem iniciada com sucesso!', 'success');
      setScrapingActiveUI(true);
      startPolling();
    } catch (err) {
      showToast(err.message, 'error');
      btnStartScrape.disabled = false;
    }
  });

  btnStopScrape.addEventListener('click', async () => {
    try {
      await fetch('/api/scrape/stop', { method: 'POST' });
      showToast('Solicitação de parada enviada.', 'warning');
    } catch (err) {
      showToast('Erro ao parar raspagem.', 'error');
    }
  });

  function setScrapingActiveUI(active) {
    if (active) {
      btnStartScrape.style.display = 'none';
      btnStopScrape.style.display = 'inline-flex';
      systemStatusDot.classList.add('running');
      systemStatusText.textContent = 'Raspando Google...';
      statCurrentState.textContent = 'RUNNING';
      statCurrentState.style.color = 'var(--primary)';
    } else {
      btnStartScrape.style.display = 'inline-flex';
      btnStartScrape.disabled = false;
      btnStopScrape.style.display = 'none';
      systemStatusDot.classList.remove('running');
      systemStatusText.textContent = 'Backend Pronto';
      statCurrentState.textContent = 'IDLE';
      statCurrentState.style.color = 'var(--text-main)';
    }
  }

  function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    lastLogCount = 0;

    pollInterval = setInterval(async () => {
      try {
        const res = await fetch('/api/scrape/status');
        if (!res.ok) return;
        const status = await res.json();

        // Update progress bar
        const pct = status.progress_percentage || 0;
        progressBarFill.style.width = `${pct}%`;
        progressPercentageText.textContent = `${pct}%`;

        if (status.is_running) {
          progressLabel.textContent = status.current_term 
            ? `Buscando (${status.current_index}/${status.total_terms}): "${status.current_term}"`
            : 'Iniciando motor Playwright...';
          statTotalResults.textContent = status.current_results_count || 0;
        }

        // Render new logs
        if (status.logs && status.logs.length > lastLogCount) {
          for (let i = lastLogCount; i < status.logs.length; i++) {
            const l = status.logs[i];
            appendLog(l.timestamp, l.message, l.level);
          }
          lastLogCount = status.logs.length;
        }

        // Live partial results render
        if (status.results && status.results.length > 0 && status.is_running) {
          allResults = status.results;
          renderResults(allResults);
        }

        // Check if finished
        if (!status.is_running) {
          clearInterval(pollInterval);
          pollInterval = null;
          setScrapingActiveUI(false);

          if (status.status === 'completed') {
            progressLabel.textContent = '✓ Raspagem concluída!';
            showToast('Raspagem finalizada com sucesso!', 'success');
            await loadLatestResults();
            await loadFilesList();
          } else if (status.status === 'cancelled') {
            progressLabel.textContent = '⏹ Raspagem cancelada.';
            showToast('Raspagem cancelada pelo usuário.', 'warning');
          } else if (status.status === 'failed') {
            progressLabel.textContent = '✗ Falha durante a raspagem.';
            showToast('Ocorreu uma falha na coleta.', 'error');
          }
        }
      } catch (err) {
        console.error('Erro no polling:', err);
      }
    }, 1000);
  }

  // -------------------------------------------------------------------------
  // Results & SERP Explorer
  // -------------------------------------------------------------------------
  async function loadLatestResults() {
    try {
      const res = await fetch('/api/results/latest');
      if (!res.ok) return;
      const json = await res.json();
      const report = json.data;

      if (report && report.reports) {
        allResults = [];
        report.reports.forEach(r => {
          if (r.results) {
            r.results.forEach(resItem => {
              allResults.push({
                term: r.term,
                position: resItem.position,
                title: resItem.title,
                url: resItem.url,
                snippet: resItem.snippet,
                status: r.status,
              });
            });
          }
        });

        statTotalResults.textContent = allResults.length;
        statSuccessRate.textContent = `${Math.round((report.success_rate || 1) * 100)}%`;
        renderResults(allResults);
      }
    } catch (err) {
      console.warn('Nenhum resultado anterior disponível:', err);
    }
  }

  function renderResults(results) {
    if (!results || results.length === 0) {
      resultsCardsList.innerHTML = `
        <div style="text-align: center; padding: 40px; color: var(--text-dim);">
          <div style="font-size: 32px; margin-bottom: 10px;">🔍</div>
          <p>Nenhum resultado correspondente aos filtros.</p>
        </div>
      `;
      return;
    }

    resultsCardsList.innerHTML = '';
    results.forEach(item => {
      const card = document.createElement('article');
      card.className = 'serp-card';

      let rankClass = '';
      if (item.position === 1) rankClass = 'rank-1';
      else if (item.position === 2) rankClass = 'rank-2';
      else if (item.position === 3) rankClass = 'rank-3';

      card.innerHTML = `
        <div class="rank-badge ${rankClass}">#${item.position}</div>
        <div class="serp-content">
          <div class="serp-meta">
            <span class="serp-term-tag">${escapeHtml(item.term)}</span>
            <span>Posição ${item.position}</span>
          </div>
          <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" class="serp-title">
            ${escapeHtml(item.title)}
            <span style="font-size: 0.8rem;">↗</span>
          </a>
          <div class="serp-url">${escapeHtml(item.url)}</div>
          <p class="serp-snippet">${escapeHtml(item.snippet || 'Nenhum snippet retornado para este resultado.')}</p>
        </div>
        <div class="serp-actions">
          <button class="btn-icon btn-copy-url" title="Copiar URL" data-url="${escapeHtml(item.url)}">📋</button>
        </div>
      `;
      resultsCardsList.appendChild(card);
    });

    // Attach copy handlers
    document.querySelectorAll('.btn-copy-url').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const url = e.currentTarget.getAttribute('data-url');
        navigator.clipboard.writeText(url);
        showToast('URL copiada para a área de transferência!', 'success');
      });
    });
  }

  // Filter Results
  inputFilterResults.addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase().trim();
    if (!query) {
      renderResults(allResults);
      return;
    }

    const filtered = allResults.filter(item => 
      item.title.toLowerCase().includes(query) ||
      item.url.toLowerCase().includes(query) ||
      item.term.toLowerCase().includes(query) ||
      (item.snippet && item.snippet.toLowerCase().includes(query))
    );
    renderResults(filtered);
  });

  btnRefreshResults.addEventListener('click', async () => {
    await loadLatestResults();
    await loadFilesList();
    showToast('Resultados atualizados.', 'info');
  });

  // -------------------------------------------------------------------------
  // File Downloads & History
  // -------------------------------------------------------------------------
  async function loadFilesList() {
    try {
      const res = await fetch('/api/results');
      if (!res.ok) return;
      const data = await res.json();
      const files = data.files || [];

      resultsFileList.innerHTML = '';
      if (files.length === 0) {
        resultsFileList.innerHTML = '<span style="color: var(--text-dim); font-size: 0.8rem;">Nenhum arquivo gerado ainda.</span>';
        return;
      }

      files.slice(0, 5).forEach(f => {
        const row = document.createElement('div');
        row.style.display = 'flex';
        row.style.justifyContent = 'space-between';
        row.style.alignItems = 'center';
        row.style.padding = '6px 10px';
        row.style.background = 'rgba(255, 255, 255, 0.02)';
        row.style.borderRadius = 'var(--radius-sm)';
        row.style.border = '1px solid var(--border-subtle)';

        const sizeKb = Math.round(f.size_bytes / 1024);
        row.innerHTML = `
          <div style="display: flex; gap: 8px; align-items: center; font-size: 0.85rem;">
            <span style="font-weight: 700; color: var(--primary); font-size: 0.75rem;">[${f.type}]</span>
            <span style="color: var(--text-main); font-family: monospace;">${escapeHtml(f.name)}</span>
            <span style="color: var(--text-dim); font-size: 0.75rem;">(${sizeKb} KB)</span>
          </div>
          <a href="/api/results/download/${encodeURIComponent(f.name)}" download class="btn-icon" title="Baixar Arquivo" style="width: 28px; height: 28px; font-size: 12px; text-decoration: none;">⬇</a>
        `;
        resultsFileList.appendChild(row);
      });
    } catch (err) {
      console.warn('Erro ao carregar lista de arquivos:', err);
    }
  }

  // -------------------------------------------------------------------------
  // Validation Panel
  // -------------------------------------------------------------------------
  btnValidateNow.addEventListener('click', async () => {
    try {
      btnValidateNow.disabled = true;
      const res = await fetch('/api/validate', { method: 'POST' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Nenhum resultado para validar');
      }

      const val = await res.json();
      sectionValidationPanel.style.display = 'block';
      
      const isValid = val.is_valid;
      validationHealthBadge.textContent = isValid ? 'Aprovado ✓' : 'Com Inconsistências ✗';
      validationHealthBadge.style.color = isValid ? 'var(--success)' : 'var(--error)';
      validationHealthBadge.style.borderColor = isValid ? 'var(--success)' : 'var(--error)';

      let issuesHtml = '';
      if (val.issues && val.issues.length > 0) {
        issuesHtml = `
          <h4 style="margin-top: 14px; margin-bottom: 8px; font-size: 0.9rem; color: var(--warning);">Apontamentos Identificados:</h4>
          <ul style="padding-left: 20px; font-size: 0.85rem; color: var(--text-muted); display: flex; flex-direction: column; gap: 4px;">
            ${val.issues.map(i => `<li><strong>[${i.severity.toUpperCase()}] ${escapeHtml(i.term)}:</strong> ${escapeHtml(i.message)}</li>`).join('')}
          </ul>
        `;
      } else {
        issuesHtml = '<p style="color: var(--success); font-size: 0.9rem; margin-top: 10px;">✓ Todas as verificações de integridade, URLs e contagem passaram com sucesso!</p>';
      }

      validationDetailsContent.innerHTML = `
        <div style="display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 12px; font-size: 0.88rem;">
          <div><strong>Arquivo:</strong> <code>${escapeHtml(val.file)}</code></div>
          <div><strong>Total de Verificações:</strong> ${val.total_checks}</div>
          <div><strong>Aprovadas:</strong> <span style="color: var(--success);">${val.passed}</span></div>
          <div><strong>Avisos:</strong> <span style="color: var(--warning);">${val.warnings}</span></div>
          <div><strong>Erros:</strong> <span style="color: var(--error);">${val.errors}</span></div>
        </div>
        ${issuesHtml}
      `;

      showToast(isValid ? 'Resultados validados com sucesso!' : 'Validação encontrou alertas.', isValid ? 'success' : 'warning');
      sectionValidationPanel.scrollIntoView({ behavior: 'smooth' });
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btnValidateNow.disabled = false;
    }
  });

  // Helper: Escape HTML
  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, m => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[m]));
  }

  // Initial Load
  loadTerms();
  loadLatestResults();
  loadFilesList();
});
