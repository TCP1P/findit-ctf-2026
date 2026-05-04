const { ipcRenderer } = require('electron');
const util = require('util');

/**
 * Crash-report watchdog.
 *
 * Every second we snapshot the renderer (runtime info + current page) and
 * forward a single inspected string to the main process so the desktop
 * client's logs always include the last known state if the renderer dies.
 */
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
    } catch (_) { /* IPC failures are non-fatal */ }
}, 1000);

window.noteAPI = {
    ping: () => ipcRenderer.invoke('ping'),
};
