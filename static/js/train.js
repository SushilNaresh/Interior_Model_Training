import { pzSetImage, pzSetPlaceholder, pzFit, pzReset, pzZoom, pzInitAll } from './panzoom.js';

let rawImages = [];
let labelledImages = [];
let viewMode = 'raw';
let viewImages = [];
let currentImgIdx = 0;
let uploadedFiles = {};
let folderPaths = { raw: '', labelled: '' };
let selectedRawFiles = new Set();
let _metadataSessionChoice = null;
let _metadataResolve = null;
let trainSseBound = false;

function dashLog(msg) {
  const t = document.getElementById('log-terminal');
  if (t) { t.innerText += '\n' + msg; t.scrollTop = t.scrollHeight; }
}

function appendTrainLog(text) {
  const el = document.getElementById('train-log-output');
  if (el) {
    const line = document.createElement('div');
    line.className = 'log-line';
    if (text.includes('✅') || text.includes('✓')) line.classList.add('success');
    else if (text.includes('ERROR') || text.includes('SKIP')) line.classList.add('error');
    else if (text.includes('Epoch') || text.includes('Device')) line.classList.add('info');
    line.textContent = text;
    el.appendChild(line);
    el.scrollTop = el.scrollHeight;
  }
  dashLog('[TRAIN] ' + text);
}

function updateTrainProgress(pct, status, metrics) {
  const fill = document.getElementById('train-progress-fill');
  if (fill && pct != null) fill.style.width = pct + '%';
  if (status) {
    const badge = document.getElementById('system-status');
    if (badge) badge.innerText = 'Engine Status: ' + status;
  }
  if (metrics && Object.keys(metrics).length) {
    const grid = document.getElementById('train-metrics-grid');
    if (grid) {
      grid.innerHTML = '';
      for (const [k, v] of Object.entries(metrics)) {
        grid.innerHTML += `<div class="metric-card"><div class="value">${v}</div><div class="label">${k}</div></div>`;
      }
    }
  }
}

async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    return await res.json();
  } catch { return null; }
}

function bindTrainSse() {
  if (trainSseBound) return;
  trainSseBound = true;
  const es = new EventSource('/api/stream');
  es.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data);
      if (d.log) appendTrainLog(d.log);
      if (d.progress) updateTrainProgress(d.progress.pct, d.progress.status, d.progress.metrics);
    } catch (_) {}
  };
}

function updateSelectionCount() {
  const n = selectedRawFiles.size;
  const el = document.getElementById('selCount');
  const btn = document.getElementById('btnTrainSelected');
  if (el) el.textContent = n > 0 ? `${n} selected` : 'None selected';
  if (btn) btn.disabled = n === 0;
}

function updateFolderPath() {
  const bar = document.getElementById('folderPathBar');
  if (!bar) return;
  if (viewMode === 'raw') {
    bar.textContent = folderPaths.raw || (rawImages.length ? `gdrive_dataset/images_raw/  (${rawImages.length} images)` : 'No raw images — download or upload first');
  } else {
    bar.textContent = folderPaths.labelled || (labelledImages.length ? `gdrive_dataset/marked/  (${labelledImages.length} labelled)` : 'No labelled images — run Auto-Label first');
  }
}

function renderThumbStrip() {
  const strip = document.getElementById('thumbStrip');
  if (!strip) return;
  if (!viewImages.length) {
    strip.innerHTML = '<div style="padding:20px;color:var(--muted);font-size:12px">No images yet</div>';
    return;
  }
  strip.innerHTML = '';
  viewImages.forEach((name, i) => {
    const div = document.createElement('div');
    div.className = 'thumb-item' + (i === currentImgIdx ? ' selected' : '');
    div.title = name;
    const isSelected = viewMode === 'raw' && selectedRawFiles.has(name);
    if (isSelected) div.classList.add('selected');
    div.onclick = () => {
      if (viewMode === 'raw') {
        if (selectedRawFiles.has(name)) selectedRawFiles.delete(name);
        else selectedRawFiles.add(name);
        updateSelectionCount();
      }
      currentImgIdx = i;
      renderThumbStrip();
      showCurrentImage();
    };
    const chk = viewMode === 'raw'
      ? `<div style="position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:3px;border:2px solid #fff;background:${isSelected ? 'var(--accent)' : 'rgba(0,0,0,0.4)'};display:flex;align-items:center;justify-content:center;font-size:9px;color:#fff">${isSelected ? '✓' : ''}</div>`
      : '';
    if (viewMode === 'raw' && uploadedFiles[name]) {
      div.innerHTML = `<img src="${uploadedFiles[name]}">${chk}<div class="thumb-label">${name}</div>`;
    } else if (viewMode === 'labelled') {
      div.innerHTML = `<img src="/api/thumb/${encodeURIComponent(name)}" onerror="this.style.display='none'">${chk}<div class="thumb-label">${name}</div>`;
    } else {
      div.innerHTML = `<img src="/api/raw_thumb/${encodeURIComponent(name)}" style="width:100%;height:100%;object-fit:cover" onerror="this.style.display='none'">${chk}<div class="thumb-label">${name}</div>`;
    }
    strip.appendChild(div);
  });
  const selected = strip.children[currentImgIdx];
  if (selected) selected.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
}

async function showCurrentImage() {
  if (!viewImages.length) {
    pzSetPlaceholder('trainViewer', 'No images to show');
    const c = document.getElementById('imgCounter');
    if (c) c.textContent = '0 / 0';
    const s = document.getElementById('imgStats');
    if (s) s.textContent = '';
    return;
  }
  const name = viewImages[currentImgIdx];
  const counter = document.getElementById('imgCounter');
  if (counter) counter.textContent = `${currentImgIdx + 1} / ${viewImages.length}`;

  if (viewMode === 'raw') {
    if (uploadedFiles[name]) {
      pzSetImage('trainViewer', uploadedFiles[name], name);
      document.getElementById('imgStats').textContent = name + '  (raw — preview)';
    } else {
      try {
        const res = await fetch('/api/raw/' + encodeURIComponent(name));
        const data = await res.json();
        if (data.img_b64) {
          pzSetImage('trainViewer', `data:image/jpeg;base64,${data.img_b64}`, name);
          document.getElementById('imgStats').textContent = name + '  (raw)';
        }
      } catch {
        pzSetPlaceholder('trainViewer', 'Cannot load: ' + name);
      }
    }
    return;
  }

  const basename = name;
  try {
    const res = await fetch('/api/image/' + encodeURIComponent(basename));
    const data = await res.json();
    if (data.marked_b64) {
      pzSetImage('trainViewer', `data:image/jpeg;base64,${data.marked_b64}`, basename);
    }
    if (data.labels) {
      const parts = Object.entries(data.labels).map(([k, v]) => `${k}: ${v}`).join('  ·  ');
      document.getElementById('imgStats').textContent = `${basename}  —  ${parts}  (${data.n_labels || 0} total)`;
    }
  } catch {
    pzSetPlaceholder('trainViewer', 'Error loading image');
  }
}

function setViewMode(mode) {
  viewMode = mode;
  document.getElementById('vmRaw')?.classList.toggle('active', mode === 'raw');
  document.getElementById('vmLabelled')?.classList.toggle('active', mode === 'labelled');
  viewImages = mode === 'labelled' ? labelledImages : rawImages;
  currentImgIdx = 0;
  const bar = document.getElementById('selectionBar');
  if (bar) bar.style.display = mode === 'raw' ? 'flex' : 'none';
  updateFolderPath();
  updateSelectionCount();
  if (viewImages.length) {
    renderThumbStrip();
    showCurrentImage();
  } else {
    pzSetPlaceholder('trainViewer', mode === 'raw' ? 'No raw images yet — Download from GDrive or Upload Images' : 'No labelled images yet — run Auto-Label first');
    document.getElementById('imgCounter').textContent = '0 / 0';
    document.getElementById('imgStats').textContent = '';
    renderThumbStrip();
    fetchStatus().then((s) => {
      if (!s) return;
      if (s.raw_images) rawImages = s.raw_images;
      if (s.labelled_images) labelledImages = s.labelled_images;
      if (s.raw_folder) folderPaths.raw = s.raw_folder + '  (' + rawImages.length + ' images)';
      if (s.labelled_folder) folderPaths.labelled = s.labelled_folder + '  (' + labelledImages.length + ' labelled)';
      viewImages = mode === 'labelled' ? labelledImages : rawImages;
      updateFolderPath();
      if (viewImages.length) { renderThumbStrip(); showCurrentImage(); }
    });
  }
}

async function refreshFromStatus() {
  const s = await fetchStatus();
  if (!s) return;
  rawImages = s.raw_images || [];
  labelledImages = s.labelled_images || [];
  if (s.raw_folder) folderPaths.raw = s.raw_folder + '  (' + rawImages.length + ' images)';
  if (s.labelled_folder) folderPaths.labelled = s.labelled_folder + '  (' + labelledImages.length + ' labelled)';
  viewImages = viewMode === 'labelled' ? labelledImages : rawImages;
  updateFolderPath();
  updateSelectionCount();
  renderThumbStrip();
  if (viewImages.length) showCurrentImage();
}

function metadataChoice(choice) {
  document.getElementById('metadataModal')?.classList.remove('open');
  if (choice === 'all') {
    const mode = prompt('Apply to all images:\n  use = use existing\n  local = re-analyse locally\n  gemini = re-analyse with Gemini\n\nEnter choice:', 'use');
    _metadataSessionChoice = mode || 'use';
    if (_metadataResolve) _metadataResolve(_metadataSessionChoice);
  } else if (_metadataResolve) {
    _metadataResolve(choice);
  }
  _metadataResolve = null;
}

async function checkMetadata(basename) {
  if (_metadataSessionChoice) return _metadataSessionChoice;
  try {
    const res = await fetch('/api/metadata/check?basename=' + encodeURIComponent(basename));
    const data = await res.json();
    if (!data.exists) return 'local';
    const counts = Object.entries(data.label_counts || {}).map(([k, v]) => k + ': ' + v).join(', ') || 'none';
    const ifc = Object.keys(data.ifc_classes || {}).join(', ') || '—';
    const body = document.getElementById('metadataModalBody');
    if (body) {
      body.innerHTML = `<strong>${basename}</strong><br>Source: <span style="color:var(--accent)">${data.source}</span>  Saved: ${data.saved_at || '—'}<br>Labels: ${data.n_labels}  Rooms: ${data.n_rooms}<br>Classes: ${counts}<br>IFC: ${ifc}`;
    }
    document.getElementById('metadataModal')?.classList.add('open');
    return new Promise((resolve) => { _metadataResolve = resolve; });
  } catch {
    return 'local';
  }
}

async function downloadGDriveTrain() {
  const btn = document.getElementById('btnDownload');
  if (btn) btn.disabled = true;
  appendTrainLog('Starting Google Drive download...');
  try {
    await fetch('/api/download', { method: 'POST' });
    appendTrainLog('Download task started (check log for progress)');
    const iv = setInterval(async () => {
      const s = await fetchStatus();
      if (s && s.raw_images && s.raw_images.length) {
        rawImages = s.raw_images;
        if (s.raw_folder) folderPaths.raw = s.raw_folder + '  (' + rawImages.length + ' images)';
        setViewMode('raw');
        clearInterval(iv);
        if (btn) btn.disabled = false;
      }
    }, 3000);
    setTimeout(() => { clearInterval(iv); if (btn) btn.disabled = false; }, 300000);
  } catch (e) {
    appendTrainLog('ERROR: ' + e.message);
    if (btn) btn.disabled = false;
  }
}

async function uploadTrainFiles(files) {
  if (!files || !files.length) return;
  const imgFiles = Array.from(files).filter((f) => f.type.startsWith('image/') || f.name.toLowerCase().endsWith('.svg'));
  if (!imgFiles.length) { appendTrainLog('No image files selected.'); return; }
  appendTrainLog(`Adding ${imgFiles.length} file(s) to Raw Images...`);
  await Promise.all(imgFiles.map((f) => new Promise((resolve) => {
    if (f.name.toLowerCase().endsWith('.svg')) { resolve(); return; }
    const r = new FileReader();
    r.onload = (e) => { uploadedFiles[f.name] = e.target.result; resolve(); };
    r.readAsDataURL(f);
  })));
  setViewMode('raw');
  const fd = new FormData();
  imgFiles.forEach((f) => fd.append('files', f));
  try {
    window.showLoader?.('Uploading images...');
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
    const data = await res.json();
    rawImages = data.images || [];
    if (data.raw_folder) folderPaths.raw = data.raw_folder + '  (' + rawImages.length + ' images)';
    appendTrainLog(`✅ ${data.saved} image(s) added`);
    setViewMode('raw');
    await refreshFromStatus();
  } catch (e) {
    appendTrainLog('ERROR uploading: ' + e.message);
  } finally {
    window.hideLoader?.();
  }
}

function pollForLabels() {
  const interval = setInterval(async () => {
    const status = await fetchStatus();
    if (!status) return;
    if (status.labelled_images && status.labelled_images.length) {
      labelledImages = status.labelled_images;
      if (status.labelled_folder) folderPaths.labelled = status.labelled_folder + '  (' + labelledImages.length + ' labelled)';
      setViewMode('labelled');
      document.getElementById('btnAutoLabel').disabled = false;
      if (status.status && (status.status.includes('Labelled') || status.status.includes('Done') || status.status === 'Ready')) {
        clearInterval(interval);
      }
    }
  }, 2000);
  setTimeout(() => clearInterval(interval), 600000);
}

async function autoLabelTrain() {
  const btn = document.getElementById('btnAutoLabel');
  if (btn) btn.disabled = true;
  _metadataSessionChoice = null;
  const status = await fetchStatus();
  const files = (status && status.raw_images) || [];
  if (!files.length) {
    appendTrainLog('No raw images found. Upload or download images first.');
    if (btn) btn.disabled = false;
    return;
  }
  const firstBasename = files[0].replace(/\.[^.]+$/, '');
  const choice = await checkMetadata(firstBasename);
  appendTrainLog('Metadata choice: ' + choice);
  appendTrainLog('Starting auto-labelling...');
  try {
    await fetch('/api/autolabel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ metadata_choice: choice }),
    });
    appendTrainLog('Auto-label task started');
    pollForLabels();
  } catch (e) {
    appendTrainLog('ERROR: ' + e.message);
    if (btn) btn.disabled = false;
  }
}

function pollForTraining() {
  const interval = setInterval(async () => {
    const status = await fetchStatus();
    if (status && !status.training) {
      document.getElementById('btnTrain').disabled = false;
      document.getElementById('btnTrainSelected') && (document.getElementById('btnTrainSelected').disabled = selectedRawFiles.size === 0);
      clearInterval(interval);
      refreshModelVersions();
    }
  }, 3000);
  setTimeout(() => {
    clearInterval(interval);
    const b = document.getElementById('btnTrain');
    if (b) b.disabled = false;
  }, 7200000);
}

async function trainSelected() {
  const files = Array.from(selectedRawFiles);
  if (!files.length) return;
  const btn = document.getElementById('btnTrainSelected');
  if (btn) btn.disabled = true;
  appendTrainLog(`Auto-labelling + training ${files.length} selected file(s)...`);
  try {
    const res = await fetch('/api/autolabel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files }),
    });
    if (!res.ok) { appendTrainLog('ERROR starting auto-label'); if (btn) btn.disabled = false; return; }
  } catch (e) {
    appendTrainLog('ERROR: ' + e.message);
    if (btn) btn.disabled = false;
    return;
  }
  const iv = setInterval(async () => {
    const s = await fetchStatus();
    if (!s) return;
    if (s.status && (s.status.includes('Labelled') || s.status.includes('Done') || s.status === 'Ready')) {
      clearInterval(iv);
      labelledImages = s.labelled_images || labelledImages;
      appendTrainLog('✅ Labelling complete — starting training...');
      const body = {
        epochs: parseInt(document.getElementById('train-epochs').value) || 50,
        batch: parseInt(document.getElementById('train-batch').value) || 4,
        imgsz: parseInt(document.getElementById('train-imgsz').value) || 640,
      };
      try {
        await fetch('/api/train', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      } catch (e) { appendTrainLog('ERROR starting training: ' + e.message); }
      pollForTraining();
      setViewMode('labelled');
      selectedRawFiles.clear();
      updateSelectionCount();
      if (btn) btn.disabled = false;
    }
  }, 2000);
  setTimeout(() => { clearInterval(iv); if (btn) btn.disabled = false; }, 600000);
}

async function startTraining() {
  const btn = document.getElementById('btnTrain');
  if (btn) btn.disabled = true;
  const body = {
    epochs: parseInt(document.getElementById('train-epochs').value) || 50,
    batch: parseInt(document.getElementById('train-batch').value) || 4,
    imgsz: parseInt(document.getElementById('train-imgsz').value) || 640,
  };
  appendTrainLog(`Starting training: ${body.epochs} epochs, batch=${body.batch}, imgsz=${body.imgsz}`);
  try {
    const res = await fetch('/api/train', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (res.status === 409) appendTrainLog('⚠️ Training already in progress');
    else appendTrainLog('Training task started');
    pollForTraining();
  } catch (e) {
    appendTrainLog('ERROR: ' + e.message);
    if (btn) btn.disabled = false;
  }
}

async function refreshModelVersions() {
  try {
    const res = await fetch('/api/model_versions');
    const data = await res.json();
    renderModelVersions(data);
  } catch (_) {}
}

function renderModelVersions(data) {
  const el = document.getElementById('modelVersionList');
  if (!el) return;
  const versions = data.versions || [];
  if (!versions.length) {
    el.innerHTML = '<div style="color:var(--muted);padding:8px;font-size:12px">No versions yet — train a model first</div>';
    return;
  }
  el.innerHTML = versions.map((v) => {
    const isActive = v.is_active;
    const ts = (v.ts || '').replace('T', ' ');
    const map50f = parseFloat(v.mAP50);
    const map50Color = map50f >= 0.5 ? 'var(--success)' : map50f >= 0.2 ? '#fb923c' : 'var(--danger)';
    const map50Disp = isNaN(map50f) ? '—' : `<span style="color:${map50Color};font-weight:600">${v.mAP50}</span>`;
    const shortName = (v.name || v.path).split('/').slice(-3).join('/');
    return `<div style="padding:6px 8px;border-radius:6px;margin-bottom:4px;background:${isActive ? 'rgba(16,185,129,0.08)' : '#020617'};border:1px solid ${isActive ? 'var(--success)' : 'rgba(255,255,255,0.06)'}">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">
        <span style="font-size:12px;font-weight:${isActive ? '600' : '400'};flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${v.path}">${isActive ? '★ ' : ''}${shortName}</span>
        ${isActive ? '<span style="font-size:10px;color:var(--success)">Active</span>' : `<button class="btn-secondary" style="font-size:10px;padding:2px 8px" data-model-path="${encodeURIComponent(v.path)}">Use</button>`}
      </div>
      <div style="font-size:10px;color:var(--muted)">mAP50: ${map50Disp} · Epochs: ${v.epochs || '—'} · ${ts}</div>
    </div>`;
  }).join('');
  el.querySelectorAll('[data-model-path]').forEach((b) => {
    b.addEventListener('click', async () => {
      const path = decodeURIComponent(b.dataset.modelPath);
      if (!confirm('Set as active model?\n' + path.split('/').pop())) return;
      const res = await fetch('/api/set_model', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path }) });
      const j = await res.json();
      if (j.ok) { appendTrainLog('✅ Active model updated'); refreshModelVersions(); }
    });
  });
}

export function initTrain() {
  if (!document.getElementById('panel-train')) return;
  bindTrainSse();
  pzInitAll(['trainViewer']);

  document.getElementById('btnDownload')?.addEventListener('click', downloadGDriveTrain);
  document.getElementById('btnUpload')?.addEventListener('click', () => document.getElementById('trainFileInput')?.click());
  document.getElementById('trainFileInput')?.addEventListener('change', (e) => uploadTrainFiles(e.target.files));
  document.getElementById('btnAutoLabel')?.addEventListener('click', autoLabelTrain);
  document.getElementById('btnTrain')?.addEventListener('click', startTraining);
  document.getElementById('btnTrainSelected')?.addEventListener('click', trainSelected);
  document.getElementById('vmRaw')?.addEventListener('click', () => setViewMode('raw'));
  document.getElementById('vmLabelled')?.addEventListener('click', () => setViewMode('labelled'));
  document.getElementById('btnSelectAllRaw')?.addEventListener('click', () => { rawImages.forEach((f) => selectedRawFiles.add(f)); updateSelectionCount(); renderThumbStrip(); });
  document.getElementById('btnDeselectAllRaw')?.addEventListener('click', () => { selectedRawFiles.clear(); updateSelectionCount(); renderThumbStrip(); });
  document.getElementById('btnPrevImage')?.addEventListener('click', () => { if (viewImages.length) { currentImgIdx = (currentImgIdx - 1 + viewImages.length) % viewImages.length; renderThumbStrip(); showCurrentImage(); } });
  document.getElementById('btnNextImage')?.addEventListener('click', () => { if (viewImages.length) { currentImgIdx = (currentImgIdx + 1) % viewImages.length; renderThumbStrip(); showCurrentImage(); } });
  document.getElementById('btnTrainAddImages')?.addEventListener('click', () => document.getElementById('trainFileInput')?.click());
  document.getElementById('btnTrainPzIn')?.addEventListener('click', () => pzZoom('trainViewer', 1.25));
  document.getElementById('btnTrainPzOut')?.addEventListener('click', () => pzZoom('trainViewer', 0.8));
  document.getElementById('btnTrainPzFit')?.addEventListener('click', () => pzFit('trainViewer'));
  document.getElementById('btnTrainPzReset')?.addEventListener('click', () => pzReset('trainViewer'));
  document.getElementById('btnRefreshModels')?.addEventListener('click', refreshModelVersions);
  document.getElementById('metadataUse')?.addEventListener('click', () => metadataChoice('use'));
  document.getElementById('metadataGemini')?.addEventListener('click', () => metadataChoice('gemini'));
  document.getElementById('metadataLocal')?.addEventListener('click', () => metadataChoice('local'));
  document.getElementById('metadataAll')?.addEventListener('click', () => metadataChoice('all'));
  document.getElementById('metadataModal')?.addEventListener('click', (e) => { if (e.target.id === 'metadataModal') metadataChoice('local'); });

  window.refreshTrainLists = refreshFromStatus;
  refreshFromStatus();
  refreshModelVersions();
  setViewMode('raw');
}
