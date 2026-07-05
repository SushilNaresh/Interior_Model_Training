/** Standalone OCR / room text mapping */
export function initAnalyse() {
    // Panel HTML is injected via insertAdjacentHTML AFTER this module runs,
    // so getElementById calls here return null. Resolve elements lazily.
    const get = id => document.getElementById(id);
    const terminal = () => document.getElementById('log-terminal');

    async function refreshImages() {
        const imageSelect = get('analyse-image-select');
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
        const fileInput = get('analyse-file');
        const imageSelect = get('analyse-image-select');
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

    // Use event delegation — panel is not in DOM when initAnalyse() runs
    document.addEventListener('click', async e => {
        if (e.target.id === 'analyse-refresh-btn') {
            refreshImages();
            return;
        }
        if (e.target.id !== 'analyse-run-btn') return;

        const img = await getImageBlob();
        if (!img) return alert('Select an image or upload a file');
        const t = terminal();
        t && (t.innerText += `\n[ANALYSE] Running OCR on ${img.name}`);
        try {
            window.showLoader?.('Running OCR analysis…');
            const fd = new FormData();
            fd.append('file', img.blob, img.name);
            const res = await fetch('/api/analyse', { method: 'POST', body: fd });
            const data = await res.json();
            if (!res.ok) {
                t && (t.innerText += `\n[ANALYSE] Error: ${JSON.stringify(data)}`);
                return;
            }
            const overlayImg = get('analyse-overlay');
            const placeholder = get('analyse-placeholder');
            const mappingsEl = get('analyse-mappings');
            const summaryEl = get('analyse-summary');
            if (data.overlay_b64 && overlayImg && placeholder) {
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
                if (!(data.mappings || []).length) mappingsEl.innerHTML = '<li style="color:var(--muted)">No mappings found</li>';
            }
            if (summaryEl) summaryEl.textContent = JSON.stringify(data.summary || {}, null, 2);
            t && (t.innerText += `\n[ANALYSE] ${(data.mappings || []).length} mapping(s)`);
        } catch (e) {
            t && (t.innerText += `\n[ANALYSE] Exception: ${e}`);
        } finally {
            window.hideLoader?.();
        }
    });

    // Refresh image list when OCR nav tab is clicked
    document.getElementById('nav-analyse')?.addEventListener('click', refreshImages);
}
