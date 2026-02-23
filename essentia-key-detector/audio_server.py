"""
Audio Processing Server for Essentia Key Detector
Handles audio decoding AND key detection to avoid Electron crashes
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import librosa
import numpy as np
import os

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
        
        print(f'Decoding: {file_path}')
        
        # Load only first 30 seconds for speed
        # Resample to 22050 Hz, mono
        y, sr = librosa.load(file_path, sr=22050, mono=True, duration=30)
        
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
        print(f'Error decoding audio: {e}')
        return jsonify({'error': str(e)}), 500


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
        
        print(f'Detecting key: {file_path}')
        
        # Load audio (first 30s)
        y, sr = librosa.load(file_path, sr=22050, mono=True, duration=30)
        
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
        print(f'Error detecting key: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    print('Starting Audio Processing Server on http://localhost:5000')
    app.run(host='127.0.0.1', port=5000, debug=False)
