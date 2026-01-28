#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scene change-based episode boundary detection.

Uses FFmpeg's scene detection filter to find significant visual transitions
that indicate episode boundaries.
"""

import logging
import re
import subprocess
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.scene_change_detector")


@dataclass
class SceneChange:
    """Represents a detected scene change."""
    timestamp: float  # seconds
    score: float      # scene change score (0-1)


class SceneChangeDetector:
    """
    Detects episode boundaries by finding significant scene changes.

    Uses FFmpeg's scene detection filter to identify dramatic visual
    transitions that typically occur at episode boundaries.
    """

    def __init__(
        self,
        scene_threshold: float = 0.3,
        min_episode_length: float = 900,
        max_episode_length: float = 5400,
    ):
        """
        Initialize the scene change detector.

        Args:
            scene_threshold: Minimum scene change score to detect (0-1, default 0.3)
            min_episode_length: Minimum episode duration in seconds
            max_episode_length: Maximum episode duration in seconds
        """
        self.scene_threshold = scene_threshold
        self.min_episode_length = min_episode_length
        self.max_episode_length = max_episode_length

    def detect_in_windows(
        self,
        file_path: str,
        search_windows: List,  # List of SearchWindow objects
        total_duration: float,
    ) -> List[Tuple[float, float, dict]]:
        """
        Find the most significant scene change within each search window.

        Args:
            file_path: Path to the video file
            search_windows: List of SearchWindow objects defining where to search
            total_duration: Total file duration

        Returns:
            List of (boundary_time, confidence, metadata) tuples, one per window
        """
        results = []

        for window in search_windows:
            window_duration = window.end_time - window.start_time
            scene_changes = self._detect_scenes_in_window(
                file_path, window.start_time, window_duration
            )

            if not scene_changes:
                # No scene changes found - use center as fallback
                logger.debug(
                    f"No scene changes in window {window.start_time/60:.1f}-{window.end_time/60:.1f}m"
                )
                results.append((window.center_time, 0.3, {
                    'source': 'scene_fallback',
                    'window_source': window.source,
                    'fallback': True,
                }))
                continue

            # Find the most significant scene change
            # Weight by both score AND proximity to center
            window_half = window_duration / 2
            best_scene = None
            best_weighted_score = -1

            for scene in scene_changes:
                distance_from_center = abs(scene.timestamp - window.center_time)
                proximity = 1.0 - (distance_from_center / window_half) if window_half > 0 else 0.5

                # Combined score: scene change magnitude + proximity bonus
                weighted_score = (scene.score * 0.7) + (proximity * 0.3)

                if weighted_score > best_weighted_score:
                    best_weighted_score = weighted_score
                    best_scene = scene

            if best_scene:
                # Higher scene score = higher confidence
                confidence = min(0.90, 0.5 + (best_scene.score * 0.5))

                logger.debug(
                    f"Window {window.start_time/60:.1f}-{window.end_time/60:.1f}m: "
                    f"best scene change at {best_scene.timestamp/60:.1f}m "
                    f"(score={best_scene.score:.2f})"
                )

                results.append((best_scene.timestamp, confidence, {
                    'source': 'scene_change',
                    'window_source': window.source,
                    'scene_score': best_scene.score,
                }))
            else:
                results.append((window.center_time, 0.3, {
                    'source': 'scene_fallback',
                    'window_source': window.source,
                    'fallback': True,
                }))

        return results

    def _detect_scenes_in_window(
        self,
        file_path: str,
        window_start: float,
        window_duration: float,
    ) -> List[SceneChange]:
        """
        Detect scene changes within a specific time window.

        Args:
            file_path: Path to the video file
            window_start: Start time in seconds
            window_duration: Duration to scan in seconds

        Returns:
            List of SceneChange objects with timestamps in full-file coordinates
        """
        # Use FFmpeg to detect scene changes
        # The select filter with scene detection outputs frame info for significant changes
        cmd = [
            'ffmpeg',
            '-ss', str(window_start),
            '-i', file_path,
            '-t', str(window_duration),
            '-vf', f"select='gt(scene,{self.scene_threshold})',showinfo",
            '-f', 'null',
            '-'
        ]

        logger.debug(f"Running scene detection for window {window_start/60:.1f}-{(window_start+window_duration)/60:.1f}m")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout per window
            )
        except subprocess.TimeoutExpired:
            logger.error(f"Scene detection timed out for window at {window_start/60:.1f}m")
            return []
        except Exception as e:
            logger.error(f"Scene detection error: {e}")
            return []

        # Parse the output
        return self._parse_scene_output(result.stderr, window_start)

    def _parse_scene_output(self, output: str, window_start: float) -> List[SceneChange]:
        """
        Parse FFmpeg showinfo output for scene changes.

        The showinfo filter outputs lines like:
        [Parsed_showinfo_1 @ 0x...] n:123 pts:12345 pts_time:123.456 ...

        Args:
            output: FFmpeg stderr output
            window_start: Window start time for coordinate adjustment

        Returns:
            List of SceneChange objects
        """
        scenes = []

        # Pattern to extract pts_time from showinfo output
        # Also try to get scene score if available
        pts_pattern = re.compile(r'pts_time:\s*([\d.]+)')

        for line in output.split('\n'):
            if 'showinfo' in line.lower() and 'pts_time' in line:
                match = pts_pattern.search(line)
                if match:
                    pts_time = float(match.group(1))
                    # Adjust to full-file coordinates
                    absolute_time = pts_time + window_start

                    # Since we filtered with scene threshold, all detected frames
                    # have scene score > threshold. Estimate score from position in output.
                    # (FFmpeg doesn't directly output the scene score in showinfo)
                    # We'll use a base score of the threshold + small bonus
                    estimated_score = self.scene_threshold + 0.1

                    scenes.append(SceneChange(
                        timestamp=absolute_time,
                        score=estimated_score
                    ))

        # If we want actual scene scores, we need a different approach
        # Let's also try parsing the scene metadata if present
        scene_score_pattern = re.compile(r'scene:(\d+\.?\d*)')

        for line in output.split('\n'):
            match = scene_score_pattern.search(line)
            if match:
                # Found actual scene score - update corresponding scene
                score = float(match.group(1))
                pts_match = pts_pattern.search(line)
                if pts_match:
                    pts_time = float(pts_match.group(1))
                    absolute_time = pts_time + window_start
                    # Update or add scene with actual score
                    for scene in scenes:
                        if abs(scene.timestamp - absolute_time) < 0.1:
                            scene.score = score
                            break

        logger.debug(f"Found {len(scenes)} scene changes in window")
        return scenes

    def detect_raw_in_windows(
        self,
        file_path: str,
        search_windows: List,  # List of SearchWindow objects
    ) -> List:
        """
        Return ALL scene change detections as RawDetection objects.

        Score is based on scene change magnitude (0-1 scale * 100).

        Args:
            file_path: Path to the video file
            search_windows: List of SearchWindow objects defining where to search

        Returns:
            List of RawDetection objects (imported from raw_detection module)
        """
        from .raw_detection import RawDetection

        all_detections = []

        for window in search_windows:
            window_duration = window.end_time - window.start_time
            scene_changes = self._detect_scenes_in_window(
                file_path, window.start_time, window_duration
            )

            logger.debug(
                f"Window {window.start_time/60:.1f}-{window.end_time/60:.1f}m: "
                f"found {len(scene_changes)} scene changes"
            )

            # Convert each scene change to a RawDetection
            for scene in scene_changes:
                # Score based on scene change magnitude (scale to similar range as others)
                # Scene score is 0-1, multiply by 100 to get comparable scores
                score = scene.score * 100

                all_detections.append(RawDetection(
                    timestamp=scene.timestamp,
                    score=score,
                    source='scene_change',
                    metadata={
                        'scene_score': scene.score,
                        'window_center': window.center_time,
                    }
                ))

        logger.info(f"Scene change detector: {len(all_detections)} raw detections")
        return all_detections
