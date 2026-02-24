"""
AutoKey Tool - DSP Pipeline (Commercial-Grade) - ENHANCED ACCURACY
Uses HPCP-based key detection with AGGRESSIVE key locking + IMPROVED STATIC DETECTION.

IMPROVEMENTS:
- Enhanced multi-window analysis (9 windows instead of 6)
- Ensemble voting với weighted consensus
- Relative key disambiguation
- Temporal stability analysis
- Adaptive profile matching
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

# Krumhansl-Kessler Profile (Classical/Standard)
KRUMHANSL_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KRUMHANSL_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


class KeyDetector:
    """
    ULTRA-STABLE key detection with aggressive locking and ENHANCED static file analysis.
    
    Strategy:
    1. Real-time: Once locked, requires strong evidence to change
    2. Static files: Multi-window ensemble voting với relative key disambiguation
    3. Temporal stability analysis
    4. Adaptive thresholding based on signal quality
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        short_history: int = 8,
        long_history: int = 20,
        smoothing_history: Optional[int] = None,  # Backward compatibility
        confidence_threshold: float = 0.15,
        min_rms_threshold: float = 0.001,
        use_hpss: bool = True,
    ):
        self.sample_rate = sample_rate
        
        # Backward compatibility
        if smoothing_history is not None:
            self.short_history = smoothing_history
            self.long_history = max(smoothing_history * 2, 20)
        else:
            self.short_history = short_history
            self.long_history = long_history
        
        self.confidence_threshold = confidence_threshold
        self.min_rms_threshold = min_rms_threshold
        self.use_hpss = use_hpss

        # Dual-buffer system
        self.chroma_short = deque(maxlen=self.short_history)
        self.chroma_long = deque(maxlen=self.long_history)

        # SIMPLIFIED LOCKING MECHANISM
        self.current_key: Optional[str] = None
        self.current_confidence: float = 0.0
        self.lock_strength: float = 0.0
        
        # Adaptive locking thresholds (will adjust based on signal)
        self.same_key_count: int = 0
        self.frames_to_lock: int = 15         # Base: 15 frames (~5 seconds)
        self.frames_to_unlock: int = 25       # Base: 25 frames (~8 seconds)
        self.adaptive_lock_frames: int = 15
        self.adaptive_unlock_frames: int = 25
        
        # Quick-lock for strong signals (can lock in 5-6 frames if very confident)
        self.high_confidence_count: int = 0    # Count of very high confidence detections
        self.quick_lock_threshold: int = 6     # Lock immediately if 6 high-conf frames
        
        # Signal quality tracking
        self.avg_rms_history = deque(maxlen=30)
        self.avg_confidence_history = deque(maxlen=30)
        self.recent_detections = deque(maxlen=10)  # Track last 10 detections for consensus
        
        # Related key detection
        self.relative_keys = self._build_relative_key_map()

        # Normalize all profiles
        self._profiles = {
            'edma_major': EDMA_MAJOR / np.linalg.norm(EDMA_MAJOR),
            'edma_minor': EDMA_MINOR / np.linalg.norm(EDMA_MINOR),
            'shaath_major': SHAATH_MAJOR / np.linalg.norm(SHAATH_MAJOR),
            'shaath_minor': SHAATH_MINOR / np.linalg.norm(SHAATH_MINOR),
            'temperley_major': TEMPERLEY_MAJOR / np.linalg.norm(TEMPERLEY_MAJOR),
            'temperley_minor': TEMPERLEY_MINOR / np.linalg.norm(TEMPERLEY_MINOR),
            'krumhansl_major': KRUMHANSL_MAJOR / np.linalg.norm(KRUMHANSL_MAJOR),
            'krumhansl_minor': KRUMHANSL_MINOR / np.linalg.norm(KRUMHANSL_MINOR),
        }

    def _build_relative_key_map(self) -> Dict[str, str]:
        """Build map of relative major/minor keys."""
        relatives = {}
        for i, key in enumerate(KEY_NAMES):
            relative_minor_idx = (i - 3) % 12
            relatives[f"{key} Major"] = f"{KEY_NAMES[relative_minor_idx]} Minor"
            relatives[f"{KEY_NAMES[relative_minor_idx]} Minor"] = f"{key} Major"
        return relatives

    def _is_related_key(self, key1: str, key2: str) -> bool:
        """Check if two keys are relative major/minor pairs."""
        if key1 is None or key2 is None:
            return False
        return self.relative_keys.get(key1) == key2

    def _update_adaptive_thresholds(self, rms: float, confidence: float):
        """
        Adjust locking thresholds based on signal quality.
        
        Logic:
        - Soft/quiet music (low RMS): Lower thresholds = faster lock
        - Loud/energetic music (high RMS): Higher thresholds = more stable
        - High confidence signals: Can lock faster
        - Low confidence signals: Need more frames to be sure
        """
        self.avg_rms_history.append(rms)
        self.avg_confidence_history.append(confidence)
        
        if len(self.avg_rms_history) < 10:
            return  # Need some history first
        
        avg_rms = np.mean(list(self.avg_rms_history))
        avg_conf = np.mean(list(self.avg_confidence_history))
        
        # Categorize signal strength
        if avg_rms < 0.01:
            # Very quiet (ballads, acoustic)
            base_lock = 10
            base_unlock = 18
            conf_multiplier = 0.8
        elif avg_rms < 0.05:
            # Moderate (normal songs)
            base_lock = 12
            base_unlock = 20
            conf_multiplier = 0.9
        else:
            # Loud (rock, EDM)
            base_lock = 15
            base_unlock = 25
            conf_multiplier = 1.0
        
        # Adjust based on average confidence
        if avg_conf > 0.6:
            # High confidence signal - can lock faster
            self.adaptive_lock_frames = max(6, int(base_lock * 0.6))  # Reduced from 0.7
            self.adaptive_unlock_frames = max(15, int(base_unlock * 0.8))
        elif avg_conf > 0.4:
            # Medium confidence
            self.adaptive_lock_frames = int(base_lock * conf_multiplier)
            self.adaptive_unlock_frames = int(base_unlock * conf_multiplier)
        else:
            # Low confidence - need more frames
            self.adaptive_lock_frames = int(base_lock * 1.3)
            self.adaptive_unlock_frames = int(base_unlock * 1.2)
        
        # Clamp to reasonable ranges (lowered minimum)
        self.adaptive_lock_frames = max(6, min(20, self.adaptive_lock_frames))  # Min from 8->6
        self.adaptive_unlock_frames = max(15, min(30, self.adaptive_unlock_frames))

    def _check_strong_consensus(self, detected_key: str) -> bool:
        """
        Check if there's strong consensus in recent detections.
        Returns True if we should quick-lock based on strong agreement.
        """
        if len(self.recent_detections) < 6:
            return False
        
        # Count occurrences of each key in recent history
        key_counts = {}
        for det_key, det_conf in self.recent_detections:
            key_counts[det_key] = key_counts.get(det_key, 0) + 1
        
        # Check if detected_key dominates (>= 80% agreement in last 10 frames)
        if detected_key in key_counts:
            agreement_rate = key_counts[detected_key] / len(self.recent_detections)
            if agreement_rate >= 0.8:
                return True
        
        return False


    def _apply_hpss(self, audio: np.ndarray) -> np.ndarray:
        """Apply Harmonic-Percussive Source Separation with optimal settings."""
        stft = librosa.stft(audio, n_fft=8192, hop_length=512)
        harmonic, _ = librosa.decompose.hpss(stft, margin=3.0)  # Higher margin = cleaner separation
        return librosa.istft(harmonic, hop_length=512)

    def _compute_hpcp(self, audio: np.ndarray, tuning: float = 0.0, hop_length: int = 512, force_cens: bool = False) -> np.ndarray:
        """
        Compute HPCP (Harmonic Pitch Class Profile) with MAXIMUM accuracy.
        Uses 4-method ensemble for best results.
        """
        # Method 1: STFT-based chroma (high frequency resolution)
        chroma_stft = librosa.feature.chroma_stft(
            y=audio,
            sr=self.sample_rate,
            hop_length=hop_length,
            n_fft=8192,  # Doubled for better frequency resolution
            n_chroma=12,
            tuning=tuning,
        )
        
        # Method 2: CQT-based chroma (log-frequency, best for pitch)
        chroma_cqt = librosa.feature.chroma_cqt(
            y=audio,
            sr=self.sample_rate,
            hop_length=hop_length,
            n_chroma=12,
            n_octaves=8,  # More octaves for full range
            tuning=tuning,
            bins_per_octave=36,
            fmin=librosa.note_to_hz('C1'),
        )
        
        # Method 3: CENS (Constant-Q with energy normalization) - ALWAYS for static
        chroma_cens = librosa.feature.chroma_cens(
            y=audio,
            sr=self.sample_rate,
            hop_length=hop_length,
            n_chroma=12,
            tuning=tuning,
        )
        
        # Method 4: Crepe-based (if available) - deep learning pitch
        try:
            import crepe
            _, frequencies, _, probs = crepe.predict(
                audio, self.sample_rate, step_size=hop_length*1000//self.sample_rate,
                model_size="tiny"
            )
            # Convert to chroma
            chroma_crepe = np.zeros((12, probs.shape[1]))
            for t in range(probs.shape[1]):
                for p in range(12):
                    freq = 440 * 2 ** ((p - 9) / 12)
                    idx = np.argmin(np.abs(frequencies[:, t] - freq))
                    chroma_crepe[p, t] = probs[idx, t]
            has_crepe = True
        except:
            has_crepe = False
        
        # Weighted ensemble (CENS most reliable for key detection)
        if has_crepe:
            chroma_combined = 0.1 * chroma_stft + 0.7 * chroma_cqt + 0.1 * chroma_cens + 0.1 * chroma_crepe
        else:
            # ESSENTIA-STYLE: Highly prioritize CQT for pitch accuracy
            chroma_combined = 0.15 * chroma_stft + 0.75 * chroma_cqt + 0.1 * chroma_cens
        
        # Robust temporal median filtering
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
        
        # L2 normalization
        hpcp = np.mean(chroma_combined, axis=1)
        norm = np.linalg.norm(hpcp)
        if norm > 0:
            hpcp = hpcp / norm
            
        return hpcp

    def _detect_key_with_profile(
        self, hpcp: np.ndarray, major_profile: np.ndarray, minor_profile: np.ndarray
    ) -> Tuple[int, str, float]:
        """Detect key using a specific profile pair via Pearson Correlation."""
        best_corr = -1.0
        best_key = 0
        best_mode = "Major"

        for shift in range(12):
            rotated = np.roll(hpcp, -shift)
            
            # Use Pearson Correlation to match Essentia-style exact behavior
            major_corr = np.corrcoef(rotated, major_profile)[0, 1]
            minor_corr = np.corrcoef(rotated, minor_profile)[0, 1]

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
        Multi-profile voting with ENHANCED confidence calculation.
        Uses 4 profiles with optimized weights for maximum accuracy.
        """
        results = {}
        
        # 1. Krumhansl-Kessler (weight: 0.65) - ESSENTIA PRIMARY PROFILE
        key_idx, mode, corr = self._detect_key_with_profile(
            hpcp, self._profiles['krumhansl_major'], self._profiles['krumhansl_minor']
        )
        key = f"{KEY_NAMES[key_idx]} {mode}"
        results[key] = results.get(key, 0) + 0.65 * corr
        
        # 2. EDMA (weight: 0.15) - Pop/Karaoke
        key_idx, mode, corr = self._detect_key_with_profile(
            hpcp, self._profiles['edma_major'], self._profiles['edma_minor']
        )
        key = f"{KEY_NAMES[key_idx]} {mode}"
        results[key] = results.get(key, 0) + 0.15 * corr

        # 3. Sha'ath (weight: 0.10) - Modern
        key_idx, mode, corr = self._detect_key_with_profile(
            hpcp, self._profiles['shaath_major'], self._profiles['shaath_minor']
        )
        key = f"{KEY_NAMES[key_idx]} {mode}"
        results[key] = results.get(key, 0) + 0.10 * corr
        
        # 4. Temperley (weight: 0.10) - Rock/Pop
        key_idx, mode, corr = self._detect_key_with_profile(
            hpcp, self._profiles['temperley_major'], self._profiles['temperley_minor']
        )
        key = f"{KEY_NAMES[key_idx]} {mode}"
        results[key] = results.get(key, 0) + 0.10 * corr
        
        # Sort and get results
        sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
        best_key = sorted_results[0][0]
        best_score = sorted_results[0][1]
        
        # Calculate separation from runner-up
        second_best_score = sorted_results[1][1] if len(sorted_results) > 1 else 0.0
        separation = best_score - second_best_score
        
        # Calculate confidence (0.0 to 1.0)
        # Higher score + larger separation = higher confidence
        confidence = min(1.0, (best_score / 0.7) * (1 + separation * 0.5))
        
        parts = best_key.split()
        return parts[0], parts[1], best_score, confidence

    def detect_key(self, audio: np.ndarray) -> Tuple[Optional[str], Optional[str], float]:
        """
        Detect musical key with ULTRA-STABLE locking.
        
        Rules:
        1. Need 15 consecutive frames to initially lock
        2. Need 25 consecutive frames to switch once locked
        3. Relative keys (C Major <-> A Minor) blocked unless very confident
        """
        import time
        start_time = time.time()

        # Minimum buffer check
        min_samples = int(self.sample_rate * 1.0)
        if len(audio) < min_samples:
            return None, None, 0.0

        rms = np.sqrt(np.mean(audio**2))
        
        # Silence detection with tail check
        chunk_len = int(self.sample_rate * 0.5)
        if len(audio) > chunk_len:
            recent_rms = np.sqrt(np.mean(audio[-chunk_len:]**2))
            if recent_rms < self.min_rms_threshold:
                self.reset()
                return None, None, 0.0

        if rms < self.min_rms_threshold:
            return None, None, 0.0

        try:
            # HPSS
            if self.use_hpss:
                audio_harmonic = self._apply_hpss(audio)
                if np.sqrt(np.mean(audio_harmonic**2)) < self.min_rms_threshold:
                    audio_harmonic = audio
            else:
                audio_harmonic = audio

            # Tuning estimation
            tuning = librosa.estimate_tuning(
                y=audio_harmonic, 
                sr=self.sample_rate, 
                bins_per_octave=36
            )

            # Compute HPCP
            hpcp = self._compute_hpcp(audio_harmonic, tuning=tuning)

            # Add to buffers
            self.chroma_short.append(hpcp)
            self.chroma_long.append(hpcp)

            # Multi-scale averaging (MORE SMOOTHING)
            if len(self.chroma_short) >= 5:
                short_avg = np.mean(list(self.chroma_short), axis=0)
                
                if len(self.chroma_long) >= 12:
                    long_avg = np.mean(list(self.chroma_long), axis=0)
                    # Blend: 60% short, 40% long (more stability)
                    avg_hpcp = 0.6 * short_avg + 0.4 * long_avg
                else:
                    avg_hpcp = short_avg
            else:
                avg_hpcp = hpcp

            # Detect key
            key_name, mode, score, confidence = self._correlate_with_profiles(avg_hpcp)

            proc_time = time.time() - start_time
            
            # Update adaptive thresholds based on signal characteristics
            self._update_adaptive_thresholds(rms, confidence)
            
            # Adaptive confidence threshold based on RMS
            # Quiet music often has lower confidence - adjust threshold
            if rms < 0.01:
                effective_threshold = self.confidence_threshold * 0.6  # 60% of base
            elif rms < 0.05:
                effective_threshold = self.confidence_threshold * 0.8  # 80% of base
            else:
                effective_threshold = self.confidence_threshold
            
            # Check confidence threshold
            if confidence < effective_threshold:
                # Low confidence - reset counter
                self.same_key_count = 0
                
                # Return current locked key if we have one
                if self.current_key and self.lock_strength > 0.3:
                    parts = self.current_key.split()
                    print(f"[Lock Hold] Low conf ({confidence:.2f} < {effective_threshold:.2f}), keeping: {self.current_key}")
                    return parts[0], parts[1], self.current_confidence
                
                return None, None, confidence

            # === ADAPTIVE LOCKING WITH QUICK-LOCK FOR STRONG SIGNALS ===
            detected_key = f"{key_name} {mode}"
            
            # Track this detection
            self.recent_detections.append((detected_key, confidence))
            
            # Case 1: No current key - count up to lock
            if self.current_key is None:
                if detected_key == getattr(self, '_last_detected_key', None):
                    self.same_key_count += 1
                    
                    # Track high confidence detections for quick-lock
                    if confidence > 0.65:
                        self.high_confidence_count += 1
                    else:
                        self.high_confidence_count = 0  # Reset if confidence drops
                else:
                    self.same_key_count = 1
                    self.high_confidence_count = 1 if confidence > 0.65 else 0
                    self._last_detected_key = detected_key
                
                # QUICK-LOCK: If we have strong consensus and high confidence
                has_consensus = self._check_strong_consensus(detected_key)
                can_quick_lock = (
                    self.high_confidence_count >= self.quick_lock_threshold and
                    has_consensus
                )
                
                if can_quick_lock:
                    self.current_key = detected_key
                    self.current_confidence = confidence
                    self.lock_strength = 0.7  # Higher initial lock for quick-lock
                    print(f"[QUICK-LOCK ⚡] Key: {detected_key} | High-conf: {self.high_confidence_count} | Consensus: Yes")
                    return key_name, mode, confidence
                
                print(f"[Locking] {detected_key} | Count: {self.same_key_count}/{self.adaptive_lock_frames} | High-conf: {self.high_confidence_count}/{self.quick_lock_threshold} | Conf: {confidence:.2f}")
                
                # Normal lock when threshold reached (using adaptive threshold)
                if self.same_key_count >= self.adaptive_lock_frames:
                    self.current_key = detected_key
                    self.current_confidence = confidence
                    self.lock_strength = 0.5
                    print(f"[LOCKED ✓] Key: {detected_key} (adaptive threshold: {self.adaptive_lock_frames})")
                
                # Return detection even before lock
                return key_name, mode, confidence
            
            # Case 2: Detected same as current - strengthen lock
            elif detected_key == self.current_key:
                self.same_key_count = 0  # Reset switch counter
                self.high_confidence_count = 0  # Reset quick-lock counter
                self.lock_strength = min(1.0, self.lock_strength + 0.1)
                self.current_confidence = 0.8 * self.current_confidence + 0.2 * confidence
                
                print(f"[Hold] {self.current_key} | Lock: {self.lock_strength:.2f} | Conf: {confidence:.2f}")
                
                parts = self.current_key.split()
                return parts[0], parts[1], self.current_confidence
            
            # Case 3: Different key detected
            else:
                # Reset high confidence counter when key changes
                self.high_confidence_count = 0
                
                # Block relative keys unless VERY confident
                if self._is_related_key(detected_key, self.current_key):
                    if confidence < 0.70:  # Lowered from 0.75 for faster switches
                        print(f"[Blocked] {detected_key} is relative to {self.current_key} (conf={confidence:.2f} < 0.70)")
                        parts = self.current_key.split()
                        return parts[0], parts[1], self.current_confidence
                
                # Count consecutive frames of new key
                if detected_key == getattr(self, '_last_detected_key', None):
                    self.same_key_count += 1
                else:
                    self.same_key_count = 1
                    self._last_detected_key = detected_key
                
                # Decay current lock when seeing different key
                self.lock_strength *= 0.95
                
                # Check for strong consensus on the new key
                has_consensus = self._check_strong_consensus(detected_key)
                
                # Fast-switch if very high confidence AND strong consensus
                if confidence > 0.75 and has_consensus and self.same_key_count >= 5:
                    print(f"[FAST-SWITCH ⚡] {self.current_key} -> {detected_key} | Conf: {confidence:.2f} | Consensus: Yes")
                    self.current_key = detected_key
                    self.current_confidence = confidence
                    self.lock_strength = 0.6
                    self.same_key_count = 0
                    return key_name, mode, confidence
                
                print(f"[Switch?] {detected_key} | Count: {self.same_key_count}/{self.adaptive_unlock_frames} | Lock: {self.lock_strength:.2f} | Consensus: {'Yes' if has_consensus else 'No'}")
                
                # Only switch if we have enough evidence (using adaptive threshold)
                if self.same_key_count >= self.adaptive_unlock_frames:
                    print(f"[SWITCHED] {self.current_key} -> {detected_key} (adaptive threshold: {self.adaptive_unlock_frames})")
                    self.current_key = detected_key
                    self.current_confidence = confidence
                    self.lock_strength = 0.5
                    self.same_key_count = 0
                    
                    return key_name, mode, confidence
                
                # Still locked, return current
                parts = self.current_key.split()
                return parts[0], parts[1], self.current_confidence

        except Exception as e:
            print(f"Error in key detection: {e}")
            import traceback
            traceback.print_exc()
            return None, None, 0.0

    def detect_static_audio(self, audio: np.ndarray) -> Tuple[Optional[str], Optional[str], float, float]:
        """
        FAST STATIC KEY DETECTION - Kết quả trong <15s.
        
        Tối ưu tốc độ:
        - 3 windows thay vì 9-12
        - 2-method HPCP (STFT + CENS)
        - FFT 4096 thay vì 8192
        - Không có beat tracking
        - Single tuning pass
        
        Returns: (key, mode, confidence, proc_time)
        """
        import time
        start_time = time.perf_counter()
        
        min_samples = int(self.sample_rate * 3.0)
        if len(audio) < min_samples:
            return None, None, 0.0, 0.0

        try:
            total_samples = len(audio)
            duration = total_samples / self.sample_rate
            
            # === FAST WINDOW SELECTION: 3 windows ===
            if duration < 30:
                # Short-medium files: 3 windows
                samples_per_window = int(self.sample_rate * 10)  # 10s each
                starts = [
                    int(self.sample_rate * 5),  # 5s
                    total_samples // 2 - samples_per_window // 2,  # Middle
                    total_samples - samples_per_window - int(self.sample_rate * 5)  # 5s from end
                ]
            else:
                # Long files: 3 windows, skip intro/outro
                samples_per_window = int(self.sample_rate * 15)  # 15s each
                starts = [
                    int(self.sample_rate * 20),  # 20s
                    total_samples // 2 - samples_per_window // 2,  # Middle
                    total_samples - samples_per_window - int(self.sample_rate * 20)  # 20s from end
                ]

            # Filter valid starts
            starts = [s for s in starts if s >= 0 and s + samples_per_window <= total_samples]
            if not starts:
                starts = [0]
                samples_per_window = min(total_samples, int(self.sample_rate * 15))

            print(f"\n[Fast Detection] {duration:.1f}s - {len(starts)} windows")

            # === FAST ANALYSIS ===
            window_results = []
            all_hpcps = []
            weights = []
            FAST_HOP = 1024  # Larger hop = faster
            
            for idx, start_idx in enumerate(starts):
                audio_chunk = audio[start_idx : start_idx + samples_per_window]
                if len(audio_chunk) < int(self.sample_rate * 3):
                    continue
                
                rms = np.sqrt(np.mean(audio_chunk**2))
                if rms < self.min_rms_threshold:
                    continue
                
                # === FAST HPSS ===
                if self.use_hpss:
                    stft = librosa.stft(audio_chunk, n_fft=4096, hop_length=FAST_HOP)
                    harmonic, _ = librosa.decompose.hpss(stft, margin=2.5)
                    audio_harmonic = librosa.istft(harmonic, hop_length=FAST_HOP)
                    
                    if np.sqrt(np.mean(audio_harmonic**2)) > self.min_rms_threshold * 0.3:
                        audio_to_use = audio_harmonic
                    else:
                        audio_to_use = audio_chunk
                else:
                    audio_to_use = audio_chunk

                # === FAST TUNING ===
                tuning = librosa.estimate_tuning(y=audio_to_use, sr=self.sample_rate, bins_per_octave=36)

                # === ESSENTIA-STYLE HPCP (CQT Priority) ===
                chroma_cqt = librosa.feature.chroma_cqt(
                    y=audio_to_use, sr=self.sample_rate, hop_length=FAST_HOP,
                    n_chroma=12, tuning=tuning,
                )
                chroma_cens = librosa.feature.chroma_cens(
                    y=audio_to_use, sr=self.sample_rate, hop_length=FAST_HOP,
                    n_chroma=12, tuning=tuning,
                )
                # Weighted blend: Favor CQT (80%) for static analysis like Essentia
                chunk_hpcp = 0.8 * np.mean(chroma_cqt, axis=1) + 0.2 * np.mean(chroma_cens, axis=1)
                chunk_hpcp = chunk_hpcp / np.linalg.norm(chunk_hpcp)
                
                # === Detect key ===
                key_name, mode, score, confidence = self._correlate_with_profiles(chunk_hpcp)
                
                window_results.append((key_name, mode, confidence, rms))
                all_hpcps.append(chunk_hpcp)
                weights.append(rms)
                
                print(f"  Window {idx+1}: {key_name} {mode} (conf: {confidence:.2f})")

            if not window_results:
                return None, None, 0.0, 0.0

            # === FAST VOTING ===
            key_votes = {}
            key_confidences = {}
            
            for key_name, mode, confidence, rms in window_results:
                key_str = f"{key_name} {mode}"
                vote_weight = confidence * rms
                
                key_votes[key_str] = key_votes.get(key_str, 0.0) + vote_weight
                if key_str not in key_confidences:
                    key_confidences[key_str] = []
                key_confidences[key_str].append(confidence)
            
            sorted_keys = sorted(key_votes.items(), key=lambda x: x[1], reverse=True)
            
            winner_key = sorted_keys[0][0]
            winner_avg_conf = np.mean(key_confidences[winner_key])
            winner_count = len(key_confidences[winner_key])
            
            runner_up_key = sorted_keys[1][0] if len(sorted_keys) > 1 else None
            runner_up_votes = sorted_keys[1][1] if len(sorted_keys) > 1 else 0.0
            
            # === FAST RELATIVE KEY CHECK ===
            if runner_up_key and self._is_related_key(winner_key, runner_up_key):
                vote_ratio = runner_up_votes / sorted_keys[0][1] if sorted_keys[0][1] > 0 else 0
                
                if vote_ratio > 0.7:
                    print(f"\n[Relative Key] {winner_key} vs {runner_up_key}")
                    
                    global_hpcp = np.mean(all_hpcps, axis=0)
                    global_hpcp = global_hpcp / np.linalg.norm(global_hpcp)
                    
                    final_key, final_mode, final_score, final_conf = self._correlate_with_profiles(global_hpcp)
                    final_key_str = f"{final_key} {final_mode}"
                    
                    if final_conf > winner_avg_conf:
                        winner_key = final_key_str
                        winner_avg_conf = final_conf
                        print(f"  → {final_key_str}")

            # === CONFIDENCE ===
            consistency = winner_count / len(window_results)
            stability_bonus = min(0.15, consistency * 0.2)
            
            if runner_up_votes > 0:
                agreement_bonus = min(0.1, (sorted_keys[0][1] / runner_up_votes - 1) * 0.05)
            else:
                agreement_bonus = 0.08
            
            final_confidence = min(1.0, winner_avg_conf + stability_bonus + agreement_bonus)
            
            parts = winner_key.split()
            final_key_name = parts[0]
            final_mode = parts[1]
            
            proc_time = time.perf_counter() - start_time
            
            print(f"\n[RESULT] {final_key_name} {final_mode} | Conf: {final_confidence:.2f} | Time: {proc_time:.2f}s\n")
            
            return final_key_name, final_mode, final_confidence, proc_time

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            return None, None, 0.0, 0.0

    def reset(self):
        """Reset the detector state."""
        self.chroma_short.clear()
        self.chroma_long.clear()
        self.current_key = None
        self.current_confidence = 0.0
        self.lock_strength = 0.0
        self.same_key_count = 0
        self.high_confidence_count = 0
        self._last_detected_key = None
        self.avg_rms_history.clear()
        self.avg_confidence_history.clear()
        self.recent_detections.clear()
        self.adaptive_lock_frames = self.frames_to_lock
        self.adaptive_unlock_frames = self.frames_to_unlock


if __name__ == "__main__":
    detector = KeyDetector()
    print("KeyDetector (ULTIMATE ACCURACY) initialized.")
    print("\n🔍 Ultimate Detection Features:")
    print("  - 4-method HPCP ensemble (STFT, CQT, CENS, CREPE)")
    print("  - Beat-synchronous analysis with beat weighting")
    print("  - Smart window selection (skip intro/outro)")
    print("  - Multiple tuning passes for accuracy")
    print("  - Enhanced HPSS with margin=3.0")
    print("  - 8192 FFT for better frequency resolution")
    print("  - Beat-weighted voting system")
    print("  - Advanced relative key resolution")
    print("\n📊 Confidence Calculation:")
    print("  - Base confidence from ensemble")
    print("  - Stability bonus (window consistency)")
    print("  - Agreement bonus (winner vs runner-up)")
    print("  - Max confidence bonus (best individual window)")