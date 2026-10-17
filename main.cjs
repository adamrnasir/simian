const { app, BrowserWindow, nativeTheme, net, protocol } = require('electron');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const ROOT = path.join(__dirname, 'web');

// Module scripts need an origin, which file:// pages lack, so web/ is served
// from a privileged custom scheme instead.
protocol.registerSchemesAsPrivileged([{ scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true } }]);

function createWindow() {
  const window = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 900,
    minHeight: 640,
    title: 'Simian',
    backgroundColor: nativeTheme.shouldUseDarkColors ? '#080909' : '#f5f4f0',
    webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false }
  });
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', event => event.preventDefault());
  window.loadURL('app://simian/index.html');
}

app.whenReady().then(() => {
  protocol.handle('app', request => {
    const file = path.join(ROOT, path.normalize(decodeURIComponent(new URL(request.url).pathname)));
    if (!file.startsWith(ROOT + path.sep)) return new Response('Not found', { status: 404 });
    return net.fetch(pathToFileURL(file).toString());
  });
  createWindow();
  app.on('activate', () => { if (!BrowserWindow.getAllWindows().length) createWindow(); });
});

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
