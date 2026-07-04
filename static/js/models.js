/** Model management: set active, merge models */
export function initModels() {
    const listEl = document.getElementById('models-list');
    const mergeA = document.getElementById('merge-model-a');
    const mergeB = document.getElementById('merge-model-b');
    const mergeAlpha = document.getElementById('merge-alpha');
    const mergeName = document.getElementById('merge-name');
    const mergeBtn = document.getElementById('merge-run-btn');
    const refreshBtn = document.getElementById('models-refresh-btn');
    const terminal = document.getElementById('log-terminal');

    async function loadModels() {
        try {
            const res = await fetch('/api/model_versions');
            const data = await res.json();
            const versions = data.versions || [];
            const active = data.best_model || '';

            const fillSelect = (sel) => {
                if (!sel) return;
                sel.innerHTML = '<option value="">— select —</option>';
                versions.forEach(v => {
                    const opt = document.createElement('option');
                    opt.value = v.path || '';
                    opt.textContent = `${v.name || 'model'}  mAP50=${v.mAP50}  ${v.is_active ? '(active)' : ''}`;
                    if (v.path === active) opt.selected = true;
                    sel.appendChild(opt);
                });
            };
            fillSelect(mergeA);
            fillSelect(mergeB);

            if (listEl) {
                listEl.innerHTML = '';
                if (!versions.length) {
                    listEl.innerHTML = '<p style="color:var(--muted)">No trained models found.</p>';
                    return;
                }
                versions.forEach(v => {
                    const row = document.createElement('div');
                    row.className = 'model-row';
                    row.innerHTML = `
                        <div class="model-row-info">
                            <strong>${v.name || 'unknown'}</strong>
                            <span class="model-meta">mAP50: ${v.mAP50} · epochs: ${v.epochs} · ${v.size_mb || '?'}MB · ${v.source || ''}</span>
                            ${v.is_active ? '<span class="badge-active">ACTIVE</span>' : ''}
                        </div>
                        <button class="btn small set-active-btn" data-path="${v.path || ''}" ${v.is_active ? 'disabled' : ''}>Set Active</button>
                    `;
                    listEl.appendChild(row);
                });
                listEl.querySelectorAll('.set-active-btn').forEach(btn => {
                    btn.addEventListener('click', async () => {
                        const path = btn.dataset.path;
                        if (!path) return;
                        terminal && (terminal.innerText += `\n[MODELS] Setting active: ${path}`);
                        const r = await fetch('/api/set_model', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ path })
                        });
                        const j = await r.json();
                        terminal && (terminal.innerText += `\n[MODELS] ${JSON.stringify(j)}`);
                        loadModels();
                        try { window.refreshTrainLists?.(); window.refreshTestLists?.(); } catch (_) {}
                    });
                });
            }
        } catch (e) {
            terminal && (terminal.innerText += `\n[MODELS] Load failed: ${e}`);
        }
    }

    mergeBtn?.addEventListener('click', async () => {
        const model_a = mergeA?.value;
        const model_b = mergeB?.value;
        if (!model_a || !model_b) return alert('Select both models to merge');
        const alpha = parseFloat(mergeAlpha?.value) || 0.5;
        const name = mergeName?.value || 'merged';
        terminal && (terminal.innerText += `\n[MODELS] Merging (alpha=${alpha})…`);
        try {
            window.showLoader?.('Merging models…');
            const res = await fetch('/api/merge_models', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_a, model_b, alpha, name })
            });
            const j = await res.json();
            terminal && (terminal.innerText += `\n[MODELS] ${JSON.stringify(j)}`);
            setTimeout(loadModels, 2000);
        } catch (e) {
            terminal && (terminal.innerText += `\n[MODELS] Error: ${e}`);
        } finally {
            window.hideLoader?.();
        }
    });

    refreshBtn?.addEventListener('click', loadModels);
    loadModels();
    window.refreshModelsList = loadModels;
}
