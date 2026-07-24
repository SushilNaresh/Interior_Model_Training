/** Room Re-layout: upload photo → Gemini suggests furniture rearrangement */
export function initRearrange() {
    const el = (id) => document.getElementById(id);

    document.addEventListener('click', async (e) => {
        if (e.target.id !== 'rearrange-run-btn') return;

        const fileInput = el('rearrange-file');
        if (!fileInput?.files?.length) return alert('Please select a room photo first.');

        const style = el('rearrange-style')?.value?.trim() || '';
        const fd = new FormData();
        fd.append('file', fileInput.files[0]);
        fd.append('style', style);

        el('rearrange-result').innerHTML = '<em>Analysing room…</em>';
        el('rearrange-orig').style.display    = 'none';
        el('rearrange-overlay').style.display = 'none';
        window.showLoader?.('Analysing room layout…');

        try {
            const res  = await fetch('/api/rearrange', { method: 'POST', body: fd });
            const data = await res.json();
            if (data.error) { el('rearrange-result').textContent = '❌ ' + data.error; return; }

            // Show images
            if (data.orig_b64) {
                el('rearrange-orig').src     = 'data:image/jpeg;base64,' + data.orig_b64;
                el('rearrange-orig').style.display = 'block';
            }
            if (data.overlay_b64) {
                el('rearrange-overlay').src     = 'data:image/jpeg;base64,' + data.overlay_b64;
                el('rearrange-overlay').style.display = 'block';
            }

            // Render plan
            const p = data.plan || {};
            let html = '';

            if (p.expected_improvement)
                html += `<div class="rearrange-highlight">✨ ${p.expected_improvement}</div>`;

            if (p.current_issues?.length) {
                html += `<h4>Current Issues</h4><ul>${p.current_issues.map(i => `<li>${i}</li>`).join('')}</ul>`;
            }

            if (p.furniture_detected?.length) {
                html += `<h4>Furniture Moves</h4><table class="rearrange-table">
                    <tr><th>Item</th><th>Now</th><th>Move To</th><th>Why</th></tr>
                    ${p.furniture_detected.map(f => `
                        <tr>
                            <td><strong>${f.name || ''}</strong></td>
                            <td>${f.current_position || ''}</td>
                            <td class="rearrange-arrow">→ ${f.suggested_position || ''}</td>
                            <td>${f.reason || ''}</td>
                        </tr>`).join('')}
                </table>`;
            }

            if (p.layout_steps?.length) {
                html += `<h4>Step-by-Step</h4><ol>${p.layout_steps.map(s => `<li>${s}</li>`).join('')}</ol>`;
            }

            if (p.space_tips?.length) {
                html += `<h4>Space Tips</h4><ul>${p.space_tips.map(t => `<li>${t}</li>`).join('')}</ul>`;
            }

            el('rearrange-result').innerHTML = html || '<em>No plan returned.</em>';
        } catch (err) {
            el('rearrange-result').textContent = '❌ ' + err;
        } finally {
            window.hideLoader?.();
        }
    });
}
