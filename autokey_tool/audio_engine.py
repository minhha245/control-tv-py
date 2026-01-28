"""
AutoKey Tool - Audio Engine (PyAudioWPatch version)
Captures system audio via WASAPI Loopback on Windows.
Uses PyAudioWPatch for reliable Windows loopback support.
"""

import threading
import numpy as np
from collections import deque
from typing import Optional, Callable
import struct

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    raise ImportError("Please install pyaudiowpatch: pip install pyaudiowpatch")


class AudioEngine:
    """
    Real-time audio capture from system loopback (WASAPI on Windows).
    Maintains a sliding window buffer for analysis.
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        buffer_seconds: float = 4.0,
        chunk_size: int = 2048,
        on_audio_callback: Optional[Callable[[np.ndarray], None]] = None,
    ):
        """
        Initialize the audio engine.

        Args:
            sample_rate: Audio sample rate (Hz)
            buffer_seconds: Length of the sliding window buffer (seconds)
            chunk_size: Number of samples per read chunk
            on_audio_callback: Callback function when new audio is available
        """
        self.sample_rate = sample_rate
        self.buffer_seconds = buffer_seconds
        self.chunk_size = chunk_size
        self.on_audio_callback = on_audio_callback

        # Circular buffer to store audio samples
        self.buffer_size = int(sample_rate * buffer_seconds)
        self.audio_buffer = deque(maxlen=self.buffer_size)

        # Threading control
        self._running = False
        self._lock = threading.Lock()

        # PyAudio instance
        self._pa: Optional[pyaudio.PyAudio] = None
        self._stream = None
        self._loopback_device = None
        self._actual_sample_rate = 44100

    def _find_loopback_device(self) -> Optional[dict]:
        """Find the WASAPI loopback device for the default output."""
        if self._pa is None:
            self._pa = pyaudio.PyAudio()
        
        try:
            # Get default WASAPI output device
            wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = self._pa.get_device_info_by_index(
                wasapi_info["defaultOutputDevice"]
            )
            
            # Check if this device has loopback capability
            if not default_speakers.get("isLoopbackDevice", False):
                # Search for the loopback version of this device
                for i in range(self._pa.get_device_count()):
                    device = self._pa.get_device_info_by_index(i)
                    if device.get("isLoopbackDevice", False):
                        # Found a loopback device
                        if default_speakers["name"] in device["name"]:
                            return device
                
                # If we can't find specific match, return first loopback device
                for i in range(self._pa.get_device_count()):
                    device = self._pa.get_device_info_by_index(i)
                    if device.get("isLoopbackDevice", False):
                        return device
            
            return default_speakers
            
        except Exception as e:
            print(f"Error finding loopback device: {e}")
            return None

    def get_loopback_devices(self) -> list:
        """Get list of available loopback devices."""
        if self._pa is None:
            self._pa = pyaudio.PyAudio()
            
        devices = []
        for i in range(self._pa.get_device_count()):
            try:
                device = self._pa.get_device_info_by_index(i)
                if device.get("isLoopbackDevice", False):
                    devices.append({
                        "id": i,
                        "name": device["name"],
                        "channels": device["maxInputChannels"],
                        "sample_rate": int(device["defaultSampleRate"]),
                    })
            except:
                pass
        return devices

    def _stream_callback(self, in_data, frame_count, time_info, status):
        """Callback for PyAudio to feed audio data."""
        try:
            # Convert bytes to numpy array
            data = np.frombuffer(in_data, dtype=np.float32)

            # Convert to mono if multi-channel
            if self._channels > 1:
                # Simple averaging for mono downmix
                data = data.reshape(-1, self._channels).mean(axis=1)

            with self._lock:
                self.audio_buffer.extend(data)

            # Call external callback if set
            if self.on_audio_callback:
                self.on_audio_callback(data)
                
            return (None, pyaudio.paContinue)
        except Exception as e:
            print(f"[AudioEngine] Callback error: {e}")
            return (None, pyaudio.paContinue)

    def start(self, device_id: Optional[int] = None) -> bool:
        """
        Start capturing audio from loopback (Callback Mode).

        Args:
            device_id: Specific device ID to use, or None for auto-detect

        Returns:
            True if started successfully
        """
        if self._running:
            return True

        try:
            if self._pa is None:
                self._pa = pyaudio.PyAudio()

            # Find loopback device
            if device_id is not None:
                self._loopback_device = self._pa.get_device_info_by_index(device_id)
            else:
                self._loopback_device = self._find_loopback_device()

            if self._loopback_device is None:
                print("[AudioEngine] Error: Could not find loopback device")
                return False

            # Use device's native format (crucial for WASAPI loopback)
            device_rate = int(self._loopback_device["defaultSampleRate"])
            channels = int(self._loopback_device["maxInputChannels"])
            
            print(f"[AudioEngine] Samplerate: {device_rate}Hz | Channels: {channels}")
            
            self._actual_sample_rate = device_rate
            self._channels = channels

            # Open stream in Callback mode (non-blocking)
            self._stream = self._pa.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=device_rate,
                input=True,
                input_device_index=self._loopback_device["index"],
                frames_per_buffer=self.chunk_size,
                stream_callback=self._stream_callback
            )
            
            self._stream.start_stream()
            self._running = True
            return True

        except Exception as e:
            print(f"Error starting audio capture: {e}")
            import traceback
            traceback.print_exc()
            return False

    def stop(self):
        """Stop audio capture."""
        self._running = False
        
        if self._stream:
            try:
                # Stop stream safely (waits for callback to finish)
                self._stream.stop_stream()
                self._stream.close()
            except Exception as e:
                print(f"[AudioEngine] Error closing stream: {e}")
            finally:
                self._stream = None

    def get_buffer(self) -> np.ndarray:
        """
        Get current audio buffer as numpy array.

        Returns:
            Audio samples as float32 numpy array
        """
        with self._lock:
            return np.array(self.audio_buffer, dtype=np.float32)

    def get_buffer_rms(self) -> float:
        """Get RMS level of current buffer (for activity detection)."""
        buffer = self.get_buffer()
        if len(buffer) == 0:
            return 0.0
        return float(np.sqrt(np.mean(buffer**2)))

    @property
    def is_running(self) -> bool:
        """Check if audio capture is active."""
        return self._running

    def __del__(self):
        """Cleanup on deletion."""
        self.stop()
        if self._pa:
            self._pa.terminate()


# Quick test
if __name__ == "__main__":
    engine = AudioEngine()
    print("Available loopback devices:")
    for dev in engine.get_loopback_devices():
        print(f"  - [{dev['id']}] {dev['name']} ({dev['sample_rate']}Hz, {dev['channels']}ch)")

    print("\nStarting capture...")
    if engine.start():
        import time

        for i in range(10):
            time.sleep(0.5)
            rms = engine.get_buffer_rms()
            meter = "█" * min(int(rms * 500), 50)
            print(f"RMS Level: {rms:.6f} | {meter}")
        engine.stop()
        print("Stopped.")
    else:
        print("Failed to start audio capture.")
