const { app, BrowserWindow, ipcMain, desktopCapturer } = require('electron');
const path = require('path');
const net = require('net');

let mainWindow;
let pythonSocket = null;

// Python bridge configuration
const PYTHON_HOST = '127.0.0.1';
const PYTHON_PORT = 9999;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1000,
        minHeight: 700,
        backgroundColor: '#0a0a0f',
        titleBarStyle: 'hiddenInset',
        frame: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js'),
            webviewTag: true, // Enable webview for YouTube
            webSecurity: false
        }
    });

    mainWindow.loadFile('index.html');

    // Open DevTools in development
    if (process.argv.includes('--dev')) {
        mainWindow.webContents.openDevTools();
    }
}

// Connect to Python bridge
function connectToPython() {
    pythonSocket = new net.Socket();

    pythonSocket.connect(PYTHON_PORT, PYTHON_HOST, () => {
        console.log('Connected to Python bridge');
        mainWindow?.webContents.send('python-status', { connected: true });
    });

    pythonSocket.on('error', (err) => {
        console.log('Python bridge not available:', err.message);
        mainWindow?.webContents.send('python-status', { connected: false });
        // Retry connection after 5 seconds
        setTimeout(connectToPython, 5000);
    });

    pythonSocket.on('close', () => {
        console.log('Python bridge disconnected');
        mainWindow?.webContents.send('python-status', { connected: false });
        setTimeout(connectToPython, 5000);
    });

    pythonSocket.on('data', (data) => {
        try {
            const response = JSON.parse(data.toString());
            mainWindow?.webContents.send('python-response', response);
        } catch (e) {
            console.error('Invalid response from Python:', e);
        }
    });
}

// Send key data to Python/Cubase
ipcMain.handle('send-to-cubase', async (event, keyData) => {
    if (pythonSocket && pythonSocket.writable) {
        const message = JSON.stringify({
            action: 'set_key',
            key: keyData.key,
            scale: keyData.scale,
            confidence: keyData.confidence
        });
        pythonSocket.write(message + '\n');
        return { success: true };
    }
    return { success: false, error: 'Python bridge not connected' };
});

// Get audio sources for capture
ipcMain.handle('get-audio-sources', async () => {
    const sources = await desktopCapturer.getSources({
        types: ['window', 'screen'],
        fetchWindowIcons: true
    });
    return sources.map(source => ({
        id: source.id,
        name: source.name,
        thumbnail: source.thumbnail.toDataURL()
    }));
});

app.whenReady().then(() => {
    createWindow();
    connectToPython();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

// Quit when Python bridge is closed by user
ipcMain.on('quit-app', () => {
    app.quit();
});
