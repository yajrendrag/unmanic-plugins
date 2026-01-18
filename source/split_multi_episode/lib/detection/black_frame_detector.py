#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Black frame-based episode boundary detection.

Uses FFmpeg's blackdetect filter to find black sequences between episodes.
"""

import logging
import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.black_frame_detector")


@dataclass
class BlackRegion:
    """Represents a detected black frame region."""
    start_time: float  # seconds
    end_time: float    # seconds
    duration: float    # seconds


@dataclass
class EpisodeBoundary:
    """Represents a detected episode boundary."""
    start_time: float  # seconds
    end_time: float    # seconds
    confidence: float  # 0.0 to 1.0
    source: str        # detection method name
    metadata: dict     # additional info


class BlackFrameDetector:
    """
    Detects episode boundaries by finding black frame sequences.

    Uses FFmpeg's blackdetect filter to identify extended black frames
    that may indicate breaks between episodes.
    """

    BASE_CONFIDENCE = 0.5
    SILENCE_COMBO_BOOST = 0.1  # Confidence boost when combined with silence

    def __init__(
        self,
        min_black_duration: float = 1.0,
        picture_threshold: float = 0.98,
        pixel_threshold: float = 0.1,
        min_episode_length: float = 900,
        max_episode_length: float = 5400,
    ):
        """
        Initialize the black frame detector.

        Args:
            min_black_duration: Minimum black frame duration to detect (default: 1 second)
            picture_threshold: Ratio of black pixels to detect black frame (default: 0.98)
            pixel_threshold: Pixel brightness threshold for black (default: 0.1)
            min_episode_length: Minimum episode duration in seconds (default: 15 min)
            max_episode_length: Maximum episode duration in seconds (default: 90 min)
        """
        self.min_black_duration = min_black_duration
        self.picture_threshold = picture_threshold
        self.pixel_threshold = pixel_threshold
        self.min_episode_length = min_episode_length
        self.max_episode_length = max_episode_length

    def detect(self, file_path: str, total_duration: float) -> List[EpisodeBoundary]:
        """
        Detect episode boundaries from black frame regions.

        Args:
            file_path: Path to the video file
            total_duration: Total duration of the file in seconds

        Returns:
            List of EpisodeBoundary objects representing detected episodes
        """
        # Find black regions
        black_regions = self._detect_black_regions(file_path)

        if not black_regions:
            logger.debug("No black frame regions detected")
            return []

        logger.info(f"Found {len(black_regions)} black frame regions")

        # Filter and convert to boundaries
        boundaries = self._black_to_boundaries(black_regions, total_duration)

        logger.info(f"Detected {len(boundaries)} potential episode boundaries from black frames")
        return boundaries

    def _detect_black_regions(self, file_path: str) -> List[BlackRegion]:
        """
        Run FFmpeg blackdetect filter on the file.

        Args:
            file_path: Path to the video file

        Returns:
            List of BlackRegion objects
        """
        cmd = [
            'ffmpeg',
            '-i', file_path,
            '-vf', f'blackdetect=d={self.min_black_duration}:pic_th={self.picture_threshold}:pix_th={self.pixel_threshold}',
            '-an',  # Disable audio processing for speed
            '-f', 'null',
            '-'
        ]

        logger.debug(f"Running black frame detection: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=900  # 15 minute timeout (video processing is slow)
            )
        except subprocess.TimeoutExpired:
            logger.error("Black frame detection timed out")
            return []
        except Exception as e:
            logger.error(f"Black frame detection error: {e}")
            return []

        # Parse the output (blackdetect outputs to stderr)
        return self._parse_black_output(result.stderr)

    def _parse_black_output(self, output: str) -> List[BlackRegion]:
        """
        Parse FFmpeg blackdetect output.

        Output format:
        [blackdetect @ 0x...] black_start:1234.567 black_end:1238.901 black_duration:4.334

        Args:
            output: FFmpeg stderr output

        Returns:
            List of BlackRegion objects
        """
        regions = []

        # Pattern for parsing blackdetect output
        pattern = re.compile(
            r'black_start:\s*([\d.]+)\s+black_end:\s*([\d.]+)\s+black_duration:\s*([\d.]+)'
        )

        for line in output.split('\n'):
            match = pattern.search(line)
            if match:
                regions.append(BlackRegion(
                    start_time=float(match.group(1)),
                    end_time=float(match.group(2)),
                    duration=float(match.group(3))
                ))

        return regions

    def _black_to_boundaries(
        self,
        black_regions: List[BlackRegion],
        total_duration: float
    ) -> List[EpisodeBoundary]:
        """
        Convert black frame regions to episode boundaries.

        Args:
            black_regions: List of detected black regions
            total_duration: Total file duration in seconds

        Returns:
            List of EpisodeBoundary objects
        """
        # Filter to significant black regions
        significant_blacks = [r for r in black_regions if r.duration >= self.min_black_duration]

        if not significant_blacks:
            return []

        # Sort by timestamp
        significant_blacks.sort(key=lambda x: x.start_time)

        # Convert to boundaries
        boundaries = []
        prev_end = 0.0

        for i, black in enumerate(significant_blacks):
            split_point = (black.start_time + black.end_time) / 2
            episode_duration = split_point - prev_end

            # Check if this creates a valid episode
            if episode_duration >= self.min_episode_length:
                if episode_duration <= self.max_episode_length:
                    confidence = self.BASE_CONFIDENCE

                    # Boost confidence for longer black periods
                    if black.duration >= 2.0:
                        confidence += 0.1
                    if black.duration >= 5.0:
                        confidence += 0.1

                    boundaries.append(EpisodeBoundary(
                        start_time=prev_end,
                        end_time=split_point,
                        confidence=min(confidence, 0.7),
                        source='black_frame',
                        metadata={
                            'black_start': black.start_time,
                            'black_end': black.end_time,
                            'black_duration': black.duration,
                        }
                    ))
                    prev_end = split_point

        # Add final episode
        if total_duration - prev_end >= self.min_episode_length:
            boundaries.append(EpisodeBoundary(
                start_time=prev_end,
                end_time=total_duration,
                confidence=self.BASE_CONFIDENCE,
                source='black_frame',
                metadata={'final_episode': True}
            ))

        return boundaries

    def get_raw_black_regions(self, file_path: str) -> List[BlackRegion]:
        """
        Get raw black frame regions without filtering.
        Useful for combining with other detection methods.

        Args:
            file_path: Path to the video file

        Returns:
            List of all detected BlackRegion objects
        """
        return self._detect_black_regions(file_path)

    def enhance_with_silence(
        self,
        boundaries: List[EpisodeBoundary],
        silence_regions: List,
        tolerance: float = 5.0
    ) -> List[EpisodeBoundary]:
        """
        Enhance boundary confidence when black frames coincide with silence.

        Args:
            boundaries: Episode boundaries detected from black frames
            silence_regions: Silence regions from SilenceDetector
            tolerance: Time tolerance for matching (seconds)

        Returns:
            Enhanced boundaries with boosted confidence where applicable
        """
        enhanced = []

        for boundary in boundaries:
            # Get the split point for this boundary
            split_point = boundary.metadata.get('black_start', boundary.end_time)

            # Check if any silence region overlaps with this black region
            has_silence = False
            for silence in silence_regions:
                # Check for overlap within tolerance
                if (abs(silence.start_time - split_point) < tolerance or
                    abs(silence.end_time - split_point) < tolerance or
                    (silence.start_time <= split_point <= silence.end_time)):
                    has_silence = True
                    break

            if has_silence:
                # Boost confidence
                new_confidence = min(boundary.confidence + self.SILENCE_COMBO_BOOST, 0.85)
                enhanced_boundary = EpisodeBoundary(
                    start_time=boundary.start_time,
                    end_time=boundary.end_time,
                    confidence=new_confidence,
                    source='black_frame+silence',
                    metadata={
                        **boundary.metadata,
                        'silence_confirmed': True
                    }
                )
                enhanced.append(enhanced_boundary)
                logger.debug(f"Boosted confidence for boundary at {boundary.end_time:.1f}s (black+silence)")
            else:
                enhanced.append(boundary)

        return enhanced
