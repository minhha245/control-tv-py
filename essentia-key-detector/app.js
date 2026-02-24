/**
 * Essentia Key Detector - Audio File Key Detection Engine
 * Upload audio files and detect key/scale using Essentia.js
 * Multi-profile voting with Krumhansl-Kessler & Temperley profiles
 */

// ============================================
// Constants & Key Profiles
// ============================================

const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

// Krumhansl-Kessler profiles
const KK_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88];
const KK_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17];

// Temperley profiles
const TEMPERLEY_MAJOR = [5.0, 2.0, 3.5, 2.0, 4.5, 4.0, 2.0, 4.5, 2.0, 3.5, 1.5, 4.0];
const TEMPERLEY_MINOR = [5.0, 2.0, 3.5, 4.5, 2.0, 4.0, 2.0, 4.5, 3.5, 2.0, 1.5, 4.0];

// Aarden-Essen profiles
const AARDEN_MAJOR = [17.7661, 0.145624, 14.9265, 0.160186, 19.8049, 11.3587, 0.291248, 22.062, 0.145624, 8.15494, 0.232998, 4.95122];
const AARDEN_MINOR = [18.2648, 0.737619, 14.0499, 16.8599, 0.702494, 14.4362, 0.702494, 18.6004, 4.56621, 1.93186, 7.37619, 1.75623];

// ============================================
// Utility Functions
// ============================================

function normalizeArray(arr) {
    const sum = arr.reduce((a, b) => a + b, 0);
    if (sum === 0) return arr.map(() => 0);
    return arr.map(v => v / sum);
}

function dotProduct(a, b) {
    return a.reduce((sum, val, i) => sum + val * b[i], 0);
}

function rotateArray(arr, shift) {
    const n = arr.length;
    const s = ((shift % n) + n) % n;
    return [...arr.slice(s), ...arr.slice(0, s)];
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function pearsonCorrelation(x, y) {
    const n = x.length;
    const meanX = x.reduce((a, b) => a + b, 0) / n;
    const meanY = y.reduce((a, b) => a + b, 0) / n;

    let numr = 0, denomX = 0, denomY = 0;
    for (let i = 0; i < n; i++) {
        const dx = x[i] - meanX;
        const dy = y[i] - meanY;
        numr += dx * dy;
        denomX += dx * dx;
        denomY += dy * dy;
    }

    const denom = Math.sqrt(denomX * denomY);
    return denom === 0 ? 0 : numr / denom;
}

// ============================================
// Key Detection Engine
// ============================================

class KeyDetectionEngine {
    constructor() {
        this.essentia = null;
        this.isReady = false;
        this.audioContext = null;
        this.fileHistory = [];
        this.activeFileIndex = -1;

        // UI elements (will be bound)
        this.dropZone = null;
        this.browseBtn = null;
        this.fileList = null;
        this.progressContainer = null;
        this.progressFill = null;
        this.progressPercent = null;
        this.progressLabel = null;
        this.keyValue = null;
        this.scaleValue = null;
        this.scaleBadge = null;
        this.confidenceValue = null;
        this.confidenceFill = null;
        this.chromaBars = null;
        this.fileInfo = null;
        this.fileName = null;
        this.fileSize = null;
        this.analysisTime = null;
        this.altKeysSection = null;
        this.altKeysList = null;
    }

    async initialize() {
        try {
            if (typeof EssentiaWASM !== 'undefined') {
                const wasmModule = await EssentiaWASM();
                this.essentia = new Essentia(wasmModule);
                this.isReady = true;
                console.log('Essentia.js initialized successfully');
            }
        } catch (e) {
            console.error('Essentia init error:', e);
        }

        this.bindUIElements();
        this.bindEvents();
        return true;
    }

    bindUIElements() {
        this.dropZone = document.getElementById('dropZone');
        this.browseBtn = document.getElementById('browseBtn');
        this.fileList = document.getElementById('fileList');
        this.progressContainer = document.getElementById('progressContainer');
        this.progressFill = document.getElementById('progressFill');
        this.progressPercent = document.getElementById('progressPercent');
        this.progressLabel = document.getElementById('progressLabel');
        this.keyValue = document.getElementById('keyValue');
        this.scaleValue = document.getElementById('scaleValue');
        this.scaleBadge = document.getElementById('scaleBadge');
        this.confidenceValue = document.getElementById('confidenceValue');
        this.confidenceFill = document.getElementById('confidenceFill');
        this.chromaBars = document.getElementById('chromaBars');
        this.fileInfo = document.getElementById('fileInfo');
        this.fileName = document.getElementById('fileName');
        this.fileSize = document.getElementById('fileSize');
        this.analysisTime = document.getElementById('analysisTime');
        this.altKeysSection = document.getElementById('altKeysSection');
        this.altKeysList = document.getElementById('altKeysList');
    }

    bindEvents() {
        // Drag and drop events
        if (this.dropZone) {
            this.dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                this.dropZone.classList.add('drag-over');
            });

            this.dropZone.addEventListener('dragleave', (e) => {
                e.preventDefault();
                this.dropZone.classList.remove('drag-over');
            });

            this.dropZone.addEventListener('drop', async (e) => {
                e.preventDefault();
                this.dropZone.classList.remove('drag-over');

                // Try to get file path from Electron
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    const file = files[0];

                    // If running in Electron and file has path, use Electron API
                    if (window.electronAPI && file.path) {
                        console.log('Using Electron API for dropped file:', file.path);
                        const fileInfo = {
                            path: file.path,
                            name: file.name,
                            size: file.size
                        };

                        try {
                            this.showProgress();
                            this.updateProgress(0, 'Đang đọc file...');

                            const buffer = await window.electronAPI.readAudioFile(file.path);
                            if (!buffer) {
                                throw new Error('Không thể đọc file');
                            }

                            const arrayBuffer = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);
                            await this.analyzeAudioBuffer(arrayBuffer, fileInfo);
                        } catch (err) {
                            console.error('Error reading dropped file:', err);
                            alert('Lỗi: ' + err.message);
                            this.hideProgress();
                        }
                    } else {
                        // Fallback to browser File API
                        await this.handleFileSelect(file);
                    }
                }
            });

            // Click to browse
            this.dropZone.addEventListener('click', () => {
                this.browseFile();
            });
        }

        // Browse button
        if (this.browseBtn) {
            this.browseBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.browseFile();
            });
        }
    }

    browseFile() {
        // Use Electron file dialog instead of browser input
        if (window.electronAPI) {
            this.openElectronFileDialog();
        } else {
            // Fallback to browser file input
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'audio/*';
            input.onchange = async (e) => {
                if (e.target.files.length > 0) {
                    await this.handleFileSelect(e.target.files[0]);
                }
            };
            input.click();
        }
    }

    async openElectronFileDialog() {
        try {
            const fileInfo = await window.electronAPI.openFileDialog();
            if (!fileInfo) return;

            console.log('File selected via Electron:', fileInfo);

            this.showProgress();
            this.updateProgress(0, 'Đang kiểm tra Python server...');

            // Check if Python server is running
            console.log('Checking Python server...');
            const pythonReady = await window.electronAPI.checkPythonServer();
            console.log('Python server ready:', pythonReady);

            if (pythonReady) {
                console.log('Using Python server for key detection');
                await this.detectKeyViaPython(fileInfo);
            } else {
                console.warn('Python server not available');
                this.hideProgress();

                const retry = confirm('Python server chưa chạy.\n\nVui lòng chạy: python audio_server.py\n\nBấm OK để thử lại, Cancel để hủy.');
                if (retry) {
                    setTimeout(() => this.openElectronFileDialog(), 1000);
                }
            }
        } catch (err) {
            console.error('Electron file dialog error:', err);
            alert('Lỗi: ' + err.message);
            this.hideProgress();
        }
    }

    async detectKeyViaPython(fileInfo) {
        const startTime = performance.now();

        try {
            this.showProgress();
            this.updateProgress(10, 'Đang phân tích key qua Python...');

            // Detect key via Python (FAST & ACCURATE)
            const result = await window.electronAPI.detectKeyPython(fileInfo.path);

            if (!result || result.error) {
                throw new Error(result?.error || 'Python key detection failed');
            }

            console.log('Python detected:', result);

            this.updateProgress(90, 'Đang hoàn tất...');

            const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);

            // Generate chroma for visualization
            const chroma = new Array(12).fill(0);
            const keyMap = {
                'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5,
                'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11
            };
            const keyIndex = keyMap[result.key] || 0;
            chroma[keyIndex] = 1.0;
            chroma[(keyIndex + 7) % 12] = 0.7; // Fifth
            chroma[(keyIndex + 4) % 12] = 0.6; // Third (major) or minor third

            // Add to history
            const historyItem = {
                name: fileInfo.name,
                size: fileInfo.size,
                key: result.key,
                scale: result.scale,
                confidence: result.confidence,
                chroma: chroma,
                alternatives: result.alternatives || [],
                analysisTime: elapsed,
                timestamp: new Date()
            };

            this.fileHistory.unshift(historyItem);
            this.activeFileIndex = 0;

            // Update UI
            this.displayResult(historyItem);
            this.renderFileList();

            this.updateProgress(100, 'Hoàn tất!');
            setTimeout(() => this.hideProgress(), 1000);

        } catch (err) {
            console.error('Python key detection error:', err);
            alert('Lỗi: ' + err.message);
            this.hideProgress();
        }
    }

    async decodeViaPython(fileInfo) {
        const startTime = performance.now();

        try {
            this.showProgress();
            this.updateProgress(0, 'Đang decode audio qua Python...');

            // Decode via Python server
            const audioData = await window.electronAPI.decodeAudioPython(fileInfo.path);

            if (!audioData) {
                throw new Error('Python decode failed');
            }

            console.log('Python decoded:', audioData.numSamples, 'samples,', audioData.sampleRate, 'Hz');

            // Convert array to Float32Array
            const samples = new Float32Array(audioData.samples);

            this.updateProgress(20, 'Đang phân tích key...');

            // Extract chroma or get direct result
            const chromaOrResult = await this.extractChroma(samples, audioData.sampleRate);

            let result;

            // Check if Essentia returned direct result
            if (chromaOrResult.directResult) {
                console.log('Using Essentia direct result');
                result = {
                    key: chromaOrResult.key,
                    scale: chromaOrResult.scale,
                    confidence: chromaOrResult.confidence,
                    alternatives: []
                };

                // Generate fake chroma for visualization
                const chroma = new Array(12).fill(0);
                const keyMap = {
                    'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5,
                    'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11
                };
                const keyIndex = keyMap[result.key] || 0;
                chroma[keyIndex] = 1.0;
                chroma[(keyIndex + 7) % 12] = 0.7; // Fifth
                chroma[(keyIndex + 4) % 12] = 0.6; // Third

                result.chroma = chroma;
            } else {
                // Use Krumhansl-Schmuckler on chroma
                this.updateProgress(50, 'Đang tính correlation...');
                const chroma = chromaOrResult;
                result = this.detectKey(chroma);
                result.chroma = chroma;
            }

            this.updateProgress(90, 'Đang hoàn tất...');

            const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);

            // Add to history
            const historyItem = {
                name: fileInfo.name,
                size: fileInfo.size,
                key: result.key,
                scale: result.scale,
                confidence: result.confidence,
                chroma: result.chroma,
                alternatives: result.alternatives || [],
                analysisTime: elapsed,
                timestamp: new Date()
            };

            this.fileHistory.unshift(historyItem);
            this.activeFileIndex = 0;

            // Update UI
            this.displayResult(historyItem);
            this.renderFileList();

            this.updateProgress(100, 'Hoàn tất!');
            setTimeout(() => this.hideProgress(), 1000);

        } catch (err) {
            console.error('Python decode error:', err);
            alert('Lỗi: ' + err.message);
            this.hideProgress();
        }
    }

    async decodeAndAnalyze(arrayBuffer, fileInfo) {
        const startTime = performance.now();

        try {
            this.updateProgress(5, 'Đang decode audio...');

            // Create fresh AudioContext for each decode to avoid crashes
            const tempContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 22050
            });

            console.log('Decoding with fresh AudioContext...');

            // Decode with timeout
            const audioBuffer = await Promise.race([
                tempContext.decodeAudioData(arrayBuffer),
                new Promise((_, reject) =>
                    setTimeout(() => reject(new Error('Decode timeout')), 30000)
                )
            ]);

            console.log('Decoded:', audioBuffer.duration, 's,', audioBuffer.numberOfChannels, 'ch');

            // Get mono samples
            let samples;
            if (audioBuffer.numberOfChannels === 1) {
                samples = audioBuffer.getChannelData(0);
            } else {
                const left = audioBuffer.getChannelData(0);
                const right = audioBuffer.getChannelData(1);
                samples = new Float32Array(left.length);
                for (let i = 0; i < left.length; i++) {
                    samples[i] = (left[i] + right[i]) / 2;
                }
            }

            // Close temp context
            await tempContext.close();

            this.updateProgress(20, 'Đang phân tích chroma...');

            // Extract chroma
            const chroma = await this.extractChroma(samples, audioBuffer.sampleRate);
            this.updateProgress(50, 'Đang tính correlation...');

            // Detect key
            const result = this.detectKey(chroma);
            this.updateProgress(90, 'Đang hoàn tất...');

            const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);

            // Add to history
            const historyItem = {
                name: fileInfo.name,
                size: fileInfo.size,
                key: result.key,
                scale: result.scale,
                confidence: result.confidence,
                chroma: chroma,
                alternatives: result.alternatives,
                analysisTime: elapsed,
                timestamp: new Date()
            };

            this.fileHistory.unshift(historyItem);
            this.activeFileIndex = 0;

            // Update UI
            this.displayResult(historyItem);
            this.renderFileList();

            this.updateProgress(100, 'Hoàn tất!');
            setTimeout(() => this.hideProgress(), 1000);

        } catch (err) {
            console.error('Decode and analyze error:', err);
            alert('Lỗi: ' + err.message);
            this.hideProgress();
        }
    }

    async handleFileSelect(file) {
        if (!file.type.startsWith('audio/')) {
            alert('Vui lòng chọn file audio');
            return;
        }

        // Limit file size to 50MB
        const maxSize = 50 * 1024 * 1024;
        if (file.size > maxSize) {
            alert('File quá lớn! Vui lòng chọn file nhỏ hơn 50MB');
            return;
        }

        // Check if engine is ready
        if (!this.isReady) {
            alert('Engine chưa sẵn sàng. Vui lòng đợi...');
            return;
        }

        try {
            const fileInfo = {
                name: file.name,
                size: file.size,
                path: file.path || file.name
            };

            this.showProgress();
            this.updateProgress(0, 'Đang đọc file...');

            console.log('Reading file:', fileInfo.name, 'Size:', fileInfo.size);

            const arrayBuffer = await file.arrayBuffer();
            console.log('ArrayBuffer loaded, size:', arrayBuffer.byteLength);

            await this.analyzeAudioBuffer(arrayBuffer, fileInfo);
        } catch (err) {
            console.error('File select error:', err);
            alert('Lỗi khi đọc file: ' + err.message);
            this.hideProgress();
        }
    }

    /**
     * Decode audio file buffer to mono float32 samples
     * Resamples to 11025Hz to reduce memory usage and processing time
     */
    async decodeAudioFile(arrayBuffer) {
        try {
            console.log('Decoding audio, buffer size:', arrayBuffer.byteLength);

            if (!this.audioContext) {
                // Use lower sample rate to reduce memory
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                    sampleRate: 22050
                });
                console.log('AudioContext created, sample rate:', this.audioContext.sampleRate);
            }

            // Decode original audio with timeout protection
            console.log('Starting decodeAudioData...');

            const audioBuffer = await Promise.race([
                this.audioContext.decodeAudioData(arrayBuffer.slice(0)), // Clone buffer
                new Promise((_, reject) =>
                    setTimeout(() => reject(new Error('Decode timeout')), 30000)
                )
            ]);

            console.log('Audio decoded:', audioBuffer.duration, 'seconds,', audioBuffer.numberOfChannels, 'channels');

            // Get mono samples directly if already mono
            if (audioBuffer.numberOfChannels === 1) {
                const samples = audioBuffer.getChannelData(0);
                console.log('Using mono channel directly, samples:', samples.length);
                return {
                    samples: samples,
                    sampleRate: audioBuffer.sampleRate,
                    duration: audioBuffer.duration,
                    numChannels: 1
                };
            }

            // Mix to mono if stereo
            const leftChannel = audioBuffer.getChannelData(0);
            const rightChannel = audioBuffer.getChannelData(1);
            const monoSamples = new Float32Array(leftChannel.length);

            for (let i = 0; i < leftChannel.length; i++) {
                monoSamples[i] = (leftChannel[i] + rightChannel[i]) / 2;
            }

            console.log('Mixed to mono, samples:', monoSamples.length);

            return {
                samples: monoSamples,
                sampleRate: audioBuffer.sampleRate,
                duration: audioBuffer.duration,
                numChannels: 1
            };
        } catch (err) {
            console.error('Audio decode error:', err);
            throw new Error('Không thể decode file audio: ' + err.message);
        }
    }

    async processFile(fileInfo) {
        if (!window.electronAPI) return;

        try {
            this.showProgress();
            this.updateProgress(1, 'Đang đọc file...');

            // Read file via Electron main process (more stable than fetch file://)
            const buffer = await window.electronAPI.readAudioFile(fileInfo.path);

            if (!buffer) {
                throw new Error('Lỗi đọc file từ đĩa');
            }

            // Convert Node Buffer to ArrayBuffer
            const arrayBuffer = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength);

            this.updateProgress(5, 'Đang giải mã audio...');
            await this.analyzeAudioBuffer(arrayBuffer, fileInfo);
        } catch (err) {
            console.error('Error processing file:', err);
            this.showProgress();
            this.updateProgress(0, 'Lỗi: ' + err.message);
            setTimeout(() => this.hideProgress(), 3000);
        }
    }

    async analyzeAudioBuffer(arrayBuffer, fileInfo) {
        this.showProgress();
        this.updateProgress(0, 'Đang decode audio...');

        const startTime = performance.now();

        try {
            // Decode audio
            const audioData = await this.decodeAudioFile(arrayBuffer);
            this.updateProgress(10, 'Đang phân tích chroma...');

            // Extract chroma features using Essentia.js
            const chroma = await this.extractChroma(audioData.samples, audioData.sampleRate);
            this.updateProgress(30, 'Đang tính correlation...');

            // Detect key using Krumhansl-Schmuckler algorithm
            const result = this.detectKey(chroma);

            this.updateProgress(90, 'Đang hoàn tất...');

            const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);

            // Add to history
            const historyItem = {
                name: fileInfo.name,
                size: fileInfo.size,
                key: result.key,
                scale: result.scale,
                confidence: result.confidence,
                chroma: chroma,
                alternatives: result.alternatives,
                analysisTime: elapsed,
                timestamp: new Date()
            };

            this.fileHistory.unshift(historyItem);
            this.activeFileIndex = 0;

            // Update UI
            this.displayResult(historyItem);
            this.renderFileList();

            this.updateProgress(100, 'Hoàn tất!');
            setTimeout(() => this.hideProgress(), 1000);

        } catch (err) {
            console.error('Analysis error:', err);
            alert('Lỗi phân tích: ' + err.message);
            this.updateProgress(0, 'Lỗi: ' + err.message);
            setTimeout(() => this.hideProgress(), 3000);
        }
    }

    /**
     * Extract chroma features using Essentia.js
     * Uses HPCP (Harmonic Pitch Class Profile) for better key detection
     */
    async extractChroma(samples, sampleRate) {
        console.log('Extracting chroma with Essentia.js Key algorithm');

        if (!this.essentia || !this.essentia.Key) {
            console.warn('Essentia Key not available, using fallback');
            return this.computeSimpleChroma(samples, sampleRate);
        }

        try {
            // Use Essentia's built-in Key algorithm (most accurate)
            const keyResult = this.essentia.Key(samples);

            console.log('Essentia Key result:', keyResult);

            // keyResult contains: key, scale, strength
            // Convert to our format
            const keyMap = {
                'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5,
                'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11
            };

            const keyIndex = keyMap[keyResult.key] || 0;
            const scale = keyResult.scale === 'major' ? 'Major' : 'Minor';
            const confidence = Math.round(keyResult.strength * 100);

            // Return result directly without chroma
            return {
                directResult: true,
                key: keyResult.key,
                scale: scale,
                confidence: confidence
            };

        } catch (e) {
            console.error('Essentia Key error:', e);
            return this.computeSimpleChroma(samples, sampleRate);
        }
    }

    /**
     * Fallback: Compute chroma using DFT with proper tuning (OPTIMIZED)
     */
    computeSimpleChroma(samples, sampleRate = 22050) {
        const chroma = new Array(12).fill(0);
        const frameSize = 4096; // Reduced from 8192
        const hopSize = 2048; // Larger hop = fewer frames

        // Only analyze first 30 seconds for speed
        const maxSamples = Math.min(samples.length, sampleRate * 30);

        const A4 = 440.0;

        const numFrames = Math.floor((maxSamples - frameSize) / hopSize);

        for (let frame = 0; frame < numFrames; frame++) {
            const start = frame * hopSize;
            const end = Math.min(start + frameSize, maxSamples);

            if (end - start < frameSize) continue;

            const frameData = samples.slice(start, end);

            // Apply Hann window
            const windowed = new Float32Array(frameSize);
            for (let i = 0; i < frameSize; i++) {
                const window = 0.5 * (1 - Math.cos(2 * Math.PI * i / frameSize));
                windowed[i] = frameData[i] * window;
            }

            // For each pitch class
            for (let pc = 0; pc < 12; pc++) {
                let pcEnergy = 0;

                // Only 3 octaves (C3-C6) for speed
                for (let octave = 3; octave <= 5; octave++) {
                    const noteFreq = 261.63 * Math.pow(2, (octave - 4) + pc / 12);

                    // Only 2 harmonics for speed
                    for (let harmonic = 1; harmonic <= 2; harmonic++) {
                        const freq = noteFreq * harmonic;

                        if (freq >= sampleRate / 2) continue;

                        const bin = freq * frameSize / sampleRate;
                        const binLow = Math.floor(bin);
                        const binHigh = Math.ceil(bin);

                        if (binLow >= 0 && binHigh < frameSize / 2) {
                            let energy = 0;

                            // Simple DFT for these bins
                            for (const b of [binLow, binHigh]) {
                                let re = 0, im = 0;
                                for (let n = 0; n < frameSize; n++) {
                                    const angle = 2 * Math.PI * b * n / frameSize;
                                    re += windowed[n] * Math.cos(angle);
                                    im -= windowed[n] * Math.sin(angle);
                                }
                                energy += Math.sqrt(re * re + im * im);
                            }

                            const harmonicWeight = 1.0 / harmonic;
                            const octaveWeight = octave === 4 ? 1.5 : 1.0; // Favor C4 octave

                            pcEnergy += energy * harmonicWeight * octaveWeight;
                        }
                    }
                }

                chroma[pc] += pcEnergy;
            }
        }

        // Normalize
        const maxVal = Math.max(...chroma);
        if (maxVal > 0) {
            return chroma.map(v => v / maxVal);
        }

        return chroma;
    }

    /**
     * Krumhansl-Schmuckler key detection algorithm
     * Compares extracted chroma against all 24 key profiles
     */
    detectKey(chroma) {
        const profiles = [
            { name: 'KK', major: KK_MAJOR, minor: KK_MINOR },
            { name: 'Temperley', major: TEMPERLEY_MAJOR, minor: TEMPERLEY_MINOR },
            { name: 'Aarden', major: AARDEN_MAJOR, minor: AARDEN_MINOR }
        ];

        const results = [];

        // Normalize chroma
        const normChroma = normalizeArray(chroma);

        // Compare against each key profile
        profiles.forEach(profile => {
            // Test all major keys
            for (let i = 0; i < 12; i++) {
                const rotatedProfile = rotateArray(profile.major, i);
                const correlation = pearsonCorrelation(normChroma, normalizeArray(rotatedProfile));
                results.push({
                    key: NOTE_NAMES[i],
                    scale: 'Major',
                    profile: profile.name,
                    correlation: correlation
                });
            }

            // Test all minor keys
            for (let i = 0; i < 12; i++) {
                const rotatedProfile = rotateArray(profile.minor, i);
                const correlation = pearsonCorrelation(normChroma, normalizeArray(rotatedProfile));
                results.push({
                    key: NOTE_NAMES[i],
                    scale: 'Minor',
                    profile: profile.name,
                    correlation: correlation
                });
            }
        });

        // Average correlations for each key (across all profiles)
        const keyScores = {};
        results.forEach(r => {
            const key = `${r.key} ${r.scale}`;
            if (!keyScores[key]) keyScores[key] = { sum: 0, count: 0, correlations: [] };
            keyScores[key].sum += r.correlation;
            keyScores[key].count++;
            keyScores[key].correlations.push(r.correlation);
        });

        // Sort by average correlation
        const sortedKeys = Object.entries(keyScores)
            .map(([key, data]) => ({
                key: key.split(' ')[0],
                scale: key.split(' ')[1],
                avgCorrelation: data.sum / data.count,
                correlations: data.correlations
            }))
            .sort((a, b) => b.avgCorrelation - a.avgCorrelation);

        const best = sortedKeys[0];

        // Calculate confidence (normalized correlation)
        const minCorr = sortedKeys[sortedKeys.length - 1].avgCorrelation;
        const maxCorr = sortedKeys[0].avgCorrelation;
        const range = maxCorr - minCorr || 1;
        const confidence = Math.round(((best.avgCorrelation - minCorr) / range) * 100);

        // Get top alternatives
        const alternatives = sortedKeys.slice(0, 5).map(k => ({
            key: k.key,
            scale: k.scale,
            avgCorrelation: k.avgCorrelation
        }));

        return {
            key: best.key,
            scale: best.scale,
            confidence: Math.max(confidence, 20), // Minimum 20%
            alternatives: alternatives
        };
    }

    showProgress() {
        if (this.progressContainer) this.progressContainer.style.display = 'block';
    }

    hideProgress() {
        if (this.progressContainer) this.progressContainer.style.display = 'none';
    }

    updateProgress(percent, label) {
        if (this.progressFill) this.progressFill.style.width = percent + '%';
        if (this.progressPercent) this.progressPercent.textContent = percent + '%';
        if (label && this.progressLabel) this.progressLabel.textContent = label;
    }

    displayResult(item) {
        if (!item) return;

        // Key display
        if (this.keyValue) this.keyValue.textContent = item.key || '--';

        // Scale badge
        if (this.scaleBadge) {
            this.scaleBadge.className = 'scale-badge';
            if (item.scale === 'Major') {
                this.scaleBadge.classList.add('major');
                if (this.scaleValue) this.scaleValue.textContent = (item.key || '--') + ' Major';
            } else if (item.scale === 'Minor') {
                this.scaleBadge.classList.add('minor');
                if (this.scaleValue) this.scaleValue.textContent = (item.key || '--') + ' Minor';
            } else {
                if (this.scaleValue) this.scaleValue.textContent = '--';
            }
        }

        // File info
        if (this.fileInfo) this.fileInfo.style.display = 'block';
        if (this.fileName) this.fileName.textContent = item.name || '-';
        if (this.fileSize) this.fileSize.textContent = formatFileSize(item.size || 0);
        if (this.analysisTime) this.analysisTime.textContent = (item.analysisTime || '0') + 's';

        // Confidence
        if (this.confidenceValue) this.confidenceValue.textContent = (item.confidence || 0) + '%';
        if (this.confidenceFill) this.confidenceFill.style.width = (item.confidence || 0) + '%';

        // Color confidence bar based on level
        if (this.confidenceFill) {
            if (item.confidence >= 70) {
                this.confidenceFill.style.background = 'var(--gradient-success)';
            } else if (item.confidence >= 40) {
                this.confidenceFill.style.background = 'var(--gradient-primary)';
            } else {
                this.confidenceFill.style.background = 'var(--accent-orange)';
            }
        }

        // Alternative keys
        if (this.altKeysSection && this.altKeysList) {
            if (item.alternatives && item.alternatives.length > 1) {
                this.altKeysSection.style.display = 'block';
                this.altKeysList.innerHTML = item.alternatives.slice(1, 4).map(alt => `
                    <div class="alt-key-item">
                        <span class="alt-key-name">${alt.key} ${alt.scale}</span>
                        <span class="alt-key-score">${(alt.correlation * 100).toFixed(1)}%</span>
                    </div>
                `).join('');
            } else {
                this.altKeysSection.style.display = 'none';
            }
        }

        // Chroma bars
        this.updateChromaDisplay(item.chroma, item.key);
    }

    updateChromaDisplay(chroma, rootKey) {
        if (!chroma || !this.chromaBars) return;
        const bars = this.chromaBars.querySelectorAll('.chroma-bar');
        const maxVal = Math.max(...chroma);

        bars.forEach((bar, i) => {
            const height = maxVal > 0 ? 20 + (chroma[i] / maxVal) * 60 : 20;
            bar.style.height = height + 'px';

            bar.classList.remove('active', 'root');
            const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
            if (noteNames[i] === rootKey) {
                bar.classList.add('root');
            } else if (maxVal > 0 && (chroma[i] / maxVal) > 0.5) {
                bar.classList.add('active');
            }
        });
    }

    resetDisplay() {
        if (this.keyValue) this.keyValue.textContent = '--';
        if (this.scaleValue) this.scaleValue.textContent = 'Đang chờ...';
        if (this.scaleBadge) this.scaleBadge.className = 'scale-badge';
        if (this.confidenceValue) this.confidenceValue.textContent = '0%';
        if (this.confidenceFill) this.confidenceFill.style.width = '0%';
        if (this.fileInfo) this.fileInfo.style.display = 'none';
        if (this.altKeysSection) this.altKeysSection.style.display = 'none';

        if (this.chromaBars) {
            const bars = this.chromaBars.querySelectorAll('.chroma-bar');
            bars.forEach(bar => {
                bar.style.height = '20px';
                bar.classList.remove('active', 'root');
            });
        }
    }

    renderFileList() {
        if (!this.fileList) return;

        if (this.fileHistory.length === 0) {
            this.fileList.innerHTML = '<div class="file-list-empty">Chưa có file nào được phân tích</div>';
            return;
        }

        this.fileList.innerHTML = this.fileHistory.map((item, index) => `
            <div class="file-item ${index === this.activeFileIndex ? 'active' : ''}" data-index="${index}">
                <div class="file-item-left">
                    <div class="file-item-icon">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M9 18V5l12-2v13"/>
                            <circle cx="6" cy="18" r="3"/>
                            <circle cx="18" cy="16" r="3"/>
                        </svg>
                    </div>
                    <div class="file-item-info">
                        <div class="file-item-name">${item.name}</div>
                        <div class="file-item-meta">${formatFileSize(item.size)} · ${item.analysisTime}s</div>
                    </div>
                </div>
                <div class="file-item-right">
                    <span class="file-item-key">${item.key || '--'} ${item.scale ? item.scale.charAt(0) : ''}</span>
                    <span class="file-item-confidence">${item.confidence || 0}%</span>
                </div>
            </div>
        `).join('');

        // Bind click events
        this.fileList.querySelectorAll('.file-item').forEach(el => {
            el.addEventListener('click', () => {
                const idx = parseInt(el.dataset.index);
                this.activeFileIndex = idx;
                this.displayResult(this.fileHistory[idx]);
                this.renderFileList();
            });
        });
    }
}


// ============================================
// Initialize App
// ============================================

document.addEventListener('DOMContentLoaded', async () => {
    // Global error handler
    window.addEventListener('error', (e) => {
        console.error('Global error:', e.error);
        alert('Lỗi: ' + e.error.message);
    });

    window.addEventListener('unhandledrejection', (e) => {
        console.error('Unhandled promise rejection:', e.reason);
        alert('Lỗi async: ' + e.reason);
    });

    try {
        // Initialize Essentia first
        if (typeof EssentiaWASM !== 'undefined') {
            console.log('Loading Essentia WASM...');
            await EssentiaWASM();
            console.log('Essentia WASM loaded');
        } else {
            console.warn('EssentiaWASM not found, will use fallback');
        }

        window.app = new KeyDetectionEngine();
        await window.app.initialize();
        console.log('Essentia Key Detector initialized');
    } catch (err) {
        console.error('Initialization error:', err);
        alert('Lỗi khởi tạo: ' + err.message);
    }
});
