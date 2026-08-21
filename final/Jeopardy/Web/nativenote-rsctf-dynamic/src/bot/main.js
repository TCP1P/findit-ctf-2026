const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');

const BOT_URL = process.env.BOT_URL || 'http://localhost:8080';

app.commandLine.appendSwitch('disable-gpu');

app.whenReady().then(() => {
    const win = new BrowserWindow({
        width: 1280,
        height: 800,
        show: false,
        webPreferences: {
            contextIsolation: false,
            sandbox: false,
            nodeIntegration: false,
            preload: path.join(__dirname, 'preload.js'),
        },
    });

    win.loadURL(BOT_URL);
    setTimeout(() => app.quit(), 25000);
});

app.on('window-all-closed', () => app.quit());
