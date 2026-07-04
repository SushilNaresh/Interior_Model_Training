export function initTest() {
    const btn = document.getElementById('test-run-btn');
    const terminal = document.getElementById('log-terminal');
    if (!btn) return;
    const refreshBtn = document.getElementById('test-refresh-btn');
    const imageSelect = document.getElementById('test-image-select');
    const modelSelect = document.getElementById('test-model-select');
    const confInput = document.getElementById('test-conf');
    const imgszInput = document.getElementById('test-imgsz');

    async function refreshLists() {
        try {
            const [sres, mres] = await Promise.all([fetch('/api/status'), fetch('/api/model_versions')]);
            const sdata = await sres.json();
            const mdata = await mres.json();
            if (imageSelect) {
                imageSelect.innerHTML = '';
                (sdata.raw_images || []).forEach(n => {
                    const opt = document.createElement('option');
                    opt.value = n;
                    opt.innerText = n;
                    imageSelect.appendChild(opt);
                });
                (sdata.labelled_images || []).forEach(n => {
                    const opt = document.createElement('option');
                    opt.value = n;
                    opt.innerText = n + ' (labelled)';
                    imageSelect.appendChild(opt);
                });
            }
            if (modelSelect) {
                modelSelect.innerHTML = '';
                const empty = document.createElement('option');
                empty.value = '';
                empty.innerText = '— use best —';
                modelSelect.appendChild(empty);
                (mdata.versions || []).forEach(v => {
                    const opt = document.createElement('option');
                    opt.value = v.path || '';
                    opt.innerText = v.name || (v.path ? v.path.split('/').slice(-3).join('/') : 'unknown');
                    if (v.is_active) opt.textContent += ' (active)';
                    modelSelect.appendChild(opt);
                });
            }
        } catch (e) {
            console.warn('refreshLists', e);
        }
    }

    btn.addEventListener('click', async () => {
        const name = imageSelect ? imageSelect.value : null;
        if (!name) return alert('Select an image to test');
        const modelPath = modelSelect ? modelSelect.value : '';
        const conf_thresh = parseFloat(confInput?.value) || 0.1;
        const imgsz = parseInt(imgszInput?.value, 10) || 640;
        terminal.innerText += `\n[TEST] ${name} model=${modelPath || 'best'} conf=${conf_thresh} imgsz=${imgsz}`;
        try {
            window.showLoader?.('Running detection…');
            const imgRes = await fetch(`/api/raw/${encodeURIComponent(name)}`);
            if (!imgRes.ok) {
                terminal.innerText += '\n[TEST] failed to fetch raw image';
                return;
            }
            const j = await imgRes.json();
            if (!j.img_b64) {
                terminal.innerText += '\n[TEST] raw endpoint returned no image';
                return;
            }
            const byteChars = atob(j.img_b64);
            const byteArray = Uint8Array.from(byteChars, c => c.charCodeAt(0));
            const blob = new Blob([byteArray], { type: 'image/jpeg' });
            const fd = new FormData();
            fd.append('file', blob, name);
            if (modelPath) fd.append('model_path', modelPath);
            fd.append('conf_thresh', String(conf_thresh));
            fd.append('imgsz', String(imgsz));
            const detRes = await fetch('/api/detect', { method: 'POST', body: fd });
            const json = await detRes.json();
            if (detRes.ok) {
                terminal.innerText += `\n[TEST] source=${json.source} quality=${json.model_quality} counts=${JSON.stringify(json.counts)}`;
                if (json.warning) terminal.innerText += `\n[TEST] ${json.warning}`;
                if (json.result_b64) {
                    const img = document.getElementById('marked-image-view');
                    img.src = 'data:image/jpeg;base64,' + json.result_b64;
                    img.style.display = 'block';
                    document.getElementById('preview-placeholder').style.display = 'none';
                }
            } else {
                terminal.innerText += `\n[TEST] Error: ${JSON.stringify(json)}`;
            }
        } catch (e) {
            terminal.innerText += `\n[TEST] Exception: ${e}`;
        } finally {
            window.hideLoader?.();
        }
    });

    refreshBtn?.addEventListener('click', refreshLists);
    refreshLists();
    window.refreshTestLists = refreshLists;
}
