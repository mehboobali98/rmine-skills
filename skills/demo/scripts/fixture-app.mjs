import http from 'node:http';

const STYLE = `body{font:15px system-ui;margin:0}header{background:#234;color:#fff;padding:14px 24px}
main{padding:24px}table{border-collapse:collapse;width:100%}td{border-bottom:1px solid #ddd;padding:10px}
button,a.btn{background:#2563eb;color:#fff;border:0;padding:8px 14px;border-radius:6px;text-decoration:none}`;

const ROWS = Array.from({ length: 12 }, (_, i) => `<tr class="${i % 3 ? 'open' : 'closed'}"><td>Item ${i + 1}</td><td>${i % 3 ? 'Open' : 'Closed'}</td></tr>`).join('');

const PAGES = {
  '/items': `<h1>Items</h1>
    <a class="btn" href="/items/new">New item</a>
    <button onclick="document.querySelectorAll('tr.closed').forEach((r) => r.remove()); document.getElementById('count').textContent = '8 shown'">Hide closed</button>
    <p id="count">12 shown</p><table>${ROWS}</table>`,
  '/items/new': `<h1>New item</h1>
    <label>Name <input id="name"></label>
    <label>Status <select id="status"><option>Open</option><option>Closed</option></select></label>
    <button onclick="document.querySelector('h1').textContent = 'Saved ' + document.getElementById('name').value">Save</button>`,
};

PAGES['/board'] = `<h1>Board</h1>
  <div id="card" draggable="true" style="width:120px;padding:8px;border:1px solid #999">Card</div>
  <div id="zone" style="margin-top:40px;width:240px;height:80px;border:2px dashed #999">Drop zone</div>
  <div id="handle" style="margin-top:40px;width:16px;height:16px;border-radius:50%;background:#e44">&nbsp;</div>
  <div id="socket" style="margin:40px 0 0 300px;width:100px;height:40px;border:1px solid #999">Socket</div>
  <p id="status">Idle</p>
  <script>
    const zone = document.getElementById('zone');
    document.getElementById('card').addEventListener('dragstart', (e) => e.dataTransfer.setData('text/plain', 'card'));
    zone.addEventListener('dragover', (e) => e.preventDefault());
    zone.addEventListener('drop', (e) => { e.preventDefault(); zone.textContent = 'Dropped ' + e.dataTransfer.getData('text/plain'); });
    let wiring = false;
    document.getElementById('handle').addEventListener('pointerdown', () => { wiring = true; });
    document.addEventListener('pointerup', (e) => {
      if (wiring && e.target.id === 'socket') document.getElementById('status').textContent = 'Wired';
      wiring = false;
    });
  </script>`;

const html = (body) => `<!doctype html><html><head><title>Sample app</title><style>${STYLE}</style></head>
<body><header>Sample app</header><main>${body}</main></body></html>`;

export const VALID_COOKIE = 'valid-session';

/**
 * Serves /login and two signed-in pages. Without the cookie every page redirects to /login.
 * @returns {Promise<{url: string, close: () => Promise<void>}>}
 */
export async function startFixture() {
  const server = http.createServer((req, res) => {
    const signedIn = (req.headers.cookie || '').includes(`sid=${VALID_COOKIE}`);
    const route = req.url.split('?')[0];
    if (route === '/slow-asset') {
      setTimeout(() => res.end(), 20000);
      return;
    }
    if (route === '/login') {
      if (req.method === 'POST') {
        res.writeHead(302, { 'set-cookie': `sid=${VALID_COOKIE}; Path=/`, location: '/items' });
        res.end();
        return;
      }
      res.end(html('<form method="post"><label>Password <input type="password" name="p"></label><button>Sign in</button></form>'));
      return;
    }
    if (!signedIn) {
      res.writeHead(302, { location: '/login' });
      res.end();
      return;
    }
    if (route === '/late-data') {
      setTimeout(() => res.end('ok'), 1200);
      return;
    }
    if (route.startsWith('/late-color/')) {
      res.end(`<!doctype html><html><body style="margin:0;height:100vh;background:#fff">
        <script>fetch('/late-data').then(() => { document.body.style.background = '#${route.slice(12)}'; });</script></body></html>`);
      return;
    }
    if (route.startsWith('/color/')) {
      res.end(`<!doctype html><html><body style="margin:0;height:100vh;background:#${route.slice(7)}"></body></html>`);
      return;
    }
    if (route === '/') {
      res.writeHead(302, { location: '/items' });
      res.end();
      return;
    }
    const slow = (req.url.includes('slow=1') ? '<img src="/slow-asset">' : '')
      + (req.url.includes('heavy=1') ? '<script>document.addEventListener("mousemove", () => { const t = Date.now(); while (Date.now() - t < 150); });</script>' : '');
    res.writeHead(PAGES[route] ? 200 : 404, { 'content-type': 'text/html' });
    res.end(html((PAGES[route] || '<h1>Not found</h1>') + slow));
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  return {
    url,
    close: () => new Promise((resolve) => {
      server.close(resolve);
      server.closeAllConnections();
    }),
  };
}

export function sessionWithCookie(value) {
  return {
    cookies: [{ name: 'sid', value, domain: '127.0.0.1', path: '/', expires: -1, httpOnly: false, secure: false, sameSite: 'Lax' }],
    origins: [],
  };
}
