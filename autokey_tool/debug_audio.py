"""
Debug script to test audio loopback capture.
"""
import sys
import time

try:
    import soundcard as sc
    import numpy as np
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)


def main():
    print("=" * 60)
    print("  Audio Loopback Debug Tool")
    print("=" * 60)

    # List all speakers (loopback sources)
    print("\n[1] Available Speakers (Loopback Sources):")
    print("-" * 40)
    speakers = sc.all_speakers()
    for i, speaker in enumerate(speakers):
        is_default = speaker == sc.default_speaker()
        print(f"  {i}: {speaker.name}")
        print(f"      ID: {speaker.id}")
        print(f"      Default: {is_default}")
        print()

    # Get default speaker
    default_speaker = sc.default_speaker()
    print(f"\n[2] Using Default Speaker: {default_speaker.name}")

    # Try to get loopback mic
    print("\n[3] Getting Loopback Microphone...")
    try:
        loopback_mic = sc.get_microphone(
            id=str(default_speaker.id), include_loopback=True
        )
        if loopback_mic:
            print(f"    SUCCESS: {loopback_mic.name}")
        else:
            print("    FAILED: Could not get loopback microphone")
            print("    Try running as Administrator or check audio drivers")
            return
    except Exception as e:
        print(f"    ERROR: {e}")
        return

    # Test recording
    print("\n[4] Testing Audio Capture (5 seconds)...")
    print("    Play some audio in YouTube or any app NOW!")
    print("-" * 40)

    try:
        with loopback_mic.recorder(samplerate=44100, channels=1) as recorder:
            for i in range(10):
                data = recorder.record(numframes=22050)  # 0.5 second
                
                if len(data.shape) > 1:
                    data = np.mean(data, axis=1)
                
                rms = np.sqrt(np.mean(data**2))
                peak = np.max(np.abs(data))
                
                # Visual meter
                meter_len = int(rms * 500)
                meter = "█" * min(meter_len, 50)
                
                print(f"  [{i+1}/10] RMS: {rms:.6f} | Peak: {peak:.4f} | {meter}")
                
    except Exception as e:
        print(f"    RECORDING ERROR: {e}")
        return

    print("\n" + "=" * 60)
    print("  Debug Complete")
    print("=" * 60)
    print("\nIf RMS values are all near 0, audio is not being captured.")
    print("Possible fixes:")
    print("  1. Make sure audio is actually playing")
    print("  2. Try running as Administrator")
    print("  3. Check Windows sound settings -> Right click speaker -> Sounds")
    print("     -> Recording tab -> Enable 'Stereo Mix' if available")


if __name__ == "__main__":
    main()
