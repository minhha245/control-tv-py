"""
Build Python server to standalone executable using PyInstaller
"""
import PyInstaller.__main__
import os

# Get current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

PyInstaller.__main__.run([
    'audio_server.py',
    '--onefile',
    '--name=audio_server',
    '--hidden-import=sklearn.utils._cython_blas',
    '--hidden-import=sklearn.neighbors.typedefs',
    '--hidden-import=sklearn.neighbors.quad_tree',
    '--hidden-import=sklearn.tree._utils',
    '--collect-all=librosa',
    '--collect-all=soundfile',
    '--collect-all=audioread',
    '--noconsole',
    f'--distpath={os.path.join(current_dir, "dist")}',
    f'--workpath={os.path.join(current_dir, "build")}',
    f'--specpath={os.path.join(current_dir, "build")}',
])

print("\nPython server built successfully!")
print(f"Executable: {os.path.join(current_dir, 'dist', 'audio_server.exe')}")
