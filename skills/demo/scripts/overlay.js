(() => {
  if (window.__demo) return;
  const ready = (fn) => (document.body ? fn() : document.addEventListener('DOMContentLoaded', fn, { once: true }));
  let ring;

  const api = {
    pointer(x, y) {
      ready(() => {
        ring.style.display = 'block';
        ring.style.transform = `translate(${x - 11}px, ${y - 11}px)`;
      });
    },
    hidePointer() {
      ready(() => { ring.style.display = 'none'; });
    },
  };
  window.__demo = api;

  ready(() => {
    ring = document.createElement('div');
    ring.style.cssText = [
      'position:fixed', 'left:0', 'top:0', 'width:18px', 'height:18px', 'border-radius:50%',
      'border:2px solid rgba(239,68,68,.95)', 'box-shadow:0 0 0 2px rgba(255,255,255,.9),0 1px 4px rgba(0,0,0,.35)',
      'z-index:2147483647', 'pointer-events:none', 'display:none', 'transition:background .15s',
    ].join(';');
    document.documentElement.append(ring);
    if (window.__demoState) {
      window.__demoState().then((state) => {
        if (!state.hide.length) return;
        const style = document.createElement('style');
        style.textContent = `${state.hide.join(',')}{display:none !important}`;
        document.documentElement.append(style);
      });
    }
    document.addEventListener('mousemove', (e) => api.pointer(e.clientX, e.clientY), true);
    document.addEventListener('mousedown', () => {
      ring.style.background = 'rgba(239,68,68,.35)';
      setTimeout(() => { ring.style.background = 'transparent'; }, 300);
    }, true);
    if (window.__demoState) {
      window.__demoState().then((state) => {
        if (state.pointer && !state.pointerHidden) api.pointer(state.pointer[0], state.pointer[1]);
      });
    }
  });
})();
