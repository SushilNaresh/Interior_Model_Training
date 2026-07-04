/** Standalone OCR / room text mapping */
export function initAnalyse() {
    const imageSelect = document.getElementById('analyse-image-select');
    const fileInput = document.getElementById('analyse-file');
    const runBtn = document.getElementById('analyse-run-btn');
    const refreshBtn = document.getElementById('analyse-refresh-btn');
    const overlayImg = document.getElementById('analyse-overlay');
    const placeholder = document.getElementById('analyse-placeholder');
    const mappingsEl = document.getElementById('analyse-mappings');
    const summaryEl = document.getElementById('analyse-summary');
    const terminal = document.getElementById('log-terminal');

    async function refreshImages() {
        if (!imageSelect) return;
        try {
            const res = await fetch('/api/status');
            const data = await res.json();
            imageSelect.innerHTML = '<option value="">— upload file below or pick —</option>';
            (data.raw_images || []).forEach(n => {
                const opt = document.createElement('option');
                opt.value = n;
                opt.textContent = n;
                imageSelect.appendChild(opt);
            });
        } catch (_) {}
    }

    async function getImageBlob() {
        if (fileInput?.files?.length) {
            return { blob: fileInput.files[0], name: fileInput.files[0].name };
        }
        const name = imageSelect?.value;
        if (!name) return null;
        const res = await fetch(`/api/raw/${encodeURIComponent(name)}`);
        if (!res.ok) return null;
        const j = await res.json();
        if (!j.img_b64) return null;
        const bytes = Uint8Array.from(atob(j.img_b64), c => c.charCodeAt(0));
        return { blob: new Blob([bytes], { type: 'image/jpeg' }), name };
    }

    runBtn?.addEventListener('click', async () => {
        const img = await getImageBlob();
        if (!img) return alert('Select an image or upload a file');
        terminal && (terminal.innerText += `\n[ANALYSE] Running OCR on ${img.name}`);
        try {
            window.showLoader?.('Running OCR analysis…');
            const fd = new FormData();
            fd.append('file', img.blob, img.name);
            const res = await fetch('/api/analyse', { method: 'POST', body: fd });
            const data = await res.json();
            if (!res.ok) {
                terminal && (terminal.innerText += `\n[ANALYSE] Error: ${JSON.stringify(data)}`);
                return;
            }
            if (data.overlay_b64) {
                placeholder.style.display = 'none';
                overlayImg.style.display = 'block';
                overlayImg.src = 'data:image/jpeg;base64,' + data.overlay_b64;
            }
            if (mappingsEl) {
                mappingsEl.innerHTML = '';
                (data.mappings || []).forEach(m => {
                    const li = document.createElement('li');
                    li.textContent = `"${m.text}" → ${m.class} @ (${Math.round(m.cx)}, ${Math.round(m.cy)})`;
                    mappingsEl.appendChild(li);
                });
                if (!(data.mappings || []).length) mappingsEl.innerHTML = '<li style="color:var(--muted)">No mappings</li>';
            }
            if (summaryEl) summaryEl.textContent = JSON.stringify(data.summary || {}, null, 2);
            terminal && (terminal.innerText += `\n[ANALYSE] ${(data.mappings || []).length} mapping(s)`);
        } catch (e) {
            terminal && (terminal.innerText += `\n[ANALYSE] Exception: ${e}`);
        } finally {
            window.hideLoader?.();
        }
    });

    refreshBtn?.addEventListener('click', refreshImages);
    refreshImages();
}
