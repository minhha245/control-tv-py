"""
Audio Processing Server for Essentia Key Detector
Handles audio decoding AND key detection to avoid Electron crashes
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import librosa
import numpy as np
import os
import sys

# Ensure terminal can handle Unicode if possible, or avoid crashing on print
try:
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except:
    pass

app = Flask(__name__)
CORS(app)  # Enable CORS for Electron

# Default analysis duration (can be changed via API)
DEFAULT_DURATION = 30

# Key profile sets: Krumhansl-Kessler, Temperley, Aarden-Essen
KK_MAJOR         = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR         = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
TEMPERLEY_MAJOR  = np.array([5.0,  2.0,  3.5,  2.0,  4.5,  4.0,  2.0,  4.5,  2.0,  3.5,  1.5,  4.0])
TEMPERLEY_MINOR  = np.array([5.0,  2.0,  3.5,  4.5,  2.0,  4.0,  2.0,  4.5,  3.5,  2.0,  1.5,  4.0])
AARDEN_MAJOR     = np.array([17.77, 0.15, 14.93, 0.16, 19.80, 11.36, 0.29, 22.06, 0.15, 8.15, 0.23, 4.95])
AARDEN_MINOR     = np.array([18.26, 0.74, 14.05, 16.86, 0.70, 14.44, 0.70, 18.62, 4.57, 1.93, 7.38, 1.76])

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

ALL_PROFILES = [
    (KK_MAJOR,        KK_MINOR),
    (TEMPERLEY_MAJOR, TEMPERLEY_MINOR),
    (AARDEN_MAJOR,    AARDEN_MINOR),
]

def detect_key_multi_profile(chroma):
    """Key detection using ensemble voting across 3 profile sets (KK, Temperley, Aarden)."""
    chroma_norm = chroma / (np.sum(chroma) + 1e-10)

    scores = {}
    for maj_prof, min_prof in ALL_PROFILES:
        for tonic in range(12):
            for prof, scale in [(maj_prof, 'Major'), (min_prof, 'Minor')]:
                corr = float(np.corrcoef(chroma_norm, np.roll(prof, tonic))[0, 1])
                key = (NOTE_NAMES[tonic], scale)
                scores[key] = scores.get(key, 0.0) + corr

    n = len(ALL_PROFILES)
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_key, best_score = sorted_items[0]
    avg_corr = best_score / n  # average correlation across profiles, -1..1

    confidence = int(max(0, min(100, (avg_corr + 1) * 50)))

    alternatives = [
        {'key': k[0], 'scale': k[1], 'correlation': round(v / n, 4)}
        for k, v in sorted_items[:5]
    ]

    return {
        'key': best_key[0],
        'scale': best_key[1],
        'confidence': confidence,
        'alternatives': alternatives
    }


@app.route('/decode-audio', methods=['POST'])
def decode_audio():
    """
    Decode audio file and return samples with configurable duration
    """
    try:
        # Get file path and duration from request
        data = request.get_json()
        file_path = data.get('filePath')
        duration = data.get('duration', DEFAULT_DURATION)  # Use global default
        
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 400
            
        # Validate duration (5-180 seconds)
        if not isinstance(duration, (int, float)) or not (5 <= duration <= 180):
            duration = DEFAULT_DURATION

        # Safe print for Windows console
        try:
            print(f'Decoding: {file_path} (duration: {duration}s)')
        except:
            print(f'Decoding: {os.path.basename(file_path).encode("ascii", "replace").decode("ascii")} (duration: {duration}s)')
        
        # Robust decoding with configurable duration
        import soundfile as sf
        y = None
        sr = 22050
        
        try:
            with open(file_path, 'rb') as f:
                info = sf.info(f)
                sr_native = info.samplerate
                f.seek(0)
                y, _ = sf.read(f, frames=int(sr_native * duration))
                if len(y.shape) > 1:
                    y = y.mean(axis=1)
                # Resample if needed
                if sr_native != sr:
                    y = librosa.resample(y, orig_sr=sr_native, target_sr=sr)
        except Exception as e:
            print(f"Soundfile failed: {e}, falling back to librosa")
            try:
                y, _ = librosa.load(file_path, sr=sr, mono=True, duration=duration)
            except Exception as lib_err:
                error_msg = f"[{type(lib_err).__name__}] {str(lib_err)}"
                if "NoBackendError" in error_msg:
                    error_msg += " - No audio backend found (install ffmpeg)"
                raise Exception(error_msg)
        
        print(f'Decoded: {len(y)} samples, {sr} Hz, {len(y)/sr:.2f} seconds')
        
        # Convert to list for JSON
        samples = y.tolist()
        
        return jsonify({
            'samples': samples,
            'sampleRate': int(sr),
            'duration': float(len(y) / sr),
            'numSamples': len(samples),
            'requestedDuration': duration
        })
        
    except Exception as e:
        error_msg = f"[{type(e).__name__}] {str(e)}"
        if "NoBackendError" in error_msg:
            error_msg += " - No audio backend found (install ffmpeg)"
        print(f'Error decoding audio: {error_msg}')
        return jsonify({'error': error_msg}), 500



def check_ffmpeg():
    """Check if ffmpeg is available in system PATH."""
    import shutil
    return shutil.which("ffmpeg") is not None

@app.route('/detect-key', methods=['POST'])
def detect_key():
    """
    Detect key from audio file with configurable duration
    """
    try:
        data = request.get_json()
        file_path = data.get('filePath')
        duration = data.get('duration', DEFAULT_DURATION)  # Use global default
        
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 400
            
        # Validate duration (5-180 seconds)
        if not isinstance(duration, (int, float)) or not (5 <= duration <= 180):
            duration = DEFAULT_DURATION

        # Safe print for Windows console
        try:
            print(f'Detecting key: {file_path} (duration: {duration}s)')
        except:
            print(f'Detecting key: {os.path.basename(file_path).encode("ascii", "replace").decode("ascii")} (duration: {duration}s)')
        
        # Robust decoding with configurable duration
        import soundfile as sf
        y = None
        sr = 22050
        
        try:
            with open(file_path, 'rb') as f:
                info = sf.info(f)
                sr_native = info.samplerate
                f.seek(0)
                y, _ = sf.read(f, frames=int(sr_native * duration))
                if len(y.shape) > 1:
                    y = y.mean(axis=1)
                # Resample if needed
                if sr_native != sr:
                    y = librosa.resample(y, orig_sr=sr_native, target_sr=sr)
        except Exception as e:
            print(f"Soundfile failed: {e}, falling back to librosa")
            try:
                # Check for unsupported formats early to provide better error
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ['.webm', '.m4a', '.opus'] and not check_ffmpeg():
                     raise Exception(f"Định dạng {ext} yêu cầu FFmpeg để giải mã. Hãy dùng file MP3 Cloud hoặc cài FFmpeg.")
                
                y, _ = librosa.load(file_path, sr=sr, mono=True, duration=duration)
            except Exception as lib_err:
                error_msg = f"[{type(lib_err).__name__}] {str(lib_err)}"
                if "NoBackendError" in error_msg:
                    error_msg += " - No audio backend found (install ffmpeg to support .webm/.m4a)"
                raise Exception(error_msg)
            
        # Separate harmonic content (removes drums/bass noise from chroma)
        y_harmonic, _ = librosa.effects.hpss(y)

        # CQT chroma on harmonic signal only
        chroma = librosa.feature.chroma_cqt(y=y_harmonic, sr=sr, hop_length=512)

        # Filter out low-energy frames (silence / noise-dominated)
        frame_energy = np.sqrt(np.sum(chroma ** 2, axis=0))
        energy_thresh = np.median(frame_energy) * 0.3
        chroma_active = chroma[:, frame_energy > energy_thresh]
        if chroma_active.shape[1] < 10:
            chroma_active = chroma  # fallback if too few active frames

        chroma_avg = np.mean(chroma_active, axis=1)

        # Detect key using 3-profile ensemble
        result = detect_key_multi_profile(chroma_avg)
        result['analyzedDuration'] = float(len(y) / sr)

        print(f'Detected: {result["key"]} {result["scale"]} ({result["confidence"]}%) from {result["analyzedDuration"]:.1f}s audio')
        
        return jsonify(result)
        
    except Exception as e:
        error_msg = f"[{type(e).__name__}] {str(e)}"
        print(f'Error detecting key: {error_msg}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})


@app.route('/set-default-duration', methods=['POST'])
def set_default_duration():
    """Set default analysis duration"""
    try:
        data = request.get_json()
        duration = data.get('duration', 30)
        
        # Validate duration
        if not isinstance(duration, (int, float)) or not (5 <= duration <= 120):
            return jsonify({'error': 'Duration must be between 5-120 seconds'}), 400
            
        # Store in global variable (you could also save to file)
        global DEFAULT_DURATION
        DEFAULT_DURATION = duration
        
        print(f'Default analysis duration set to: {duration}s')
        return jsonify({'success': True, 'duration': duration})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get-default-duration', methods=['GET'])
def get_default_duration():
    """Get current default analysis duration"""
    global DEFAULT_DURATION
    return jsonify({'duration': DEFAULT_DURATION})


def kill_port(port):
    """Find and kill process listening on specified port (Windows only)."""
    import subprocess
    import os
    try:
        # Find PID using netstat
        cmd = f"netstat -ano | findstr LISTENING | findstr :{port}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            pids = set()
            for line in lines:
                parts = line.split()
                if len(parts) > 4:
                    pids.add(parts[-1])
            
            for pid in pids:
                if int(pid) > 0 and int(pid) != os.getpid():
                    print(f"[Server] Killing existing process on port {port} (PID: {pid})...")
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
    except Exception as e:
        print(f"[Server] Error cleaning port {port}: {e}")

def run_server(port=5000):
    """Function to run the server from another thread."""
    # Ensure port is free BEFORE running in a thread if we're not already the main process handling it
    kill_port(port)
    print(f'Starting Audio Processing Server on http://localhost:{port}')
    # Suppress Flask startup messages
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False, threaded=True)

if __name__ == '__main__':
    run_server(5000)
