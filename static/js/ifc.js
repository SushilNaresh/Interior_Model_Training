/** IFC property editor with dynamic pset dropdowns */
export function initIfc() {
    const imageSelect = document.getElementById('ifc-image-select');
    const elementSelect = document.getElementById('ifc-element-select');
    const classSelect = document.getElementById('ifc-class-select');
    const subtypeSelect = document.getElementById('ifc-subtype-select');
    const materialSelect = document.getElementById('ifc-material-select');
    const idxInput = document.getElementById('ifc-idx-input');
    const formEl = document.getElementById('ifc-pset-form');
    const saveBtn = document.getElementById('ifc-save-btn');
    const exportBtn = document.getElementById('ifc-export-btn');
    const refreshBtn = document.getElementById('ifc-refresh-btn');
    const savedList = document.getElementById('ifc-saved-list');
    const terminal = document.getElementById('log-terminal');

    let fullSchema = {};
    let materials = {};
    let currentSchema = null;
    let currentBasename = '';
    let currentCls = '';
    let currentIdx = 1;

    function basenameFromFilename(name) {
        return name.replace(/\.[^.]+$/, '');
    }

    async function loadSchemaRegistry() {
        const res = await fetch('/api/ifc/schema');
        if (!res.ok) return;
        const data = await res.json();
        fullSchema = data.schema || {};
        materials = data.materials || {};
        if (classSelect) {
            classSelect.innerHTML = '';
            Object.keys(fullSchema).filter(k => k[0] === k[0].toUpperCase()).forEach(cls => {
                const opt = document.createElement('option');
                opt.value = cls;
                opt.textContent = cls;
                classSelect.appendChild(opt);
            });
        }
        if (materialSelect) {
            materialSelect.innerHTML = '<option value="">— default —</option>';
            Object.keys(materials).forEach(m => {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = m;
                materialSelect.appendChild(opt);
            });
        }
    }

    async function refreshImages() {
        if (!imageSelect) return;
        const res = await fetch('/api/status');
        const data = await res.json();
        imageSelect.innerHTML = '<option value="">— select image —</option>';
        const seen = new Set();
        [...(data.labelled_images || []), ...(data.raw_images || [])].forEach(n => {
            const base = basenameFromFilename(n);
            if (seen.has(base)) return;
            seen.add(base);
            const opt = document.createElement('option');
            opt.value = base;
            opt.textContent = base;
            imageSelect.appendChild(opt);
        });
    }

    async function loadElements() {
        if (!elementSelect) return;
        elementSelect.innerHTML = '<option value="">— pick labelled element —</option>';
        currentBasename = imageSelect?.value || '';
        if (!currentBasename) return;
        const res = await fetch(`/api/label_details/${encodeURIComponent(currentBasename)}`);
        if (!res.ok) return;
        const data = await res.json();
        Object.entries(data.details || {}).forEach(([cls, items]) => {
            items.forEach(item => {
                const opt = document.createElement('option');
                opt.value = `${cls}|${item.idx}`;
                opt.textContent = `${cls} #${item.idx} (area ${item.area})`;
                elementSelect.appendChild(opt);
            });
        });
        await loadSavedProps();
    }

    async function loadSavedProps() {
        if (!savedList || !currentBasename) return;
        const res = await fetch(`/api/ifc/props/${encodeURIComponent(currentBasename)}`);
        const data = await res.json();
        const props = data.props || {};
        savedList.innerHTML = '';
        const keys = Object.keys(props);
        if (!keys.length) {
            savedList.innerHTML = '<p style="color:var(--muted);font-size:13px">No saved IFC props yet.</p>';
            return;
        }
        keys.forEach(key => {
            const p = props[key];
            const div = document.createElement('div');
            div.className = 'ifc-saved-row';
            div.innerHTML = `<span><strong>${p.cls_name}</strong> #${p.idx} · ${p.ifc_class || ''} · ${p.subtype || ''}</span>
                <button class="btn small ifc-load-btn" data-key="${key}">Edit</button>
                <button class="btn small ifc-del-btn" data-key="${key}">Delete</button>`;
            savedList.appendChild(div);
        });
        savedList.querySelectorAll('.ifc-load-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const p = props[btn.dataset.key];
                if (!p) return;
                if (classSelect) classSelect.value = p.cls_name;
                if (idxInput) idxInput.value = p.idx;
                if (subtypeSelect && p.subtype) subtypeSelect.value = p.subtype;
                if (materialSelect && p.material) materialSelect.value = p.material;
                loadClassForm(p.cls_name, p.psets || {});
            });
        });
        savedList.querySelectorAll('.ifc-del-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                await fetch(`/api/ifc/props/${encodeURIComponent(currentBasename)}/${encodeURIComponent(btn.dataset.key)}`, { method: 'DELETE' });
                loadSavedProps();
            });
        });
    }

    function fieldInput(propName, meta, value) {
        const wrap = document.createElement('div');
        wrap.className = 'form-group ifc-field';
        wrap.dataset.pset = meta._pset;
        wrap.dataset.prop = propName;
        const label = document.createElement('label');
        label.textContent = propName + (meta.unit ? ` (${meta.unit})` : '');
        wrap.appendChild(label);
        let input;
        const v = value !== undefined && value !== null ? value : (meta.default ?? '');
        if (meta.type === 'select' || (meta.type === 'text' && meta.options)) {
            input = document.createElement('select');
            (meta.options || []).forEach(o => {
                const opt = document.createElement('option');
                opt.value = o;
                opt.textContent = o;
                if (String(o) === String(v)) opt.selected = true;
                input.appendChild(opt);
            });
        } else if (meta.type === 'bool') {
            input = document.createElement('select');
            ['false', 'true'].forEach(o => {
                const opt = document.createElement('option');
                opt.value = o;
                opt.textContent = o;
                if (String(v) === o || (v === true && o === 'true') || (v === false && o === 'false')) opt.selected = true;
                input.appendChild(opt);
            });
        } else if (meta.type === 'color') {
            input = document.createElement('input');
            input.type = 'color';
            input.value = String(v).startsWith('#') ? v : '#888888';
        } else {
            input = document.createElement('input');
            input.type = meta.type === 'number' ? 'number' : 'text';
            input.value = v;
            if (meta.type === 'number') input.step = 'any';
        }
        input.className = 'ifc-prop-input';
        wrap.appendChild(input);
        return wrap;
    }

    async function loadClassForm(clsName, existingPsets = {}) {
        currentCls = clsName;
        currentIdx = parseInt(idxInput?.value, 10) || 1;
        const res = await fetch(`/api/ifc/schema/${encodeURIComponent(clsName)}`);
        if (!res.ok) {
            formEl.innerHTML = '<p style="color:var(--muted)">No schema for this class.</p>';
            return;
        }
        const data = await res.json();
        currentSchema = data.schema || {};
        formEl.innerHTML = '';
        if (subtypeSelect) {
            subtypeSelect.innerHTML = '<option value="">— none —</option>';
            (currentSchema.subtypes || []).forEach(s => {
                const opt = document.createElement('option');
                opt.value = s;
                opt.textContent = s;
                subtypeSelect.appendChild(opt);
            });
        }
        Object.entries(currentSchema.psets || {}).forEach(([psetName, props]) => {
            const fieldset = document.createElement('fieldset');
            fieldset.className = 'ifc-pset-block';
            const legend = document.createElement('legend');
            legend.textContent = psetName;
            fieldset.appendChild(legend);
            Object.entries(props).forEach(([propName, meta]) => {
                const m = { ...meta, _pset: psetName };
                const val = existingPsets[psetName]?.[propName];
                fieldset.appendChild(fieldInput(propName, m, val));
            });
            formEl.appendChild(fieldset);
        });
        if (!formEl.children.length) formEl.innerHTML = '<p style="color:var(--muted)">No property sets defined.</p>';
    }

    function collectPsets() {
        const psets = {};
        formEl.querySelectorAll('.ifc-field').forEach(wrap => {
            const pset = wrap.dataset.pset;
            const prop = wrap.dataset.prop;
            const input = wrap.querySelector('.ifc-prop-input');
            if (!input) return;
            psets[pset] = psets[pset] || {};
            let val = input.value;
            if (input.type === 'number') val = parseFloat(val) || 0;
            if (input.tagName === 'SELECT' && (val === 'true' || val === 'false')) val = val === 'true';
            psets[pset][prop] = val;
        });
        return psets;
    }

    imageSelect?.addEventListener('change', () => { currentBasename = imageSelect.value; loadElements(); });
    elementSelect?.addEventListener('change', () => {
        const v = elementSelect.value;
        if (!v) return;
        const [cls, idx] = v.split('|');
        if (classSelect) classSelect.value = cls;
        if (idxInput) idxInput.value = idx;
        loadClassForm(cls, {});
    });
    classSelect?.addEventListener('change', () => loadClassForm(classSelect.value, {}));

    saveBtn?.addEventListener('click', async () => {
        if (!currentBasename) return alert('Select an image');
        const cls_name = classSelect?.value;
        if (!cls_name) return alert('Select a class');
        const body = {
            cls_name,
            idx: parseInt(idxInput?.value, 10) || 1,
            subtype: subtypeSelect?.value || '',
            material: materialSelect?.value || '',
            psets: collectPsets(),
        };
        terminal && (terminal.innerText += `\n[IFC] Saving ${cls_name} #${body.idx} for ${currentBasename}`);
        const res = await fetch(`/api/ifc/props/${encodeURIComponent(currentBasename)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const j = await res.json();
        terminal && (terminal.innerText += `\n[IFC] ${JSON.stringify(j)}`);
        loadSavedProps();
    });

    exportBtn?.addEventListener('click', async () => {
        if (!currentBasename) return alert('Select an image');
        const res = await fetch(`/api/ifc/export/${encodeURIComponent(currentBasename)}`);
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `${currentBasename}_ifc_props.json`;
        a.click();
    });

    refreshBtn?.addEventListener('click', async () => { await refreshImages(); await loadElements(); });
    loadSchemaRegistry().then(refreshImages);
}
