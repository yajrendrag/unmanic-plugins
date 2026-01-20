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

    def detect_in_windows(
        self,
        file_path: str,
        search_windows: List,  # List of SearchWindow objects
        total_duration: float,
    ) -> List[Tuple[float, float, dict]]:
        """
        Find episode boundaries within search windows using audio fingerprinting.

        Extracts a reference audio segment from the start of the file (intro music),
        then searches within each window for audio that matches the intro pattern.

        Args:
            file_path: Path to the video file
            search_windows: List of SearchWindow objects defining where to search
            total_duration: Total file duration

        Returns:
            List of (boundary_time, confidence, metadata) tuples, one per window
        """
        from typing import Tuple

        results = []
        sample_interval = 10  # Sample every 10 seconds within windows

        with tempfile.TemporaryDirectory(prefix='split_audio_win_') as temp_dir:
            # Extract reference audio from the start of the file (intro music)
            # Use first 30 seconds as the intro reference
            ref_path = os.path.join(temp_dir, 'reference.wav')
            ref_segment = self._extract_single_segment(file_path, 0.0, ref_path)

            if not ref_segment:
                logger.warning("Failed to extract reference audio segment")
                return [(w.center_time, 0.3, {'fallback': True, 'source': 'audio_fallback'})
                        for w in search_windows]

            ref_profile = self._compute_energy_profile(ref_path)
            if not ref_profile:
                logger.warning("Failed to compute reference audio profile")
                return [(w.center_time, 0.3, {'fallback': True, 'source': 'audio_fallback'})
                        for w in search_windows]

            for window in search_windows:
                best_time = window.center_time
                best_similarity = 0.0

                # Sample densely within the window
                current = window.start_time
                while current < window.end_time - self.segment_duration:
                    sample_path = os.path.join(temp_dir, f'sample_{current:.0f}.wav')

                    if self._extract_single_segment(file_path, current, sample_path):
                        sample_profile = self._compute_energy_profile(sample_path)

                        if sample_profile:
                            similarity = self._compare_profiles(ref_profile, sample_profile)

                            if similarity > best_similarity:
                                best_similarity = similarity
                                best_time = current

                        # Clean up sample file
                        try:
                            os.remove(sample_path)
                        except:
                            pass

                    current += sample_interval

                # Calculate confidence based on similarity
                if best_similarity > 0.5:
                    confidence = min(0.85, 0.4 + (best_similarity * 0.5))
                    logger.debug(
                        f"Window {window.start_time/60:.1f}-{window.end_time/60:.1f}m: "
                        f"best audio match at {best_time/60:.1f}m (similarity={best_similarity:.2f})"
                    )
                    results.append((best_time, confidence, {
                        'source': 'audio_fingerprint',
                        'window_source': window.source,
                        'similarity': best_similarity,
                    }))
                else:
                    # No good match found - use window center as fallback
                    logger.debug(
                        f"Window {window.start_time/60:.1f}-{window.end_time/60:.1f}m: "
                        f"no good audio match (best similarity={best_similarity:.2f})"
                    )
                    results.append((window.center_time, 0.3, {
                        'source': 'audio_fallback',
                        'window_source': window.source,
                        'fallback': True,
                    }))

        return results

    def _extract_single_segment(
        self,
        file_path: str,
        timestamp: float,
        output_path: str,
    ) -> bool:
        """
        Extract a single audio segment at the given timestamp.

        Args:
            file_path: Path to the video file
            timestamp: Start time in seconds
            output_path: Path for output WAV file

        Returns:
            True if successful, False otherwise
        """
        cmd = [
            'ffmpeg',
            '-ss', str(timestamp),
            '-i', file_path,
            '-t', str(self.segment_duration),
            '-vn',  # No video
            '-ac', '1',  # Mono
            '-ar', str(self.sample_rate),
            '-y',
            output_path
        ]

        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            logger.debug(f"Failed to extract audio at {timestamp}s: {e}")
            return False

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

        Uses actual timestamps from matches rather than dividing into
        equal intervals. Matching audio segments indicate recurring
        intro/outro music, so those timestamps are episode starts.

        Args:
            matches: List of AudioMatch objects
            total_duration: Total file duration

        Returns:
            List of EpisodeBoundary objects
        """
        if not matches:
            return []

        # Collect all timestamps where similar audio was found
        # These are potential episode start points (intro music locations)
        timestamp_scores: Dict[float, List[float]] = {}  # timestamp -> list of similarities

        for match in matches:
            # Both timestamps in a match are potential episode starts
            for ts in [match.timestamp1, match.timestamp2]:
                if ts not in timestamp_scores:
                    timestamp_scores[ts] = []
                timestamp_scores[ts].append(match.similarity)

        if not timestamp_scores:
            return []

        # Sort timestamps and filter to those with good support
        sorted_timestamps = sorted(timestamp_scores.keys())

        # Filter: keep timestamps that appear in multiple matches or have high similarity
        good_timestamps = []
        for ts in sorted_timestamps:
            scores = timestamp_scores[ts]
            avg_score = sum(scores) / len(scores)
            # Keep if appears in multiple matches OR has high average similarity
            if len(scores) >= 2 or avg_score >= 0.8:
                good_timestamps.append((ts, avg_score, len(scores)))

        if not good_timestamps:
            # Fall back to all timestamps if filtering removed everything
            good_timestamps = [(ts, sum(s)/len(s), len(s))
                              for ts, s in timestamp_scores.items()]
            good_timestamps.sort(key=lambda x: x[0])

        # Create boundaries from consecutive timestamps
        boundaries = []
        prev_end = 0.0

        for ts, avg_sim, match_count in good_timestamps:
            # Skip if too close to previous boundary
            if ts - prev_end < self.min_episode_length * 0.5:
                continue

            # Skip timestamps too close to the start (likely the first episode's intro)
            if ts < self.min_episode_length * 0.5:
                continue

            duration = ts - prev_end
            if self.min_episode_length <= duration <= self.max_episode_length:
                confidence = self.CONFIDENCE * avg_sim * min(1.0, match_count / 3.0)

                boundaries.append(EpisodeBoundary(
                    start_time=prev_end,
                    end_time=ts,
                    confidence=confidence,
                    source='audio_fingerprint',
                    metadata={
                        'match_timestamp': ts,
                        'match_count': match_count,
                        'avg_similarity': avg_sim,
                    }
                ))
                prev_end = ts

        # Add final episode if there's remaining duration
        if total_duration - prev_end >= self.min_episode_length:
            boundaries.append(EpisodeBoundary(
                start_time=prev_end,
                end_time=total_duration,
                confidence=self.CONFIDENCE * 0.7,  # Lower confidence for final segment
                source='audio_fingerprint',
                metadata={
                    'final_episode': True,
                }
            ))

        logger.debug(f"Audio fingerprint found boundaries at: {[f'{b.end_time/60:.1f}m' for b in boundaries]}")

        return boundaries
