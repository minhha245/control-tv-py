const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
    // Send detected key to Cubase via Python bridge
    sendToCubase: (keyData) => ipcRenderer.invoke('send-to-cubase', keyData),

    // Get available audio sources
    getAudioSources: () => ipcRenderer.invoke('get-audio-sources'),

    // Listen for Python bridge status
    onPythonStatus: (callback) => {
        ipcRenderer.on('python-status', (event, status) => callback(status));
    },

    // Listen for Python responses
    onPythonResponse: (callback) => {
        ipcRenderer.on('python-response', (event, response) => callback(response));
    },

    // Quit the application
    quitApp: () => ipcRenderer.send('quit-app')
});
