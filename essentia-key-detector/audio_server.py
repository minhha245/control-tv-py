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

# Krumhansl-Kessler key profiles
KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def detect_key_krumhansl(chroma):
    """
    Krumhansl-Schmuckler key detection algorithm
    """
    # Normalize chroma
    chroma_norm = chroma / (np.sum(chroma) + 1e-10)
    
    max_corr = -1
    detected_key = 'C'
    detected_scale = 'Major'
    
    all_results = []
    
    # Test all 24 keys
    for tonic in range(12):
        # Test Major
        major_profile = np.roll(KK_MAJOR, tonic)
        major_corr = np.corrcoef(chroma_norm, major_profile)[0, 1]
        
        all_results.append({
            'key': NOTE_NAMES[tonic],
            'scale': 'Major',
            'correlation': float(major_corr)
        })
        
        if major_corr > max_corr:
            max_corr = major_corr
            detected_key = NOTE_NAMES[tonic]
            detected_scale = 'Major'
        
        # Test Minor
        minor_profile = np.roll(KK_MINOR, tonic)
        minor_corr = np.corrcoef(chroma_norm, minor_profile)[0, 1]
        
        all_results.append({
            'key': NOTE_NAMES[tonic],
            'scale': 'Minor',
            'correlation': float(minor_corr)
        })
        
        if minor_corr > max_corr:
            max_corr = minor_corr
            detected_key = NOTE_NAMES[tonic]
            detected_scale = 'Minor'
    
    # Sort by correlation
    all_results.sort(key=lambda x: x['correlation'], reverse=True)
    
    # Calculate confidence
    confidence = int(max(0, min(100, (max_corr + 1) * 50)))
    
    return {
        'key': detected_key,
        'scale': detected_scale,
        'confidence': confidence,
        'alternatives': all_results[:5]
    }


@app.route('/decode-audio', methods=['POST'])
def decode_audio():
    """
    Decode audio file and return samples (OPTIMIZED - first 30s only)
    """
    try:
        # Get file path from request
        data = request.get_json()
        file_path = data.get('filePath')
        
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 400
        
        # Safe print for Windows console
        try:
            print(f'Decoding: {file_path}')
        except:
            print(f'Decoding: {os.path.basename(file_path).encode("ascii", "replace").decode("ascii")}')
        
        # Robust decoding
        import soundfile as sf
        y = None
        sr = 22050
        
        try:
            with open(file_path, 'rb') as f:
                info = sf.info(f)
                sr_native = info.samplerate
                f.seek(0)
                y, _ = sf.read(f, frames=int(sr_native * 30))
                if len(y.shape) > 1:
                    y = y.mean(axis=1)
                # Resample if needed
                if sr_native != sr:
                    y = librosa.resample(y, orig_sr=sr_native, target_sr=sr)
        except Exception as e:
            print(f"Soundfile failed: {e}, falling back to librosa")
            try:
                y, _ = librosa.load(file_path, sr=sr, mono=True, duration=30)
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
            'numSamples': len(samples)
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
    Detect key from audio file (FAST - uses librosa chroma)
    """
    try:
        data = request.get_json()
        file_path = data.get('filePath')
        
        if not file_path or not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 400
        
        # Safe print for Windows console
        try:
            print(f'Detecting key: {file_path}')
        except:
            print(f'Detecting key: {os.path.basename(file_path).encode("ascii", "replace").decode("ascii")}')
        
        # Robust decoding
        import soundfile as sf
        y = None
        sr = 22050
        
        try:
            with open(file_path, 'rb') as f:
                info = sf.info(f)
                sr_native = info.samplerate
                f.seek(0)
                y, _ = sf.read(f, frames=int(sr_native * 30))
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
                
                y, _ = librosa.load(file_path, sr=sr, mono=True, duration=30)
            except Exception as lib_err:
                error_msg = f"[{type(lib_err).__name__}] {str(lib_err)}"
                if "NoBackendError" in error_msg:
                    error_msg += " - No audio backend found (install ffmpeg to support .webm/.m4a)"
                raise Exception(error_msg)
            
        # Extract chroma features using librosa (FAST & ACCURATE)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=2048)
        
        # Average over time
        chroma_avg = np.mean(chroma, axis=1)
        
        print(f'Chroma: {chroma_avg}')
        
        # Detect key using Krumhansl-Schmuckler
        result = detect_key_krumhansl(chroma_avg)
        
        print(f'Detected: {result["key"]} {result["scale"]} ({result["confidence"]}%)')
        
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
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    run_server(5000)
