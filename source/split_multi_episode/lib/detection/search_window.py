#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Search window determination for episode boundary detection.

Phase 1 of the two-phase detection process:
1. Define narrow search windows where episode breaks are likely
2. Phase 2 detectors then search only within these windows

Window determination priority:
1. Chapter marks (if available) - most precise
2. Filename episode count + total duration - nominal episode length
3. TMDB runtimes - adjust nominal if significantly different
4. Commercial time estimation - further refinement
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.search_window")


@dataclass
class SearchWindow:
    """Represents a time window to search for an episode boundary."""
    start_time: float      # Window start in seconds
    end_time: float        # Window end in seconds
    center_time: float     # Expected boundary location (center of window)
    confidence: float      # How confident we are this is a good window (0-1)
    source: str            # What determined this window
    episode_before: int    # Episode number before this boundary
    episode_after: int     # Episode number after this boundary
    metadata: dict         # Additional info


class SearchWindowDeterminer:
    """
    Determines search windows for episode boundary detection.

    Uses available information to narrow down where episode breaks
    likely occur, so detectors can focus their analysis.
    """

    DEFAULT_WINDOW_SIZE = 300  # 5 minutes on each side = 10 minute window
    MIN_WINDOW_SIZE = 120      # 2 minutes minimum
    MAX_WINDOW_SIZE = 600      # 10 minutes maximum

    def __init__(
        self,
        total_duration: float,
        expected_episode_count: int,
        min_episode_length: float = 900,
        max_episode_length: float = 5400,
        window_size: float = None,
    ):
        """
        Initialize the search window determiner.

        Args:
            total_duration: Total file duration in seconds
            expected_episode_count: Number of episodes expected (from filename)
            min_episode_length: Minimum valid episode length in seconds
            max_episode_length: Maximum valid episode length in seconds
            window_size: Size of search window (seconds on each side of center)
        """
        self.total_duration = total_duration
        self.expected_episode_count = expected_episode_count
        self.min_episode_length = min_episode_length
        self.max_episode_length = max_episode_length
        self.window_size = window_size or self.DEFAULT_WINDOW_SIZE

        # Calculate nominal episode length
        self.nominal_episode_length = total_duration / expected_episode_count

        logger.debug(
            f"SearchWindowDeterminer initialized: {total_duration/60:.1f}m file, "
            f"{expected_episode_count} episodes, nominal {self.nominal_episode_length/60:.1f}m each"
        )

    def determine_windows(
        self,
        chapter_boundaries: Optional[List[Tuple[float, float]]] = None,
        tmdb_runtimes: Optional[List[int]] = None,
        commercial_times: Optional[List[Tuple[float, float]]] = None,
        commercial_times_per_episode: Optional[List[float]] = None,
    ) -> List[SearchWindow]:
        """
        Determine search windows using available information.

        Priority:
        1. TMDB runtimes + commercial times per episode (most precise when both available)
        2. Chapter marks
        3. TMDB runtimes alone (estimate commercials)
        4. Episode count + total duration (fallback)

        Args:
            chapter_boundaries: List of (start, end) from chapter detection
            tmdb_runtimes: List of episode runtimes in minutes from TMDB
            commercial_times: List of (start, end) for detected commercial breaks
            commercial_times_per_episode: List of total commercial duration (seconds)
                per episode, from chapter markers

        Returns:
            List of SearchWindow objects, one for each expected boundary
        """
        num_boundaries = self.expected_episode_count - 1

        if num_boundaries < 1:
            logger.warning("Expected episode count < 2, no boundaries to find")
            return []

        # Try each method in priority order
        windows = None

        # Priority 1: TMDB runtimes + actual commercial times per episode
        # This is the most accurate when we have both pieces of data
        if (tmdb_runtimes and len(tmdb_runtimes) >= self.expected_episode_count and
            commercial_times_per_episode and len(commercial_times_per_episode) >= self.expected_episode_count):
            windows = self._windows_from_tmdb(tmdb_runtimes, commercial_times_per_episode)
            if windows:
                logger.info(f"Using TMDB+chapters search windows ({len(windows)} windows)")
                return windows

        # Priority 2: Chapter-based windows (when no TMDB data)
        if chapter_boundaries and len(chapter_boundaries) >= self.expected_episode_count:
            windows = self._windows_from_chapters(chapter_boundaries)
            if windows:
                logger.info(f"Using chapter-based search windows ({len(windows)} windows)")
                return windows

        # Priority 3: TMDB runtime-based windows (estimate commercials)
        if tmdb_runtimes and len(tmdb_runtimes) >= self.expected_episode_count:
            windows = self._windows_from_tmdb(tmdb_runtimes, None)
            if windows:
                logger.info(f"Using TMDB-based search windows ({len(windows)} windows)")
                return windows

        # Priority 4: Equal division with commercial adjustment
        if commercial_times:
            windows = self._windows_from_commercials(commercial_times)
            if windows:
                logger.info(f"Using commercial-adjusted search windows ({len(windows)} windows)")
                return windows

        # Fallback: Simple equal division
        windows = self._windows_from_equal_division()
        logger.info(f"Using equal-division search windows ({len(windows)} windows)")
        return windows

    def _windows_from_chapters(
        self,
        chapter_boundaries: List[Tuple[float, float]]
    ) -> Optional[List[SearchWindow]]:
        """
        Create search windows from chapter-detected boundaries.

        Chapter boundaries give us approximate regions. We create
        windows around the end of each episode region.

        Args:
            chapter_boundaries: List of (start, end) episode regions

        Returns:
            List of search windows, or None if not enough data
        """
        if len(chapter_boundaries) < 2:
            return None

        windows = []

        # Each window is centered on the end of an episode (except the last)
        for i in range(len(chapter_boundaries) - 1):
            ep_end = chapter_boundaries[i][1]
            next_ep_start = chapter_boundaries[i + 1][0]

            # Window center is between episode end and next start
            center = (ep_end + next_ep_start) / 2

            # Adjust window to span from before ep_end to after next_ep_start
            window_start = max(0, ep_end - self.window_size)
            window_end = min(self.total_duration, next_ep_start + self.window_size)

            windows.append(SearchWindow(
                start_time=window_start,
                end_time=window_end,
                center_time=center,
                confidence=0.9,
                source='chapter',
                episode_before=i + 1,
                episode_after=i + 2,
                metadata={
                    'chapter_ep_end': ep_end,
                    'chapter_next_start': next_ep_start,
                }
            ))

        return windows if len(windows) == self.expected_episode_count - 1 else None

    def _windows_from_tmdb(
        self,
        tmdb_runtimes: List[int],
        commercial_times_per_episode: Optional[List[float]] = None,
    ) -> Optional[List[SearchWindow]]:
        """
        Create search windows from TMDB episode runtimes.

        TMDB runtimes are content-only (no commercials). If we have actual
        commercial times per episode (from chapter markers), we use those.
        Otherwise we estimate commercial time from the file duration difference.

        Args:
            tmdb_runtimes: Episode runtimes in minutes
            commercial_times_per_episode: Optional list of commercial durations
                per episode in seconds (from chapter markers)

        Returns:
            List of search windows
        """
        if len(tmdb_runtimes) < self.expected_episode_count:
            return None

        # Use only the runtimes we need
        runtimes_min = tmdb_runtimes[:self.expected_episode_count]
        runtimes_sec = [r * 60 for r in runtimes_min]  # Convert to seconds
        total_content_time = sum(runtimes_sec)

        # Determine commercial time per episode
        if (commercial_times_per_episode and
            len(commercial_times_per_episode) >= self.expected_episode_count):
            # Use actual commercial times from chapter markers
            commercials_sec = commercial_times_per_episode[:self.expected_episode_count]
            total_commercial_time = sum(commercials_sec)
            use_actual_commercials = True

            logger.debug(
                f"TMDB+Chapters: Using actual commercial times per episode: "
                f"{[f'{c/60:.1f}m' for c in commercials_sec]}"
            )
        else:
            # Estimate: file duration - content time = commercial time
            total_commercial_time = max(0, self.total_duration - total_content_time)
            commercials_sec = [total_commercial_time / self.expected_episode_count] * self.expected_episode_count
            use_actual_commercials = False

            logger.debug(
                f"TMDB: Estimating {total_commercial_time/60:.1f}m total commercials "
                f"({commercials_sec[0]/60:.1f}m per episode)"
            )

        # Calculate episode totals (content + commercials)
        episode_totals = [runtimes_sec[i] + commercials_sec[i]
                         for i in range(self.expected_episode_count)]
        calculated_duration = sum(episode_totals)

        # Pro-rate any discrepancy between calculated and actual file duration
        discrepancy = self.total_duration - calculated_duration
        if abs(discrepancy) > 1.0:  # More than 1 second difference
            logger.debug(
                f"Duration discrepancy: calculated {calculated_duration/60:.1f}m vs "
                f"actual {self.total_duration/60:.1f}m (diff: {discrepancy/60:.2f}m)"
            )
            # Distribute discrepancy proportionally to each episode's total
            for i in range(self.expected_episode_count):
                proportion = episode_totals[i] / calculated_duration
                episode_totals[i] += discrepancy * proportion

            logger.debug(
                f"Adjusted episode totals: {[f'{t/60:.1f}m' for t in episode_totals]}"
            )

        logger.debug(
            f"TMDB: {total_content_time/60:.1f}m content + "
            f"{total_commercial_time/60:.1f}m commercials = "
            f"{sum(episode_totals)/60:.1f}m total"
        )

        # Build windows at cumulative episode boundaries
        windows = []
        cumulative_time = 0.0

        for i in range(self.expected_episode_count - 1):
            cumulative_time += episode_totals[i]

            # Window centered on cumulative time
            window_start = max(0, cumulative_time - self.window_size)
            window_end = min(self.total_duration, cumulative_time + self.window_size)

            windows.append(SearchWindow(
                start_time=window_start,
                end_time=window_end,
                center_time=cumulative_time,
                confidence=0.85 if use_actual_commercials else 0.8,
                source='tmdb+chapters' if use_actual_commercials else 'tmdb',
                episode_before=i + 1,
                episode_after=i + 2,
                metadata={
                    'tmdb_runtime_min': runtimes_min[i],
                    'commercial_sec': commercials_sec[i],
                    'episode_total_sec': episode_totals[i],
                    'actual_commercials': use_actual_commercials,
                }
            ))

        return windows

    def _windows_from_commercials(
        self,
        commercial_times: List[Tuple[float, float]]
    ) -> Optional[List[SearchWindow]]:
        """
        Create search windows using commercial break timing.

        Analyzes commercial break patterns to find likely episode boundaries.
        Episode boundaries typically occur after longer commercial breaks
        or at regular intervals.

        Args:
            commercial_times: List of (start, end) for commercial breaks

        Returns:
            List of search windows
        """
        if not commercial_times:
            return None

        # Calculate commercial break durations
        breaks_with_duration = [
            (start, end, end - start)
            for start, end in commercial_times
        ]

        # Sort by position
        breaks_with_duration.sort(key=lambda x: x[0])

        # Find breaks near expected episode boundaries
        windows = []

        for i in range(self.expected_episode_count - 1):
            expected_time = self.nominal_episode_length * (i + 1)

            # Find commercial break closest to expected time
            best_break = None
            best_distance = float('inf')

            for start, end, duration in breaks_with_duration:
                # Use end of commercial as potential boundary
                distance = abs(end - expected_time)
                if distance < best_distance and distance < self.window_size * 2:
                    best_distance = distance
                    best_break = (start, end, duration)

            if best_break:
                center = best_break[1]  # End of commercial break
            else:
                center = expected_time

            window_start = max(0, center - self.window_size)
            window_end = min(self.total_duration, center + self.window_size)

            windows.append(SearchWindow(
                start_time=window_start,
                end_time=window_end,
                center_time=center,
                confidence=0.7,
                source='commercial',
                episode_before=i + 1,
                episode_after=i + 2,
                metadata={
                    'nearest_commercial': best_break,
                }
            ))

        return windows

    def _windows_from_equal_division(self) -> List[SearchWindow]:
        """
        Create search windows by dividing file into equal parts.

        Fallback when no better information is available.

        Returns:
            List of search windows
        """
        windows = []

        for i in range(self.expected_episode_count - 1):
            center = self.nominal_episode_length * (i + 1)

            window_start = max(0, center - self.window_size)
            window_end = min(self.total_duration, center + self.window_size)

            windows.append(SearchWindow(
                start_time=window_start,
                end_time=window_end,
                center_time=center,
                confidence=0.5,  # Lower confidence for equal division
                source='equal_division',
                episode_before=i + 1,
                episode_after=i + 2,
                metadata={
                    'nominal_episode_length': self.nominal_episode_length,
                }
            ))

        return windows

    def refine_windows_with_chapters(
        self,
        windows: List[SearchWindow],
        chapter_info: dict,
    ) -> List[SearchWindow]:
        """
        Refine existing windows using chapter information.

        If we have "Commercial 1" markers, we know approximately where
        each episode's first commercial starts. The episode boundary
        is somewhere between the end of episode N's last commercial
        and the start of episode N+1's content.

        Args:
            windows: Existing search windows
            chapter_info: Chapter detection info with commercial markers

        Returns:
            Refined search windows
        """
        commercial_1_times = chapter_info.get('commercial_1_times', [])

        if not commercial_1_times or len(commercial_1_times) < len(windows):
            return windows

        refined = []

        for i, window in enumerate(windows):
            if i < len(commercial_1_times):
                # "Commercial 1" marks first commercial of episode i+2
                # So episode boundary is BEFORE this
                commercial_1_time = commercial_1_times[i]

                # Adjust window to end at Commercial 1 (boundary must be before it)
                # and extend search backwards
                new_center = commercial_1_time - (self.window_size / 2)
                new_start = max(0, commercial_1_time - self.window_size * 2)
                new_end = commercial_1_time

                refined.append(SearchWindow(
                    start_time=new_start,
                    end_time=new_end,
                    center_time=new_center,
                    confidence=min(window.confidence + 0.1, 0.95),
                    source=f'{window.source}+commercial_refined',
                    episode_before=window.episode_before,
                    episode_after=window.episode_after,
                    metadata={
                        **window.metadata,
                        'commercial_1_time': commercial_1_time,
                    }
                ))
            else:
                refined.append(window)

        return refined
