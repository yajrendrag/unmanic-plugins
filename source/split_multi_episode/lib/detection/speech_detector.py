#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Speech-based episode boundary detection using faster-whisper.

Uses speech-to-text to detect phrases like "Stay tuned", "Next time on",
etc. that indicate the episode content has ended. The actual split point
should be AFTER these phrases, at the next black/silent scene (ideally
within 30 seconds).
"""

import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.speech_detector")


def _setup_nvidia_libraries():
    """
    Set up nvidia pip package libraries for ctranslate2/faster-whisper.

    When nvidia-cublas-cu12 etc. are installed via pip, they put .so files
    in site-packages/nvidia/*/lib/ which ctranslate2 doesn't find by default.
    We preload them with ctypes so they're available when ctranslate2 needs them.
    """
    import ctypes
    import glob

    nvidia_libs_loaded = False
    try:
        # Find nvidia package location via site-packages
        import nvidia
        nvidia_base = os.path.dirname(nvidia.__path__[0]) if hasattr(nvidia, '__path__') else None

        if nvidia_base is None:
            return False

        # Find cublas and cudnn lib directories
        cublas_dir = os.path.join(nvidia_base, 'nvidia', 'cublas', 'lib')
        cudnn_dir = os.path.join(nvidia_base, 'nvidia', 'cudnn', 'lib')

        nvidia_paths = []
        if os.path.isdir(cublas_dir):
            nvidia_paths.append(cublas_dir)
        if os.path.isdir(cudnn_dir):
            nvidia_paths.append(cudnn_dir)

        if not nvidia_paths:
            return False

        # Add to LD_LIBRARY_PATH for any subprocess or dlopen calls
        current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        new_paths = [p for p in nvidia_paths if p not in current_ld_path]

        if new_paths:
            new_ld_path = ':'.join(new_paths)
            if current_ld_path:
                new_ld_path = f"{new_ld_path}:{current_ld_path}"
            os.environ['LD_LIBRARY_PATH'] = new_ld_path

        # Preload libraries with ctypes so they're available for ctranslate2
        libs_to_load = [
            os.path.join(cublas_dir, 'libcublas.so.12'),
            os.path.join(cublas_dir, 'libcublasLt.so.12'),
            os.path.join(cudnn_dir, 'libcudnn.so.9'),
        ]

        for lib_path in libs_to_load:
            if os.path.exists(lib_path):
                try:
                    ctypes.CDLL(lib_path, mode=ctypes.RTLD_GLOBAL)
                    nvidia_libs_loaded = True
                except OSError:
                    pass

    except (ImportError, AttributeError, IndexError):
        # nvidia packages not installed via pip
        pass

    return nvidia_libs_loaded


# Set up nvidia libraries BEFORE importing faster_whisper/ctranslate2
_nvidia_libs_loaded = _setup_nvidia_libraries()

# Optional imports
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.debug("faster-whisper not available")

# Note: stable-ts integration removed - faster-whisper alone is sufficient
# for detecting episode-end phrases


@dataclass
class SpeechSegment:
    """A transcribed speech segment with timing."""
    start_time: float  # seconds
    end_time: float    # seconds
    text: str
    confidence: float


# Phrases that indicate episode content has ended - split should be AFTER these
# (typically after a brief preview, at the next black/silent scene)
EPISODE_END_PHRASES = [
    "stay tuned",
    "next time on",
    "next on",
    "coming up next",
    "coming up on",
    "on the next episode",
    "on the next",
    "scenes from our next",
    "scenes from the next",
    "next week on",
    "previously on",  # This indicates START of next episode
]


class SpeechDetector:
    """
    Detects episode boundaries using speech-to-text analysis.

    Uses faster-whisper to transcribe audio and find phrases that
    indicate episode boundaries or preview content.
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        min_episode_length: float = 900,
        max_episode_length: float = 5400,
    ):
        """
        Initialize the speech detector.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v2)
            device: Device to use (auto, cpu, cuda)
            compute_type: Compute type (auto, int8, float16, float32)
            min_episode_length: Minimum episode duration in seconds
            max_episode_length: Maximum episode duration in seconds
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.min_episode_length = min_episode_length
        self.max_episode_length = max_episode_length
        self._model = None

    def is_available(self) -> bool:
        """Check if faster-whisper is available."""
        return WHISPER_AVAILABLE

    def _get_model(self):
        """Lazy-load the Whisper model."""
        if self._model is None and WHISPER_AVAILABLE:
            logger.info(f"Loading Whisper model: {self.model_size}")
            try:
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type
                )
                logger.info(f"Whisper model loaded successfully (device={self.device})")
            except Exception as e:
                # CUDA libraries may be missing or incompatible - fall back to CPU
                error_str = str(e).lower()
                if "cuda" in error_str or "cublas" in error_str or "cudnn" in error_str:
                    logger.warning(f"CUDA not available ({e}), falling back to CPU")
                    try:
                        self._model = WhisperModel(
                            self.model_size,
                            device="cpu",
                            compute_type="int8"
                        )
                        logger.info("Whisper model loaded on CPU (fallback)")
                    except Exception as e2:
                        logger.error(f"Failed to load Whisper model on CPU: {e2}")
                        self._model = None
                else:
                    logger.error(f"Failed to load Whisper model: {e}")
                    self._model = None
        return self._model

    def detect_in_windows(
        self,
        file_path: str,
        search_windows: List,  # List of SearchWindow objects
        total_duration: float,
    ) -> List[Tuple[float, float, dict]]:
        """
        Find episode-end markers within each search window using speech detection.

        Transcribes audio in each window and looks for phrases indicating
        the episode has ended (e.g., "Stay tuned for scenes from...").

        Args:
            file_path: Path to the video file
            search_windows: List of SearchWindow objects defining where to search
            total_duration: Total file duration

        Returns:
            List of (marker_time, confidence, metadata) tuples, one per window.
            marker_time is the END of the detected phrase - the actual split
            should be at a black/silent scene AFTER this time (within ~30 sec).
        """
        if not self.is_available():
            logger.warning("Speech detection not available (faster-whisper not installed)")
            return [(w.center_time, 0.3, {'source': 'speech_fallback', 'fallback': True})
                    for w in search_windows]

        results = []
        model = self._get_model()

        if model is None:
            return [(w.center_time, 0.3, {'source': 'speech_fallback', 'fallback': True})
                    for w in search_windows]

        with tempfile.TemporaryDirectory(prefix='split_speech_') as temp_dir:
            for window in search_windows:
                window_duration = window.end_time - window.start_time

                # Extract audio for this window
                audio_path = os.path.join(temp_dir, f'window_{window.start_time:.0f}.wav')
                if not self._extract_audio(file_path, window.start_time, window_duration, audio_path):
                    logger.debug(f"Failed to extract audio for window {window.start_time/60:.1f}-{window.end_time/60:.1f}m")
                    results.append((window.center_time, 0.3, {
                        'source': 'speech_fallback',
                        'window_source': window.source,
                        'fallback': True,
                    }))
                    continue

                # Transcribe the audio
                segments = self._transcribe(audio_path, window.start_time)

                if not segments:
                    logger.debug(f"No speech detected in window {window.start_time/60:.1f}-{window.end_time/60:.1f}m")
                    results.append((window.center_time, 0.3, {
                        'source': 'speech_fallback',
                        'window_source': window.source,
                        'fallback': True,
                    }))
                    continue

                # Look for episode-end phrases
                episode_end_markers = self._find_episode_end_markers(segments)

                if episode_end_markers:
                    # Found "stay tuned" or similar - split should be AFTER this
                    # at the next black/silent scene (ideally within 30 seconds)
                    first_marker = episode_end_markers[0]
                    # Return the END time of the phrase as the minimum boundary point
                    marker_time = first_marker.end_time

                    logger.info(
                        f"Window {window.start_time/60:.1f}-{window.end_time/60:.1f}m: "
                        f"Found '{first_marker.text}' at {first_marker.start_time/60:.1f}m "
                        f"(ends at {marker_time/60:.1f}m) - split should be AFTER this"
                    )

                    results.append((marker_time, 0.85, {
                        'source': 'speech_episode_end',
                        'window_source': window.source,
                        'episode_end_phrase': first_marker.text,
                        'phrase_start_time': first_marker.start_time,
                        'phrase_end_time': first_marker.end_time,
                    }))
                else:
                    # No episode-end phrases found - return fallback
                    logger.debug(
                        f"Window {window.start_time/60:.1f}-{window.end_time/60:.1f}m: "
                        f"No episode-end phrases detected"
                    )
                    results.append((window.center_time, 0.3, {
                        'source': 'speech_fallback',
                        'window_source': window.source,
                        'fallback': True,
                    }))

        return results

    def _extract_audio(
        self,
        file_path: str,
        start_time: float,
        duration: float,
        output_path: str
    ) -> bool:
        """
        Extract audio from video file for a specific time window.

        Args:
            file_path: Path to the video file
            start_time: Start time in seconds
            duration: Duration in seconds
            output_path: Path to save the extracted audio

        Returns:
            True if extraction succeeded, False otherwise
        """
        cmd = [
            'ffmpeg',
            '-ss', str(start_time),
            '-i', file_path,
            '-t', str(duration),
            '-vn',  # No video
            '-acodec', 'pcm_s16le',  # PCM format for Whisper
            '-ar', '16000',  # 16kHz sample rate
            '-ac', '1',  # Mono
            '-y',
            output_path
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=120
            )
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            logger.error(f"Audio extraction failed: {e}")
            return False

    def _transcribe(
        self,
        audio_path: str,
        time_offset: float
    ) -> List[SpeechSegment]:
        """
        Transcribe audio file using faster-whisper.

        Args:
            audio_path: Path to the audio file
            time_offset: Time offset to add to segment timestamps (window start time)

        Returns:
            List of SpeechSegment objects with absolute timestamps
        """
        model = self._get_model()
        if model is None:
            return []

        try:
            # Use faster-whisper for transcription
            segments_gen, info = model.transcribe(
                audio_path,
                beam_size=5,
                vad_filter=True,
            )
            segments = []
            for segment in segments_gen:
                segments.append(SpeechSegment(
                    start_time=segment.start + time_offset,
                    end_time=segment.end + time_offset,
                    text=segment.text.strip().lower(),
                    confidence=segment.avg_logprob if hasattr(segment, 'avg_logprob') else 0.0
                ))
            return segments

        except Exception as e:
            # Check if this is a CUDA library error - try to reload on CPU and retry
            error_str = str(e).lower()
            if "cuda" in error_str or "cublas" in error_str or "cudnn" in error_str:
                logger.warning(f"CUDA error during transcription ({e}), reloading model on CPU")
                try:
                    self._model = WhisperModel(
                        self.model_size,
                        device="cpu",
                        compute_type="int8"
                    )
                    logger.info("Whisper model reloaded on CPU, retrying transcription")
                    # Retry transcription on CPU
                    segments_gen, info = self._model.transcribe(
                        audio_path,
                        beam_size=5,
                        vad_filter=True,
                    )
                    segments = []
                    for segment in segments_gen:
                        segments.append(SpeechSegment(
                            start_time=segment.start + time_offset,
                            end_time=segment.end + time_offset,
                            text=segment.text.strip().lower(),
                            confidence=segment.avg_logprob if hasattr(segment, 'avg_logprob') else 0.0
                        ))
                    return segments
                except Exception as e2:
                    logger.error(f"CPU fallback transcription also failed: {e2}")
                    return []
            else:
                logger.error(f"Transcription failed: {e}")
                return []

    def _find_episode_end_markers(
        self,
        segments: List[SpeechSegment]
    ) -> List[SpeechSegment]:
        """
        Find segments containing episode-end phrases.

        Args:
            segments: List of transcribed segments

        Returns:
            List of segments containing episode-end phrases, sorted by time
        """
        markers = []

        for segment in segments:
            text = segment.text.lower()
            for phrase in EPISODE_END_PHRASES:
                if phrase in text:
                    markers.append(segment)
                    logger.debug(f"Found episode-end phrase: '{phrase}' in '{segment.text}' at {segment.start_time/60:.1f}m")
                    break  # Don't add same segment multiple times

        # Sort by start time
        markers.sort(key=lambda x: x.start_time)
        return markers
