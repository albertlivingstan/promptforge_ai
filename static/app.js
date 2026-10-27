const $ = id => document.getElementById(id);

const descriptions = {
  structured: 'Organized sections, examples, and checklist',
  few_shot: 'Learn response style from an example',
  role_based: 'Professor-level perspective and clarity',
  decomposition: 'Split complex tasks into smaller parts',
  constraints: 'Accuracy, limits, and explicit criteria',
  self_refine: 'Revise and verify the final answer'
};

const escapeHTML = s => String(s || '').replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[c]));

async function api(path, data) {
  const r = await fetch('/api/' + path, {
    method: data ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: data ? JSON.stringify(data) : undefined
  });
  const j = await r.json();
  if (!r.ok) throw Error(j.detail || 'Request failed');
  return j;
}

const payload = () => ({
  prompt: $('prompt').value.trim(),
  audience: $('audience').value.trim(),
  expected: $('expected').value.trim(),
  route: $('route') ? $('route').value : 'auto'
});

const selected = () => [...document.querySelectorAll('.strategy input:checked')].map(x => x.value);
const status = s => $('status').textContent = s;

function diagnostic(a) {
  $('diagnostics').innerHTML = `
    <div class="metric">Clarity heuristic: <b>${a.clarity}/100</b></div>
    <div class="metric">Task: <b>${escapeHTML(a.task_type)}</b></div>
    <div class="metric">Words: <b>${a.word_count}</b></div>
    <h3 style="margin-top:14px;font-size:14px;color:var(--text)">Diagnostic Recommendations</h3>
    <ul style="padding-left:18px;margin:8px 0;color:var(--muted);font-size:13px">
      ${a.suggestions.map(s => `<li>${escapeHTML(s)}</li>`).join('')}
    </ul>
    <p class="hint">Diagnostic scores are rules-based indicators to guide prompt refinement.</p>
  `;
}

let previewTimer = null;
async function updateRoutePreview() {
  const p = payload();
  if (!p.prompt || p.prompt.length < 3) return;
  try {
    const res = await api('route-preview', p);
    const orderStr = res.attempt_order.join(' → ');
    $('routePreview').textContent = `⚡ Policy: ${res.reason} (Order: ${orderStr})`;
  } catch {
    $('routePreview').textContent = `Route: ${p.route}`;
  }
}

function debounceRoutePreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(updateRoutePreview, 300);
}

async function analyze() {
  const p = payload();
  if (!p.prompt || p.prompt.length < 3) {
    alert('Please enter a prompt of at least 3 characters.');
    return;
  }
  try {
    status('Analyzing prompt...');
    const result = await api('analyze', p);
    diagnostic(result);
    status('Analysis complete');
  } catch (e) {
    status('Analysis failed');
    alert(e.message);
  }
}

async function optimize() {
  const p = payload();
  const strats = selected();
  if (!p.prompt || p.prompt.length < 3) {
    alert('Please enter a prompt of at least 3 characters.');
    return;
  }
  if (!strats.length) {
    alert('Please select at least one optimization strategy.');
    return;
  }
  try {
    status('Generating prompt variants...');
    const a = await api('optimize', { ...p, strategies: strats });
    diagnostic(a.analysis);
    $('results').innerHTML = `
      <div style="margin-bottom:14px;color:var(--mint);font-size:13px">Generated ${a.candidates.length} prompt variations. Click "Run Selected Strategies" to test LLM outputs.</div>
      ${a.candidates.map(x => `
        <div class="result">
          <h3>${escapeHTML(x.strategy.replace('_', ' '))}</h3>
          <pre>${escapeHTML(x.prompt)}</pre>
        </div>
      `).join('')}
    `;
    status('Ready');
  } catch (e) {
    status('Error: ' + e.message);
    alert(e.message);
  }
}

async function compare() {
  const p = payload();
  const strats = selected();
  if (!p.prompt || p.prompt.length < 3) {
    alert('Please enter a prompt of at least 3 characters.');
    return;
  }
  if (!strats.length) {
    alert('Please select at least one optimization strategy.');
    return;
  }

  try {
    status('Executing model runs...');
    $('compare').disabled = true;
    $('results').innerHTML = '<div class="empty">Running candidate prompts through selected route... Please wait.</div>';

    const a = await api('compare', { ...p, strategies: strats });

    $('results').innerHTML = `
      <div class="hint" style="background:#1b1932;border:1px solid #3d3570;padding:12px;border-radius:10px;margin-bottom:18px">
        ★ Top heuristic candidate: <b style="color:var(--mint)">${escapeHTML(a.best_strategy)}</b>. ${escapeHTML(a.selection_note)}
      </div>
      ${a.results.map(x => {
        const isBest = x.strategy === a.best_strategy;
        const gen = x.generation || {};
        return `
          <div class="result" style="${isBest ? 'border-left:3px solid var(--mint);padding-left:14px' : ''}">
            <h3>
              <span>${escapeHTML(x.strategy.replace('_', ' '))} ${isBest ? '★ (Best score)' : ''}</span>
              <span style="font-size:12px;color:var(--muted)">Route: ${escapeHTML(gen.route || '')} (${escapeHTML(gen.model || '')})</span>
            </h3>
            <div style="margin:8px 0">
              ${Object.entries(x.metrics).map(([k, v]) => `
                <span class="metric">${escapeHTML(k.replace('_proxy', '').replace('_', ' '))}: <b>${v}</b></span>
              `).join('')}
              <span class="metric">⚡ ${gen.latency_ms || 0} ms</span>
              <span class="metric">🔤 ${gen.tokens || 0} tokens</span>
            </div>
            <h4 style="font-size:12px;color:var(--muted);margin:12px 0 4px">Optimized Prompt</h4>
            <pre>${escapeHTML(x.optimized)}</pre>
            <h4 style="font-size:12px;color:var(--muted);margin:12px 0 4px">Model Response</h4>
            <pre>${escapeHTML(x.response)}</pre>
          </div>
        `;
      }).join('')}
    `;
    status(`Completed ${a.results.length} runs successfully`);
  } catch (e) {
    status('Execution error');
    $('results').innerHTML = `
      <div class="error-box">
        <b>Execution failed:</b> ${escapeHTML(e.message)}
        <div style="margin-top:10px;font-size:12px;color:#fce4e4">
          💡 <b>Tip:</b> If running offline without local Ollama or OpenAI keys, switch the <b>Routing Policy</b> dropdown to <b>Mock Demo</b> for simulated outputs.
        </div>
      </div>
    `;
  } finally {
    $('compare').disabled = false;
  }
}

async function history() {
  try {
    const [stats, rows] = await Promise.all([
      api('stats').catch(() => null),
      api('history?limit=50').catch(() => [])
    ]);

    if (stats) {
      $('historyStats').innerHTML = `
        <div class="stat-card">
          <div class="val">${stats.total}</div>
          <div class="lbl">Total Experiments</div>
        </div>
        <div class="stat-card">
          <div class="val">${stats.avg_latency_ms} ms</div>
          <div class="lbl">Avg Latency</div>
        </div>
        <div class="stat-card">
          <div class="val">${stats.tokens}</div>
          <div class="lbl">Total Tokens</div>
        </div>
      `;
    }

    if (!rows.length) {
      $('historyRows').innerHTML = '<div class="empty">No experiment history yet. Run strategies in the Optimization Lab to record results.</div>';
      return;
    }

    $('historyRows').innerHTML = rows.map(x => `
      <div class="result" style="display:flex;justify-content:space-between;align-items:flex-start;gap:15px">
        <div style="flex:1">
          <b>#${x.id} · ${escapeHTML(x.strategy.replace('_', ' '))}</b>
          <div style="font-size:11px;color:var(--muted);margin:3px 0 8px">
            ${escapeHTML(x.provider)} / ${escapeHTML(x.model)} · ${escapeHTML(x.created_at)}
          </div>
          <p style="margin:6px 0;font-size:13px;color:#d2dcf0">${escapeHTML(x.original)}</p>
          <div>
            <span class="metric">Score: ${x.metrics.heuristic_score}</span>
            <span class="metric">${x.latency_ms} ms</span>
            <span class="metric">${x.tokens} tokens</span>
          </div>
        </div>
        <button class="secondary btn-load" data-id="${x.id}" style="padding:6px 12px;font-size:12px">Load</button>
      </div>
    `).join('');

    document.querySelectorAll('.btn-load').forEach(btn => {
      btn.onclick = async () => {
        const id = btn.dataset.id;
        try {
          const exp = await api('experiments/' + id);
          $('prompt').value = exp.original;
          $('nav-lab').click();
          status(`Loaded experiment #${id}`);
        } catch (e) {
          alert('Could not load experiment: ' + e.message);
        }
      };
    });
  } catch (e) {
    $('historyRows').innerHTML = `<div class="error-box">${escapeHTML(e.message)}</div>`;
  }
}

// Nav handling
document.querySelectorAll('.nav').forEach(b => {
  b.onclick = () => {
    document.querySelectorAll('.nav').forEach(n => n.classList.remove('active'));
    b.classList.add('active');
    document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
    const targetPage = $(b.dataset.page);
    if (targetPage) targetPage.classList.remove('hidden');
    if (b.dataset.page === 'history') history();
  };
});

// Render strategy checkboxes
$('strategyList').innerHTML = Object.entries(descriptions).map(([k, v], i) => `
  <div class="strategy">
    <label>
      <input type="checkbox" value="${k}" ${i < 3 ? 'checked' : ''}>
      <b>${escapeHTML(k.replace('_', ' '))}</b>
    </label>
    <p>${escapeHTML(v)}</p>
  </div>
`).join('');

// Bind buttons & listeners
$('analyze').onclick = analyze;
$('optimize').onclick = optimize;
$('compare').onclick = compare;
$('refresh').onclick = history;

$('prompt').addEventListener('input', debounceRoutePreview);
$('route').addEventListener('change', updateRoutePreview);

// Check providers and status
async function initProviders() {
  try {
    const p = await api('providers');
    const badge = $('provider');
    if (p.local_ready) {
      badge.textContent = `● Ollama: ${p.local_model}`;
      badge.classList.remove('offline');
    } else if (p.cloud_configured) {
      badge.textContent = `● Cloud: ${p.cloud_model}`;
      badge.classList.remove('offline');
    } else {
      badge.textContent = `● Mock Mode`;
      badge.classList.remove('offline');
    }
  } catch {
    $('provider').textContent = '● Offline';
    $('provider').classList.add('offline');
  }
  updateRoutePreview();
}

initProviders();
