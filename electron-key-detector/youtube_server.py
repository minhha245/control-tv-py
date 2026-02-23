"""
YouTube Download & Key Detection Server
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import librosa
import numpy as np
import os
import tempfile

app = Flask(__name__)
CORS(app)

# Krumhansl-Kessler key profiles
KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def detect_key_krumhansl(chroma):
    """Krumhansl-Schmuckler key detection"""
    chroma_norm = chroma / (np.sum(chroma) + 1e-10)
    
    max_corr = -1
    detected_key = 'C'
    detected_scale = 'Major'
    
    all_results = []
    
    for tonic in range(12):
        # Major
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
        
        # Minor
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
    
    all_results.sort(key=lambda x: x['correlation'], reverse=True)
    confidence = int(max(0, min(100, (max_corr + 1) * 50)))
    
    return {
        'key': detected_key,
        'scale': detected_scale,
        'confidence': confidence,
        'alternatives': all_results[:5]
    }


@app.route('/download-and-detect', methods=['POST'])
def download_and_detect():
    """Download YouTube video and detect key"""
    try:
        data = request.get_json()
        video_url = data.get('url')
        
        if not video_url:
            return jsonify({'error': 'URL required'}), 400
        
        print(f'Downloading: {video_url}')
        
        # Create temp file
        temp_dir = tempfile.gettempdir()
        temp_audio = os.path.join(temp_dir, 'youtube_audio.m4a')
        
        # Download audio with yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': temp_audio,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }]
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)
        
        print(f'Downloaded: {title}')
        
        # Load audio (first 30s)
        y, sr = librosa.load(temp_audio, sr=22050, mono=True, duration=30)
        
        # Extract chroma
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=2048)
        chroma_avg = np.mean(chroma, axis=1)
        
        # Detect key
        result = detect_key_krumhansl(chroma_avg)
        
        print(f'Detected: {result["key"]} {result["scale"]} ({result["confidence"]}%)')
        
        # Cleanup
        try:
            os.remove(temp_audio)
        except:
            pass
        
        return jsonify({
            'title': title,
            'duration': duration,
            'key': result['key'],
            'scale': result['scale'],
            'confidence': result['confidence'],
            'alternatives': result['alternatives']
        })
        
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    print('Starting YouTube Key Detection Server on http://localhost:5001')
    app.run(host='127.0.0.1', port=5001, debug=False)
