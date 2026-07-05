import { pzSetImage, pzSetPlaceholder, pzFit, pzReset, pzZoom, pzInitDrag, pzGet } from './panzoom.js';
import { CLASS_COLORS, DRAW_CLASS_SELECT_HTML, initDrawClassSelect, populateClassDropdowns } from './draw-classes.js';

let _correctData = {};
let _correctView = 'marked';
let _correctBasename = '';
let _pendingChanges = false;
let _labelDetails = {};
let _activeEdit = null;
let _drawMode = false;
let _drawStart = null;
let _drawRect = null;
let _resizeDrag = null;
let _yoloClasses = [];
let _ifcSchema = null;
let _ifcMaterials = null;
let _ifcCurrentKey = null;
let _ftMode = 'incremental';
let _ftScope = 'all';
let _ftAllFiles = [];
let _ftCorrectedFiles = [];

function dashLog(msg) {
  const t = document.getElementById('log-terminal');
  if (t) { t.innerText += '\n' + msg; t.scrollTop = t.scrollHeight; }
}

function appendCorrectLog(text) {
  dashLog('[CORRECT] ' + text);
}

async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    return await res.json();
  } catch { return null; }
}

async function refreshCorrectList() {
  const status = await fetchStatus();
  const sel = document.getElementById('correct-select');
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = '<option value="">— Select image —</option>';
  (status?.labelled_images || []).forEach((name) => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    if (name === current) opt.selected = true;
    sel.appendChild(opt);
  });
}

function setCorrectView(view) {
  _correctView = view;
  ['cvMarked', 'cvPre', 'cvPost'].forEach((id) => document.getElementById(id)?.classList.remove('active'));
  const map = { marked: 'cvMarked', pre: 'cvPre', post: 'cvPost' };
  document.getElementById(map[view])?.classList.add('active');
  renderCorrectImage();
}

function renderCorrectImage() {
  const d = _correctData;
  if (!d || !d.marked_b64) return;
  let b64 = d.marked_b64;
  if (_correctView === 'pre' && d.pre_label_b64) b64 = d.pre_label_b64;
  if (_correctView === 'post' && d.post_label_b64) b64 = d.post_label_b64;
  pzSetImage('correctViewer', `data:image/jpeg;base64,${b64}`, _correctBasename + ' [' + _correctView + ']', () => {
    setTimeout(() => {
      if (_activeEdit) showEditOverlay(_activeEdit.cls, _activeEdit.idx, _activeEdit.bbox);
    }, 200);
  });
}

function updateSaveIndicator() {
  const btn = document.getElementById('correct-save-btn');
  if (!btn) return;
  if (_pendingChanges) {
    btn.style.background = '#fb923c';
    btn.textContent = '💾 Save *';
  } else {
    btn.style.background = '';
    btn.textContent = '💾 Save';
  }
}

async function loadCorrectImage() {
  const basename = document.getElementById('correct-select')?.value;
  if (!basename) return;
  if (_pendingChanges && _correctBasename && _correctBasename !== basename) {
    if (!confirm(`You have unsaved changes on "${_correctBasename}". Discard and switch?`)) {
      document.getElementById('correct-select').value = _correctBasename;
      return;
    }
  }
  _correctBasename = basename;
  _pendingChanges = false;
  _activeEdit = null;
  hideEditOverlay();
  updateSaveIndicator();
  try {
    const res = await fetch('/api/image/' + encodeURIComponent(basename));
    const data = await res.json();
    _correctData = data;
    renderCorrectImage();
    await renderLabelList(basename, data.labels || {});
    const total = data.n_labels || Object.values(data.labels || {}).reduce((a, b) => a + b, 0);
    const summary = document.getElementById('correctSummary');
    if (summary) summary.textContent = `${total} labels`;
    const ta = data.text_analysis || {};
    const bar = document.getElementById('ocrSummaryBar');
    const badge = document.getElementById('ocrCorrectionBadge');
    const summaryText = typeof ta.summary === 'string' ? ta.summary : (ta.summary ? JSON.stringify(ta.summary) : '');
    if (bar) { bar.style.display = summaryText ? 'block' : 'none'; bar.textContent = summaryText; }
    if (badge) badge.style.display = ta.was_corrected ? 'inline' : 'none';
    document.getElementById('correctStatusBar').textContent = `Loaded ${basename}`;
  } catch (e) {
    pzSetPlaceholder('correctViewer', 'Error loading');
    appendCorrectLog('Load error: ' + e.message);
  }
}

async function renderLabelList(basename, labels) {
  const el = document.getElementById('label-list');
  if (!el) return;
  const filter = document.getElementById('filterClass')?.value || '';
  if (!Object.keys(labels).length) {
    el.innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted)">No labels</div>';
    _labelDetails = {};
    return;
  }
  try {
    const res = await fetch('/api/label_details/' + encodeURIComponent(basename));
    const data = await res.json();
    _labelDetails = data.details || {};
  } catch { _labelDetails = {}; }

  let html = '';
  for (const [cls, count] of Object.entries(labels)) {
    if (filter && cls !== filter) continue;
    const color = CLASS_COLORS[cls] || '#888';
    const details = _labelDetails[cls] || [];
    for (let i = 1; i <= count; i++) {
      const det = details.find((d) => d.idx === i);
      const bboxStr = det ? `${det.bbox[2]}×${det.bbox[3]}px` : '';
      const isActive = _activeEdit && _activeEdit.cls === cls && _activeEdit.idx === i;
      html += `<div class="label-item ${isActive ? 'active-edit' : ''}" id="li_${cls}_${i}" data-cls="${cls}">
        <label style="display:flex;align-items:center;gap:6px;flex:1;cursor:pointer" onclick="window.__correctSelectLabel('${cls}',${i})">
          <input type="checkbox" class="label-row" data-class="${cls}" data-idx="${i}" onclick="event.stopPropagation()">
          <span class="color-dot" style="background:${color}"></span>
          <strong>${cls}</strong> #${i}
          ${bboxStr ? `<span style="font-size:10px;color:var(--muted)">${bboxStr}</span>` : ''}
        </label>
        <div class="actions">
          <select id="relabel_${cls}_${i}" style="width:130px;font-size:11px">
            ${DRAW_CLASS_SELECT_HTML}
          </select>
          <button class="btn small" data-action="relabel" data-cls="${cls}" data-idx="${i}">↩</button>
          <button class="btn small" data-action="ifc" data-cls="${cls}" data-idx="${i}">IFC</button>
          <button class="btn small" data-action="remove" data-cls="${cls}" data-idx="${i}">✕</button>
        </div>
      </div>`;
    }
  }
  el.innerHTML = html || '<div style="padding:20px;text-align:center;color:var(--muted)">No labels match filter</div>';
}

window.__correctSelectLabel = (cls, idx) => selectLabelForEdit(cls, idx);

function filterLabels() {
  renderLabelList(_correctBasename, _correctData.labels || {});
}

function hideEditOverlay() {
  const ov = document.getElementById('editOverlay');
  if (ov) ov.style.display = 'none';
  document.getElementById('editHandles').innerHTML = '';
}

function showEditOverlay(cls, idx, bbox) {
  const wrap = document.getElementById('correctViewer');
  const inner = document.getElementById('correctViewerInner');
  const ov = document.getElementById('editOverlay');
  const canvas = document.getElementById('editBboxCanvas');
  const handles = document.getElementById('editHandles');
  if (!wrap || !inner || !ov || !canvas) return;
  const img = inner.querySelector('img');
  if (!img) return;
  ov.style.display = 'block';
  const s = pzGet('correctViewer');
  const ww = wrap.clientWidth;
  const wh = wrap.clientHeight;
  canvas.width = ww;
  canvas.height = wh;
  const color = CLASS_COLORS[cls] || '#6c8cff';
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, ww, wh);
  const [bx, by, bw, bh] = bbox;
  const cx1 = s.tx + bx * s.scale;
  const cy1 = s.ty + by * s.scale;
  const cw = bw * s.scale;
  const ch = bh * s.scale;
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 3]);
  ctx.strokeRect(cx1, cy1, cw, ch);
  ctx.setLineDash([]);
  ctx.fillStyle = color;
  ctx.font = 'bold 13px sans-serif';
  ctx.fillText(`${cls} #${idx}  (${bw}×${bh}px)`, cx1 + 4, Math.max(14, cy1 - 6));
  handles.innerHTML = '';
  const corners = [
    { name: 'nw', fx: 0, fy: 0 }, { name: 'n', fx: 0.5, fy: 0 }, { name: 'ne', fx: 1, fy: 0 },
    { name: 'w', fx: 0, fy: 0.5 }, { name: 'e', fx: 1, fy: 0.5 },
    { name: 'sw', fx: 0, fy: 1 }, { name: 's', fx: 0.5, fy: 1 }, { name: 'se', fx: 1, fy: 1 },
  ];
  const cursorMap = { nw: 'nw-resize', n: 'n-resize', ne: 'ne-resize', w: 'w-resize', e: 'e-resize', sw: 'sw-resize', s: 's-resize', se: 'se-resize' };
  corners.forEach(({ name, fx, fy }) => {
    const h = document.createElement('div');
    h.className = 'resize-handle';
    h.style.left = (cx1 + fx * cw) + 'px';
    h.style.top = (cy1 + fy * ch) + 'px';
    h.style.cursor = cursorMap[name] || 'move';
    h.dataset.handle = name;
    h.addEventListener('mousedown', (e) => startResize(e, name, bbox, s, img.naturalWidth || img.width, img.naturalHeight || img.height));
    handles.appendChild(h);
  });
}

async function selectLabelForEdit(cls, idx) {
  if (_activeEdit && _activeEdit.cls === cls && _activeEdit.idx === idx) {
    _activeEdit = null;
    hideEditOverlay();
    document.querySelectorAll('.label-item').forEach((el) => el.classList.remove('active-edit'));
    return;
  }
  document.querySelectorAll('.label-item').forEach((el) => el.classList.remove('active-edit'));
  document.getElementById(`li_${cls}_${idx}`)?.classList.add('active-edit');
  const details = _labelDetails[cls] || [];
  const det = details.find((d) => d.idx === idx);
  if (!det) { hideEditOverlay(); return; }
  _activeEdit = { cls, idx, bbox: [...det.bbox] };
  showEditOverlay(cls, idx, det.bbox);
}

function startResize(e, handle, origBbox, s, imgW, imgH) {
  e.preventDefault();
  e.stopPropagation();
  _resizeDrag = { handle, origBbox: [...origBbox], s, imgW, imgH, startX: e.clientX, startY: e.clientY, curBbox: [...origBbox] };
  document.getElementById('correctStatusBar').textContent = `Dragging ${handle} handle — release to apply`;
}

function doResizeDrag(cx, cy) {
  const d = _resizeDrag;
  if (!d) return;
  const dx = (cx - d.startX) / d.s.scale;
  const dy = (cy - d.startY) / d.s.scale;
  let [x, y, w, h] = d.origBbox;
  if (d.handle.includes('w')) { x += dx; w -= dx; }
  if (d.handle.includes('e')) { w += dx; }
  if (d.handle.includes('n')) { y += dy; h -= dy; }
  if (d.handle.includes('s')) { h += dy; }
  x = Math.max(0, Math.round(x));
  y = Math.max(0, Math.round(y));
  w = Math.max(8, Math.min(Math.round(w), d.imgW - x));
  h = Math.max(8, Math.min(Math.round(h), d.imgH - y));
  d.curBbox = [x, y, w, h];
  if (_activeEdit) showEditOverlay(_activeEdit.cls, _activeEdit.idx, [x, y, w, h]);
}

async function applyResize() {
  const d = _resizeDrag;
  _resizeDrag = null;
  if (!d || !_activeEdit) return;
  const [x, y, w, h] = d.curBbox;
  if (!confirm(`Resize ${_activeEdit.cls} #${_activeEdit.idx} to [${x},${y},${w}×${h}]?`)) {
    showEditOverlay(_activeEdit.cls, _activeEdit.idx, _activeEdit.bbox);
    return;
  }
  try {
    const res = await fetch('/api/resize_label', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ basename: _correctBasename, cls_name: _activeEdit.cls, idx: _activeEdit.idx, bbox: [x, y, w, h] }),
    });
    const data = await res.json();
    if (data.ok) {
      _activeEdit.bbox = [x, y, w, h];
      if (data.marked_b64) { _correctData.marked_b64 = data.marked_b64; renderCorrectImage(); }
      if (data.labels) _correctData.labels = data.labels;
      await renderLabelList(_correctBasename, data.labels || _correctData.labels || {});
      document.getElementById('correctStatusBar').textContent = `✓ ${data.msg || 'Resized'}`;
    }
  } catch (e) { appendCorrectLog('ERROR: ' + e.message); }
}

async function correctLabel(basename, action, clsName, idx) {
  const body = { basename, action, cls_name: clsName, idx };
  if (action === 'relabel') {
    const sel = document.getElementById(`relabel_${clsName}_${idx}`);
    body.new_cls = sel ? sel.value : clsName;
    if (body.new_cls === clsName) return;
    if (!confirm(`Relabel ${clsName} #${idx} → ${body.new_cls}?`)) return;
  }
  try {
    const res = await fetch('/api/correct', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await res.json();
    if (data.ok) {
      _correctData.labels = data.labels || {};
      if (data.marked_b64) _correctData.marked_b64 = data.marked_b64;
      _pendingChanges = true;
      updateSaveIndicator();
      _activeEdit = null;
      hideEditOverlay();
      renderCorrectImage();
      await renderLabelList(basename, _correctData.labels);
      const total = Object.values(_correctData.labels).reduce((a, b) => a + b, 0);
      const summary = document.getElementById('correctSummary');
      if (summary) summary.textContent = `${total} labels`;
      document.getElementById('correctStatusBar').textContent = `✓ ${data.msg || action}`;
    } else appendCorrectLog('ERROR: ' + (data.error || 'Unknown'));
  } catch (e) { appendCorrectLog('ERROR: ' + e.message); }
}

function toggleDrawMode() {
  _drawMode = !_drawMode;
  const btn = document.getElementById('btnDrawMode');
  const canvas = document.getElementById('correctDrawCanvas');
  const status = document.getElementById('drawStatus');
  const cancel = document.getElementById('btnCancelDraw');
  const wrap = document.getElementById('correctViewer');
  if (_drawMode) {
    btn?.classList.add('draw-on');
    if (btn) btn.textContent = '🖊 Drawing...';
    canvas?.classList.add('draw-active');
    wrap?.classList.add('draw-mode');
    if (status) { status.textContent = 'Drag a rectangle on the image'; status.style.color = '#fb923c'; }
    if (cancel) cancel.style.display = 'inline';
    initDrawCanvas();
  } else exitDrawMode();
}

function exitDrawMode() {
  _drawMode = false;
  const btn = document.getElementById('btnDrawMode');
  const canvas = document.getElementById('correctDrawCanvas');
  const status = document.getElementById('drawStatus');
  const cancel = document.getElementById('btnCancelDraw');
  const wrap = document.getElementById('correctViewer');
  btn?.classList.remove('draw-on');
  if (btn) btn.textContent = '🖊 Draw Region';
  canvas?.classList.remove('draw-active');
  wrap?.classList.remove('draw-mode');
  if (status) { status.textContent = 'Select class and click Draw Region'; status.style.color = ''; }
  if (cancel) cancel.style.display = 'none';
  clearDrawCanvas();
  _drawStart = null;
  _drawRect = null;
}

function clearDrawCanvas() {
  const c = document.getElementById('correctDrawCanvas');
  if (!c) return;
  c.getContext('2d').clearRect(0, 0, c.width, c.height);
}

function initDrawCanvas() {
  const wrap = document.getElementById('correctViewer');
  if (!wrap || wrap._drawInited) return;
  wrap._drawInited = true;
  const getWrapPos = (e) => {
    const rect = wrap.getBoundingClientRect();
    const src = e.touches ? e.touches[0] : e;
    return { x: src.clientX - rect.left, y: src.clientY - rect.top };
  };
  wrap.addEventListener('mousedown', (e) => {
    if (!_drawMode || e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    _drawStart = getWrapPos(e);
    _drawRect = null;
  });
  window.addEventListener('mousemove', (e) => {
    if (!_drawMode || !_drawStart) return;
    const pos = getWrapPos(e);
    _drawRect = { x: Math.min(_drawStart.x, pos.x), y: Math.min(_drawStart.y, pos.y), w: Math.abs(pos.x - _drawStart.x), h: Math.abs(pos.y - _drawStart.y) };
    renderDrawRect();
  });
  window.addEventListener('mouseup', () => {
    if (!_drawMode || !_drawStart || !_drawRect) return;
    if (_drawRect.w < 8 || _drawRect.h < 8) { _drawStart = null; _drawRect = null; return; }
    confirmDrawRect();
    _drawStart = null;
  });
}

function renderDrawRect() {
  const canvas = document.getElementById('correctDrawCanvas');
  const wrap = document.getElementById('correctViewer');
  if (!canvas || !wrap || !_drawRect) return;
  canvas.width = wrap.clientWidth;
  canvas.height = wrap.clientHeight;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const sel = document.getElementById('draw-class');
  const cls = sel?.value || 'Room';
  const sub = sel?.options[sel.selectedIndex]?.dataset?.subtype || '';
  const color = CLASS_COLORS[cls] || '#6c8cff';
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 3]);
  ctx.strokeRect(_drawRect.x, _drawRect.y, _drawRect.w, _drawRect.h);
  ctx.fillStyle = color + '22';
  ctx.fillRect(_drawRect.x, _drawRect.y, _drawRect.w, _drawRect.h);
  ctx.setLineDash([]);
  ctx.fillStyle = color;
  ctx.font = 'bold 13px sans-serif';
  ctx.fillText(sub ? `${cls} — ${sub}` : cls, _drawRect.x + 4, _drawRect.y + 16);
}

async function confirmDrawRect() {
  if (!_drawRect || !_correctBasename) return;
  const sel = document.getElementById('draw-class');
  const cls = sel?.value || 'Room';
  const subtype = sel?.options[sel.selectedIndex]?.dataset?.subtype || '';
  const s = pzGet('correctViewer');
  const img = document.querySelector('#correctViewerInner img');
  if (!img) { exitDrawMode(); return; }
  const imgW = img.naturalWidth || img.width;
  const imgH = img.naturalHeight || img.height;
  const bx = Math.max(0, Math.round((_drawRect.x - s.tx) / s.scale));
  const by = Math.max(0, Math.round((_drawRect.y - s.ty) / s.scale));
  const bw = Math.min(imgW - bx, Math.round(_drawRect.w / s.scale));
  const bh = Math.min(imgH - by, Math.round(_drawRect.h / s.scale));
  if (bw < 4 || bh < 4) { exitDrawMode(); return; }
  const displayName = subtype ? `${cls} — ${subtype}` : cls;
  if (!confirm(`Add ${displayName} at [${bx},${by},${bw}×${bh}]?`)) { clearDrawCanvas(); _drawRect = null; return; }
  try {
    const res = await fetch('/api/section', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ basename: _correctBasename, label: cls, subtype, bbox: [bx, by, bw, bh] }),
    });
    const data = await res.json();
    if (data.ok) {
      if (data.marked_b64) _correctData.marked_b64 = data.marked_b64;
      if (data.labels) _correctData.labels = data.labels;
      renderCorrectImage();
      await renderLabelList(_correctBasename, data.labels || {});
      document.getElementById('correctStatusBar').textContent = `✓ Added ${displayName}`;
    } else appendCorrectLog('ERROR: ' + (data.error || 'Unknown'));
  } catch (e) { appendCorrectLog('ERROR: ' + e.message); }
  clearDrawCanvas();
  _drawRect = null;
}

async function loadIfcSchema() {
  if (_ifcSchema) return;
  try {
    const d = await fetch('/api/ifc/schema').then((r) => r.json());
    _ifcSchema = d.schema;
    _ifcMaterials = d.materials;
  } catch { _ifcSchema = {}; _ifcMaterials = {}; }
}

async function openIfcPanel(cls, idx) {
  await loadIfcSchema();
  const schema = (_ifcSchema || {})[cls];
  if (!schema) { appendCorrectLog('No IFC schema for ' + cls); return; }
  _ifcCurrentKey = cls + '_' + idx;
  document.getElementById('ifcClassName').textContent = schema.ifc_class + ' #' + idx;
  let existing = {};
  try {
    const d = await fetch('/api/ifc/props/' + encodeURIComponent(_correctBasename)).then((r) => r.json());
    existing = (d.props || {})[_ifcCurrentKey] || {};
  } catch (_) {}
  renderIfcPanel(cls, schema, existing);
  document.getElementById('ifcPropsPanel')?.classList.add('open');
  document.querySelector('.correct-layout')?.classList.add('ifc-open');
}

function closeIfcPanel() {
  document.getElementById('ifcPropsPanel')?.classList.remove('open');
  document.querySelector('.correct-layout')?.classList.remove('ifc-open');
  _ifcCurrentKey = null;
}

function renderIfcPanel(cls, schema, existing) {
  const psets = schema.psets || {};
  const subtypes = schema.subtypes || [];
  const existPsets = existing.psets || {};
  let h = `<div style="margin-bottom:8px"><label class="ifc-prop-label">Subtype</label>
    <select id="ifcSubtype" class="ifc-prop-input">${subtypes.map((s) => `<option${existing.subtype === s ? ' selected' : ''}>${s}</option>`).join('')}</select></div>`;
  const mats = Object.keys(_ifcMaterials || {});
  h += `<div style="display:grid;grid-template-columns:1fr 80px;gap:6px;margin-bottom:8px">
    <div><label class="ifc-prop-label">Material</label><select id="ifcMaterial" class="ifc-prop-input"><option value="">none</option>
    ${mats.map((m) => `<option value="${m}"${existing.material === m ? ' selected' : ''}>${m}</option>`).join('')}</select></div>
    <div><label class="ifc-prop-label">Color</label><input type="color" id="ifcColor" class="ifc-prop-input" style="height:26px" value="${existing.color || '#888888'}"></div></div>`;
  h += `<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin-bottom:8px">`;
  ['Width', 'Depth', 'Height'].forEach((d) => {
    h += `<div><label class="ifc-prop-label">${d}(m)</label><input type="number" id="ifcDim${d}" class="ifc-prop-input" step="0.01" value="${(existing.dimensions || {})[d] || ''}"></div>`;
  });
  h += '</div>';
  for (const [psetName, props] of Object.entries(psets)) {
    h += `<div class="ifc-pset-title">${psetName}</div>`;
    const ep = existPsets[psetName] || {};
    for (const [propName, meta] of Object.entries(props)) {
      const val = ep[propName] !== undefined ? ep[propName] : (meta.default !== undefined ? meta.default : '');
      const uid = 'ifcP_' + psetName.replace(/\W/g, '_') + '_' + propName.replace(/\W/g, '_');
      h += `<div class="ifc-prop-row"><span class="ifc-prop-label">${propName}</span>`;
      if (meta.options?.length) {
        h += `<select id="${uid}" class="ifc-prop-input"><option value="">-</option>${meta.options.map((o) => `<option${val === o ? ' selected' : ''}>${o}</option>`).join('')}</select>`;
      } else if (meta.type === 'bool') {
        h += `<select id="${uid}" class="ifc-prop-input"><option value="">-</option><option value="true"${val === true || val === 'true' ? ' selected' : ''}>Yes</option><option value="false"${val === false || val === 'false' ? ' selected' : ''}>No</option></select>`;
      } else {
        h += `<input type="${meta.type === 'number' ? 'number' : 'text'}" id="${uid}" class="ifc-prop-input" value="${val}">`;
      }
      h += '</div>';
    }
  }
  document.getElementById('ifcPanelContent').innerHTML = h;
}

async function saveIfcProps() {
  if (!_ifcCurrentKey || !_correctBasename) return;
  const parts = _ifcCurrentKey.split('_');
  const idx = parseInt(parts.pop());
  const cls = parts.join('_');
  const schema = (_ifcSchema || {})[cls] || {};
  const psetData = {};
  for (const [psetName, props] of Object.entries(schema.psets || {})) {
    psetData[psetName] = {};
    for (const propName of Object.keys(props)) {
      const uid = 'ifcP_' + psetName.replace(/\W/g, '_') + '_' + propName.replace(/\W/g, '_');
      const el = document.getElementById(uid);
      if (el && el.value && el.value !== '-') psetData[psetName][propName] = el.value;
    }
  }
  const body = {
    cls_name: cls, idx,
    subtype: document.getElementById('ifcSubtype')?.value || '',
    material: document.getElementById('ifcMaterial')?.value || '',
    color: document.getElementById('ifcColor')?.value || '',
    dimensions: {
      Width: parseFloat(document.getElementById('ifcDimWidth')?.value) || null,
      Depth: parseFloat(document.getElementById('ifcDimDepth')?.value) || null,
      Height: parseFloat(document.getElementById('ifcDimHeight')?.value) || null,
    },
    psets: psetData,
  };
  try {
    const d = await fetch('/api/ifc/props/' + encodeURIComponent(_correctBasename), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then((r) => r.json());
    if (d.ok) document.getElementById('correctStatusBar').textContent = 'IFC props saved: ' + cls + ' #' + idx;
  } catch (e) { appendCorrectLog('ERROR: ' + e.message); }
}

async function exportIfcProps() {
  if (!_correctBasename) return;
  try {
    const d = await fetch('/api/ifc/export/' + encodeURIComponent(_correctBasename)).then((r) => r.json());
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' }));
    a.download = _correctBasename + '_ifc.json';
    a.click();
  } catch (e) { appendCorrectLog('ERROR: ' + e.message); }
}

function setFtMode(mode) {
  _ftMode = mode;
  ['ftModeIncremental', 'ftModeScratch', 'ftModeMerge'].forEach((id) => document.getElementById(id)?.classList.remove('active'));
  document.getElementById('ftMode' + mode.charAt(0).toUpperCase() + mode.slice(1))?.classList.add('active');
  document.getElementById('ftParamsPanel').style.display = mode === 'merge' ? 'none' : 'block';
  document.getElementById('ftMergePanel').style.display = mode === 'merge' ? 'block' : 'none';
  document.getElementById('ftScopePanel').style.display = mode === 'merge' ? 'none' : 'block';
  const btn = document.getElementById('btnStartFinetune');
  if (btn) btn.textContent = mode === 'merge' ? '🔀 Merge Models' : mode === 'scratch' ? '🆕 Train from Scratch' : '▶ Start Fine-tune';
  const base = document.getElementById('ftBaseModel');
  if (base) base.disabled = mode === 'scratch';
}

function setFtScope(scope) {
  _ftScope = scope;
  ['ftScopeAll', 'ftScopeCorrected', 'ftScopeCustom'].forEach((id) => document.getElementById(id)?.classList.remove('active'));
  document.getElementById('ftScope' + scope.charAt(0).toUpperCase() + scope.slice(1))?.classList.add('active');
  const listEl = document.getElementById('ftFileList');
  const hintEl = document.getElementById('ftScopeHint');
  if (scope === 'all') {
    listEl.style.display = 'none';
    hintEl.textContent = 'All labelled images will be used (' + _ftAllFiles.length + ' total).';
  } else {
    listEl.style.display = 'block';
    const pre = scope === 'corrected' ? _ftCorrectedFiles : _ftAllFiles;
    hintEl.textContent = scope === 'corrected' ? `${_ftCorrectedFiles.length} corrected this session` : 'Check images to include';
    renderFileCheckboxes(_ftAllFiles, scope === 'corrected' ? _ftCorrectedFiles : []);
  }
}

function renderFileCheckboxes(files, preChecked) {
  const el = document.getElementById('ftFileCheckboxes');
  const checked = new Set(preChecked);
  el.innerHTML = files.map((f) =>
    `<label style="display:flex;align-items:center;gap:6px;padding:3px;font-size:12px;cursor:pointer">
      <input type="checkbox" value="${f}" ${checked.has(f) ? 'checked' : ''}><span>${f}</span></label>`
  ).join('');
}

function getSelectedFtFiles() {
  if (_ftScope === 'all') return [];
  return Array.from(document.querySelectorAll('#ftFileCheckboxes input:checked')).map((b) => b.value);
}

async function openUpdateModelPanel() {
  _ftMode = 'incremental';
  _ftScope = 'all';
  setFtMode('incremental');
  document.getElementById('updateModelPanel')?.classList.add('open');
  const info = document.getElementById('updateModelInfo');
  if (info) info.textContent = 'Loading...';
  try {
    const [statusRes, versionsRes, correctedRes] = await Promise.all([
      fetchStatus(),
      fetch('/api/model_versions').then((r) => r.json()),
      fetch('/api/corrected_files').then((r) => r.json()),
    ]);
    _ftAllFiles = correctedRes.all || statusRes?.labelled_images || [];
    _ftCorrectedFiles = correctedRes.corrected || [];
    if (info) {
      info.innerHTML = `Labelled: <strong>${(statusRes?.labelled_images || []).length}</strong> · Corrected: <strong>${_ftCorrectedFiles.length}</strong> · Versions: <strong>${(versionsRes.versions || []).length}</strong>`;
    }
    setFtScope(_ftCorrectedFiles.length ? 'corrected' : 'all');
    ['ftBaseModel', 'ftMergeA', 'ftMergeB'].forEach((id, i) => {
      const sel = document.getElementById(id);
      if (!sel) return;
      sel.innerHTML = '<option value="">— select —</option>';
      (versionsRes.versions || []).forEach((v) => {
        const opt = document.createElement('option');
        opt.value = v.path;
        opt.textContent = (v.name || v.path).split('/').slice(-3).join('/') + (v.is_active ? ' ★' : '');
        if (v.is_active && i === 0) opt.selected = true;
        sel.appendChild(opt);
      });
    });
  } catch (e) {
    if (info) info.textContent = 'Could not load: ' + e.message;
  }
}

function closeUpdateModelPanel() {
  document.getElementById('updateModelPanel')?.classList.remove('open');
}

async function startFinetune() {
  const btn = document.getElementById('btnStartFinetune');
  const status = document.getElementById('finetuneStatus');
  if (btn) btn.disabled = true;
  if (status) { status.style.display = 'block'; status.textContent = '⏳ Starting...'; }
  try {
    let res, data;
    if (_ftMode === 'merge') {
      const modelA = document.getElementById('ftMergeA').value;
      const modelB = document.getElementById('ftMergeB').value;
      const alpha = parseInt(document.getElementById('ftAlpha').value) / 100;
      res = await fetch('/api/merge_models', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model_a: modelA, model_b: modelB, alpha }) });
      data = await res.json();
    } else {
      const trainFiles = getSelectedFtFiles();
      if (_ftScope !== 'all' && !trainFiles.length) {
        status.textContent = '❌ No images selected';
        if (btn) btn.disabled = false;
        return;
      }
      res = await fetch('/api/train_from_corrections', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          epochs: parseInt(document.getElementById('ftEpochs').value) || 5,
          batch: parseInt(document.getElementById('ftBatch').value) || 2,
          imgsz: parseInt(document.getElementById('ftImgsz').value) || 640,
          mode: _ftMode,
          base_model: _ftMode === 'scratch' ? '' : document.getElementById('ftBaseModel').value,
          train_scope: _ftScope,
          train_files: trainFiles,
        }),
      });
      data = await res.json();
    }
    if (data.ok) {
      status.textContent = '✓ Started — check Training Log';
      setTimeout(closeUpdateModelPanel, 1200);
    } else status.textContent = '❌ ' + (data.error || 'Failed');
  } catch (e) {
    status.textContent = '❌ ' + e.message;
  }
  if (btn) btn.disabled = false;
}

export function initCorrect() {
  if (!document.getElementById('panel-correct')) return;
  initDrawClassSelect();
  fetch('/api/classes').then((r) => r.json()).then((j) => {
    _yoloClasses = j.yolo_classes || Object.keys(j.classes || {});
    populateClassDropdowns(['filterClass', 'bulkRelabelClass'], _yoloClasses);
  });

  pzInitDrag('correctViewer', { blockPan: () => _drawMode });

  document.getElementById('correct-refresh')?.addEventListener('click', refreshCorrectList);
  document.getElementById('correct-select')?.addEventListener('change', loadCorrectImage);
  document.getElementById('cvMarked')?.addEventListener('click', () => setCorrectView('marked'));
  document.getElementById('cvPre')?.addEventListener('click', () => setCorrectView('pre'));
  document.getElementById('cvPost')?.addEventListener('click', () => setCorrectView('post'));
  document.getElementById('btnDrawMode')?.addEventListener('click', toggleDrawMode);
  document.getElementById('btnCancelDraw')?.addEventListener('click', exitDrawMode);
  document.getElementById('filterClass')?.addEventListener('change', filterLabels);
  document.getElementById('correctPzIn')?.addEventListener('click', () => pzZoom('correctViewer', 1.25));
  document.getElementById('correctPzOut')?.addEventListener('click', () => pzZoom('correctViewer', 0.8));
  document.getElementById('correctPzFit')?.addEventListener('click', () => pzFit('correctViewer'));
  document.getElementById('correctPzReset')?.addEventListener('click', () => pzReset('correctViewer'));

  document.getElementById('correct-save-btn')?.addEventListener('click', async () => {
    if (!_correctBasename) return alert('Select image');
    const res = await fetch('/api/save_corrections', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ basename: _correctBasename }) });
    const j = await res.json();
    if (j.ok) { _pendingChanges = false; updateSaveIndicator(); document.getElementById('correctStatusBar').textContent = '✅ Saved'; }
  });

  document.getElementById('correct-revert-btn')?.addEventListener('click', async () => {
    if (!_correctBasename || !confirm('Revert all corrections?')) return;
    await fetch('/api/revert', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ basename: _correctBasename }) });
    loadCorrectImage();
  });

  document.getElementById('correct-update-model')?.addEventListener('click', openUpdateModelPanel);
  document.getElementById('label-select-all')?.addEventListener('click', () => document.querySelectorAll('#label-list .label-row').forEach((cb) => { cb.checked = true; }));
  document.getElementById('label-deselect')?.addEventListener('click', () => document.querySelectorAll('#label-list .label-row').forEach((cb) => { cb.checked = false; }));

  document.getElementById('label-remove-selected')?.addEventListener('click', async () => {
    const selected = Array.from(document.querySelectorAll('#label-list .label-row:checked'));
    if (!selected.length || !confirm(`Remove ${selected.length} label(s)?`)) return;
    // Collect all {cls, idx} before any DOM re-render
    const toRemove = selected.map(cb => ({ cls: cb.dataset.class, idx: parseInt(cb.dataset.idx) }));
    // Sort descending by idx within each class so earlier removals don't shift later indices
    toRemove.sort((a, b) => a.cls === b.cls ? b.idx - a.idx : 0);
    for (const { cls, idx } of toRemove) {
      await correctLabel(_correctBasename, 'remove', cls, idx);
    }
  });

  document.getElementById('btnBulkRelabel')?.addEventListener('click', async () => {
    const to = document.getElementById('bulkRelabelClass')?.value;
    if (!to) return alert('Select target class');
    const selected = Array.from(document.querySelectorAll('#label-list .label-row:checked'));
    if (!selected.length) return alert('Select labels');
    for (const cb of selected) {
      const sel = document.getElementById(`relabel_${cb.dataset.class}_${cb.dataset.idx}`);
      if (sel) sel.value = to;
      await correctLabel(_correctBasename, 'relabel', cb.dataset.class, parseInt(cb.dataset.idx));
    }
  });

  document.getElementById('label-list')?.addEventListener('click', async (ev) => {
    const btn = ev.target.closest('button[data-action]');
    if (!btn) return;
    const { action, cls, idx } = btn.dataset;
    if (action === 'remove') {
      if (!confirm(`Remove ${cls} #${idx}?`)) return;
      await correctLabel(_correctBasename, 'remove', cls, parseInt(idx));
    } else if (action === 'relabel') await correctLabel(_correctBasename, 'relabel', cls, parseInt(idx));
    else if (action === 'ifc') openIfcPanel(cls, parseInt(idx));
  });

  document.getElementById('ifcCloseBtn')?.addEventListener('click', closeIfcPanel);
  document.getElementById('ifcSaveBtn')?.addEventListener('click', saveIfcProps);
  document.getElementById('ifcExportBtn')?.addEventListener('click', exportIfcProps);
  document.getElementById('updateModelClose')?.addEventListener('click', closeUpdateModelPanel);
  document.getElementById('updateModelPanel')?.addEventListener('click', (e) => { if (e.target.id === 'updateModelPanel') closeUpdateModelPanel(); });
  document.getElementById('btnStartFinetune')?.addEventListener('click', startFinetune);
  ['ftModeIncremental', 'ftModeScratch', 'ftModeMerge'].forEach((id, i) => {
    document.getElementById(id)?.addEventListener('click', () => setFtMode(['incremental', 'scratch', 'merge'][i]));
  });
  ['ftScopeAll', 'ftScopeCorrected', 'ftScopeCustom'].forEach((id, i) => {
    document.getElementById(id)?.addEventListener('click', () => setFtScope(['all', 'corrected', 'custom'][i]));
  });

  window.addEventListener('mousemove', (e) => { if (_resizeDrag) doResizeDrag(e.clientX, e.clientY); });
  window.addEventListener('mouseup', () => { if (_resizeDrag) applyResize(); });

  window.refreshCorrectImages = refreshCorrectList;
  refreshCorrectList();
}
