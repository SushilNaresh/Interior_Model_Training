/** Pan/zoom viewer engine (shared by Train + Correct tabs) */
const _pzState = {};

export function pzGet(id) {
  if (!_pzState[id]) _pzState[id] = { scale: 1, tx: 0, ty: 0 };
  return _pzState[id];
}

function _pzApply(id) {
  const s = pzGet(id);
  const inner = document.getElementById(id + 'Inner');
  if (!inner) return;
  inner.style.transform = `translate(${s.tx}px, ${s.ty}px) scale(${s.scale})`;
  const lbl = document.getElementById(id + 'Zoom');
  if (lbl) lbl.textContent = Math.round(s.scale * 100) + '%';
}

export function pzSetImage(id, src, alt, onLoad) {
  const inner = document.getElementById(id + 'Inner');
  if (!inner) return;
  const img = new window.Image();
  img.alt = alt || '';
  img.style.display = 'block';
  img.onload = () => {
    inner.innerHTML = '';
    inner.appendChild(img);
    pzFit(id);
    if (onLoad) onLoad(img);
  };
  img.src = src;
}

export function pzSetPlaceholder(id, msg) {
  const inner = document.getElementById(id + 'Inner');
  if (!inner) return;
  inner.innerHTML = `<div class="placeholder" style="padding:40px;color:var(--muted)">${msg}</div>`;
  const s = pzGet(id);
  s.scale = 1;
  s.tx = 0;
  s.ty = 0;
  _pzApply(id);
}

export function pzFit(id) {
  const wrap = document.getElementById(id);
  const inner = document.getElementById(id + 'Inner');
  if (!wrap || !inner) return;
  const img = inner.querySelector('img');
  if (!img) return;
  const ww = wrap.clientWidth || wrap.offsetWidth || 600;
  const wh = wrap.clientHeight || wrap.offsetHeight || 500;
  const iw = img.naturalWidth || img.width || ww;
  const ih = img.naturalHeight || img.height || wh;
  const scale = Math.min(ww / iw, wh / ih, 1);
  const s = pzGet(id);
  s.scale = scale;
  s.tx = (ww - iw * scale) / 2;
  s.ty = (wh - ih * scale) / 2;
  _pzApply(id);
}

export function pzReset(id) {
  const s = pzGet(id);
  s.scale = 1;
  s.tx = 0;
  s.ty = 0;
  _pzApply(id);
}

export function pzZoom(id, factor) {
  const wrap = document.getElementById(id);
  if (!wrap) return;
  const cx = (wrap.clientWidth || 600) / 2;
  const cy = (wrap.clientHeight || 500) / 2;
  const s = pzGet(id);
  const newScale = Math.min(Math.max(s.scale * factor, 0.1), 20);
  s.tx = cx - (cx - s.tx) * (newScale / s.scale);
  s.ty = cy - (cy - s.ty) * (newScale / s.scale);
  s.scale = newScale;
  _pzApply(id);
}

export function pzInitDrag(id, opts = {}) {
  const wrap = document.getElementById(id);
  if (!wrap || wrap._pzInited) return;
  wrap._pzInited = true;
  const blockPan = opts.blockPan || (() => false);
  let dragging = false;
  let startX, startY, startTx, startTy;

  wrap.addEventListener('mousedown', (e) => {
    if (e.button !== 0 || blockPan()) return;
    dragging = true;
    startX = e.clientX;
    startY = e.clientY;
    const s = pzGet(id);
    startTx = s.tx;
    startTy = s.ty;
    wrap.classList.add('grabbing');
    e.preventDefault();
  });
  window.addEventListener('mouseup', () => {
    dragging = false;
    wrap.classList.remove('grabbing');
  });
  window.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    const s = pzGet(id);
    s.tx = startTx + (e.clientX - startX);
    s.ty = startTy + (e.clientY - startY);
    _pzApply(id);
  });

  let lastTouchDist = null;
  wrap.addEventListener('touchstart', (e) => {
    if (blockPan()) return;
    if (e.touches.length === 1) {
      dragging = true;
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
      const s = pzGet(id);
      startTx = s.tx;
      startTy = s.ty;
    } else if (e.touches.length === 2) {
      dragging = false;
      lastTouchDist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
    }
    e.preventDefault();
  }, { passive: false });
  wrap.addEventListener('touchmove', (e) => {
    if (e.touches.length === 1 && dragging) {
      const s = pzGet(id);
      s.tx = startTx + (e.touches[0].clientX - startX);
      s.ty = startTy + (e.touches[0].clientY - startY);
      _pzApply(id);
    } else if (e.touches.length === 2 && lastTouchDist) {
      const dist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      pzZoom(id, dist / lastTouchDist);
      lastTouchDist = dist;
    }
    e.preventDefault();
  }, { passive: false });
  wrap.addEventListener('touchend', () => {
    dragging = false;
    lastTouchDist = null;
  });

  wrap.addEventListener('wheel', (e) => {
    e.preventDefault();
    const rect = wrap.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.12 : 0.89;
    const s = pzGet(id);
    const newScale = Math.min(Math.max(s.scale * factor, 0.1), 20);
    s.tx = cx - (cx - s.tx) * (newScale / s.scale);
    s.ty = cy - (cy - s.ty) * (newScale / s.scale);
    s.scale = newScale;
    _pzApply(id);
  }, { passive: false });
}

export function pzInitAll(ids, optsMap = {}) {
  ids.forEach((id) => setTimeout(() => pzInitDrag(id, optsMap[id] || {}), 200));
}
