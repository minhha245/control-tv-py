"""
AutoKey Tool - Main Application
Commercial-grade musical key detection with modern UI.
"""

import threading
import time
import sys
from typing import Optional

try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *
    from tkinter import filedialog, messagebox
except ImportError:
    print("Installing ttkbootstrap...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "ttkbootstrap"])
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *

from audio_engine import AudioEngine
from key_detector_improved import KeyDetector


class AutoKeyApp:
    """
    Main application class for AutoKey Tool.
    Features:
    - Always-on-top floating window
    - Real-time key detection
    - Modern, professional UI
    - Enhanced stability with improved key locking
    """

    def __init__(self):
        # Create main window
        self.root = ttk.Window(
            title="AutoKey Pro",
            themename="darkly",
            size=(400, 380),  # Slightly taller for new features
            resizable=(True, True),
        )

        # Always on top
        self.root.attributes("-topmost", True)

        # Initialize components
        self.audio_engine = AudioEngine(
            sample_rate=44100,
            buffer_seconds=1.5,  # Reduced for faster response
            chunk_size=2048,
        )
        
        # Log devices to terminal
        print("\n[Init] Searching for loopback devices...")
        self.device_list = self.audio_engine.get_loopback_devices()
        for d in self.device_list:
            print(f"  - [{d['id']}] {d['name']}")
        
        # Initialize improved KeyDetector with optimal settings
        self.key_detector = KeyDetector(
            sample_rate=44100,  # Will be updated when audio starts
            short_history=6,    # Faster initial response (~2 seconds)
            long_history=24,    # More stability buffer (~8 seconds)
            confidence_threshold=0.10,  # Lower threshold for better sensitivity
            min_rms_threshold=0.0005,   # More sensitive to quiet signals
            use_hpss=True,
        )

        # State
        self.is_running = False
        self.analysis_thread: Optional[threading.Thread] = None
        self.last_key_update = 0  # Timestamp for UI update throttling

        # Build UI
        self._build_ui()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        """Build the user interface."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=BOTH, expand=True)

        # Key display frame
        key_frame = ttk.Frame(main_frame)
        key_frame.pack(fill=X, pady=(0, 10))

        # Key name label (large)
        self.key_label = ttk.Label(
            key_frame,
            text="---",
            font=("Segoe UI", 56, "bold"),
            bootstyle="primary",
        )
        self.key_label.pack()

        # Mode label (Major/Minor)
        self.mode_label = ttk.Label(
            key_frame,
            text="Waiting...",
            font=("Segoe UI", 16),
            bootstyle="secondary",
        )
        self.mode_label.pack()

        # Device Selection Frame
        dev_frame = ttk.Labelframe(main_frame, text="Audio Source", padding=10)
        dev_frame.pack(fill=X, pady=10)

        device_names = [d['name'] for d in self.device_list]
        self.device_var = ttk.StringVar()
        self.device_select = ttk.Combobox(
            dev_frame, 
            textvariable=self.device_var,
            values=device_names,
            state="readonly",
        )
        self.device_select.pack(fill=X)
        
        if device_names:
            self.device_select.current(0)

        # Control buttons frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=X, pady=10)

        self.start_btn = ttk.Button(
            btn_frame,
            text="▶ START LISTENING",
            command=self._toggle_listening,
            bootstyle="success",
        )
        self.start_btn.pack(fill=X)
        
        # File upload button
        self.upload_btn = ttk.Button(
            btn_frame,
            text="📂 UPLOAD AUDIO FILE",
            command=self._detect_file_dialog,
            bootstyle="info-outline",
        )
        self.upload_btn.pack(fill=X, pady=(10, 0))

        # Confidence meter frame with label
        conf_container = ttk.Frame(main_frame)
        conf_container.pack(fill=X, pady=(5, 0))
        
        # Confidence label
        conf_label_frame = ttk.Frame(conf_container)
        conf_label_frame.pack(fill=X)
        
        ttk.Label(
            conf_label_frame,
            text="Confidence:",
            font=("Segoe UI", 9),
            bootstyle="secondary"
        ).pack(side=LEFT)
        
        self.conf_percent_label = ttk.Label(
            conf_label_frame,
            text="0%",
            font=("Segoe UI", 9, "bold"),
            bootstyle="info"
        )
        self.conf_percent_label.pack(side=RIGHT)
        
        # Progress bar
        self.confidence_bar = ttk.Progressbar(
            conf_container,
            mode="determinate",
            bootstyle="success-striped",
        )
        self.confidence_bar.pack(fill=X, pady=(3, 0))

        # Lock indicator
        self.lock_label = ttk.Label(
            main_frame,
            text="🔓 Detecting...",
            font=("Segoe UI", 9),
            bootstyle="secondary"
        )
        self.lock_label.pack(pady=(5, 0))

        # Status label (bottom)
        self.status_label = ttk.Label(
            main_frame,
            text="● Stopped",
            bootstyle="danger",
            font=("Segoe UI", 9)
        )
        self.status_label.pack(side=BOTTOM, pady=(5, 0))

    def _toggle_listening(self):
        """Start or stop listening."""
        if self.is_running:
            self._stop_listening()
        else:
            self._start_listening()

    def _start_listening(self):
        """Start audio capture and analysis."""
        # Get selected device index
        selected_idx = self.device_select.current()
        device_id = None
        if selected_idx >= 0:
            device_id = self.device_list[selected_idx]['id']
            print(f"[UI] Starting with device: {self.device_list[selected_idx]['name']}")

        if self.audio_engine.start(device_id=device_id):
            # CRITICAL: Update KeyDetector sample rate to match actual device rate
            actual_rate = getattr(self.audio_engine, '_actual_sample_rate', 44100)
            print(f"[UI] Updating KeyDetector sample rate to: {actual_rate}Hz")
            self.key_detector.sample_rate = actual_rate
            self.key_detector.reset()  # Reset buffers with new sample rate
            
            self.is_running = True
            self.start_btn.configure(text="■ STOP", bootstyle="danger")
            self.status_label.configure(text="● Listening", bootstyle="success")
            self.device_select.configure(state="disabled")

            # Start analysis thread
            self.analysis_thread = threading.Thread(
                target=self._analysis_loop, daemon=True
            )
            self.analysis_thread.start()
        else:
            self.status_label.configure(text="● Error: Loopback failed", bootstyle="danger")

    def _stop_listening(self):
        """Stop audio capture."""
        self.is_running = False
        self.audio_engine.stop()
        self.start_btn.configure(text="▶ START LISTENING", bootstyle="success")
        self.status_label.configure(text="● Stopped", bootstyle="danger")
        self.device_select.configure(state="readonly")

        # Reset display
        self.key_label.configure(text="---")
        self.mode_label.configure(text="Stopped")
        self.confidence_bar["value"] = 0
        self.conf_percent_label.configure(text="0%")
        self.lock_label.configure(text="🔓 Stopped")

    def _detect_file_dialog(self):
        """Open file dialog and start detection in a background thread."""
        if self.is_running:
            self._stop_listening()
        
        file_path = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=[
                ("Audio Files", "*.mp3 *.wav *.flac *.m4a *.ogg *.aac"),
                ("All Files", "*.*")
            ]
        )
        
        if file_path:
            threading.Thread(target=self._process_file, args=(file_path,), daemon=True).start()

    def _process_file(self, file_path):
        """Process an audio file and update UI (runs in background thread)."""
        import os
        import soundfile
        import librosa
        filename = os.path.basename(file_path)
        
        try:
            # Update UI to loading state
            self.root.after(0, lambda: self.status_label.configure(text=f"● Loading: {filename[:20]}...", bootstyle="info"))
            self.root.after(0, lambda: self.key_label.configure(text="..."))
            self.root.after(0, lambda: self.mode_label.configure(text="Analyzing file..."))
            self.root.after(0, lambda: self.upload_btn.configure(state="disabled"))
            self.root.after(0, lambda: self.start_btn.configure(state="disabled"))
            
            # Load audio using binary stream approach (more robust for Unicode/Windows)
            try:
                with open(file_path, 'rb') as f:
                    info = soundfile.info(f)
                    sr = info.samplerate
                    f.seek(0)
                    y, _ = soundfile.read(f, frames=int(sr * 180))
                    
                    if len(y.shape) > 1:
                        y = y.mean(axis=1)
            except Exception as sf_err:
                print(f"[Error] Soundfile failed: {sf_err}, falling back to librosa...")
                y, sr = librosa.load(file_path, sr=None, duration=180)
            
            # Update sample rate for detector
            self.key_detector.sample_rate = sr
            self.key_detector.reset()
            
            # Detect
            key, mode, conf, _ = self.key_detector.detect_static_audio(y)
            
            # Update UI with results
            if key and mode:
                self.root.after(0, lambda: self._update_display(key, mode, conf, 1.0))
                self.root.after(0, lambda: self.status_label.configure(text=f"● Detected: {filename[:20]}", bootstyle="success"))
                self.root.after(0, lambda: self.lock_label.configure(text="✅ File Detection Done", bootstyle="success"))
            else:
                self.root.after(0, lambda: self.status_label.configure(text="● Detection Failed", bootstyle="danger"))
                self.root.after(0, lambda: self.mode_label.configure(text="Could not detect key"))

        except Exception as e:
            print(f"[Error] File processing: {e}")
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to process audio file:\n{str(e)}"))
            self.root.after(0, lambda: self.status_label.configure(text="● Error loading file", bootstyle="danger"))
        finally:
            self.root.after(0, lambda: self.upload_btn.configure(state="normal"))
            self.root.after(0, lambda: self.start_btn.configure(state="normal"))

    def _analysis_loop(self):
        """Main analysis loop running in separate thread."""
        while self.is_running:
            try:
                # Get audio buffer
                audio = self.audio_engine.get_buffer()
                rms = self.audio_engine.get_buffer_rms()
                
                if len(audio) > 0:
                    # Detect key (this includes all the smart smoothing and locking)
                    key, mode, confidence = self.key_detector.detect_key(audio)

                    # Update UI (thread-safe) - throttle to every 100ms max
                    current_time = time.time()
                    if current_time - self.last_key_update > 0.1:
                        self.root.after(0, self._update_display, key, mode, confidence, rms)
                        self.last_key_update = current_time

                # Analysis rate (10 FPS for smooth updates)
                time.sleep(0.1)

            except Exception as e:
                print(f"[Error] Analysis loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.5)

    def _update_display(self, key: Optional[str], mode: Optional[str], confidence: float, rms: float):
        """Update the UI with detected key (called from main thread)."""
        if key and mode:
            self.key_label.configure(text=key)
            self.mode_label.configure(text=mode)

            # Update confidence bar and percentage
            conf_percent = int(confidence * 100)
            self.confidence_bar["value"] = conf_percent
            self.conf_percent_label.configure(text=f"{conf_percent}%")

            # Color based on confidence
            if confidence > 0.7:
                self.confidence_bar.configure(bootstyle="success-striped")
                self.conf_percent_label.configure(bootstyle="success")
            elif confidence > 0.5:
                self.confidence_bar.configure(bootstyle="warning-striped")
                self.conf_percent_label.configure(bootstyle="warning")
            else:
                self.confidence_bar.configure(bootstyle="info-striped")
                self.conf_percent_label.configure(bootstyle="info")

            # Update lock indicator based on lock_strength
            lock_strength = self.key_detector.lock_strength
            if lock_strength > 0.7:
                self.lock_label.configure(text="🔒 Locked (Strong)", bootstyle="success")
            elif lock_strength > 0.4:
                self.lock_label.configure(text="🔐 Locked (Medium)", bootstyle="warning")
            elif lock_strength > 0.1:
                self.lock_label.configure(text="🔓 Locking...", bootstyle="info")
            else:
                self.lock_label.configure(text="🔍 Detecting...", bootstyle="secondary")

        else:
            # No valid detection
            if rms < 0.005:
                self.mode_label.configure(text="Waiting for audio...")
                self.lock_label.configure(text="🔇 Silent", bootstyle="secondary")
            else:
                self.mode_label.configure(text="Analyzing...")
                self.lock_label.configure(text="🔍 Detecting...", bootstyle="info")
            
            # Keep confidence bar showing last value during silence
            if rms < 0.001:
                self.confidence_bar["value"] = 0
                self.conf_percent_label.configure(text="0%")

    def _on_close(self):
        """Handle window close."""
        print("\n[Exit] Shutting down...")
        self._stop_listening()
        self.root.destroy()

    def run(self):
        """Start the application."""
        self.root.mainloop()


def main():
    """Entry point."""
    print("=" * 60)
    print("  AutoKey Pro - Musical Key Detection (Enhanced)")
    print("=" * 60)
    print("\nFeatures:")
    print("  • Multi-scale temporal smoothing")
    print("  • Confidence-weighted key locking")
    print("  • Relative key detection (prevents flickering)")
    print("  • Adaptive thresholding")
    print("  • Enhanced HPCP (STFT + CQT + CENS)")
    print("\nStarting application...")

    try:
        app = AutoKeyApp()
        app.run()
    except KeyboardInterrupt:
        print("\n\n[Exit] Interrupted by user")
    except Exception as e:
        print(f"\n[Error] Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
