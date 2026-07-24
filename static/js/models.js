/** Model management: set active, merge models */
export function initModels() {
    const terminal = () => document.getElementById('log-terminal');
    const el = (id) => document.getElementById(id);

    async function loadModels() {
        try {
            const [res, baseRes] = await Promise.all([
                fetch('/api/model_versions'),
                fetch('/api/base_models'),
            ]);
            const data = await res.json();
            const baseData = await baseRes.json();
            const versions = data.versions || [];
            const baseModels = baseData.base_models || [];
            const active = data.best_model || '';

            const fillSelect = (sel) => {
                if (!sel) return;
                sel.innerHTML = '<option value="">— select —</option>';
                if (versions.length) {
                    const grpTrained = document.createElement('optgroup');
                    grpTrained.label = 'Trained Models';
                    versions.forEach(v => {
                        const opt = document.createElement('option');
                        opt.value = v.path || '';
                        opt.textContent = `${v.name || 'model'}  mAP50=${v.mAP50}  ${v.is_active ? '(active)' : ''}`;
                        if (v.path === active) opt.selected = true;
                        grpTrained.appendChild(opt);
                    });
                    sel.appendChild(grpTrained);
                }
                if (baseModels.length) {
                    const grpBase = document.createElement('optgroup');
                    grpBase.label = 'Base YOLO Models';
                    baseModels.forEach(b => {
                        const opt = document.createElement('option');
                        opt.value = b.path;
                        opt.textContent = `${b.name}  (base / pretrained)`;
                        grpBase.appendChild(opt);
                    });
                    sel.appendChild(grpBase);
                }
            };
            fillSelect(el('merge-model-a'));
            fillSelect(el('merge-model-b'));

            const listEl = el('models-list');
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
            }
        } catch (e) {
            const t = terminal();
            t && (t.innerText += `\n[MODELS] Load failed: ${e}`);
        }
    }

    // Event delegation — works regardless of when DOM is ready
    document.addEventListener('click', async (e) => {
        if (e.target.id === 'models-refresh-btn') {
            loadModels();
            return;
        }

        if (e.target.classList.contains('set-active-btn')) {
            const path = e.target.dataset.path;
            if (!path) return;
            const t = terminal();
            t && (t.innerText += `\n[MODELS] Setting active: ${path}`);
            const r = await fetch('/api/set_model', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path })
            });
            const j = await r.json();
            t && (t.innerText += `\n[MODELS] ${JSON.stringify(j)}`);
            loadModels();
            try { window.refreshTrainLists?.(); window.refreshTestLists?.(); } catch (_) {}
            return;
        }

        if (e.target.id === 'merge-run-btn') {
            const model_a = el('merge-model-a')?.value;
            const model_b = el('merge-model-b')?.value;
            if (!model_a || !model_b) return alert('Select both models to merge');
            const alpha = parseFloat(el('merge-alpha')?.value) || 0.5;
            const name = el('merge-name')?.value || 'merged';
            const t = terminal();
            t && (t.innerText += `\n[MODELS] Merging (alpha=${alpha})…`);
            try {
                window.showLoader?.('Merging models…');
                const res = await fetch('/api/merge_models', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ model_a, model_b, alpha, name })
                });
                const j = await res.json();
                t && (t.innerText += `\n[MODELS] ${JSON.stringify(j)}`);
                setTimeout(loadModels, 3000);
            } catch (e) {
                t && (t.innerText += `\n[MODELS] Error: ${e}`);
            } finally {
                window.hideLoader?.();
            }
        }
    });

    loadModels();
    window.refreshModelsList = loadModels;
}
