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
    if (route === '/') {
      res.writeHead(302, { location: '/items' });
      res.end();
      return;
    }
    const slow = req.url.includes('slow=1') ? '<img src="/slow-asset">' : '';
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
