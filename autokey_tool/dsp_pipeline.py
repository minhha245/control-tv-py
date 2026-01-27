"""
AutoKey Tool - DSP Pipeline (Commercial-Grade)
Uses HPCP-based key detection similar to Essentia/AutoKey.
"""

import numpy as np
from typing import Tuple, Optional
from collections import deque

try:
    import librosa
    import warnings
    # Suppress librosa warnings about n_fft vs signal length
    warnings.filterwarnings("ignore", category=UserWarning, module="librosa")
except ImportError:
    raise ImportError("Please install librosa: pip install librosa")


# ============================================================================
# KEY PROFILES - Multiple Profile Systems for Best Accuracy
# ============================================================================

# EDMA Profile (Electronic Dance Music Analysis) - Best for pop/karaoke
EDMA_MAJOR = np.array([0.16519551, 0.04749026, 0.08293076, 0.06687112, 0.09994645, 
                       0.09274123, 0.05294487, 0.13159476, 0.05218986, 0.07443653, 
                       0.06940723, 0.06424152])
EDMA_MINOR = np.array([0.17235348, 0.05336489, 0.07703478, 0.10989745, 0.05091988, 
                       0.09632016, 0.04787113, 0.13418295, 0.09070186, 0.05765757, 
                       0.07276066, 0.06693519])

# Sha'ath Profile (Modern Enhanced)
SHAATH_MAJOR = np.array([6.6, 2.0, 3.5, 2.3, 4.6, 4.0, 2.5, 5.2, 2.4, 3.7, 2.3, 3.0])
SHAATH_MINOR = np.array([6.5, 2.8, 3.5, 5.4, 2.7, 3.5, 2.5, 5.2, 4.0, 2.7, 4.3, 3.2])

# Temperley Profile (Rock/Pop)
TEMPERLEY_MAJOR = np.array([5.0, 2.0, 3.5, 2.0, 4.5, 4.0, 2.0, 4.5, 2.0, 3.5, 1.5, 4.0])
TEMPERLEY_MINOR = np.array([5.0, 2.0, 3.5, 4.5, 2.0, 4.0, 2.0, 4.5, 3.5, 2.0, 1.5, 4.0])

KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


class KeyDetector:
    """
    Commercial-grade key detection using:
    1. HPCP (Harmonic Pitch Class Profile) - Industry standard
    2. Multiple key profile voting
    3. Weighted averaging across profiles
    4. Temporal smoothing with hysteresis
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        smoothing_history: int = 10,  # Reduced from 20 for faster response
        confidence_threshold: float = 0.1,
        min_rms_threshold: float = 0.001,
        use_hpss: bool = True,
    ):
        self.sample_rate = sample_rate
        self.smoothing_history = smoothing_history
        self.confidence_threshold = confidence_threshold
        self.min_rms_threshold = min_rms_threshold
        self.use_hpss = use_hpss

        # Chroma history buffer
        self.chroma_history = deque(maxlen=smoothing_history)

        # Key lock mechanism
        self.current_key: Optional[str] = None
        self.current_confidence: float = 0.0
        self.candidate_key: Optional[str] = None
        self.candidate_count: int = 0
        self.lock_threshold: int = 8  # Require 8 frames (~2.5 seconds) to switch

        # Normalize all profiles
        self._profiles = {
            'edma_major': EDMA_MAJOR / np.linalg.norm(EDMA_MAJOR),
            'edma_minor': EDMA_MINOR / np.linalg.norm(EDMA_MINOR),
            'shaath_major': SHAATH_MAJOR / np.linalg.norm(SHAATH_MAJOR),
            'shaath_minor': SHAATH_MINOR / np.linalg.norm(SHAATH_MINOR),
            'temperley_major': TEMPERLEY_MAJOR / np.linalg.norm(TEMPERLEY_MAJOR),
            'temperley_minor': TEMPERLEY_MINOR / np.linalg.norm(TEMPERLEY_MINOR),
        }

    def _apply_hpss(self, audio: np.ndarray) -> np.ndarray:
        """Apply Harmonic-Percussive Source Separation."""
        stft = librosa.stft(audio, n_fft=4096, hop_length=1024)
        harmonic, _ = librosa.decompose.hpss(stft, margin=2.0)
        return librosa.istft(harmonic)

    def _compute_hpcp(self, audio: np.ndarray, tuning: float = 0.0) -> np.ndarray:
        """
        Compute HPCP (Harmonic Pitch Class Profile).
        Uses chroma_stft which is more accurate for tuning.
        """
        # Method 1: Use chroma_stft (more accurate for semitone detection)
        chroma_stft = librosa.feature.chroma_stft(
            y=audio,
            sr=self.sample_rate,
            hop_length=512,
            n_fft=4096,
            n_chroma=12,
            tuning=tuning,
        )
        
        # Method 2: Use chroma_cqt as secondary
        chroma_cqt = librosa.feature.chroma_cqt(
            y=audio,
            sr=self.sample_rate,
            hop_length=512,
            n_chroma=12,
            n_octaves=6,
            tuning=tuning,
            bins_per_octave=36,
            fmin=librosa.note_to_hz('C2'),
        )
        
        # Combine both methods (weighted average)
        # STFT is more accurate for pitch, CQT captures harmonics better
        chroma_combined = 0.6 * chroma_stft + 0.4 * chroma_cqt
        
        # Average across time
        hpcp = np.mean(chroma_combined, axis=1)
        
        # Normalize
        norm = np.linalg.norm(hpcp)
        if norm > 0:
            hpcp = hpcp / norm
            
        return hpcp

    def _detect_key_with_profile(
        self, hpcp: np.ndarray, major_profile: np.ndarray, minor_profile: np.ndarray
    ) -> Tuple[int, str, float]:
        """Detect key using a specific profile pair. Returns (key_index, mode, correlation)."""
        best_corr = -1.0
        best_key = 0
        best_mode = "Major"

        for shift in range(12):
            rotated = np.roll(hpcp, -shift)
            
            major_corr = np.dot(rotated, major_profile)
            minor_corr = np.dot(rotated, minor_profile)

            if major_corr > best_corr:
                best_corr = major_corr
                best_key = shift
                best_mode = "Major"

            if minor_corr > best_corr:
                best_corr = minor_corr
                best_key = shift
                best_mode = "Minor"

        return best_key, best_mode, best_corr

    def _correlate_with_profiles(self, hpcp: np.ndarray) -> Tuple[str, str, float, float]:
        """
        Multi-profile voting system for robust key detection.
        Uses EDMA, Sha'ath, and Temperley profiles with weighted voting.
        """
        results = {}
        
        # EDMA (weight: 0.5 - best for pop/electronic)
        key_idx, mode, corr = self._detect_key_with_profile(
            hpcp, self._profiles['edma_major'], self._profiles['edma_minor']
        )
        key = f"{KEY_NAMES[key_idx]} {mode}"
        results[key] = results.get(key, 0) + 0.5 * corr
        
        # Sha'ath (weight: 0.3 - modern balanced)
        key_idx, mode, corr = self._detect_key_with_profile(
            hpcp, self._profiles['shaath_major'], self._profiles['shaath_minor']
        )
        key = f"{KEY_NAMES[key_idx]} {mode}"
        results[key] = results.get(key, 0) + 0.3 * corr
        
        # Temperley (weight: 0.2 - rock/pop specific)
        key_idx, mode, corr = self._detect_key_with_profile(
            hpcp, self._profiles['temperley_major'], self._profiles['temperley_minor']
        )
        key = f"{KEY_NAMES[key_idx]} {mode}"
        results[key] = results.get(key, 0) + 0.2 * corr
        
        # Find winner
        best_key = max(results, key=results.get)
        best_score = results[best_key]
        
        parts = best_key.split()
        key_name = parts[0]
        mode = parts[1]
        
        # Calculate confidence (normalize by max possible score)
        confidence = min(1.0, best_score / 0.9)
        
        return key_name, mode, best_score, confidence

    def detect_key(self, audio: np.ndarray) -> Tuple[Optional[str], Optional[str], float]:
        """Detect musical key from audio buffer."""
        import time
        start_time = time.time()

        # Minimum buffer check - need at least 1 second of audio for reliable detection
        min_samples = int(self.sample_rate * 1.0)
        if len(audio) < min_samples:
            return None, None, 0.0

        rms = np.sqrt(np.mean(audio**2))
        
        # Smart Silence Detection:
        # Check if the last 0.5s of audio is silent. If so, clear history and return None.
        # This prevents the "ghost key" effect when music stops.
        chunk_len = int(self.sample_rate * 0.5)
        if len(audio) > chunk_len:
            recent_rms = np.sqrt(np.mean(audio[-chunk_len:]**2))
            if recent_rms < self.min_rms_threshold:
                # Silence detected at tail
                self.reset()
                return None, None, 0.0

        if rms < self.min_rms_threshold:
            return None, None, 0.0

        try:
            # Step 1: HPSS
            if self.use_hpss:
                audio_harmonic = self._apply_hpss(audio)
                if np.sqrt(np.mean(audio_harmonic**2)) < self.min_rms_threshold:
                    audio_harmonic = audio
            else:
                audio_harmonic = audio

            # Step 2: Tuning estimation
            tuning = librosa.estimate_tuning(y=audio_harmonic, sr=self.sample_rate, bins_per_octave=36)

            # Step 3: Compute HPCP
            hpcp = self._compute_hpcp(audio_harmonic, tuning=tuning)

            # Step 4: Add to history
            self.chroma_history.append(hpcp)

            # Step 5: Average across history
            if len(self.chroma_history) >= 3:
                avg_hpcp = np.mean(list(self.chroma_history), axis=0)
            else:
                avg_hpcp = hpcp

            # Step 6: Multi-profile key detection
            key_name, mode, score, confidence = self._correlate_with_profiles(avg_hpcp)

            proc_time = time.time() - start_time
            print(f"[Debug] RMS: {rms:.4f} | Key: {key_name} {mode} | Conf: {confidence:.2f} | Time: {proc_time:.2f}s")

            # Step 7: Key locking with hysteresis
            full_key = f"{key_name} {mode}"

            if confidence < self.confidence_threshold:
                if self.current_key:
                    parts = self.current_key.split()
                    return parts[0], parts[1], self.current_confidence
                return None, None, confidence

            if full_key == self.current_key:
                self.candidate_key = None
                self.candidate_count = 0
                self.current_confidence = 0.85 * self.current_confidence + 0.15 * confidence
            else:
                if full_key == self.candidate_key:
                    self.candidate_count += 1
                else:
                    self.candidate_key = full_key
                    self.candidate_count = 1

                if self.candidate_count >= self.lock_threshold:
                    self.current_key = full_key
                    self.current_confidence = confidence
                    self.candidate_key = None
                    self.candidate_count = 0
                    print(f"[Stable] Key switched to: {full_key}")

            if self.current_key:
                parts = self.current_key.split()
                return parts[0], parts[1], self.current_confidence
            return key_name, mode, confidence

        except Exception as e:
            print(f"Error in key detection: {e}")
            import traceback
            traceback.print_exc()
            return None, None, 0.0

    def reset(self):
        """Reset the detector state."""
        self.chroma_history.clear()
        self.current_key = None
        self.current_confidence = 0.0
        self.candidate_key = None
        self.candidate_count = 0


if __name__ == "__main__":
    detector = KeyDetector()
    print("KeyDetector (Commercial-Grade) initialized.")
