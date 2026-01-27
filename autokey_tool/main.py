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
except ImportError:
    print("Installing ttkbootstrap...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "ttkbootstrap"])
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *

from audio_engine import AudioEngine
from dsp_pipeline import KeyDetector


class AutoKeyApp:
    """
    Main application class for AutoKey Tool.
    Features:
    - Always-on-top floating window
    - Real-time key detection
    - Modern, professional UI
    """

    def __init__(self):
        # Create main window
        self.root = ttk.Window(
            title="AutoKey",
            themename="darkly",
            size=(400, 350),  # Increased size to ensure visibility
            resizable=(True, True),
        )

        # Always on top
        self.root.attributes("-topmost", True)

        # Initialize components
        self.audio_engine = AudioEngine(
            sample_rate=44100,
            buffer_seconds=1.5, # Reduced for faster response
            chunk_size=2048,
        )
        
        # Log devices to terminal
        print("\n[Init] Searching for loopback devices...")
        self.device_list = self.audio_engine.get_loopback_devices()
        for d in self.device_list:
            print(f"  - [{d['id']}] {d['name']}")
        
        self.key_detector = KeyDetector(
            sample_rate=44100,  # Will be updated when audio starts
            smoothing_history=20,
            confidence_threshold=0.1,
            use_hpss=True,
        )

        # State
        self.is_running = False
        self.analysis_thread: Optional[threading.Thread] = None

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

        # Confidence meter frame
        conf_frame = ttk.Frame(main_frame)
        conf_frame.pack(fill=X)
        
        self.confidence_bar = ttk.Progressbar(
            conf_frame,
            mode="determinate",
            bootstyle="success-striped",
        )
        self.confidence_bar.pack(fill=X)

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
            self.start_btn.configure(text="■ Stop", bootstyle="danger")
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
        self.start_btn.configure(text="▶ Start", bootstyle="success")
        self.status_label.configure(text="● Stopped", bootstyle="danger")

        # Reset display
        self.key_label.configure(text="---")
        self.mode_label.configure(text="Stopped")
        self.confidence_bar["value"] = 0

    def _analysis_loop(self):
        """Main analysis loop running in separate thread."""
        while self.is_running:
            try:
                # Get audio buffer
                audio = self.audio_engine.get_buffer()
                rms = self.audio_engine.get_buffer_rms()
                
                if len(audio) > 0:
                    # Log to terminal for debugging
                    print(f"[Loop] Buffer: {len(audio)} | RMS: {rms:.6f}")
                    
                    # Detect key
                    key, mode, confidence = self.key_detector.detect_key(audio)

                    # Update UI (thread-safe)
                    self.root.after(0, self._update_display, key, mode, confidence)

                # Analysis rate (faster updates)
                time.sleep(0.1)

            except Exception as e:
                print(f"Analysis error: {e}")
                time.sleep(0.5)

    def _update_display(self, key: Optional[str], mode: Optional[str], confidence: float):
        """Update the UI with detected key (called from main thread)."""
        if key and mode:
            self.key_label.configure(text=key)
            self.mode_label.configure(text=mode)

            # Update confidence bar
            conf_percent = int(confidence * 100)
            self.confidence_bar["value"] = conf_percent

            # Color based on confidence
            if confidence > 0.7:
                self.confidence_bar.configure(bootstyle="success-striped")
            elif confidence > 0.5:
                self.confidence_bar.configure(bootstyle="warning-striped")
            else:
                self.confidence_bar.configure(bootstyle="danger-striped")
        else:
            # No valid detection
            rms = self.audio_engine.get_buffer_rms()
            if rms < 0.005:
                self.mode_label.configure(text="Waiting for audio...")
            else:
                self.mode_label.configure(text="Analyzing...")

    def _on_close(self):
        """Handle window close."""
        self._stop_listening()
        self.root.destroy()

    def run(self):
        """Start the application."""
        self.root.mainloop()


def main():
    """Entry point."""
    print("=" * 50)
    print("  AutoKey Tool - Musical Key Detection")
    print("=" * 50)
    print("\nStarting application...")

    app = AutoKeyApp()
    app.run()


if __name__ == "__main__":
    main()
