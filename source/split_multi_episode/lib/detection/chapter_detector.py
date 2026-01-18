#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Chapter-based episode boundary detection.

Parses chapter markers from video files to identify episode boundaries.
This method is only used when chapters clearly indicate episode separations,
not when they mark commercials, scenes, or other non-episode markers.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.chapter_detector")


@dataclass
class EpisodeBoundary:
    """Represents a detected episode boundary."""
    start_time: float  # seconds
    end_time: float    # seconds
    confidence: float  # 0.0 to 1.0
    source: str        # detection method name
    metadata: dict     # additional info (chapter title, etc.)


class ChapterDetector:
    """
    Detects episode boundaries from chapter markers in video files.

    IMPORTANT: Chapters are only used for splitting when they clearly indicate
    episode boundaries. Chapters that mark commercials, scenes, or other
    non-episode content are filtered out.

    Detection criteria:
    1. Chapter titles must indicate episodes (e.g., "Episode 1", "E01", "Part 1")
    2. OR chapters must have episode-appropriate durations (15-90 minutes)
    3. AND the chapter structure must be consistent with episodes (not commercials)
    """

    CONFIDENCE = 0.9

    # Patterns that STRONGLY indicate episode chapters (high confidence)
    EPISODE_TITLE_PATTERNS = [
        r'\bepisode\s*\d+',           # "Episode 1", "Episode 01"
        r'\bep\.?\s*\d+',             # "Ep 1", "Ep. 01"
        r'\be\d+\b',                  # "E1", "E01" (word boundary)
        r'\bpart\s*\d+',              # "Part 1", "Part One"
        r'\bpart\s+(one|two|three|four|five|six|seven|eight|nine|ten)\b',
        r'^\d+\s*[-:\.]\s*\d+$',      # "1-01" or "1:01" or "1.01" (season-episode)
        r'\bs\d+\s*e\d+',             # "S01E01", "S1E1"
    ]

    # Patterns that indicate NON-episode chapters (skip these)
    NON_EPISODE_PATTERNS = [
        r'^menu$',
        r'^scene\s+selection',
        r'^scene\s*\d*$',             # "Scene", "Scene 1"
        r'^chapter\s*\d*$',           # Generic "Chapter 1" without episode context
        r'^bonus',
        r'^extras?$',
        r'^special\s+features?',
        r'^deleted\s+scenes?',
        r'^commentary',
        r'^trailer',
        r'^preview',
        r'^commercial\s+\d+',         # "Commercial 2", "Commercial 3" etc (but NOT "Commercial 1")
        r'^advertisement',
        r'^ad\s*break',
        r'^break\s*\d*$',
        r'^intermission',
        r'^recap',
        r'^opening\s*(credits?)?$',   # Opening credits alone
        r'^closing\s*(credits?)?$',
        r'^end\s*credits?$',
        r'^credits?$',
        r'^intro$',                   # Intro alone (not "intro to episode")
        r'^outro$',
    ]

    # Pattern for "Commercial 1" which often marks episode boundaries
    EPISODE_BOUNDARY_COMMERCIAL_PATTERN = re.compile(r'^commercial\s*1$', re.IGNORECASE)

    # Typical commercial break duration range (seconds)
    COMMERCIAL_MIN_DURATION = 15      # 15 seconds
    COMMERCIAL_MAX_DURATION = 300     # 5 minutes

    def __init__(self, min_episode_length: float = 900, max_episode_length: float = 5400):
        """
        Initialize the chapter detector.

        Args:
            min_episode_length: Minimum episode duration in seconds (default: 15 min)
            max_episode_length: Maximum episode duration in seconds (default: 90 min)
        """
        self.min_episode_length = min_episode_length
        self.max_episode_length = max_episode_length
        self._episode_patterns = [re.compile(p, re.IGNORECASE) for p in self.EPISODE_TITLE_PATTERNS]
        self._non_episode_patterns = [re.compile(p, re.IGNORECASE) for p in self.NON_EPISODE_PATTERNS]

    def detect(self, probe_data: dict) -> List[EpisodeBoundary]:
        """
        Detect episode boundaries from chapter markers.

        Only returns boundaries if chapters clearly indicate episode separations.

        Args:
            probe_data: FFprobe output dictionary containing 'chapters' key

        Returns:
            List of EpisodeBoundary objects representing detected episodes,
            or empty list if chapters don't indicate episode boundaries
        """
        chapters = probe_data.get('chapters', [])

        if not chapters:
            logger.debug("No chapters found in file")
            return []

        logger.info(f"Found {len(chapters)} chapters in file")

        # First, check for "Commercial 1" markers which often indicate episode boundaries
        commercial_boundaries = self._detect_from_commercial_markers(chapters, probe_data)
        if commercial_boundaries:
            logger.info(f"Detected {len(commercial_boundaries)} episodes from 'Commercial 1' markers")
            return commercial_boundaries

        # Analyze chapter structure to determine if they represent episodes
        analysis = self._analyze_chapter_structure(chapters)

        if not analysis['is_episode_structure']:
            logger.info(f"Chapters do not appear to indicate episodes: {analysis['reason']}")
            return []

        # Filter to episode chapters
        episode_chapters = analysis['episode_chapters']

        if len(episode_chapters) < 2:
            logger.debug("Not enough episode chapters to split (need at least 2)")
            return []

        # Convert chapters to boundaries
        boundaries = self._chapters_to_boundaries(episode_chapters, probe_data)

        logger.info(f"Detected {len(boundaries)} episode boundaries from chapters")
        return boundaries

    def _detect_from_commercial_markers(
        self,
        chapters: List[dict],
        probe_data: dict
    ) -> List[EpisodeBoundary]:
        """
        Detect episode boundaries from "Commercial 1" chapter markers.

        In recordings with commercials, "Commercial 1" often marks the start
        of the first commercial break after a new episode begins. The time
        just before "Commercial 1" (or the start of the file for the first
        episode) marks episode boundaries.

        Args:
            chapters: List of chapter dictionaries from ffprobe
            probe_data: Full probe data for total duration

        Returns:
            List of EpisodeBoundary objects, or empty list if pattern not found
        """
        total_duration = float(probe_data.get('format', {}).get('duration', 0))

        # Find all "Commercial 1" markers
        commercial_1_times = []
        for ch in chapters:
            title = ch.get('tags', {}).get('title', '')
            if self.EPISODE_BOUNDARY_COMMERCIAL_PATTERN.match(title):
                start_time = float(ch.get('start_time', 0))
                commercial_1_times.append(start_time)

        if len(commercial_1_times) < 1:
            return []

        logger.debug(f"Found {len(commercial_1_times)} 'Commercial 1' markers at: {commercial_1_times}")

        # The first episode starts at 0, subsequent episodes start at each "Commercial 1"
        # Actually, "Commercial 1" marks the FIRST commercial of an episode,
        # so episode boundaries are BEFORE "Commercial 1" markers

        # Build episode regions: each episode ends just before the next "Commercial 1"
        # and the last episode ends at the file end
        boundaries = []
        episode_starts = [0.0] + commercial_1_times
        episode_ends = commercial_1_times + [total_duration]

        for i in range(len(episode_starts)):
            start = episode_starts[i]
            end = episode_ends[i]
            duration = end - start

            # Validate duration
            if duration < self.min_episode_length:
                logger.debug(f"Episode {i+1} too short ({duration/60:.1f} min), skipping")
                continue

            if duration > self.max_episode_length:
                logger.debug(f"Episode {i+1} longer than max ({duration/60:.1f} min), but including")

            boundaries.append(EpisodeBoundary(
                start_time=start,
                end_time=end,
                confidence=0.85,  # High confidence from commercial markers
                source='chapter_commercial',
                metadata={
                    'episode_index': i + 1,
                    'detection_method': 'commercial_1_marker',
                }
            ))

        # Need at least 2 episodes for splitting
        if len(boundaries) < 2:
            return []

        return boundaries

    def get_estimated_episode_regions(
        self,
        probe_data: dict,
        expected_episode_count: Optional[int] = None
    ) -> List[Tuple[float, float]]:
        """
        Get estimated episode time regions from chapter analysis.

        This method provides time windows where episodes are likely located,
        useful for narrowing down silence detection or other methods.

        Args:
            probe_data: FFprobe output dictionary
            expected_episode_count: Expected number of episodes (from filename)

        Returns:
            List of (start_time, end_time) tuples for estimated episode regions
        """
        chapters = probe_data.get('chapters', [])
        total_duration = float(probe_data.get('format', {}).get('duration', 0))

        if not chapters:
            # No chapters - divide evenly if we know episode count
            if expected_episode_count and expected_episode_count > 1:
                episode_duration = total_duration / expected_episode_count
                return [
                    (i * episode_duration, (i + 1) * episode_duration)
                    for i in range(expected_episode_count)
                ]
            return []

        # Try "Commercial 1" markers first
        commercial_1_times = []
        for ch in chapters:
            title = ch.get('tags', {}).get('title', '')
            if self.EPISODE_BOUNDARY_COMMERCIAL_PATTERN.match(title):
                start_time = float(ch.get('start_time', 0))
                commercial_1_times.append(start_time)

        if commercial_1_times:
            # Build regions from Commercial 1 markers
            episode_starts = [0.0] + commercial_1_times
            episode_ends = commercial_1_times + [total_duration]
            return list(zip(episode_starts, episode_ends))

        # Fall back to even division if expected count is known
        if expected_episode_count and expected_episode_count > 1:
            episode_duration = total_duration / expected_episode_count
            return [
                (i * episode_duration, (i + 1) * episode_duration)
                for i in range(expected_episode_count)
            ]

        return []

    def _analyze_chapter_structure(self, chapters: List[dict]) -> dict:
        """
        Analyze chapter structure to determine if chapters represent episodes.

        Returns a dictionary with:
        - is_episode_structure: bool - whether chapters indicate episodes
        - reason: str - explanation of the decision
        - episode_chapters: List[dict] - chapters that appear to be episodes

        Args:
            chapters: List of chapter dictionaries from ffprobe

        Returns:
            Analysis dictionary
        """
        if not chapters:
            return {
                'is_episode_structure': False,
                'reason': 'No chapters found',
                'episode_chapters': []
            }

        # Collect info about each chapter
        chapter_info = []
        for ch in chapters:
            title = ch.get('tags', {}).get('title', '')
            start = float(ch.get('start_time', 0))
            end = float(ch.get('end_time', 0))
            duration = end - start

            is_episode_title = any(p.search(title) for p in self._episode_patterns)
            is_non_episode = any(p.search(title) for p in self._non_episode_patterns)
            is_episode_duration = self.min_episode_length <= duration <= self.max_episode_length
            is_commercial_duration = self.COMMERCIAL_MIN_DURATION <= duration <= self.COMMERCIAL_MAX_DURATION

            chapter_info.append({
                'chapter': ch,
                'title': title,
                'duration': duration,
                'is_episode_title': is_episode_title,
                'is_non_episode': is_non_episode,
                'is_episode_duration': is_episode_duration,
                'is_commercial_duration': is_commercial_duration,
            })

        # Count different types
        episode_title_count = sum(1 for c in chapter_info if c['is_episode_title'])
        non_episode_count = sum(1 for c in chapter_info if c['is_non_episode'])
        episode_duration_count = sum(1 for c in chapter_info if c['is_episode_duration'])
        commercial_duration_count = sum(1 for c in chapter_info if c['is_commercial_duration'])

        total = len(chapter_info)

        logger.debug(f"Chapter analysis: {total} total, {episode_title_count} episode titles, "
                     f"{non_episode_count} non-episode, {episode_duration_count} episode-length, "
                     f"{commercial_duration_count} commercial-length")

        # Decision logic:

        # Case 1: Chapters have explicit episode titles
        if episode_title_count >= 2:
            episode_chapters = [c['chapter'] for c in chapter_info
                                if c['is_episode_title'] and not c['is_non_episode']]
            if len(episode_chapters) >= 2:
                return {
                    'is_episode_structure': True,
                    'reason': f'Found {len(episode_chapters)} chapters with episode titles',
                    'episode_chapters': episode_chapters
                }

        # Case 2: Most chapters are commercial-length (not episode structure)
        if commercial_duration_count > total * 0.5:
            return {
                'is_episode_structure': False,
                'reason': f'{commercial_duration_count}/{total} chapters have commercial-like duration',
                'episode_chapters': []
            }

        # Case 3: Most chapters match non-episode patterns
        if non_episode_count > total * 0.3:
            return {
                'is_episode_structure': False,
                'reason': f'{non_episode_count}/{total} chapters match non-episode patterns',
                'episode_chapters': []
            }

        # Case 4: Few chapters with episode-appropriate durations
        if episode_duration_count >= 2 and episode_duration_count == total:
            # All chapters have episode-like duration - likely episodes
            episode_chapters = [c['chapter'] for c in chapter_info
                                if c['is_episode_duration'] and not c['is_non_episode']]
            if len(episode_chapters) >= 2:
                return {
                    'is_episode_structure': True,
                    'reason': f'All {len(episode_chapters)} chapters have episode-appropriate duration',
                    'episode_chapters': episode_chapters
                }

        # Case 5: Mixed structure - only use explicitly titled episode chapters
        episode_chapters = [c['chapter'] for c in chapter_info
                           if c['is_episode_title'] and not c['is_non_episode']
                           and c['is_episode_duration']]
        if len(episode_chapters) >= 2:
            return {
                'is_episode_structure': True,
                'reason': f'Found {len(episode_chapters)} chapters with episode titles and duration',
                'episode_chapters': episode_chapters
            }

        # Default: Can't determine episode structure from chapters
        return {
            'is_episode_structure': False,
            'reason': 'Chapter structure does not clearly indicate episodes',
            'episode_chapters': []
        }

    def _chapters_to_boundaries(self, chapters: List[dict], probe_data: dict) -> List[EpisodeBoundary]:
        """
        Convert filtered chapters to episode boundaries.

        Args:
            chapters: List of filtered chapter dictionaries
            probe_data: Full probe data for additional context

        Returns:
            List of EpisodeBoundary objects
        """
        boundaries = []
        total_duration = float(probe_data.get('format', {}).get('duration', 0))

        for i, chapter in enumerate(chapters):
            start_time = float(chapter.get('start_time', 0))
            end_time = float(chapter.get('end_time', 0))
            title = chapter.get('tags', {}).get('title', f'Episode {i + 1}')

            # Validate duration
            duration = end_time - start_time
            if duration < self.min_episode_length:
                logger.debug(f"Skipping chapter '{title}': too short ({duration:.1f}s)")
                continue

            if duration > self.max_episode_length:
                logger.warning(f"Chapter '{title}' exceeds max episode length ({duration:.1f}s)")

            boundary = EpisodeBoundary(
                start_time=start_time,
                end_time=end_time,
                confidence=self.CONFIDENCE,
                source='chapter',
                metadata={
                    'title': title,
                    'chapter_index': i,
                    'chapter_id': chapter.get('id'),
                }
            )
            boundaries.append(boundary)

        return boundaries

    def has_multi_episode_chapters(self, probe_data: dict) -> bool:
        """
        Quick check if file appears to have multiple episode chapters.
        Used for the file test runner to determine if file should be queued.

        Args:
            probe_data: FFprobe output dictionary

        Returns:
            True if file appears to contain multiple episodes based on chapters
        """
        chapters = probe_data.get('chapters', [])

        if len(chapters) < 2:
            return False

        # Use the full analysis
        analysis = self._analyze_chapter_structure(chapters)
        return analysis['is_episode_structure'] and len(analysis['episode_chapters']) >= 2

    def get_chapter_summary(self, probe_data: dict) -> str:
        """
        Get a human-readable summary of chapter analysis.

        Args:
            probe_data: FFprobe output dictionary

        Returns:
            Summary string
        """
        chapters = probe_data.get('chapters', [])

        if not chapters:
            return "No chapters found"

        analysis = self._analyze_chapter_structure(chapters)

        lines = [f"Total chapters: {len(chapters)}"]

        for ch in chapters:
            title = ch.get('tags', {}).get('title', '(untitled)')
            duration = float(ch.get('end_time', 0)) - float(ch.get('start_time', 0))
            lines.append(f"  - {title}: {duration/60:.1f} min")

        lines.append(f"Episode structure: {analysis['is_episode_structure']}")
        lines.append(f"Reason: {analysis['reason']}")

        return '\n'.join(lines)
