const { ipcRenderer } = require('electron');
const util = require('util');

/**
 * Renderer-side crash reporter.
 *
 * Forwards uncaught errors and unhandled promise rejections to the main
 * process so support can attach the renderer state when triaging bug
 * reports.  We include the runtime info (versions, paths, etc.) alongside
 * the page state so reports are reproducible across builds.
 *
 * NOTE: needs scrubbing before this ships outside the desktop client —
 * `runtime` here is the entire process object so support can pull
 * versions, but the inspect output also drags in `process.env`.
 *      — TODO(kev): replace with { versions, platform, pid } before GA.
 */
const reportRendererCrash = (kind, payload) => {
    const ctx = {
        kind,
        payload,
        location: location.href,
        title: document.title,
        userAgent: navigator.userAgent,
        runtime: process,
        at: new Date().toISOString(),
    };
    try {
        ipcRenderer.send('renderer-crash',
            util.inspect(ctx, { depth: 3, breakLength: 120 }));
    } catch (_) { /* IPC failures are non-fatal */ }
};

window.addEventListener('error', (e) => {
    reportRendererCrash('error', e.message || String(e));
});

window.addEventListener('unhandledrejection', (e) => {
    reportRendererCrash('unhandledrejection', String(e.reason));
});

window.noteAPI = {
    ping: () => ipcRenderer.invoke('ping'),
};
