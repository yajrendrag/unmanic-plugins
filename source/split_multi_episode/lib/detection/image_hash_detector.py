#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Perceptual image hash-based episode boundary detection.

Extracts frames and uses perceptual hashing to find recurring
intro/outro sequences within a single file.
"""

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.image_hash_detector")

# Optional imports - these may not be available
try:
    from PIL import Image
    import imagehash
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
    logger.warning("imagehash/Pillow not available - image hash detection disabled")


@dataclass
class FrameHash:
    """Represents a frame with its perceptual hash."""
    timestamp: float      # seconds
    hash_value: str       # perceptual hash as string
    frame_path: str       # temporary frame file path


@dataclass
class HashMatch:
    """Represents a match between two frames with similar hashes."""
    timestamp1: float
    timestamp2: float
    similarity: float     # 0.0 to 1.0 (1.0 = identical)


@dataclass
class EpisodeBoundary:
    """Represents a detected episode boundary."""
    start_time: float  # seconds
    end_time: float    # seconds
    confidence: float  # 0.0 to 1.0
    source: str        # detection method name
    metadata: dict     # additional info


class ImageHashDetector:
    """
    Detects episode boundaries using perceptual image hashing.

    Extracts frames at regular intervals and computes perceptual hashes
    to find recurring patterns (intros/outros) that indicate episode boundaries.
    """

    CONFIDENCE = 0.85

    def __init__(
        self,
        frame_interval: float = 30.0,
        hash_threshold: int = 10,
        min_episode_length: float = 900,
        max_episode_length: float = 5400,
        intro_search_duration: float = 180,  # Search first 3 minutes for intro
    ):
        """
        Initialize the image hash detector.

        Args:
            frame_interval: Interval between frame extractions (seconds)
            hash_threshold: Maximum hamming distance for hash match
            min_episode_length: Minimum episode duration in seconds
            max_episode_length: Maximum episode duration in seconds
            intro_search_duration: Duration at start/end to search for intros
        """
        self.frame_interval = frame_interval
        self.hash_threshold = hash_threshold
        self.min_episode_length = min_episode_length
        self.max_episode_length = max_episode_length
        self.intro_search_duration = intro_search_duration

    def is_available(self) -> bool:
        """Check if required libraries are available."""
        return IMAGEHASH_AVAILABLE

    def detect(self, file_path: str, total_duration: float) -> List[EpisodeBoundary]:
        """
        Detect episode boundaries from recurring visual patterns.

        Args:
            file_path: Path to the video file
            total_duration: Total duration of the file in seconds

        Returns:
            List of EpisodeBoundary objects representing detected episodes
        """
        if not self.is_available():
            logger.warning("Image hash detection not available (missing dependencies)")
            return []

        with tempfile.TemporaryDirectory(prefix='split_hash_') as temp_dir:
            # Extract frames
            frame_hashes = self._extract_and_hash_frames(file_path, total_duration, temp_dir)

            if len(frame_hashes) < 10:
                logger.debug("Not enough frames extracted for analysis")
                return []

            logger.info(f"Extracted and hashed {len(frame_hashes)} frames")

            # Find matching patterns
            matches = self._find_hash_matches(frame_hashes)

            if not matches:
                logger.debug("No recurring patterns found")
                return []

            logger.info(f"Found {len(matches)} potential recurring patterns")

            # Convert matches to boundaries
            boundaries = self._matches_to_boundaries(matches, total_duration)

            logger.info(f"Detected {len(boundaries)} episode boundaries from image patterns")
            return boundaries

    def _extract_and_hash_frames(
        self,
        file_path: str,
        total_duration: float,
        temp_dir: str
    ) -> List[FrameHash]:
        """
        Extract frames at intervals and compute perceptual hashes.

        Args:
            file_path: Path to the video file
            total_duration: Total file duration
            temp_dir: Temporary directory for frame files

        Returns:
            List of FrameHash objects
        """
        frame_hashes = []
        timestamps = []

        # Generate timestamps for frame extraction
        # Focus on potential intro/outro locations
        current_time = 0.0
        while current_time < total_duration:
            timestamps.append(current_time)
            current_time += self.frame_interval

        # Extract frames using ffmpeg
        for i, ts in enumerate(timestamps):
            frame_path = os.path.join(temp_dir, f'frame_{i:05d}.jpg')

            cmd = [
                'ffmpeg',
                '-ss', str(ts),
                '-i', file_path,
                '-vframes', '1',
                '-q:v', '2',
                '-y',
                frame_path
            ]

            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=30
                )
            except Exception as e:
                logger.debug(f"Failed to extract frame at {ts}s: {e}")
                continue

            if os.path.exists(frame_path):
                try:
                    # Compute perceptual hash
                    img = Image.open(frame_path)
                    phash = imagehash.phash(img)

                    frame_hashes.append(FrameHash(
                        timestamp=ts,
                        hash_value=str(phash),
                        frame_path=frame_path
                    ))
                except Exception as e:
                    logger.debug(f"Failed to hash frame at {ts}s: {e}")

        return frame_hashes

    def _find_hash_matches(self, frame_hashes: List[FrameHash]) -> List[HashMatch]:
        """
        Find frames with similar perceptual hashes.

        Looks for patterns that repeat at intervals suggesting episode boundaries.

        Args:
            frame_hashes: List of FrameHash objects

        Returns:
            List of HashMatch objects
        """
        matches = []

        # Compare hashes to find similar frames
        for i, hash1 in enumerate(frame_hashes):
            for j, hash2 in enumerate(frame_hashes[i + 1:], i + 1):
                # Skip frames that are too close in time
                time_diff = abs(hash2.timestamp - hash1.timestamp)
                if time_diff < self.min_episode_length:
                    continue

                # Compare perceptual hashes
                try:
                    h1 = imagehash.hex_to_hash(hash1.hash_value)
                    h2 = imagehash.hex_to_hash(hash2.hash_value)
                    distance = h1 - h2

                    if distance <= self.hash_threshold:
                        similarity = 1.0 - (distance / 64.0)  # Normalize to 0-1
                        matches.append(HashMatch(
                            timestamp1=hash1.timestamp,
                            timestamp2=hash2.timestamp,
                            similarity=similarity
                        ))
                except Exception as e:
                    logger.debug(f"Hash comparison error: {e}")

        return matches

    def _matches_to_boundaries(
        self,
        matches: List[HashMatch],
        total_duration: float
    ) -> List[EpisodeBoundary]:
        """
        Convert hash matches to episode boundaries.

        Analyzes the time intervals between matching frames to identify
        recurring patterns that suggest episode boundaries.

        Args:
            matches: List of HashMatch objects
            total_duration: Total file duration

        Returns:
            List of EpisodeBoundary objects
        """
        if not matches:
            return []

        # Group matches by their interval (time between matching frames)
        interval_counts: Dict[int, List[HashMatch]] = {}

        for match in matches:
            interval = int(match.timestamp2 - match.timestamp1)
            # Round to nearest minute for grouping
            interval_bucket = (interval // 60) * 60

            if interval_bucket not in interval_counts:
                interval_counts[interval_bucket] = []
            interval_counts[interval_bucket].append(match)

        # Find the most common interval (likely episode length)
        if not interval_counts:
            return []

        best_interval = max(interval_counts.keys(), key=lambda k: len(interval_counts[k]))
        best_matches = interval_counts[best_interval]

        logger.debug(f"Most common interval: {best_interval}s ({len(best_matches)} matches)")

        # Validate interval is within episode length range
        if not (self.min_episode_length <= best_interval <= self.max_episode_length):
            logger.debug(f"Interval {best_interval}s outside valid episode range")
            return []

        # Create boundaries based on the detected interval
        boundaries = []
        current_start = 0.0
        episode_count = int(total_duration / best_interval)

        for i in range(episode_count):
            start = i * best_interval
            end = min((i + 1) * best_interval, total_duration)

            if end - start >= self.min_episode_length * 0.8:  # Allow some tolerance
                boundaries.append(EpisodeBoundary(
                    start_time=start,
                    end_time=end,
                    confidence=self.CONFIDENCE * (len(best_matches) / len(matches)),
                    source='image_hash',
                    metadata={
                        'detected_interval': best_interval,
                        'match_count': len(best_matches),
                    }
                ))

        return boundaries

    def detect_intro_pattern(
        self,
        file_path: str,
        total_duration: float,
        candidate_times: List[float]
    ) -> List[Tuple[float, float]]:
        """
        Check if similar visual patterns exist at candidate boundary times.

        Args:
            file_path: Path to the video file
            total_duration: Total file duration
            candidate_times: List of potential boundary timestamps

        Returns:
            List of (timestamp, confidence) tuples for confirmed boundaries
        """
        if not self.is_available() or len(candidate_times) < 2:
            return []

        with tempfile.TemporaryDirectory(prefix='split_intro_') as temp_dir:
            # Extract frames at candidate times (and shortly after for intro detection)
            intro_hashes = []

            for ts in candidate_times:
                # Extract frames at the boundary and shortly after
                for offset in [0, 5, 10, 30, 60]:
                    frame_ts = ts + offset
                    if frame_ts >= total_duration:
                        continue

                    frame_path = os.path.join(temp_dir, f'intro_{ts:.0f}_{offset}.jpg')

                    cmd = [
                        'ffmpeg',
                        '-ss', str(frame_ts),
                        '-i', file_path,
                        '-vframes', '1',
                        '-q:v', '2',
                        '-y',
                        frame_path
                    ]

                    try:
                        subprocess.run(cmd, capture_output=True, timeout=30)
                        if os.path.exists(frame_path):
                            img = Image.open(frame_path)
                            phash = str(imagehash.phash(img))
                            intro_hashes.append((ts, offset, phash))
                    except Exception:
                        pass

            # Compare intro sequences across candidate times
            confirmed = []
            for i, ts1 in enumerate(candidate_times[:-1]):
                for ts2 in candidate_times[i + 1:]:
                    # Get hashes for both timestamps
                    hashes1 = [(o, h) for t, o, h in intro_hashes if t == ts1]
                    hashes2 = [(o, h) for t, o, h in intro_hashes if t == ts2]

                    # Compare matching offsets
                    match_count = 0
                    for o1, h1 in hashes1:
                        for o2, h2 in hashes2:
                            if o1 == o2:
                                try:
                                    dist = imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2)
                                    if dist <= self.hash_threshold:
                                        match_count += 1
                                except Exception:
                                    pass

                    if match_count >= 2:  # At least 2 matching frames
                        confidence = min(0.9, 0.7 + match_count * 0.05)
                        if ts1 not in [c[0] for c in confirmed]:
                            confirmed.append((ts1, confidence))
                        if ts2 not in [c[0] for c in confirmed]:
                            confirmed.append((ts2, confidence))

            return confirmed
