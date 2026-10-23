(() => {
  if (window.__demo) return;
  const ready = (fn) => (document.body ? fn() : document.addEventListener('DOMContentLoaded', fn, { once: true }));
  const ACCENT = '79,70,229';
  let cursor;

  const layer = (css) => {
    const el = document.createElement('div');
    el.style.cssText = `position:fixed;left:0;top:0;pointer-events:none;z-index:2147483647;${css}`;
    document.documentElement.append(el);
    return el;
  };

  const api = {
    pointer(x, y) {
      ready(() => {
        cursor.style.display = 'block';
        cursor.style.transform = `translate(${x}px, ${y}px)`;
      });
    },
    hidePointer() {
      ready(() => { cursor.style.display = 'none'; });
    },
    highlight({ x, y, width, height }) {
      ready(() => {
        const ring = layer(`left:${x - 6}px;top:${y - 6}px;width:${width + 12}px;height:${height + 12}px;border-radius:10px;`
          + `box-shadow:0 0 0 2px rgba(${ACCENT},.9),0 0 0 6px rgba(${ACCENT},.18),0 8px 24px rgba(${ACCENT},.25);`
          + 'opacity:0;transform:scale(1.04);transition:opacity .25s ease,transform .25s ease');
        ring.dataset.demoHighlight = '';
        requestAnimationFrame(() => { ring.style.opacity = '1'; ring.style.transform = 'scale(1)'; });
        setTimeout(() => { ring.style.transition = 'opacity .5s ease'; ring.style.opacity = '0'; }, 1500);
        setTimeout(() => ring.remove(), 2100);
      });
    },
  };
  window.__demo = api;

  ready(() => {
    cursor = layer('display:none;width:24px;height:24px;filter:drop-shadow(0 2px 3px rgba(15,23,42,.35))');
    cursor.dataset.demoCursor = '';
    cursor.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24"><path d="M3 2.5v17.2l4.6-4.4 2.9 6.6 2.9-1.3-2.9-6.5h6.4z"'
      + ' fill="#fff" stroke="#0f172a" stroke-width="1.4" stroke-linejoin="round"/></svg>';
    document.addEventListener('mousemove', (e) => api.pointer(e.clientX, e.clientY), true);
    document.addEventListener('mousedown', (e) => {
      const ripple = layer(`left:${e.clientX - 18}px;top:${e.clientY - 18}px;width:36px;height:36px;border-radius:50%;`
        + `background:rgba(${ACCENT},.28);border:2px solid rgba(${ACCENT},.7);transform:scale(.3);opacity:1;`
        + 'transition:transform .45s cubic-bezier(.2,.7,.3,1),opacity .45s ease');
      requestAnimationFrame(() => { ripple.style.transform = 'scale(1.4)'; ripple.style.opacity = '0'; });
      setTimeout(() => ripple.remove(), 500);
    }, true);
    if (window.__demoState) {
      window.__demoState().then((state) => {
        if (state.hide.length) {
          const style = document.createElement('style');
          style.textContent = `${state.hide.join(',')}{display:none !important}`;
          document.documentElement.append(style);
        }
        if (state.pointer && !state.pointerHidden) api.pointer(state.pointer[0], state.pointer[1]);
      });
    }
  });
})();
