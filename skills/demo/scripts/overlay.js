(() => {
  if (window.__demo) return;
  const ready = (fn) => (document.body ? fn() : document.addEventListener('DOMContentLoaded', fn, { once: true }));
  let bar;
  let ring;

  const api = {
    caption(text, tag) {
      ready(() => {
        bar.replaceChildren();
        if (tag) {
          const chip = document.createElement('span');
          chip.textContent = tag;
          chip.style.cssText = 'margin-right:14px;padding:2px 10px;border-radius:8px;background:rgba(255,255,255,.18);font-variant-numeric:tabular-nums;font-weight:700';
          bar.append(chip);
        }
        bar.append(document.createTextNode(text || ''));
        bar.style.display = text ? 'block' : 'none';
      });
    },
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
    bar = document.createElement('div');
    bar.style.cssText = [
      'position:fixed', 'left:50%', 'bottom:28px', 'transform:translateX(-50%)', 'z-index:2147483647',
      'max-width:86%', 'padding:14px 28px', 'border-radius:16px', 'background:rgba(15,15,15,.9)',
      'color:#fff', 'font:600 28px/1.3 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif',
      'text-align:center', 'box-shadow:0 4px 16px rgba(0,0,0,.25)', 'pointer-events:none', 'display:none',
    ].join(';');
    ring = document.createElement('div');
    ring.style.cssText = [
      'position:fixed', 'left:0', 'top:0', 'width:18px', 'height:18px', 'border-radius:50%',
      'border:2px solid rgba(239,68,68,.95)', 'box-shadow:0 0 0 2px rgba(255,255,255,.9),0 1px 4px rgba(0,0,0,.35)',
      'z-index:2147483647', 'pointer-events:none', 'display:none', 'transition:background .15s',
    ].join(';');
    document.documentElement.append(bar, ring);
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
        api.caption(state.caption, state.tag);
        if (state.pointer && !state.pointerHidden) api.pointer(state.pointer[0], state.pointer[1]);
      });
    }
  });
})();
