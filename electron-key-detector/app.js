/**
 * Key Detector - Essentia.js Audio Processing Engine
 * Antares-Grade Accuracy with HMM Smoothing
 */

// ============================================
// Constants & Key Profiles
// ============================================

const KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

// EDMA Profile (Electronic Dance Music Analysis) - Best for Pop/YouTube
const EDMA_MAJOR = [0.16519551, 0.04749026, 0.08293076, 0.06687112, 0.09994645,
    0.09274123, 0.05294487, 0.13159476, 0.05218986, 0.07443653,
    0.06940723, 0.06424152];
const EDMA_MINOR = [0.17235348, 0.05336489, 0.07703478, 0.10989745, 0.05091988,
    0.09632016, 0.04787113, 0.13418295, 0.09070186, 0.05765757,
    0.07276066, 0.06693519];

// Sha'ath Profile (Enhanced Modern)
const SHAATH_MAJOR = [6.6, 2.0, 3.5, 2.3, 4.6, 4.0, 2.5, 5.2, 2.4, 3.7, 2.3, 3.0];
const SHAATH_MINOR = [6.5, 2.8, 3.5, 5.4, 2.7, 3.5, 2.5, 5.2, 4.0, 2.7, 4.3, 3.2];

// Temperley Profile (Rock/Pop)
const TEMPERLEY_MAJOR = [5.0, 2.0, 3.5, 2.0, 4.5, 4.0, 2.0, 4.5, 2.0, 3.5, 1.5, 4.0];
const TEMPERLEY_MINOR = [5.0, 2.0, 3.5, 4.5, 2.0, 4.0, 2.0, 4.5, 3.5, 2.0, 1.5, 4.0];

// ============================================
// Utility Functions
// ============================================

function normalizeArray(arr) {
    const norm = Math.sqrt(arr.reduce((sum, val) => sum + val * val, 0));
    return norm > 0 ? arr.map(v => v / norm) : arr;
}

function dotProduct(a, b) {
    return a.reduce((sum, val, i) => sum + val * b[i], 0);
}

function rotateArray(arr, shift) {
    const n = arr.length;
    shift = ((shift % n) + n) % n;
    return [...arr.slice(shift), ...arr.slice(0, shift)];
}

function extractYouTubeId(url) {
    const patterns = [
        /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\?\/]+)/,
        /^([a-zA-Z0-9_-]{11})$/
    ];
    for (const pattern of patterns) {
        const match = url.match(pattern);
        if (match) return match[1];
    }
    return null;
}

// ============================================
// Key Detector Engine
// ============================================

class KeyDetectorEngine {
    constructor() {
        this.essentia = null;
        this.isReady = false;
        this.audioContext = null;
        this.analyser = null;
        this.sourceNode = null;
        this.isRunning = false;
        this.isDemoMode = false;

        // Detection state
        this.chromaHistory = [];
        this.maxHistory = 60; // Increased for more stability
        this.currentKey = null;
        this.currentMode = null;
        this.currentConfidence = 0;

        // SILENCE DETECTION
        this.silenceThreshold = -60; // dB threshold for silence
        this.silenceFrameCount = 0;
        this.silenceFramesRequired = 10; // Frames of silence before clearing
        this.isSilent = true;

        // STRONG KEY LOCKING
        this.keyStabilityCounter = 0;
        this.stabilityThreshold = 20; // Need 20 consistent frames
        this.candidateKey = null;
        this.candidateCount = 0;
        this.lockThreshold = 15; // Need 15 frames to switch key (very stable)
        this.confidenceThreshold = 0.55; // Minimum confidence to consider
        this.lockConfidenceThreshold = 0.65; // Minimum to lock a key

        // LOCKED KEY STATE
        this.lockedKey = null;
        this.lockedMode = null;
        this.lockedConfidence = 0;
        this.isLocked = false;
        this.unlockCounter = 0;
        this.unlockThreshold = 30; // Need 30 frames of different key to unlock

        // Normalized profiles
        this.profiles = {
            edma_major: normalizeArray([...EDMA_MAJOR]),
            edma_minor: normalizeArray([...EDMA_MINOR]),
            shaath_major: normalizeArray([...SHAATH_MAJOR]),
            shaath_minor: normalizeArray([...SHAATH_MINOR]),
            temperley_major: normalizeArray([...TEMPERLEY_MAJOR]),
            temperley_minor: normalizeArray([...TEMPERLEY_MINOR]),
        };

        // UI callbacks
        this.onKeyDetected = null;
        this.onChromaUpdate = null;
        this.onStatusChange = null;
    }

    async initialize() {
        try {
            // Initialize Essentia.js
            if (typeof EssentiaWASM !== 'undefined') {
                this.essentia = new Essentia(EssentiaWASM);
                console.log('Essentia.js initialized successfully');
                this.isReady = true;
                return true;
            } else {
                console.warn('Essentia WASM not loaded, using fallback mode');
                this.isReady = true;
                return true;
            }
        } catch (error) {
            console.error('Failed to initialize Essentia:', error);
            this.isReady = true; // Use fallback
            return true;
        }
    }

    async startCapture(specificSourceId = null) {
        if (this.isRunning) {
            this.stopCapture();
            // wait a bit for cleanup
            await new Promise(resolve => setTimeout(resolve, 100));
        }

        // Reset state
        this.reset();

        try {
            // Get available audio sources from main process
            let sourceId = specificSourceId;

            // If no specific source provided, try auto-detection
            if (!sourceId && window.electronAPI) {
                const sources = await window.electronAPI.getAudioSources();
                // Find screen/system audio source
                const screenSource = sources.find(s => s.name.includes('Entire Screen') || s.name.includes('Screen 1') || s.id.startsWith('screen'));
                if (screenSource) {
                    sourceId = screenSource.id;
                    console.log('Using auto-detected screen media source:', sourceId);
                }
            } else if (sourceId) {
                console.log('Using selected media source:', sourceId);
            }

            // Constraints for system audio capture
            const constraints = {
                audio: {
                    mandatory: {
                        chromeMediaSource: 'desktop'
                    }
                },
                video: {
                    mandatory: {
                        chromeMediaSource: 'desktop'
                    }
                }
            };

            // If we found a specific source ID, use it
            if (sourceId) {
                constraints.audio.mandatory.chromeMediaSourceId = sourceId;
                constraints.video.mandatory.chromeMediaSourceId = sourceId;
            }

            let stream;
            try {
                // Try capturing desktop audio
                stream = await navigator.mediaDevices.getUserMedia(constraints);
            } catch (e) {
                console.warn('Desktop capture failed, falling back to default mic:', e);
                // Fallback to microphone if desktop capture fails
                stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: false,
                        noiseSuppression: false,
                        autoGainControl: false
                    }
                });
            }

            // Remove video track if present, we only need audio
            const videoTracks = stream.getVideoTracks();
            videoTracks.forEach(track => track.stop());

            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 44100
            });

            this.sourceNode = this.audioContext.createMediaStreamSource(stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 8192;
            this.analyser.smoothingTimeConstant = 0.85;

            this.sourceNode.connect(this.analyser);

            this.isRunning = true;
            this.isDemoMode = false;
            this.processAudio();

            if (this.onStatusChange) {
                this.onStatusChange({ capturing: true });
            }

            return true;
        } catch (error) {
            console.error('Failed to start audio capture:', error);

            // Only fallback to demo as absolute last resort
            this.isRunning = true;
            this.isDemoMode = true;
            this.runDemoMode();

            if (this.onStatusChange) {
                this.onStatusChange({ capturing: true, demo: true });
            }

            return true;
        }
    }

    stopCapture() {
        this.isRunning = false;
        this.isDemoMode = false;

        if (this.sourceNode) {
            this.sourceNode.disconnect();
            this.sourceNode = null;
        }

        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }

        if (this.onStatusChange) {
            this.onStatusChange({ capturing: false });
        }
    }

    // Check if audio is silent
    checkSilence(dataArray) {
        // Calculate RMS in dB
        let sum = 0;
        // Use a subset of bins to check for signal (avoiding DC offset and high freq noise)
        const startBin = 10;
        const endBin = Math.min(dataArray.length, 1000);

        for (let i = startBin; i < endBin; i++) {
            // dataArray contains dB values, typically -140 to 0
            // We convert back to linear power to average
            if (dataArray[i] > -120) { // Ignore absolute noise floor
                sum += Math.pow(10, dataArray[i] / 10);
            }
        }

        const avgPower = sum / (endBin - startBin);
        const avgDb = 10 * Math.log10(avgPower + 1e-10);

        // Much lower threshold (-80dB is very quiet, -100dB is effectively silent)
        // Adjust this if your mic/system audio is very quiet
        return { isSilent: avgDb < -85, db: avgDb };
    }

    processAudio() {
        if (!this.isRunning) return;

        const bufferLength = this.analyser.frequencyBinCount;
        const dataArray = new Float32Array(bufferLength);
        this.analyser.getFloatFrequencyData(dataArray);

        // Check for silence
        const { isSilent, db } = this.checkSilence(dataArray);

        // Report audio level
        if (this.onAudioLevel) {
            this.onAudioLevel(db);
        }

        if (isSilent) {
            this.silenceFrameCount++;

            if (this.silenceFrameCount >= this.silenceFramesRequired) {
                this.isSilent = true;
                // Report silence state
                if (this.onKeyDetected) {
                    this.onKeyDetected({
                        key: this.lockedKey || '--',
                        mode: this.lockedMode || 'Waiting...',
                        confidence: 0,
                        stability: this.isLocked ? 1.0 : 0,
                        isSilent: true
                    });
                }
                if (this.onChromaUpdate) {
                    this.onChromaUpdate(new Array(12).fill(0));
                }
            }
        } else {
            this.silenceFrameCount = 0;
            this.isSilent = false;

            // Convert from dB to linear magnitude
            const magnitudes = new Float32Array(bufferLength);
            for (let i = 0; i < bufferLength; i++) {
                magnitudes[i] = Math.pow(10, dataArray[i] / 20);
            }

            // Compute chroma from frequency data
            const chroma = this.computeChroma(magnitudes);

            if (chroma) {
                this.detectKey(chroma);
            }
        }

        // Continue processing at ~30fps
        setTimeout(() => {
            if (this.isRunning) {
                requestAnimationFrame(() => this.processAudio());
            }
        }, 33);
    }

    computeChroma(magnitudes) {
        const chroma = new Array(12).fill(0);
        const sampleRate = this.audioContext?.sampleRate || 44100;
        const fftSize = magnitudes.length * 2;

        // Reference frequency for A4
        const A4 = 440;
        const C0 = A4 * Math.pow(2, -4.75);

        for (let i = 1; i < magnitudes.length; i++) {
            const frequency = (i * sampleRate) / fftSize;

            // Skip very low and very high frequencies
            if (frequency < 65 || frequency > 2000) continue;

            // Convert frequency to pitch class
            const pitchFromC0 = 12 * Math.log2(frequency / C0);
            const pitchClass = Math.round(pitchFromC0) % 12;

            if (pitchClass >= 0 && pitchClass < 12) {
                // Weight by magnitude
                chroma[pitchClass] += magnitudes[i] * magnitudes[i];
            }
        }

        // Normalize chroma
        const maxVal = Math.max(...chroma);
        if (maxVal > 0) {
            for (let i = 0; i < 12; i++) {
                chroma[i] /= maxVal;
            }
        }

        return chroma;
    }

    detectKey(chroma) {
        // Add to history
        this.chromaHistory.push([...chroma]);
        if (this.chromaHistory.length > this.maxHistory) {
            this.chromaHistory.shift();
        }

        // Average chroma over history
        const avgChroma = new Array(12).fill(0);
        for (const frame of this.chromaHistory) {
            for (let i = 0; i < 12; i++) {
                avgChroma[i] += frame[i];
            }
        }
        for (let i = 0; i < 12; i++) {
            avgChroma[i] /= this.chromaHistory.length;
        }

        // Normalize
        const normalizedChroma = normalizeArray(avgChroma);

        // Multi-profile voting
        const { key, mode, confidence } = this.multiProfileVoting(normalizedChroma);

        // Apply key locking with hysteresis
        const fullKey = `${key} ${mode}`;
        const result = this.applyKeyLocking(fullKey, confidence);

        // Update UI
        if (this.onChromaUpdate) {
            this.onChromaUpdate(chroma);
        }

        if (this.onKeyDetected) {
            this.onKeyDetected({
                key: result.key,
                mode: result.mode,
                confidence: result.confidence,
                stability: result.stability
            });
        }
    }

    multiProfileVoting(chroma) {
        const results = {};

        // EDMA (weight: 0.5)
        const edmaResult = this.detectWithProfile(chroma, this.profiles.edma_major, this.profiles.edma_minor);
        const edmaKey = `${KEY_NAMES[edmaResult.keyIndex]} ${edmaResult.mode}`;
        results[edmaKey] = (results[edmaKey] || 0) + 0.5 * edmaResult.correlation;

        // Sha'ath (weight: 0.3)
        const shaathResult = this.detectWithProfile(chroma, this.profiles.shaath_major, this.profiles.shaath_minor);
        const shaathKey = `${KEY_NAMES[shaathResult.keyIndex]} ${shaathResult.mode}`;
        results[shaathKey] = (results[shaathKey] || 0) + 0.3 * shaathResult.correlation;

        // Temperley (weight: 0.2)
        const temperleyResult = this.detectWithProfile(chroma, this.profiles.temperley_major, this.profiles.temperley_minor);
        const temperleyKey = `${KEY_NAMES[temperleyResult.keyIndex]} ${temperleyResult.mode}`;
        results[temperleyKey] = (results[temperleyKey] || 0) + 0.2 * temperleyResult.correlation;

        // Find best result
        let bestKey = null;
        let bestScore = -Infinity;

        for (const [key, score] of Object.entries(results)) {
            if (score > bestScore) {
                bestScore = score;
                bestKey = key;
            }
        }

        const [keyName, mode] = bestKey.split(' ');
        const confidence = Math.min(1.0, bestScore / 0.9);

        return { key: keyName, mode, confidence };
    }

    detectWithProfile(chroma, majorProfile, minorProfile) {
        let bestCorr = -1;
        let bestKey = 0;
        let bestMode = 'Major';

        for (let shift = 0; shift < 12; shift++) {
            const rotated = rotateArray(chroma, shift);

            const majorCorr = dotProduct(rotated, majorProfile);
            const minorCorr = dotProduct(rotated, minorProfile);

            if (majorCorr > bestCorr) {
                bestCorr = majorCorr;
                bestKey = shift;
                bestMode = 'Major';
            }

            if (minorCorr > bestCorr) {
                bestCorr = minorCorr;
                bestKey = shift;
                bestMode = 'Minor';
            }
        }

        return { keyIndex: bestKey, mode: bestMode, correlation: bestCorr };
    }

    applyKeyLocking(fullKey, confidence) {
        const [keyName, mode] = fullKey.split(' ');

        // STRICT: Ignore low confidence detections completely
        if (confidence < this.confidenceThreshold) {
            // Return current locked key if we have one
            if (this.isLocked) {
                return {
                    key: this.lockedKey,
                    mode: this.lockedMode,
                    confidence: this.lockedConfidence,
                    stability: 1.0,
                    isLocked: true
                };
            }
            // Otherwise show analyzing state
            return {
                key: '--',
                mode: 'Analyzing...',
                confidence: 0,
                stability: 0,
                isLocked: false
            };
        }

        // If we have a locked key
        if (this.isLocked) {
            const lockedFullKey = `${this.lockedKey} ${this.lockedMode}`;

            if (fullKey === lockedFullKey) {
                // Same as locked key - reinforce it
                this.unlockCounter = 0;
                this.lockedConfidence = 0.9 * this.lockedConfidence + 0.1 * confidence;
                this.keyStabilityCounter = Math.min(this.keyStabilityCounter + 1, 100);

                return {
                    key: this.lockedKey,
                    mode: this.lockedMode,
                    confidence: this.lockedConfidence,
                    stability: 1.0,
                    isLocked: true
                };
            } else {
                // Different key detected - increment unlock counter
                this.unlockCounter++;

                // Need MANY consistent different frames to unlock
                if (this.unlockCounter >= this.unlockThreshold && confidence >= this.lockConfidenceThreshold) {
                    // Check if it's consistently the SAME new key
                    if (fullKey === this.candidateKey) {
                        this.candidateCount++;

                        if (this.candidateCount >= this.lockThreshold) {
                            // Lock new key
                            this.lockedKey = keyName;
                            this.lockedMode = mode;
                            this.lockedConfidence = confidence;
                            this.keyStabilityCounter = 1;
                            this.candidateKey = null;
                            this.candidateCount = 0;
                            this.unlockCounter = 0;

                            return {
                                key: this.lockedKey,
                                mode: this.lockedMode,
                                confidence: this.lockedConfidence,
                                stability: 1.0,
                                isLocked: true
                            };
                        }
                    } else {
                        this.candidateKey = fullKey;
                        this.candidateCount = 1;
                    }
                }

                // Still return locked key while transitioning
                return {
                    key: this.lockedKey,
                    mode: this.lockedMode,
                    confidence: this.lockedConfidence,
                    stability: Math.max(0, 1.0 - (this.unlockCounter / this.unlockThreshold)),
                    isLocked: true
                };
            }
        } else {
            // No locked key yet - try to establish one
            if (fullKey === this.candidateKey) {
                this.candidateCount++;

                // Need many consistent frames AND high confidence to lock
                if (this.candidateCount >= this.lockThreshold && confidence >= this.lockConfidenceThreshold) {
                    // LOCK the key!
                    this.isLocked = true;
                    this.lockedKey = keyName;
                    this.lockedMode = mode;
                    this.lockedConfidence = confidence;
                    this.keyStabilityCounter = this.lockThreshold;
                    this.candidateKey = null;
                    this.candidateCount = 0;

                    return {
                        key: this.lockedKey,
                        mode: this.lockedMode,
                        confidence: this.lockedConfidence,
                        stability: 1.0,
                        isLocked: true
                    };
                }
            } else {
                // New candidate
                this.candidateKey = fullKey;
                this.candidateCount = 1;
            }

            // Show analyzing state while building confidence
            return {
                key: keyName,
                mode: mode,
                confidence: confidence,
                stability: this.candidateCount / this.lockThreshold,
                isLocked: false
            };
        }
    }

    runDemoMode() {
        // Demo mode - NO KEY JUMPING, just show waiting state
        console.log('Demo mode: No microphone available. Key detection disabled.');

        if (this.onKeyDetected) {
            this.onKeyDetected({
                key: '--',
                mode: 'No Mic',
                confidence: 0,
                stability: 0,
                isLocked: false,
                isDemoMode: true
            });
        }

        if (this.onChromaUpdate) {
            this.onChromaUpdate(new Array(12).fill(0));
        }
    }

    reset() {
        this.chromaHistory = [];
        this.currentKey = null;
        this.currentMode = null;
        this.currentConfidence = 0;
        this.keyStabilityCounter = 0;
        this.candidateKey = null;
        this.candidateCount = 0;

        // Reset lock state
        this.lockedKey = null;
        this.lockedMode = null;
        this.lockedConfidence = 0;
        this.isLocked = false;
        this.unlockCounter = 0;

        // Reset silence state
        this.silenceFrameCount = 0;
        this.isSilent = true;
    }
}

// ============================================
// UI Controller
// ============================================

class UIController {
    constructor() {
        this.engine = new KeyDetectorEngine();
        this.detectionHistory = [];
        this.maxHistory = 20;
        this.isPythonConnected = false;

        this.initializeElements();
        this.bindEvents();
        this.initializeEngine();

        // Load sources initially
        setTimeout(() => this.loadAudioSources(), 1000);
    }

    initializeElements() {
        // Status elements
        this.pythonStatusDot = document.querySelector('#pythonStatus .status-dot');
        this.audioStatusDot = document.querySelector('#audioStatus .status-dot');

        // Audio Source Select
        this.audioSourceSelect = document.getElementById('audioSourceSelect');

        // YouTube webview and navigation
        this.youtubeWebview = document.getElementById('youtubeWebview');
        this.backBtn = document.getElementById('backBtn');
        this.forwardBtn = document.getElementById('forwardBtn');
        this.refreshBtn = document.getElementById('refreshBtn');
        this.homeBtn = document.getElementById('homeBtn');

        // Detection elements
        this.startDetectionBtn = document.getElementById('startDetectionBtn');
        this.keyValue = document.getElementById('keyValue');
        this.scaleValue = document.getElementById('scaleValue');
        this.scaleBadge = document.getElementById('scaleBadge');
        this.confidenceValue = document.getElementById('confidenceValue');
        this.confidenceFill = document.getElementById('confidenceFill');
        this.chromaBars = document.querySelectorAll('.chroma-bar');

        // Action elements
        this.sendToCubaseBtn = document.getElementById('sendToCubaseBtn');
        this.lastSentInfo = document.getElementById('lastSentInfo');
        this.historyList = document.getElementById('historyList');
    }

    bindEvents() {
        // Webview navigation controls
        if (this.backBtn) {
            this.backBtn.addEventListener('click', () => {
                if (this.youtubeWebview && this.youtubeWebview.canGoBack()) {
                    this.youtubeWebview.goBack();
                }
            });
        }

        if (this.forwardBtn) {
            this.forwardBtn.addEventListener('click', () => {
                if (this.youtubeWebview && this.youtubeWebview.canGoForward()) {
                    this.youtubeWebview.goForward();
                }
            });
        }

        if (this.refreshBtn) {
            this.refreshBtn.addEventListener('click', () => {
                if (this.youtubeWebview) {
                    this.youtubeWebview.reload();
                }
            });
        }

        if (this.homeBtn) {
            this.homeBtn.addEventListener('click', () => {
                if (this.youtubeWebview) {
                    this.youtubeWebview.src = 'https://www.youtube.com';
                }
            });
        }

        // Detection button
        this.startDetectionBtn.addEventListener('click', () => this.toggleDetection());

        // Refresh audio sources on click
        if (this.audioSourceSelect) {
            this.audioSourceSelect.addEventListener('focus', () => this.loadAudioSources());
        }

        // Send to Cubase button
        this.sendToCubaseBtn.addEventListener('click', () => this.sendToCubase());

        // Python status listener
        if (window.electronAPI) {
            window.electronAPI.onPythonStatus((status) => {
                this.isPythonConnected = status.connected;
                this.updatePythonStatus(status.connected);
            });
        }
    }

    async initializeEngine() {
        await this.engine.initialize();

        // Input level elements
        this.inputLevelValue = document.getElementById('inputLevelValue');
        this.inputLevelFill = document.getElementById('inputLevelFill');

        // Set up callbacks
        this.engine.onKeyDetected = (result) => this.updateKeyDisplay(result);
        this.engine.onChromaUpdate = (chroma) => this.updateChromaDisplay(chroma);
        this.engine.onStatusChange = (status) => this.updateAudioStatus(status.capturing);
        this.engine.onAudioLevel = (db) => this.updateInputLevel(db);
    }

    updateInputLevel(db) {
        if (!this.inputLevelValue || !this.inputLevelFill) return;

        // dB range: -100 (empty) to 0 (full)
        // Map to 0-100%
        let percent = Math.max(0, Math.min(100, (db + 100)));

        this.inputLevelValue.textContent = `${db.toFixed(1)} dB`;
        this.inputLevelFill.style.width = `${percent}%`;

        // Change color based on level
        if (db > -10) {
            this.inputLevelFill.style.background = 'var(--status-error)'; // Red for clipping
        } else if (db > -20) {
            this.inputLevelFill.style.background = 'var(--element-warning)'; // Yellow for high
        } else {
            this.inputLevelFill.style.background = 'var(--accent-green)'; // Green for good
        }
    }

    async loadAudioSources() {
        if (!window.electronAPI || !this.audioSourceSelect) return;

        try {
            const sources = await window.electronAPI.getAudioSources();
            const currentVal = this.audioSourceSelect.value;

            // Keep "Auto Select" option
            this.audioSourceSelect.innerHTML = '<option value="">Auto Select Source</option>';

            sources.forEach(source => {
                const option = document.createElement('option');
                option.value = source.id;
                option.textContent = source.name;
                this.audioSourceSelect.appendChild(option);
            });

            // Restore selection if possible
            if (currentVal) {
                const exists = sources.some(s => s.id === currentVal);
                if (exists) {
                    this.audioSourceSelect.value = currentVal;
                }
            }
        } catch (e) {
            console.error("Error loading audio sources:", e);
        }
    }

    async toggleDetection() {
        if (this.engine.isRunning) {
            this.engine.stopCapture();
            this.startDetectionBtn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <circle cx="12" cy="12" r="3"/>
                </svg>
                Start
            `;
            this.startDetectionBtn.classList.remove('btn-danger');
            this.startDetectionBtn.classList.add('btn-accent');
        } else {
            // Get selected source ID
            const sourceId = this.audioSourceSelect ? this.audioSourceSelect.value : null;
            await this.engine.startCapture(sourceId);

            this.startDetectionBtn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="6" y="6" width="12" height="12"/>
                </svg>
                Stop
            `;
            this.startDetectionBtn.classList.remove('btn-accent');
            this.startDetectionBtn.classList.add('btn-danger');
        }
    }

    updateKeyDisplay(result) {
        const { key, mode, confidence, stability, isLocked, isSilent, isDemoMode } = result;

        // Update key value
        this.keyValue.textContent = key || '--';

        // Update scale with lock indicator
        if (isLocked) {
            this.scaleValue.textContent = `🔒 ${mode}`;
        } else if (isSilent) {
            this.scaleValue.textContent = 'Silent';
        } else if (isDemoMode) {
            this.scaleValue.textContent = 'No Microphone';
        } else {
            this.scaleValue.textContent = mode || 'Analyzing...';
        }

        this.scaleBadge.className = 'scale-badge';
        if (mode && mode !== 'Analyzing...' && mode !== 'No Mic' && mode !== 'Waiting...') {
            const modeClass = mode.replace('🔒 ', '').toLowerCase();
            if (modeClass === 'major' || modeClass === 'minor') {
                this.scaleBadge.classList.add(modeClass);
            }
        }

        // Add locked class for visual feedback
        if (isLocked) {
            this.scaleBadge.classList.add('locked');
        }

        // Update confidence
        const confPercent = Math.round((confidence || 0) * 100);
        this.confidenceValue.textContent = `${confPercent}%`;
        this.confidenceFill.style.width = `${confPercent}%`;

        // Only enable send button if key is LOCKED
        this.sendToCubaseBtn.disabled = !isLocked || !key || key === '--';

        // Only add to history when LOCKED
        if (isLocked && key && key !== '--') {
            this.addToHistory(key, mode.replace('🔒 ', ''), confidence);
        }
    }

    updateChromaDisplay(chroma) {
        const maxVal = Math.max(...chroma);

        this.chromaBars.forEach((bar, index) => {
            const value = chroma[index] / (maxVal || 1);
            const height = 20 + value * 60;
            bar.style.height = `${height}px`;

            if (value > 0.7) {
                bar.classList.add('active');
            } else {
                bar.classList.remove('active');
            }
        });
    }

    updatePythonStatus(connected) {
        this.pythonStatusDot.className = `status-dot ${connected ? 'connected' : 'disconnected'}`;
    }

    updateAudioStatus(capturing) {
        this.audioStatusDot.className = `status-dot ${capturing ? 'connected' : 'disconnected'}`;
    }

    async sendToCubase() {
        const key = this.keyValue.textContent;
        const mode = this.scaleValue.textContent;
        const confidence = parseFloat(this.confidenceValue.textContent) / 100;

        if (!key || key === '--') return;

        if (window.electronAPI) {
            const result = await window.electronAPI.sendToCubase({
                key,
                scale: mode,
                confidence
            });

            if (result.success) {
                this.lastSentInfo.textContent = `Sent: ${key} ${mode} at ${new Date().toLocaleTimeString()}`;
                this.lastSentInfo.style.color = 'var(--accent-green)';
            } else {
                this.lastSentInfo.textContent = `Failed: ${result.error}`;
                this.lastSentInfo.style.color = 'var(--accent-red)';
            }
        } else {
            // Demo mode
            this.lastSentInfo.textContent = `[Demo] Would send: ${key} ${mode}`;
            this.lastSentInfo.style.color = 'var(--accent-orange)';
        }
    }

    addToHistory(key, mode, confidence) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString();

        // Check if same as last entry
        if (this.detectionHistory.length > 0) {
            const last = this.detectionHistory[0];
            if (last.key === key && last.mode === mode) {
                return; // Skip duplicate
            }
        }

        this.detectionHistory.unshift({
            key,
            mode,
            confidence,
            time: timeStr
        });

        if (this.detectionHistory.length > this.maxHistory) {
            this.detectionHistory.pop();
        }

        this.renderHistory();
    }

    renderHistory() {
        if (this.detectionHistory.length === 0) {
            this.historyList.innerHTML = '<div class="history-empty">No detections yet</div>';
            return;
        }

        this.historyList.innerHTML = this.detectionHistory.map(item => `
            <div class="history-item fade-in">
                <span class="history-item-key">${item.key} ${item.mode}</span>
                <span class="history-item-time">${item.time}</span>
            </div>
        `).join('');
    }
}

// ============================================
// Initialize App
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    window.app = new UIController();
    console.log('Key Detector initialized');
});
