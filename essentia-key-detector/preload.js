const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // Open native file dialog to select audio file
    openFileDialog: () => ipcRenderer.invoke('open-file-dialog'),

    // Open native file dialog to select multiple audio files
    openMultiFileDialog: () => ipcRenderer.invoke('open-multi-file-dialog'),

    // Read audio file from disk and return buffer
    readAudioFile: (filePath) => ipcRenderer.invoke('read-audio-file', filePath),

    // Decode audio via Python server (safe, no crash)
    decodeAudioPython: (filePath) => ipcRenderer.invoke('decode-audio-python', filePath),

    // Detect key via Python server (FAST & ACCURATE)
    detectKeyPython: (filePath) => ipcRenderer.invoke('detect-key-python', filePath),

    // Check if Python server is running
    checkPythonServer: () => ipcRenderer.invoke('check-python-server'),

    // Quit the application
    quitApp: () => ipcRenderer.send('quit-app')
});
