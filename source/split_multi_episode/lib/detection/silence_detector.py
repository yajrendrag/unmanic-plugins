#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Silence-based episode boundary detection.

Uses FFmpeg's silencedetect filter to find gaps between episodes.
Supports TMDB runtime hints for more accurate boundary detection.
"""

import logging
import re
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.silence_detector")


@dataclass
class SilenceRegion:
    """Represents a detected silence region."""
    start_time: float  # seconds
    end_time: float    # seconds
    duration: float    # seconds

    @property
    def midpoint(self) -> float:
        """Get the midpoint of the silence region."""
        return (self.start_time + self.end_time) / 2


@dataclass
class EpisodeBoundary:
    """Represents a detected episode boundary."""
    start_time: float  # seconds
    end_time: float    # seconds
    confidence: float  # 0.0 to 1.0
    source: str        # detection method name
    metadata: dict = field(default_factory=dict)  # additional info


class SilenceDetector:
    """
    Detects episode boundaries by finding silence gaps in audio.

    Uses FFmpeg's silencedetect filter to identify extended silence
    that may indicate breaks between episodes.

    Supports two modes:
    1. Runtime-guided: Uses expected episode runtimes (from TMDB) to find
       silences near expected break points.
    2. Estimation mode: Estimates episode count from total duration and
       finds the best N-1 break points.
    """

    BASE_CONFIDENCE = 0.6
    MAX_CONFIDENCE = 0.85
    RUNTIME_GUIDED_CONFIDENCE = 0.75

    def __init__(
        self,
        silence_threshold_db: float = -30,
        min_silence_duration: float = 2.0,
        min_episode_length: float = 900,
        max_episode_length: float = 5400,
        expected_runtimes: Optional[List[int]] = None,
        runtime_tolerance: float = 0.20,
    ):
        """
        Initialize the silence detector.

        Args:
            silence_threshold_db: Audio level threshold for silence (default: -30dB)
            min_silence_duration: Minimum silence duration to detect (default: 2 seconds)
            min_episode_length: Minimum episode duration in seconds (default: 15 min)
            max_episode_length: Maximum episode duration in seconds (default: 90 min)
            expected_runtimes: Optional list of expected episode runtimes in minutes (from TMDB)
            runtime_tolerance: Tolerance for matching expected runtimes (default: 20%)
        """
        self.silence_threshold_db = silence_threshold_db
        self.min_silence_duration = min_silence_duration
        self.min_episode_length = min_episode_length
        self.max_episode_length = max_episode_length
        self.expected_runtimes = expected_runtimes
        self.runtime_tolerance = runtime_tolerance
        # Cache for silence regions to avoid re-running FFmpeg
        self._cached_file_path: Optional[str] = None
        self._cached_silence_regions: Optional[List[SilenceRegion]] = None

    def detect(
        self,
        file_path: str,
        total_duration: float,
        expected_runtimes: Optional[List[int]] = None,
        expected_episode_count: Optional[int] = None
    ) -> List[EpisodeBoundary]:
        """
        Detect episode boundaries from silence regions.

        Args:
            file_path: Path to the video file
            total_duration: Total duration of the file in seconds
            expected_runtimes: Optional list of expected episode runtimes in minutes
                              (NOTE: these are content-only runtimes, not including commercials)
            expected_episode_count: Optional expected number of episodes (from filename parsing)

        Returns:
            List of EpisodeBoundary objects representing detected episodes
        """
        # Use parameter or instance variable
        runtimes = expected_runtimes or self.expected_runtimes

        # Find silence regions
        silence_regions = self._detect_silence_regions(file_path)

        if not silence_regions:
            logger.debug("No silence regions detected")
            return []

        logger.info(f"Found {len(silence_regions)} silence regions")

        # Choose detection strategy based on available information
        # Prefer episode count over runtimes since runtimes don't include commercials
        if expected_episode_count and expected_episode_count >= 2:
            logger.info(f"Using episode-count-guided detection for {expected_episode_count} episodes")
            boundaries = self._detect_with_episode_count(silence_regions, total_duration, expected_episode_count)
        elif runtimes and len(runtimes) > 1:
            # Use episode count from runtimes length
            logger.info(f"Using runtime-count-guided detection with {len(runtimes)} expected episodes")
            boundaries = self._detect_with_episode_count(silence_regions, total_duration, len(runtimes))
        else:
            logger.info("Using estimation-based detection")
            boundaries = self._detect_with_estimation(silence_regions, total_duration)

        logger.info(f"Detected {len(boundaries)} potential episode boundaries from silence")
        return boundaries

    def _detect_silence_regions(self, file_path: str) -> List[SilenceRegion]:
        """
        Run FFmpeg silencedetect filter on the file.

        Results are cached per file path to avoid re-running FFmpeg.

        Args:
            file_path: Path to the video file

        Returns:
            List of SilenceRegion objects
        """
        # Return cached results if available for this file
        if self._cached_file_path == file_path and self._cached_silence_regions is not None:
            logger.debug(f"Using cached silence regions for: {file_path}")
            return self._cached_silence_regions

        cmd = [
            'ffmpeg',
            '-i', file_path,
            '-af', f'silencedetect=noise={self.silence_threshold_db}dB:duration={self.min_silence_duration}',
            '-f', 'null',
            '-'
        ]

        logger.debug(f"Running silence detection: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
        except subprocess.TimeoutExpired:
            logger.error("Silence detection timed out")
            return []
        except Exception as e:
            logger.error(f"Silence detection error: {e}")
            return []

        # Parse the output (silencedetect outputs to stderr)
        regions = self._parse_silence_output(result.stderr)

        # Cache the results
        self._cached_file_path = file_path
        self._cached_silence_regions = regions

        return regions

    def _detect_silence_in_window(
        self,
        file_path: str,
        window_start: float,
        window_duration: float,
    ) -> List[SilenceRegion]:
        """
        Detect silence regions within a specific time window only.

        Uses FFmpeg -ss (before -i for fast seeking) and -t for duration
        to scan only the specified portion of the file.

        Args:
            file_path: Path to the video file
            window_start: Start time in seconds
            window_duration: Duration to scan in seconds

        Returns:
            List of SilenceRegion objects with timestamps in full-file coordinates
        """
        cmd = [
            'ffmpeg',
            '-ss', str(window_start),  # Seek before input for fast seeking
            '-i', file_path,
            '-t', str(window_duration),  # Limit duration
            '-af', f'silencedetect=noise={self.silence_threshold_db}dB:duration={self.min_silence_duration}',
            '-f', 'null',
            '-'
        ]

        logger.debug(f"Running silence detection for window {window_start/60:.1f}-{(window_start+window_duration)/60:.1f}m")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout per window (should be fast)
            )
        except subprocess.TimeoutExpired:
            logger.error(f"Silence detection timed out for window at {window_start/60:.1f}m")
            return []
        except Exception as e:
            logger.error(f"Silence detection error for window at {window_start/60:.1f}m: {e}")
            return []

        # Parse the output
        regions = self._parse_silence_output(result.stderr)

        # Adjust timestamps back to full-file coordinates
        adjusted_regions = []
        for region in regions:
            adjusted_regions.append(SilenceRegion(
                start_time=region.start_time + window_start,
                end_time=region.end_time + window_start,
                duration=region.duration
            ))

        logger.debug(f"Found {len(adjusted_regions)} silence regions in window")
        return adjusted_regions

    def _parse_silence_output(self, output: str) -> List[SilenceRegion]:
        """
        Parse FFmpeg silencedetect output.

        Output format:
        [silencedetect @ 0x...] silence_start: 1234.567
        [silencedetect @ 0x...] silence_end: 1238.901 | silence_duration: 4.334

        Args:
            output: FFmpeg stderr output

        Returns:
            List of SilenceRegion objects
        """
        regions = []

        # Patterns for parsing silencedetect output
        start_pattern = re.compile(r'silence_start:\s*([\d.]+)')
        end_pattern = re.compile(r'silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)')

        current_start = None

        for line in output.split('\n'):
            # Look for silence start
            start_match = start_pattern.search(line)
            if start_match:
                current_start = float(start_match.group(1))
                continue

            # Look for silence end
            end_match = end_pattern.search(line)
            if end_match and current_start is not None:
                end_time = float(end_match.group(1))
                duration = float(end_match.group(2))

                regions.append(SilenceRegion(
                    start_time=current_start,
                    end_time=end_time,
                    duration=duration
                ))

                current_start = None

        return regions

    def _detect_with_runtimes(
        self,
        silence_regions: List[SilenceRegion],
        total_duration: float,
        expected_runtimes: List[int]
    ) -> List[EpisodeBoundary]:
        """
        Detect boundaries using expected episode runtimes as guides.

        Calculates expected cumulative break points and finds the best
        silence region near each expected break.

        Args:
            silence_regions: List of detected silence regions
            total_duration: Total file duration in seconds
            expected_runtimes: List of expected episode runtimes in minutes

        Returns:
            List of EpisodeBoundary objects
        """
        # Convert runtimes to seconds and calculate cumulative break points
        runtime_seconds = [r * 60 for r in expected_runtimes]
        expected_breaks = []
        cumulative = 0.0
        for runtime in runtime_seconds[:-1]:  # No break after last episode
            cumulative += runtime
            expected_breaks.append(cumulative)

        logger.debug(f"Expected break points: {[f'{b/60:.1f}m' for b in expected_breaks]}")

        # Score all silence regions
        scored_silences = self._score_silence_regions(silence_regions)

        # Find best silence near each expected break point
        selected_breaks = []
        avg_runtime = sum(runtime_seconds) / len(runtime_seconds)
        tolerance_seconds = self.runtime_tolerance * avg_runtime

        for expected_time in expected_breaks:
            best_silence = None
            best_score = -1

            for region, base_score in scored_silences:
                # Check if silence is within tolerance of expected break
                distance = abs(region.midpoint - expected_time)
                if distance <= tolerance_seconds:
                    # Score bonus for being close to expected time
                    proximity_bonus = 1.0 - (distance / tolerance_seconds)
                    total_score = base_score + (proximity_bonus * 0.5)

                    if total_score > best_score:
                        best_score = total_score
                        best_silence = region

            if best_silence:
                selected_breaks.append((best_silence, best_score))
                logger.debug(
                    f"Found break at {best_silence.midpoint/60:.1f}m "
                    f"(expected: {expected_time/60:.1f}m, score: {best_score:.2f})"
                )
            else:
                logger.warning(
                    f"No suitable silence found near expected break at {expected_time/60:.1f}m"
                )

        # Convert to boundaries
        return self._breaks_to_boundaries(selected_breaks, total_duration, guided=True)

    def _detect_with_episode_count(
        self,
        silence_regions: List[SilenceRegion],
        total_duration: float,
        episode_count: int
    ) -> List[EpisodeBoundary]:
        """
        Detect boundaries using a known episode count.

        Uses the expected episode count from filename parsing to find
        exactly N-1 split points for N episodes.

        Args:
            silence_regions: List of detected silence regions
            total_duration: Total file duration in seconds
            episode_count: Expected number of episodes

        Returns:
            List of EpisodeBoundary objects
        """
        logger.debug(f"Finding {episode_count - 1} breaks for {episode_count} episodes "
                     f"in {total_duration/60:.1f}m file")

        # Score all silence regions
        scored_silences = self._score_silence_regions(silence_regions)

        # Find the best breaks for this episode count
        breaks, alignment_score = self._try_episode_count(
            scored_silences, total_duration, episode_count
        )

        logger.info(f"Found {len(breaks)} breaks for {episode_count} episodes "
                    f"(alignment score: {alignment_score:.3f})")

        # Convert to boundaries with guided=True since we had episode count info
        return self._breaks_to_boundaries(breaks, total_duration, guided=True)

    def _detect_with_estimation(
        self,
        silence_regions: List[SilenceRegion],
        total_duration: float
    ) -> List[EpisodeBoundary]:
        """
        Detect boundaries by estimating episode count and finding best breaks.

        Tries multiple possible episode counts and picks the one with best
        silence alignment to produce more accurate splits.

        Args:
            silence_regions: List of detected silence regions
            total_duration: Total file duration in seconds

        Returns:
            List of EpisodeBoundary objects
        """
        # Calculate possible episode count range
        min_possible = max(2, int(total_duration / self.max_episode_length))
        max_possible = min(15, int(total_duration / self.min_episode_length))

        if min_possible > max_possible:
            min_possible = max_possible = max(2, round(total_duration / 3600))

        logger.debug(
            f"Trying episode counts {min_possible}-{max_possible} "
            f"for {total_duration/60:.1f}m file"
        )

        # Score all silence regions once
        scored_silences = self._score_silence_regions(silence_regions)

        # Try each possible episode count and score the alignment
        best_count = min_possible
        best_alignment_score = -1
        best_breaks = []

        for episode_count in range(min_possible, max_possible + 1):
            breaks, alignment_score = self._try_episode_count(
                scored_silences, total_duration, episode_count
            )

            logger.debug(
                f"Episode count {episode_count}: alignment score {alignment_score:.3f}"
            )

            if alignment_score > best_alignment_score:
                best_alignment_score = alignment_score
                best_count = episode_count
                best_breaks = breaks

        logger.info(
            f"Best estimate: {best_count} episodes "
            f"(alignment score: {best_alignment_score:.3f})"
        )

        # Convert to boundaries
        return self._breaks_to_boundaries(best_breaks, total_duration, guided=False)

    def _try_episode_count(
        self,
        scored_silences: List[Tuple[SilenceRegion, float]],
        total_duration: float,
        episode_count: int
    ) -> Tuple[List[Tuple[SilenceRegion, float]], float]:
        """
        Try a specific episode count and return alignment score.

        Args:
            scored_silences: Pre-scored silence regions
            total_duration: Total file duration
            episode_count: Number of episodes to try

        Returns:
            Tuple of (selected breaks, alignment score)
        """
        num_breaks = episode_count - 1
        if num_breaks < 1:
            return [], 0.0

        ideal_interval = total_duration / episode_count
        ideal_breaks = [ideal_interval * (i + 1) for i in range(num_breaks)]

        # Find best silences near each ideal break
        selected_breaks = []
        used_regions = set()
        total_proximity_score = 0.0
        window = ideal_interval * 0.35  # 35% of interval

        for ideal_time in ideal_breaks:
            best_silence = None
            best_score = -1
            best_proximity = 0

            for region, base_score in scored_silences:
                if id(region) in used_regions:
                    continue

                distance = abs(region.midpoint - ideal_time)
                if distance <= window:
                    proximity_factor = 1.0 - (distance / window)
                    total_score = base_score * (0.6 + 0.4 * proximity_factor)

                    if total_score > best_score:
                        best_score = total_score
                        best_silence = region
                        best_proximity = proximity_factor

            if best_silence:
                selected_breaks.append((best_silence, best_score))
                used_regions.add(id(best_silence))
                total_proximity_score += best_proximity
            else:
                # Penalize for missing a break point
                total_proximity_score -= 0.5

        # Calculate alignment score:
        # - Reward finding silences close to expected break points
        # - Penalize for missing break points
        # - Bonus for using all break points
        if num_breaks > 0:
            coverage = len(selected_breaks) / num_breaks
            avg_proximity = total_proximity_score / num_breaks if num_breaks > 0 else 0
            alignment_score = (coverage * 0.6) + (avg_proximity * 0.4)
        else:
            alignment_score = 0.0

        return selected_breaks, alignment_score

    def _score_silence_regions(
        self,
        silence_regions: List[SilenceRegion]
    ) -> List[Tuple[SilenceRegion, float]]:
        """
        Score silence regions by their likelihood of being episode breaks.

        Scoring factors:
        - Duration: Longer silences are more likely to be episode breaks
        - Isolation: Silences not clustered with others (like commercial breaks)

        Args:
            silence_regions: List of silence regions

        Returns:
            List of (SilenceRegion, score) tuples, sorted by score descending
        """
        if not silence_regions:
            return []

        # Calculate duration scores (normalize by max duration)
        max_duration = max(r.duration for r in silence_regions)

        scored = []
        for i, region in enumerate(silence_regions):
            # Duration score (0.0 to 1.0)
            duration_score = region.duration / max_duration if max_duration > 0 else 0

            # Isolation score: penalize silences that are close to other silences
            # (likely commercial break clusters rather than episode breaks)
            isolation_score = 1.0
            for j, other in enumerate(silence_regions):
                if i == j:
                    continue
                gap = abs(region.midpoint - other.midpoint)
                if gap < 300:  # Within 5 minutes
                    # Reduce score for clustered silences
                    isolation_score *= 0.9

            # Combined score
            total_score = (duration_score * 0.6) + (isolation_score * 0.4)
            scored.append((region, total_score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _breaks_to_boundaries(
        self,
        selected_breaks: List[Tuple[SilenceRegion, float]],
        total_duration: float,
        guided: bool = False
    ) -> List[EpisodeBoundary]:
        """
        Convert selected break points to episode boundaries.

        Args:
            selected_breaks: List of (SilenceRegion, score) tuples
            total_duration: Total file duration
            guided: Whether runtime guidance was used

        Returns:
            List of EpisodeBoundary objects
        """
        if not selected_breaks:
            return []

        # Sort breaks by time
        sorted_breaks = sorted(selected_breaks, key=lambda x: x[0].midpoint)

        boundaries = []
        prev_end = 0.0

        for region, score in sorted_breaks:
            split_point = region.midpoint
            episode_duration = split_point - prev_end

            # Skip if episode would be too short
            if episode_duration < self.min_episode_length * 0.8:
                continue

            # Calculate confidence
            if guided:
                confidence = min(self.MAX_CONFIDENCE, self.RUNTIME_GUIDED_CONFIDENCE + score * 0.1)
                source = 'silence_guided'
            else:
                confidence = min(self.MAX_CONFIDENCE, self.BASE_CONFIDENCE + score * 0.2)
                source = 'silence'

            boundaries.append(EpisodeBoundary(
                start_time=prev_end,
                end_time=split_point,
                confidence=confidence,
                source=source,
                metadata={
                    'silence_start': region.start_time,
                    'silence_end': region.end_time,
                    'silence_duration': region.duration,
                    'score': score,
                    'guided': guided,
                }
            ))
            prev_end = split_point

        # Add final episode
        if total_duration - prev_end >= self.min_episode_length * 0.8:
            boundaries.append(EpisodeBoundary(
                start_time=prev_end,
                end_time=total_duration,
                confidence=self.BASE_CONFIDENCE if not guided else self.RUNTIME_GUIDED_CONFIDENCE,
                source='silence_guided' if guided else 'silence',
                metadata={'final_episode': True, 'guided': guided}
            ))

        return boundaries

    def _silence_to_boundaries(
        self,
        silence_regions: List[SilenceRegion],
        total_duration: float
    ) -> List[EpisodeBoundary]:
        """
        Convert silence regions to episode boundaries.

        Filters silence regions to find those likely to be episode breaks,
        then creates episode boundaries based on the gaps.

        Args:
            silence_regions: List of detected silence regions
            total_duration: Total file duration in seconds

        Returns:
            List of EpisodeBoundary objects
        """
        # Filter silence regions that could be episode breaks
        candidate_breaks = []
        for region in silence_regions:
            # Longer silences are more likely to be episode breaks
            if region.duration >= self.min_silence_duration:
                # Calculate confidence based on silence duration
                # Longer silences get higher confidence
                confidence = min(
                    self.MAX_CONFIDENCE,
                    self.BASE_CONFIDENCE + (region.duration - self.min_silence_duration) * 0.02
                )
                candidate_breaks.append((region, confidence))

        if not candidate_breaks:
            return []

        # Sort by timestamp
        candidate_breaks.sort(key=lambda x: x[0].start_time)

        # Filter to reasonable episode boundaries based on duration constraints
        valid_breaks = self._filter_by_episode_duration(candidate_breaks, total_duration)

        if not valid_breaks:
            return []

        # Convert breaks to episode boundaries
        boundaries = []
        prev_end = 0.0

        for i, (break_region, confidence) in enumerate(valid_breaks):
            # Episode ends at the midpoint of the silence
            split_point = (break_region.start_time + break_region.end_time) / 2

            # Create boundary for episode ending at this break
            if split_point - prev_end >= self.min_episode_length:
                boundaries.append(EpisodeBoundary(
                    start_time=prev_end,
                    end_time=split_point,
                    confidence=confidence,
                    source='silence',
                    metadata={
                        'silence_start': break_region.start_time,
                        'silence_end': break_region.end_time,
                        'silence_duration': break_region.duration,
                    }
                ))
                prev_end = split_point

        # Add final episode if remaining duration is valid
        if total_duration - prev_end >= self.min_episode_length:
            boundaries.append(EpisodeBoundary(
                start_time=prev_end,
                end_time=total_duration,
                confidence=self.BASE_CONFIDENCE,
                source='silence',
                metadata={'final_episode': True}
            ))

        return boundaries

    def _filter_by_episode_duration(
        self,
        candidate_breaks: List[Tuple[SilenceRegion, float]],
        total_duration: float
    ) -> List[Tuple[SilenceRegion, float]]:
        """
        Filter candidate breaks to ensure resulting episodes have valid durations.

        Args:
            candidate_breaks: List of (SilenceRegion, confidence) tuples
            total_duration: Total file duration

        Returns:
            Filtered list of valid breaks
        """
        if not candidate_breaks:
            return []

        # Try to find a set of breaks that results in valid episode durations
        valid_breaks = []
        prev_time = 0.0

        for break_region, confidence in candidate_breaks:
            split_point = (break_region.start_time + break_region.end_time) / 2
            episode_duration = split_point - prev_time

            # Check if this creates a valid episode
            if episode_duration >= self.min_episode_length:
                if episode_duration <= self.max_episode_length:
                    valid_breaks.append((break_region, confidence))
                    prev_time = split_point
                else:
                    # Episode too long - we might have missed a break
                    # Still consider this break but with lower confidence
                    valid_breaks.append((break_region, confidence * 0.8))
                    prev_time = split_point

        # Verify final segment is valid
        if valid_breaks:
            final_break = valid_breaks[-1][0]
            final_split = (final_break.start_time + final_break.end_time) / 2
            remaining = total_duration - final_split

            if remaining < self.min_episode_length and remaining < total_duration * 0.1:
                # Final segment too short - remove last break
                valid_breaks.pop()

        return valid_breaks

    def get_raw_silence_regions(self, file_path: str) -> List[SilenceRegion]:
        """
        Get raw silence regions without filtering.
        Useful for other detectors that want to combine with silence data.

        Args:
            file_path: Path to the video file

        Returns:
            List of all detected SilenceRegion objects
        """
        return self._detect_silence_regions(file_path)

    def detect_in_windows(
        self,
        file_path: str,
        search_windows: List,  # List of SearchWindow objects
        total_duration: float,
    ) -> List[Tuple[float, float, dict]]:
        """
        Find the best silence-based boundary within each search window.

        This is the Phase 2 detection method - it searches only within
        the narrow windows defined by Phase 1. Uses FFmpeg seeking to
        scan only the specific time ranges for efficiency.

        Args:
            file_path: Path to the video file
            search_windows: List of SearchWindow objects defining where to search
            total_duration: Total file duration

        Returns:
            List of (boundary_time, confidence, metadata) tuples, one per window
        """
        results = []

        for window in search_windows:
            # Scan only this window using FFmpeg seeking
            window_duration = window.end_time - window.start_time
            window_silences = self._detect_silence_in_window(
                file_path, window.start_time, window_duration
            )

            if not window_silences:
                # No silence in window - use center as fallback
                logger.debug(
                    f"No silence in window {window.start_time/60:.1f}-{window.end_time/60:.1f}m, "
                    f"using center {window.center_time/60:.1f}m"
                )
                results.append((window.center_time, 0.3, {
                    'source': 'silence_fallback',
                    'window_source': window.source,
                    'fallback': True,
                }))
                continue

            # Score silences and find the best one
            best_silence = None
            best_score = -1

            for silence in window_silences:
                # Score factors:
                # 1. Duration - longer silences are better (episode breaks are longer)
                # 2. Proximity to window center - closer is better
                # 3. Position in window - prefer middle over edges

                duration_score = min(1.0, silence.duration / 5.0)  # Max score at 5+ seconds

                distance_from_center = abs(silence.midpoint - window.center_time)
                window_half = (window.end_time - window.start_time) / 2
                proximity_score = 1.0 - (distance_from_center / window_half) if window_half > 0 else 0.5

                # Combined score
                score = (duration_score * 0.6) + (proximity_score * 0.4)

                if score > best_score:
                    best_score = score
                    best_silence = silence

            if best_silence:
                # Calculate confidence based on score and silence quality
                confidence = min(0.9, 0.5 + (best_score * 0.4))

                logger.debug(
                    f"Window {window.start_time/60:.1f}-{window.end_time/60:.1f}m: "
                    f"best silence at {best_silence.midpoint/60:.1f}m "
                    f"(dur={best_silence.duration:.1f}s, score={best_score:.2f})"
                )

                results.append((best_silence.midpoint, confidence, {
                    'source': 'silence',
                    'window_source': window.source,
                    'silence_start': best_silence.start_time,
                    'silence_end': best_silence.end_time,
                    'silence_duration': best_silence.duration,
                    'score': best_score,
                }))
            else:
                results.append((window.center_time, 0.3, {
                    'source': 'silence_fallback',
                    'window_source': window.source,
                    'fallback': True,
                }))

        return results

    def get_silences_in_window(
        self,
        file_path: str,
        window_start: float,
        window_end: float,
    ) -> List[SilenceRegion]:
        """
        Get all silence regions within a specific time window.

        Args:
            file_path: Path to the video file
            window_start: Window start time in seconds
            window_end: Window end time in seconds

        Returns:
            List of SilenceRegion objects within the window
        """
        all_silences = self._detect_silence_regions(file_path)
        return [
            r for r in all_silences
            if r.start_time >= window_start and r.end_time <= window_end
        ]

    def detect_raw_in_windows(
        self,
        file_path: str,
        search_windows: List,  # List of SearchWindow objects
    ) -> List:
        """
        Return ALL silence detections as RawDetection objects.

        Instead of picking the "best" silence per window, this returns
        all detected silences for clustering with other detectors.

        Score is based on silence duration:
        - 1 second silence = score 10
        - 2 second silence = score 20
        - etc.

        Args:
            file_path: Path to the video file
            search_windows: List of SearchWindow objects defining where to search

        Returns:
            List of RawDetection objects (imported from raw_detection module)
        """
        from .raw_detection import RawDetection

        all_detections = []

        for window in search_windows:
            # Scan only this window using FFmpeg seeking
            window_duration = window.end_time - window.start_time
            window_silences = self._detect_silence_in_window(
                file_path, window.start_time, window_duration
            )

            logger.debug(
                f"Window {window.start_time/60:.1f}-{window.end_time/60:.1f}m: "
                f"found {len(window_silences)} silence regions"
            )

            # Convert each silence region to a RawDetection
            for silence in window_silences:
                # Score based on duration (10 points per second)
                # Longer silences are more significant
                score = silence.duration * 10

                all_detections.append(RawDetection(
                    timestamp=silence.midpoint,
                    score=score,
                    source='silence',
                    metadata={
                        'silence_start': silence.start_time,
                        'silence_end': silence.end_time,
                        'silence_duration': silence.duration,
                        'window_center': window.center_time,
                    }
                ))

        logger.info(f"Silence detector: {len(all_detections)} raw detections")
        return all_detections
