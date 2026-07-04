/** Convert & evaluate: Gemini → IFC + label comparison */
export function initConvert() {
    const fileInput = document.getElementById('convert-file');
    const imageSelect = document.getElementById('convert-image-select');
    const metaChoice = document.getElementById('convert-metadata-choice');
    const weightsBefore = document.getElementById('convert-weights-before');
    const weightsAfter = document.getElementById('convert-weights-after');
    const runBtn = document.getElementById('convert-run-btn');
    const refreshBtn = document.getElementById('convert-refresh-btn');
    const resultEl = document.getElementById('convert-result');
    const terminal = document.getElementById('log-terminal');

    async function refreshLists() {
        try {
            const [sres, mres] = await Promise.all([fetch('/api/status'), fetch('/api/model_versions')]);
            const sdata = await sres.json();
            const mdata = await mres.json();
            if (imageSelect) {
                imageSelect.innerHTML = '<option value="">— upload below or pick —</option>';
                (sdata.raw_images || []).forEach(n => {
                    const opt = document.createElement('option');
                    opt.value = n;
                    opt.textContent = n;
                    imageSelect.appendChild(opt);
                });
            }
            const fillModel = (sel) => {
                if (!sel) return;
                sel.innerHTML = '<option value="">— none —</option>';
                (mdata.versions || []).forEach(v => {
                    const opt = document.createElement('option');
                    opt.value = v.path || '';
                    opt.textContent = v.name || v.path?.split('/').slice(-3).join('/') || 'model';
                    sel.appendChild(opt);
                });
            };
            fillModel(weightsBefore);
            fillModel(weightsAfter);
        } catch (_) {}
    }

    async function getFile() {
        if (fileInput?.files?.length) return fileInput.files[0];
        const name = imageSelect?.value;
        if (!name) return null;
        const res = await fetch(`/api/raw/${encodeURIComponent(name)}`);
        if (!res.ok) return null;
        const j = await res.json();
        if (!j.img_b64) return null;
        const bytes = Uint8Array.from(atob(j.img_b64), c => c.charCodeAt(0));
        return new File([bytes], name, { type: 'image/jpeg' });
    }

    runBtn?.addEventListener('click', async () => {
        const file = await getFile();
        if (!file) return alert('Select or upload an image');
        terminal && (terminal.innerText += `\n[CONVERT] Running convert & evaluate on ${file.name}`);
        try {
            window.showLoader?.('Converting & evaluating…');
            const fd = new FormData();
            fd.append('file', file);
            fd.append('metadata_choice', metaChoice?.value || 'gemini');
            if (weightsBefore?.value) fd.append('weights_before', weightsBefore.value);
            if (weightsAfter?.value) fd.append('weights_after', weightsAfter.value);
            const res = await fetch('/api/convert_and_evaluate', { method: 'POST', body: fd });
            const data = await res.json();
            if (resultEl) resultEl.textContent = JSON.stringify(data, null, 2);
            terminal && (terminal.innerText += `\n[CONVERT] ${res.ok ? 'OK' : 'FAIL'}: ${JSON.stringify(data).slice(0, 400)}`);
        } catch (e) {
            terminal && (terminal.innerText += `\n[CONVERT] Exception: ${e}`);
        } finally {
            window.hideLoader?.();
        }
    });

    refreshBtn?.addEventListener('click', refreshLists);
    refreshLists();
}
