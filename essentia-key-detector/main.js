const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

// Disable GPU acceleration to prevent crashes
app.disableHardwareAcceleration();

let mainWindow;
let pythonProcess = null;

function startPythonServer() {
    // Check if running in production (packaged app)
    const isProduction = !process.defaultApp;
    
    let serverPath;
    
    if (isProduction) {
        // In production, use bundled executable
        serverPath = path.join(process.resourcesPath, 'audio_server.exe');
    } else {
        // In development, use Python script
        serverPath = path.join(__dirname, 'audio_server.py');
    }
    
    console.log('Starting Python server:', serverPath);
    
    if (isProduction && fs.existsSync(serverPath)) {
        // Run executable
        pythonProcess = spawn(serverPath, [], {
            detached: false,
            stdio: 'pipe'
        });
    } else if (fs.existsSync(serverPath)) {
        // Run Python script
        pythonProcess = spawn('python', [serverPath], {
            detached: false,
            stdio: 'pipe'
        });
    } else {
        console.error('Python server not found:', serverPath);
        return;
    }
    
    pythonProcess.stdout.on('data', (data) => {
        console.log(`Python: ${data}`);
    });
    
    pythonProcess.stderr.on('data', (data) => {
        console.error(`Python Error: ${data}`);
    });
    
    pythonProcess.on('close', (code) => {
        console.log(`Python server exited with code ${code}`);
        pythonProcess = null;
    });
}

function stopPythonServer() {
    if (pythonProcess) {
        console.log('Stopping Python server...');
        pythonProcess.kill();
        pythonProcess = null;
    }
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 960,
        height: 750,
        minWidth: 800,
        minHeight: 600,
        backgroundColor: '#0a0a0f',
        titleBarStyle: 'hiddenInset',
        frame: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js'),
            webSecurity: false,
            // Increase memory limit
            v8CacheOptions: 'code'
        }
    });

    mainWindow.loadFile('index.html');

    // Open DevTools in development
    if (process.argv.includes('--dev')) {
        mainWindow.webContents.openDevTools();
    }

    // Prevent crashes on unhandled errors
    mainWindow.webContents.on('render-process-gone', (event, details) => {
        console.error('Renderer process gone:', details);
        if (details.reason === 'crashed' || details.reason === 'oom') {
            console.error('Process crashed or out of memory');
            // Reload window
            setTimeout(() => {
                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.reload();
                }
            }, 1000);
        }
    });

    // Log console messages from renderer
    mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
        console.log(`Renderer [${level}]:`, message);
    });
}

// Open file dialog to select audio files
ipcMain.handle('open-file-dialog', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        title: 'Select Audio File',
        filters: [
            { name: 'Audio Files', extensions: ['mp3', 'wav', 'flac', 'ogg', 'aac', 'm4a', 'wma', 'aiff'] },
            { name: 'All Files', extensions: ['*'] }
        ],
        properties: ['openFile']
    });

    if (result.canceled || result.filePaths.length === 0) {
        return null;
    }

    const filePath = result.filePaths[0];
    const stats = fs.statSync(filePath);

    return {
        path: filePath,
        name: path.basename(filePath),
        size: stats.size,
        ext: path.extname(filePath).toLowerCase()
    };
});



// Read audio file and return buffer
ipcMain.handle('read-audio-file', async (event, filePath) => {
    try {
        const buffer = fs.readFileSync(filePath);
        return buffer;
    } catch (err) {
        console.error('Error reading file:', err);
        return null;
    }
});

// Decode audio via Python server (safe, no crash)
ipcMain.handle('decode-audio-python', async (event, filePath) => {
    return new Promise((resolve, reject) => {
        const http = require('http');
        
        const postData = JSON.stringify({ filePath: filePath });
        
        const options = {
            hostname: '127.0.0.1', // Force IPv4
            port: 5000,
            path: '/decode-audio',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(postData)
            },
            timeout: 60000, // 60 seconds for large files
            family: 4 // Force IPv4
        };
        
        console.log('Requesting Python decode for:', filePath);
        
        const req = http.request(options, (res) => {
            let data = '';
            
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                try {
                    const result = JSON.parse(data);
                    
                    if (res.statusCode === 200) {
                        console.log('Python decoded:', result.numSamples, 'samples');
                        resolve(result);
                    } else {
                        console.error('Python decode error:', result.error);
                        resolve(null);
                    }
                } catch (e) {
                    console.error('Failed to parse decode response:', e);
                    resolve(null);
                }
            });
        });
        
        req.on('error', (err) => {
            console.error('Error decoding via Python:', err);
            resolve(null);
        });
        
        req.on('timeout', () => {
            console.error('Python decode timeout');
            req.destroy();
            resolve(null);
        });
        
        req.write(postData);
        req.end();
    });
});

// Detect key via Python server (FAST & ACCURATE)
ipcMain.handle('detect-key-python', async (event, filePath) => {
    return new Promise((resolve) => {
        const http = require('http');
        
        const postData = JSON.stringify({ filePath: filePath });
        
        const options = {
            hostname: '127.0.0.1',
            port: 5000,
            path: '/detect-key',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(postData)
            },
            timeout: 30000,
            family: 4
        };
        
        console.log('Requesting Python key detection for:', filePath);
        
        const req = http.request(options, (res) => {
            let data = '';
            
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                try {
                    const result = JSON.parse(data);
                    
                    if (res.statusCode === 200) {
                        console.log('Python detected:', result.key, result.scale);
                        resolve(result);
                    } else {
                        console.error('Python key detection error:', result.error);
                        resolve(null);
                    }
                } catch (e) {
                    console.error('Failed to parse key detection response:', e);
                    resolve(null);
                }
            });
        });
        
        req.on('error', (err) => {
            console.error('Error detecting key via Python:', err);
            resolve(null);
        });
        
        req.on('timeout', () => {
            console.error('Python key detection timeout');
            req.destroy();
            resolve(null);
        });
        
        req.write(postData);
        req.end();
    });
});

// Check if Python server is running
ipcMain.handle('check-python-server', async () => {
    return new Promise((resolve) => {
        const http = require('http');
        
        const options = {
            hostname: '127.0.0.1', // Force IPv4
            port: 5000,
            path: '/health',
            method: 'GET',
            timeout: 2000,
            family: 4 // Force IPv4
        };
        
        const req = http.get(options, (res) => {
            let data = '';
            
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                try {
                    const json = JSON.parse(data);
                    console.log('Python server health check:', json);
                    resolve(json.status === 'ok');
                } catch (e) {
                    console.error('Failed to parse health check:', e);
                    resolve(false);
                }
            });
        });
        
        req.on('error', (err) => {
            console.error('Python server check failed:', err.message);
            resolve(false);
        });
        
        req.on('timeout', () => {
            console.error('Python server check timeout');
            req.destroy();
            resolve(false);
        });
    });
});

// Open multiple files dialog
ipcMain.handle('open-multi-file-dialog', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        title: 'Select Audio Files',
        filters: [
            { name: 'Audio Files', extensions: ['mp3', 'wav', 'flac', 'ogg', 'aac', 'm4a', 'wma', 'aiff'] },
            { name: 'All Files', extensions: ['*'] }
        ],
        properties: ['openFile', 'multiSelections']
    });

    if (result.canceled || result.filePaths.length === 0) {
        return null;
    }

    return result.filePaths.map(filePath => {
        const stats = fs.statSync(filePath);
        return {
            path: filePath,
            name: path.basename(filePath),
            size: stats.size,
            ext: path.extname(filePath).toLowerCase()
        };
    });
});

app.whenReady().then(() => {
    // Increase memory limits
    app.commandLine.appendSwitch('js-flags', '--max-old-space-size=4096');
    app.commandLine.appendSwitch('disable-renderer-backgrounding');
    
    // Start Python server
    startPythonServer();
    
    // Wait a bit for server to start
    setTimeout(() => {
        createWindow();
    }, 2000);

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    stopPythonServer();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('before-quit', () => {
    stopPythonServer();
});

ipcMain.on('quit-app', () => {
    stopPythonServer();
    app.quit();
});
