# Electron Key Detector

A modern, high-accuracy musical key detection tool built with **Electron** and **Essentia.js**.

## Features

- 🎵 **YouTube Integration** - Paste any YouTube URL and detect the key in real-time
- 🎯 **Antares-Grade Accuracy** - Multi-profile voting system with EDMA, Sha'ath, and Temperley profiles
- 🔒 **Key Locking** - HMM-based smoothing prevents key jumping
- 🎨 **Premium UI** - Dark theme with glassmorphism and real-time chroma visualization
- 🔗 **Cubase Integration** - Send detected keys directly to Cubase via Python bridge

## Quick Start

### 1. Install Dependencies

```bash
cd electron-key-detector
npm install
```

### 2. Start the App

```bash
npm start
```

### 3. (Optional) Start Python Bridge for Cubase

```bash
python python_bridge.py
```

## How It Works

1. **Paste YouTube URL** - Enter a YouTube video URL and click "Load"
2. **Start Detection** - Click "Start Detection" to begin analyzing audio
3. **View Results** - See the detected key, scale, and confidence in real-time
4. **Send to Cubase** - Click "Send to Cubase" to update your DAW

## Audio Capture

The app can capture audio in two ways:

1. **Microphone Input** - Captures your current audio output through the microphone
2. **Demo Mode** - If no microphone is available, runs in demo mode with simulated detection

For best results on Windows, you can use a virtual audio cable to route system audio to the app.

## Architecture

```
Electron App
├── main.js          # Main process, Python bridge connection
├── preload.js       # IPC bridge to renderer
├── index.html       # UI structure
├── styles.css       # Premium dark theme
├── app.js           # Key detection engine (Essentia.js)
└── python_bridge.py # Cubase control server
```

## Customization

### Key Profiles

Edit the profile weights in `app.js`:

```javascript
// EDMA (weight: 0.5) - Best for EDM/Pop
// Sha'ath (weight: 0.3) - Modern enhanced
// Temperley (weight: 0.2) - Rock/Pop
```

### Cubase Coordinates

Edit `python_bridge.py` to set your Cubase key selector coordinates.

## License

MIT © Hau Studio 2026
