#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Audio fingerprint-based episode boundary detection.

Extracts audio segments and uses fingerprinting to find recurring
intro music patterns within a single file.
"""

import logging
import os
import subprocess
import tempfile
import hashlib
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.audio_fingerprint")


@dataclass
class AudioSegment:
    """Represents an extracted audio segment."""
    timestamp: float      # seconds
    duration: float       # segment duration
    file_path: str        # temporary audio file path
    fingerprint: str      # audio fingerprint/hash


@dataclass
class AudioMatch:
    """Represents a match between two audio segments."""
    timestamp1: float
    timestamp2: float
    similarity: float     # 0.0 to 1.0


@dataclass
class EpisodeBoundary:
    """Represents a detected episode boundary."""
    start_time: float  # seconds
    end_time: float    # seconds
    confidence: float  # 0.0 to 1.0
    source: str        # detection method name
    metadata: dict     # additional info


class AudioFingerprintDetector:
    """
    Detects episode boundaries using audio fingerprinting.

    Extracts short audio segments at potential boundaries and
    compares them to find recurring intro/outro music patterns.
    """

    CONFIDENCE = 0.85

    def __init__(
        self,
        segment_duration: float = 30.0,
        sample_rate: int = 8000,
        min_episode_length: float = 900,
        max_episode_length: float = 5400,
        intro_search_duration: float = 180,
    ):
        """
        Initialize the audio fingerprint detector.

        Args:
            segment_duration: Duration of audio segments to extract (seconds)
            sample_rate: Sample rate for audio analysis
            min_episode_length: Minimum episode duration in seconds
            max_episode_length: Maximum episode duration in seconds
            intro_search_duration: Duration at start to search for intro music
        """
        self.segment_duration = segment_duration
        self.sample_rate = sample_rate
        self.min_episode_length = min_episode_length
        self.max_episode_length = max_episode_length
        self.intro_search_duration = intro_search_duration

    def detect(self, file_path: str, total_duration: float) -> List[EpisodeBoundary]:
        """
        Detect episode boundaries from recurring audio patterns.

        Args:
            file_path: Path to the video file
            total_duration: Total duration of the file in seconds

        Returns:
            List of EpisodeBoundary objects representing detected episodes
        """
        with tempfile.TemporaryDirectory(prefix='split_audio_') as temp_dir:
            # Extract audio segments at potential boundary points
            segments = self._extract_audio_segments(file_path, total_duration, temp_dir)

            if len(segments) < 2:
                logger.debug("Not enough audio segments for analysis")
                return []

            logger.info(f"Extracted {len(segments)} audio segments")

            # Find matching patterns
            matches = self._find_audio_matches(segments)

            if not matches:
                logger.debug("No recurring audio patterns found")
                return []

            logger.info(f"Found {len(matches)} potential recurring audio patterns")

            # Convert matches to boundaries
            boundaries = self._matches_to_boundaries(matches, total_duration)

            logger.info(f"Detected {len(boundaries)} episode boundaries from audio patterns")
            return boundaries

    def _extract_audio_segments(
        self,
        file_path: str,
        total_duration: float,
        temp_dir: str
    ) -> List[AudioSegment]:
        """
        Extract audio segments at potential boundary locations.

        Args:
            file_path: Path to the video file
            total_duration: Total file duration
            temp_dir: Temporary directory for audio files

        Returns:
            List of AudioSegment objects
        """
        segments = []

        # Estimate potential episode starts
        # Sample at beginning, then every ~20 minutes, plus around silence/black regions
        timestamps = [0.0]

        current = self.min_episode_length
        while current < total_duration - self.segment_duration:
            timestamps.append(current)
            current += self.min_episode_length / 2  # Sample every ~7.5 minutes

        for i, ts in enumerate(timestamps):
            if ts + self.segment_duration > total_duration:
                continue

            audio_path = os.path.join(temp_dir, f'audio_{i:04d}.wav')

            # Extract audio segment
            cmd = [
                'ffmpeg',
                '-ss', str(ts),
                '-i', file_path,
                '-t', str(self.segment_duration),
                '-vn',  # No video
                '-ac', '1',  # Mono
                '-ar', str(self.sample_rate),  # Lower sample rate for fingerprinting
                '-y',
                audio_path
            ]

            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=60
                )
            except Exception as e:
                logger.debug(f"Failed to extract audio at {ts}s: {e}")
                continue

            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
                # Generate simple audio fingerprint
                fingerprint = self._generate_fingerprint(audio_path)

                segments.append(AudioSegment(
                    timestamp=ts,
                    duration=self.segment_duration,
                    file_path=audio_path,
                    fingerprint=fingerprint
                ))

        return segments

    def _generate_fingerprint(self, audio_path: str) -> str:
        """
        Generate a simple audio fingerprint from a WAV file.

        Uses a combination of spectral analysis and statistical features.
        For more accurate results, consider using chromaprint/acoustid.

        Args:
            audio_path: Path to the audio file

        Returns:
            Fingerprint string
        """
        try:
            # Read the raw audio data and compute a hash
            # This is a simplified approach - for production use chromaprint
            with open(audio_path, 'rb') as f:
                data = f.read()

            # Skip WAV header (44 bytes) and hash the audio data
            audio_data = data[44:]

            # Compute hash on downsampled data for robustness
            step = max(1, len(audio_data) // 10000)
            sampled_data = audio_data[::step]

            # Use MD5 for speed (not cryptographic purposes)
            return hashlib.md5(sampled_data).hexdigest()

        except Exception as e:
            logger.debug(f"Failed to generate fingerprint: {e}")
            return ""

    def _find_audio_matches(self, segments: List[AudioSegment]) -> List[AudioMatch]:
        """
        Find segments with similar audio fingerprints.

        Args:
            segments: List of AudioSegment objects

        Returns:
            List of AudioMatch objects
        """
        matches = []

        # Group segments by fingerprint similarity
        # For the simple MD5 approach, we need exact matches
        # For more sophisticated matching, use acoustic fingerprinting libraries

        fingerprint_groups: Dict[str, List[AudioSegment]] = {}

        for segment in segments:
            if segment.fingerprint:
                if segment.fingerprint not in fingerprint_groups:
                    fingerprint_groups[segment.fingerprint] = []
                fingerprint_groups[segment.fingerprint].append(segment)

        # Find groups with multiple segments (recurring patterns)
        for fingerprint, group in fingerprint_groups.items():
            if len(group) >= 2:
                # All segments in the group match each other
                for i, seg1 in enumerate(group):
                    for seg2 in group[i + 1:]:
                        time_diff = abs(seg2.timestamp - seg1.timestamp)
                        if time_diff >= self.min_episode_length:
                            matches.append(AudioMatch(
                                timestamp1=min(seg1.timestamp, seg2.timestamp),
                                timestamp2=max(seg1.timestamp, seg2.timestamp),
                                similarity=1.0
                            ))

        # Also try to find similar (but not identical) audio using spectral comparison
        matches.extend(self._find_spectral_matches(segments))

        return matches

    def _find_spectral_matches(self, segments: List[AudioSegment]) -> List[AudioMatch]:
        """
        Find similar audio using spectral analysis.

        A more robust comparison than exact fingerprint matching.

        Args:
            segments: List of AudioSegment objects

        Returns:
            List of AudioMatch objects
        """
        matches = []

        # Compare audio energy profiles
        profiles = []
        for seg in segments:
            profile = self._compute_energy_profile(seg.file_path)
            if profile:
                profiles.append((seg, profile))

        # Compare profiles
        for i, (seg1, prof1) in enumerate(profiles):
            for seg2, prof2 in profiles[i + 1:]:
                time_diff = abs(seg2.timestamp - seg1.timestamp)
                if time_diff < self.min_episode_length:
                    continue

                similarity = self._compare_profiles(prof1, prof2)
                if similarity > 0.7:
                    matches.append(AudioMatch(
                        timestamp1=min(seg1.timestamp, seg2.timestamp),
                        timestamp2=max(seg1.timestamp, seg2.timestamp),
                        similarity=similarity
                    ))

        return matches

    def _compute_energy_profile(self, audio_path: str) -> Optional[List[float]]:
        """
        Compute an energy profile (simplified spectral analysis).

        Args:
            audio_path: Path to audio file

        Returns:
            List of energy values or None on error
        """
        try:
            with open(audio_path, 'rb') as f:
                data = f.read()[44:]  # Skip WAV header

            # Convert bytes to samples (assuming 16-bit audio)
            samples = []
            for i in range(0, len(data) - 1, 2):
                sample = int.from_bytes(data[i:i+2], 'little', signed=True)
                samples.append(abs(sample))

            if not samples:
                return None

            # Compute energy in bins
            num_bins = 100
            bin_size = len(samples) // num_bins
            profile = []

            for i in range(num_bins):
                start = i * bin_size
                end = start + bin_size
                bin_energy = sum(samples[start:end]) / bin_size if bin_size > 0 else 0
                profile.append(bin_energy)

            # Normalize
            max_energy = max(profile) if profile else 1
            if max_energy > 0:
                profile = [e / max_energy for e in profile]

            return profile

        except Exception as e:
            logger.debug(f"Failed to compute energy profile: {e}")
            return None

    def _compare_profiles(self, prof1: List[float], prof2: List[float]) -> float:
        """
        Compare two energy profiles.

        Args:
            prof1: First energy profile
            prof2: Second energy profile

        Returns:
            Similarity score (0.0 to 1.0)
        """
        if not prof1 or not prof2 or len(prof1) != len(prof2):
            return 0.0

        # Compute correlation
        diff_sum = sum(abs(a - b) for a, b in zip(prof1, prof2))
        avg_diff = diff_sum / len(prof1)

        # Convert to similarity (0 diff = 1.0 similarity)
        similarity = max(0.0, 1.0 - avg_diff)
        return similarity

    def _matches_to_boundaries(
        self,
        matches: List[AudioMatch],
        total_duration: float
    ) -> List[EpisodeBoundary]:
        """
        Convert audio matches to episode boundaries.

        Args:
            matches: List of AudioMatch objects
            total_duration: Total file duration

        Returns:
            List of EpisodeBoundary objects
        """
        if not matches:
            return []

        # Group by interval
        interval_counts: Dict[int, List[AudioMatch]] = {}

        for match in matches:
            interval = int(match.timestamp2 - match.timestamp1)
            interval_bucket = (interval // 60) * 60  # Round to minute

            if interval_bucket not in interval_counts:
                interval_counts[interval_bucket] = []
            interval_counts[interval_bucket].append(match)

        if not interval_counts:
            return []

        # Find most common interval
        best_interval = max(interval_counts.keys(), key=lambda k: len(interval_counts[k]))
        best_matches = interval_counts[best_interval]

        if not (self.min_episode_length <= best_interval <= self.max_episode_length):
            return []

        # Create boundaries
        boundaries = []
        episode_count = int(total_duration / best_interval)

        for i in range(episode_count):
            start = i * best_interval
            end = min((i + 1) * best_interval, total_duration)

            if end - start >= self.min_episode_length * 0.8:
                avg_similarity = sum(m.similarity for m in best_matches) / len(best_matches)
                confidence = self.CONFIDENCE * avg_similarity

                boundaries.append(EpisodeBoundary(
                    start_time=start,
                    end_time=end,
                    confidence=confidence,
                    source='audio_fingerprint',
                    metadata={
                        'detected_interval': best_interval,
                        'match_count': len(best_matches),
                        'avg_similarity': avg_similarity,
                    }
                ))

        return boundaries
