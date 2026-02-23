#!/usr/bin/env python3
"""
Diagnostic script to check YouTube Key Detector setup
"""

import sys
import subprocess
import importlib.util

def check_python_version():
    """Check Python version"""
    version = sys.version_info
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("  ⚠ Warning: Python 3.8+ recommended")
        return False
    return True

def check_module(module_name):
    """Check if a Python module is installed"""
    spec = importlib.util.find_spec(module_name)
    if spec is not None:
        print(f"✓ {module_name} installed")
        return True
    else:
        print(f"✗ {module_name} NOT installed")
        return False

def check_ffmpeg():
    """Check if ffmpeg is available"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✓ ffmpeg installed: {version_line}")
            return True
    except FileNotFoundError:
        print("✗ ffmpeg NOT found in PATH")
        return False
    except Exception as e:
        print(f"✗ Error checking ffmpeg: {e}")
        return False

def check_port(port):
    """Check if a port is available"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    
    if result == 0:
        print(f"✓ Port {port} is in use (server running)")
        return True
    else:
        print(f"○ Port {port} is available (server not running)")
        return False

def main():
    print("=" * 50)
    print("YouTube Key Detector - Setup Check")
    print("=" * 50)
    print()
    
    all_ok = True
    
    # Check Python
    print("1. Python Environment:")
    if not check_python_version():
        all_ok = False
    print()
    
    # Check required modules
    print("2. Required Python Packages:")
    required_modules = ['flask', 'flask_cors', 'yt_dlp', 'librosa', 'numpy']
    for module in required_modules:
        if not check_module(module):
            all_ok = False
    print()
    
    # Check ffmpeg
    print("3. External Dependencies:")
    if not check_ffmpeg():
        all_ok = False
        print("   Install: https://ffmpeg.org/download.html")
    print()
    
    # Check ports
    print("4. Server Status:")
    server_running = check_port(5001)
    print()
    
    # Summary
    print("=" * 50)
    if all_ok:
        print("✓ All dependencies installed!")
        if not server_running:
            print()
            print("To start the server, run:")
            print("  python youtube_server.py")
    else:
        print("✗ Some dependencies are missing")
        print()
        print("To install Python packages:")
        print("  pip install -r requirements.txt")
        print()
        print("To install ffmpeg:")
        print("  https://ffmpeg.org/download.html")
    print("=" * 50)

if __name__ == '__main__':
    main()
