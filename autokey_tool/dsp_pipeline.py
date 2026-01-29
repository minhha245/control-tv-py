"""
AutoKey Tool - DSP Pipeline (Commercial-Grade) - IMPROVED
Uses HPCP-based key detection with enhanced stability and accuracy.
"""

import numpy as np
from typing import Tuple, Optional, Dict
from collections import deque

try:
    import librosa
    import warnings
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
    Commercial-grade key detection with improved stability:
    1. Multi-scale temporal smoothing
    2. Confidence-weighted key locking
    3. Relative key detection (major/minor pairs)
    4. Adaptive thresholding
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        short_history: int = 8,      # Fast response (2-3 seconds)
        long_history: int = 20,      # Stable average (6-7 seconds)
        confidence_threshold: float = 0.15,
        min_rms_threshold: float = 0.001,
        use_hpss: bool = True,
    ):
        self.sample_rate = sample_rate
        self.short_history = short_history
        self.long_history = long_history
        self.confidence_threshold = confidence_threshold
        self.min_rms_threshold = min_rms_threshold
        self.use_hpss = use_hpss

        # Dual-buffer system: short-term for detection, long-term for stability
        self.chroma_short = deque(maxlen=short_history)
        self.chroma_long = deque(maxlen=long_history)

        # Enhanced key locking mechanism
        self.current_key: Optional[str] = None
        self.current_confidence: float = 0.0
        self.lock_strength: float = 0.0  # 0.0 to 1.0, how confident we are
        
        # Voting system for key transitions
        self.key_votes: Dict[str, int] = {}  # key -> vote count
        self.vote_decay_rate: float = 0.7    # decay old votes
        self.min_votes_to_switch: int = 12   # need 12 consistent votes (~4 seconds)
        
        # Related key detection (prevent flickering between relative majors/minors)
        self.relative_keys = self._build_relative_key_map()
        
        # Adaptive confidence threshold
        self.adaptive_threshold: float = confidence_threshold
        self.threshold_history = deque(maxlen=50)

        # Normalize all profiles
        self._profiles = {
            'edma_major': EDMA_MAJOR / np.linalg.norm(EDMA_MAJOR),
            'edma_minor': EDMA_MINOR / np.linalg.norm(EDMA_MINOR),
            'shaath_major': SHAATH_MAJOR / np.linalg.norm(SHAATH_MAJOR),
            'shaath_minor': SHAATH_MINOR / np.linalg.norm(SHAATH_MINOR),
            'temperley_major': TEMPERLEY_MAJOR / np.linalg.norm(TEMPERLEY_MAJOR),
            'temperley_minor': TEMPERLEY_MINOR / np.linalg.norm(TEMPERLEY_MINOR),
        }

    def _build_relative_key_map(self) -> Dict[str, str]:
        """Build map of relative major/minor keys."""
        relatives = {}
        for i, key in enumerate(KEY_NAMES):
            # Relative minor is 3 semitones down
            relative_minor_idx = (i - 3) % 12
            relatives[f"{key} Major"] = f"{KEY_NAMES[relative_minor_idx]} Minor"
            relatives[f"{KEY_NAMES[relative_minor_idx]} Minor"] = f"{key} Major"
        return relatives

    def _apply_hpss(self, audio: np.ndarray) -> np.ndarray:
        """Apply Harmonic-Percussive Source Separation."""
        stft = librosa.stft(audio, n_fft=4096, hop_length=1024)
        harmonic, _ = librosa.decompose.hpss(stft, margin=2.0)
        return librosa.istft(harmonic)

    def _compute_hpcp(self, audio: np.ndarray, tuning: float = 0.0) -> np.ndarray:
        """
        Compute HPCP (Harmonic Pitch Class Profile) with enhanced accuracy.
        """
        # Triple method approach for maximum accuracy
        
        # Method 1: STFT-based chroma (fast, good for pitch)
        chroma_stft = librosa.feature.chroma_stft(
            y=audio,
            sr=self.sample_rate,
            hop_length=512,
            n_fft=4096,
            n_chroma=12,
            tuning=tuning,
        )
        
        # Method 2: CQT-based chroma (better harmonic capture)
        chroma_cqt = librosa.feature.chroma_cqt(
            y=audio,
            sr=self.sample_rate,
            hop_length=512,
            n_chroma=12,
            n_octaves=7,  # Increased from 6
            tuning=tuning,
            bins_per_octave=36,
            fmin=librosa.note_to_hz('C1'),  # Lower range
        )
        
        # Method 3: CENS (Chroma Energy Normalized Statistics) - robust to timbre
        chroma_cens = librosa.feature.chroma_cens(
            y=audio,
            sr=self.sample_rate,
            hop_length=512,
            n_chroma=12,
            tuning=tuning,
        )
        
        # Weighted combination (STFT + CQT + CENS)
        # STFT: 40%, CQT: 40%, CENS: 20%
        chroma_combined = 0.4 * chroma_stft + 0.4 * chroma_cqt + 0.2 * chroma_cens
        
        # Temporal median filtering to remove outliers
        if chroma_combined.shape[1] >= 5:
            chroma_combined = np.median(
                np.array([
                    np.roll(chroma_combined, -2, axis=1),
                    np.roll(chroma_combined, -1, axis=1),
                    chroma_combined,
                    np.roll(chroma_combined, 1, axis=1),
                    np.roll(chroma_combined, 2, axis=1),
                ]),
                axis=0
            )
        
        # Average across time with emphasis on stable regions
        hpcp = np.mean(chroma_combined, axis=1)
        
        # Normalize
        norm = np.linalg.norm(hpcp)
        if norm > 0:
            hpcp = hpcp / norm
            
        return hpcp

    def _detect_key_with_profile(
        self, hpcp: np.ndarray, major_profile: np.ndarray, minor_profile: np.ndarray
    ) -> Tuple[int, str, float]:
        """Detect key using a specific profile pair."""
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
        Enhanced multi-profile voting with second-best analysis.
        """
        results = {}
        
        # EDMA (weight: 0.45 - best for pop/electronic)
        key_idx, mode, corr = self._detect_key_with_profile(
            hpcp, self._profiles['edma_major'], self._profiles['edma_minor']
        )
        key = f"{KEY_NAMES[key_idx]} {mode}"
        results[key] = results.get(key, 0) + 0.45 * corr
        
        # Sha'ath (weight: 0.35 - modern balanced)
        key_idx, mode, corr = self._detect_key_with_profile(
            hpcp, self._profiles['shaath_major'], self._profiles['shaath_minor']
        )
        key = f"{KEY_NAMES[key_idx]} {mode}"
        results[key] = results.get(key, 0) + 0.35 * corr
        
        # Temperley (weight: 0.20 - rock/pop specific)
        key_idx, mode, corr = self._detect_key_with_profile(
            hpcp, self._profiles['temperley_major'], self._profiles['temperley_minor']
        )
        key = f"{KEY_NAMES[key_idx]} {mode}"
        results[key] = results.get(key, 0) + 0.20 * corr
        
        # Sort by score
        sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
        
        # Get top 2 candidates
        best_key = sorted_results[0][0]
        best_score = sorted_results[0][1]
        
        second_best_score = sorted_results[1][1] if len(sorted_results) > 1 else 0.0
        
        # Calculate confidence based on separation from second-best
        separation = best_score - second_best_score
        confidence = min(1.0, (best_score / 0.85) * (1 + separation))
        
        parts = best_key.split()
        key_name = parts[0]
        mode = parts[1]
        
        return key_name, mode, best_score, confidence

    def _update_adaptive_threshold(self, confidence: float):
        """Adapt threshold based on signal quality."""
        self.threshold_history.append(confidence)
        
        if len(self.threshold_history) >= 20:
            median_conf = np.median(list(self.threshold_history))
            # Lower threshold if consistently high confidence (good signal)
            # Raise threshold if low confidence (noisy signal)
            if median_conf > 0.6:
                self.adaptive_threshold = max(0.10, self.confidence_threshold - 0.05)
            elif median_conf < 0.3:
                self.adaptive_threshold = min(0.25, self.confidence_threshold + 0.05)
            else:
                self.adaptive_threshold = self.confidence_threshold

    def _is_related_key(self, key1: str, key2: str) -> bool:
        """Check if two keys are relative major/minor pairs."""
        return self.relative_keys.get(key1) == key2

    def _vote_for_key(self, new_key: str, confidence: float) -> Optional[str]:
        """
        Enhanced voting system with decay and confidence weighting.
        Returns the key to use (either current or new).
        """
        # Decay all votes
        for key in list(self.key_votes.keys()):
            self.key_votes[key] = int(self.key_votes[key] * self.vote_decay_rate)
            if self.key_votes[key] < 1:
                del self.key_votes[key]
        
        # Add weighted vote for new detection
        vote_weight = max(1, int(confidence * 3))  # High confidence = more votes
        self.key_votes[new_key] = self.key_votes.get(new_key, 0) + vote_weight
        
        # Check if we have a strong candidate
        if new_key in self.key_votes and self.key_votes[new_key] >= self.min_votes_to_switch:
            # Check if it's different from current key
            if new_key != self.current_key:
                # Allow transition if:
                # 1. No current key, OR
                # 2. Very high confidence on new key (>0.7), OR
                # 3. Current key has low lock strength (<0.3), OR
                # 4. New key is NOT a relative key (prevents major/minor flickering)
                
                if (self.current_key is None or 
                    confidence > 0.7 or 
                    self.lock_strength < 0.3 or
                    not self._is_related_key(new_key, self.current_key)):
                    
                    print(f"[Key Switch] {self.current_key} -> {new_key} (votes: {self.key_votes[new_key]}, conf: {confidence:.2f})")
                    return new_key
                else:
                    # Prefer current key if new is just relative key
                    if self._is_related_key(new_key, self.current_key):
                        print(f"[Related Key Blocked] {new_key} is relative to {self.current_key}")
                    return self.current_key
            else:
                # Same key, strengthen lock
                return new_key
        
        # Not enough votes, keep current
        return self.current_key

    def detect_key(self, audio: np.ndarray) -> Tuple[Optional[str], Optional[str], float]:
        """Detect musical key from audio buffer with enhanced stability."""
        import time
        start_time = time.time()

        # Minimum buffer check
        min_samples = int(self.sample_rate * 1.0)
        if len(audio) < min_samples:
            return None, None, 0.0

        rms = np.sqrt(np.mean(audio**2))
        
        # Smart Silence Detection with tail check
        chunk_len = int(self.sample_rate * 0.5)
        if len(audio) > chunk_len:
            recent_rms = np.sqrt(np.mean(audio[-chunk_len:]**2))
            if recent_rms < self.min_rms_threshold:
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

            # Step 2: Tuning estimation with higher resolution
            tuning = librosa.estimate_tuning(
                y=audio_harmonic, 
                sr=self.sample_rate, 
                bins_per_octave=36
            )

            # Step 3: Compute enhanced HPCP
            hpcp = self._compute_hpcp(audio_harmonic, tuning=tuning)

            # Step 4: Add to both buffers
            self.chroma_short.append(hpcp)
            self.chroma_long.append(hpcp)

            # Step 5: Multi-scale averaging
            if len(self.chroma_short) >= 4:
                # Short-term for detection
                short_avg = np.mean(list(self.chroma_short), axis=0)
                
                # Long-term for stability check
                if len(self.chroma_long) >= 10:
                    long_avg = np.mean(list(self.chroma_long), axis=0)
                    # Blend: 70% short, 30% long for balance
                    avg_hpcp = 0.7 * short_avg + 0.3 * long_avg
                else:
                    avg_hpcp = short_avg
            else:
                avg_hpcp = hpcp

            # Step 6: Multi-profile key detection
            key_name, mode, score, confidence = self._correlate_with_profiles(avg_hpcp)

            # Step 7: Update adaptive threshold
            self._update_adaptive_threshold(confidence)

            proc_time = time.time() - start_time
            print(f"[Debug] RMS: {rms:.4f} | Detected: {key_name} {mode} | Conf: {confidence:.2f} | Threshold: {self.adaptive_threshold:.2f} | Time: {proc_time:.3f}s")

            # Step 8: Check against adaptive threshold
            if confidence < self.adaptive_threshold:
                # Low confidence, decay lock strength
                self.lock_strength *= 0.9
                
                if self.current_key:
                    parts = self.current_key.split()
                    return parts[0], parts[1], self.current_confidence
                return None, None, confidence

            # Step 9: Enhanced voting and key locking
            full_key = f"{key_name} {mode}"
            decided_key = self._vote_for_key(full_key, confidence)
            
            if decided_key:
                # Update lock strength
                if decided_key == full_key:
                    # Strengthen lock when detection matches
                    self.lock_strength = min(1.0, self.lock_strength + 0.15)
                else:
                    # Decay lock when detection differs
                    self.lock_strength *= 0.85
                
                # Update current key
                if decided_key != self.current_key:
                    self.current_key = decided_key
                    self.current_confidence = confidence
                    self.lock_strength = 0.5  # Reset to medium strength on switch
                else:
                    # Smooth confidence update
                    self.current_confidence = 0.7 * self.current_confidence + 0.3 * confidence

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
        self.chroma_short.clear()
        self.chroma_long.clear()
        self.current_key = None
        self.current_confidence = 0.0
        self.lock_strength = 0.0
        self.key_votes.clear()
        self.threshold_history.clear()
        self.adaptive_threshold = self.confidence_threshold


if __name__ == "__main__":
    detector = KeyDetector()
    print("KeyDetector (Improved) initialized.")
    print("Features:")
    print("- Multi-scale temporal smoothing")
    print("- Confidence-weighted voting system")
    print("- Relative key detection (prevents major/minor flickering)")
    print("- Adaptive thresholding")
    print("- Enhanced HPCP with STFT+CQT+CENS")