#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TMDB (The Movie Database) episode runtime validation.

Uses TMDB API to fetch expected episode runtimes and validate
detected boundaries against known episode durations.
"""

import logging
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.tmdb_validator")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests library not available - TMDB validation disabled")

try:
    import PTN
    PTN_AVAILABLE = True
except ImportError:
    PTN_AVAILABLE = False
    logger.warning("PTN (parse-torrent-name) not available - filename parsing disabled")


@dataclass
class TMDBEpisodeInfo:
    """Episode information from TMDB."""
    season_number: int
    episode_number: int
    name: str
    runtime: int  # minutes
    air_date: Optional[str]


@dataclass
class ValidationResult:
    """Result of TMDB validation."""
    is_valid: bool
    confidence_adjustment: float  # +/- adjustment to boundary confidence
    expected_runtimes: List[int]  # Expected runtimes in minutes
    detected_durations: List[float]  # Detected durations in minutes
    message: str


class TMDBValidator:
    """
    Validates episode boundaries against TMDB episode runtime data.

    Fetches expected episode runtimes from TMDB and compares them
    to detected episode durations to adjust confidence scores.
    """

    TMDB_API_BASE = "https://api.themoviedb.org/3"

    def __init__(
        self,
        api_key: str = "",
        api_read_access_token: str = "",
        runtime_tolerance: float = 0.15,  # 15% tolerance
    ):
        """
        Initialize the TMDB validator.

        Args:
            api_key: TMDB API key
            api_read_access_token: TMDB API read access token (v4)
            runtime_tolerance: Acceptable runtime deviation (0.15 = 15%)
        """
        self.api_key = api_key
        self.api_read_access_token = api_read_access_token
        self.runtime_tolerance = runtime_tolerance

    def is_available(self) -> bool:
        """Check if TMDB validation is available."""
        if not REQUESTS_AVAILABLE:
            return False
        return bool(self.api_key or self.api_read_access_token)

    def validate(
        self,
        file_path: str,
        detected_durations: List[float],
        title_override: Optional[str] = None,
        season_override: Optional[int] = None,
        start_episode_override: Optional[int] = None,
        commercial_times: Optional[List[float]] = None,
    ) -> ValidationResult:
        """
        Validate detected episode durations against TMDB data.

        Args:
            file_path: Path to the video file (for title parsing if no override)
            detected_durations: List of detected episode durations in seconds
            title_override: Optional title to use instead of parsing from filename
            season_override: Optional season number override
            start_episode_override: Optional starting episode number override
            commercial_times: Optional list of commercial durations per episode (seconds)
                              If provided, these are subtracted from detected durations
                              before comparing to TMDB (which reports content-only runtimes)

        Returns:
            ValidationResult with confidence adjustment
        """
        if not self.is_available():
            return ValidationResult(
                is_valid=True,
                confidence_adjustment=0.0,
                expected_runtimes=[],
                detected_durations=[d / 60 for d in detected_durations],
                message="TMDB validation not available"
            )

        # Use overrides or parse from filename
        if title_override:
            title = title_override
            season = season_override or 1
            start_episode = start_episode_override or 1
        else:
            # Parse series info from filename
            series_info = self._parse_filename(file_path)
            if not series_info:
                return ValidationResult(
                    is_valid=True,
                    confidence_adjustment=0.0,
                    expected_runtimes=[],
                    detected_durations=[d / 60 for d in detected_durations],
                    message="Could not parse series info from filename"
                )

            title = series_info.get('title', '')
            season = season_override or series_info.get('season', 1)
            episode_info = series_info.get('episode', 1)
            # Handle episode ranges (PTN may return a list for ranges like 5-8)
            if isinstance(episode_info, list):
                start_episode = start_episode_override or (episode_info[0] if episode_info else 1)
            else:
                start_episode = start_episode_override or episode_info

        logger.info(f"Looking up TMDB info for: {title} S{season}E{start_episode}")

        # Search for the series
        series_id = self._search_series(title)
        if not series_id:
            return ValidationResult(
                is_valid=True,
                confidence_adjustment=0.0,
                expected_runtimes=[],
                detected_durations=[d / 60 for d in detected_durations],
                message=f"Series '{title}' not found on TMDB"
            )

        # Get episode info for the season
        episodes = self._get_season_episodes(series_id, season)
        if not episodes:
            return ValidationResult(
                is_valid=True,
                confidence_adjustment=0.0,
                expected_runtimes=[],
                detected_durations=[d / 60 for d in detected_durations],
                message=f"No episodes found for season {season}"
            )

        # Get expected runtimes for the detected episode count
        num_detected = len(detected_durations)
        expected_episodes = episodes[start_episode - 1:start_episode - 1 + num_detected]
        expected_runtimes = [ep.runtime for ep in expected_episodes if ep.runtime]

        # Log what episodes we found
        episode_names = [f"E{ep.episode_number}: {ep.name}" for ep in expected_episodes]
        logger.info(f"Found episodes: {episode_names}")

        if not expected_runtimes:
            # Show which episodes were found but lack runtime data
            ep_info = ", ".join([f"E{ep.episode_number}" for ep in expected_episodes])
            return ValidationResult(
                is_valid=True,
                confidence_adjustment=0.0,
                expected_runtimes=[],
                detected_durations=[d / 60 for d in detected_durations],
                message=f"Found {len(expected_episodes)} episodes ({ep_info}) but no runtime data in TMDB"
            )

        # Adjust for commercial time if provided
        adjusted_durations = detected_durations
        has_commercials = False
        if commercial_times and len(commercial_times) == len(detected_durations):
            has_commercials = True
            adjusted_durations = [
                max(0, dur - comm)  # Subtract commercial time, don't go negative
                for dur, comm in zip(detected_durations, commercial_times)
            ]
            logger.debug(
                f"Adjusting for commercials: "
                f"raw={[f'{d/60:.1f}m' for d in detected_durations]}, "
                f"commercials={[f'{c/60:.1f}m' for c in commercial_times]}, "
                f"adjusted={[f'{a/60:.1f}m' for a in adjusted_durations]}"
            )

        # Compare runtimes
        return self._compare_runtimes(
            expected_runtimes,
            [d / 60 for d in adjusted_durations],  # Convert to minutes
            commercial_adjusted=has_commercials,
        )

    def _normalize_for_parsing(self, filename: str) -> str:
        """
        Normalize filename to improve parsing of episode ranges.

        Handles:
        - "S1 E01 - E08" -> "S1E01-E08" (spaces between S and E)
        - "[E01-E08]" -> "E01-E08" (brackets around range)
        - "E01_08" or "E01 _ 08" -> "E01-08" (underscore separator)
        - "combined" keyword removal

        Args:
            filename: Original filename

        Returns:
            Normalized filename for parsing
        """
        result = filename

        # Normalize "S1 E01" -> "S1E01" (space between season and episode)
        result = re.sub(r'[Ss](\d+)\s+[Ee](\d+)', r'S\1E\2', result)

        # Normalize bracket notation: "[E01-E08]" -> "E01-E08"
        result = re.sub(r'\[([Ee]\d+\s*[-–_]\s*[Ee]?\d+)\]', r'\1', result)

        # Normalize underscore separator in ranges: E01_08 -> E01-08
        result = re.sub(r'([Ee]\d+)\s*[_]\s*(\d+)', r'\1-\2', result)

        # Remove word "combined" (case insensitive)
        result = re.sub(r'\s*\bcombined\b\s*', ' ', result, flags=re.IGNORECASE)

        # Clean up multiple spaces
        result = re.sub(r'\s+', ' ', result)

        return result

    def _parse_filename(self, file_path: str) -> Optional[Dict]:
        """
        Parse series information from filename.

        Args:
            file_path: Path to the video file

        Returns:
            Dictionary with title, season, episode or None
        """
        basename = os.path.basename(file_path)

        # Normalize filename for better parsing of episode ranges
        normalized_basename = self._normalize_for_parsing(basename)

        if PTN_AVAILABLE:
            try:
                parsed = PTN.parse(normalized_basename)
                if parsed.get('title'):
                    return {
                        'title': parsed.get('title', ''),
                        'season': parsed.get('season', 1),
                        'episode': parsed.get('episode', 1),
                    }
            except Exception as e:
                logger.debug(f"PTN parsing failed: {e}")

        # Fallback: regex parsing (use normalized name for better range detection)
        name = os.path.splitext(basename)[0]
        normalized_name = self._normalize_for_parsing(name)

        # Pattern 1: Episode range with title before OR after
        # e.g., "S1E1-3 Cambridge Spies" or "Cambridge Spies S1E1-3"
        range_pattern = re.compile(r'[Ss](\d+)[Ee](\d+)\s*[-–]\s*[Ee]?(\d+)', re.IGNORECASE)
        range_match = range_pattern.search(normalized_name)

        if range_match:
            season = int(range_match.group(1))
            episode = int(range_match.group(2))

            # Title is typically BEFORE the episode info (S##E##)
            # The content AFTER is usually quality/codec/source metadata
            # Use original name for title extraction to preserve formatting
            before = normalized_name[:range_match.start()].strip(' ._-')
            after = normalized_name[range_match.end():].strip(' ._-')

            # Prefer the "before" part as the title (standard naming convention)
            # Only use "after" if "before" is empty or very short (< 3 chars)
            if before and len(before) >= 3:
                title = before
            elif after:
                title = after
            elif before:
                title = before
            else:
                title = name

            title = title.replace('.', ' ').replace('_', ' ').strip()
            return {'title': title, 'season': season, 'episode': episode}

        # Pattern 2: Standard S01E01 with title before OR after
        se_pattern = re.compile(r'[Ss](\d+)[Ee](\d+)', re.IGNORECASE)
        se_match = se_pattern.search(normalized_name)

        if se_match:
            season = int(se_match.group(1))
            episode = int(se_match.group(2))

            # Title is typically BEFORE the episode info (S##E##)
            before = normalized_name[:se_match.start()].strip(' ._-')
            after = normalized_name[se_match.end():].strip(' ._-')

            # Prefer the "before" part as the title (standard naming convention)
            if before and len(before) >= 3:
                title = before
            elif after:
                title = after
            elif before:
                title = before
            else:
                title = name

            title = title.replace('.', ' ').replace('_', ' ').strip()
            return {'title': title, 'season': season, 'episode': episode}

        # Pattern 3: 1x01 format
        x_pattern = re.compile(r'(\d+)[Xx](\d+)')
        x_match = x_pattern.search(normalized_name)

        if x_match:
            season = int(x_match.group(1))
            episode = int(x_match.group(2))

            # Title is typically BEFORE the episode info
            before = normalized_name[:x_match.start()].strip(' ._-')
            after = normalized_name[x_match.end():].strip(' ._-')

            # Prefer the "before" part as the title (standard naming convention)
            if before and len(before) >= 3:
                title = before
            elif after:
                title = after
            elif before:
                title = before
            else:
                title = name

            title = title.replace('.', ' ').replace('_', ' ').strip()
            return {'title': title, 'season': season, 'episode': episode}

        # Last resort: clean up the name
        name = re.sub(r'\s*(720p|1080p|2160p|4K|HDR|x264|x265|HEVC|BluRay|WEB-DL).*$', '', name, flags=re.IGNORECASE)

        return {'title': name.replace('.', ' ').replace('_', ' ').strip(), 'season': 1, 'episode': 1}

    def _search_series(self, title: str) -> Optional[int]:
        """
        Search for a TV series on TMDB.

        Args:
            title: Series title to search for

        Returns:
            TMDB series ID or None if not found
        """
        try:
            headers = self._get_headers()
            params = {
                'query': title,
                'api_key': self.api_key if not self.api_read_access_token else None,
            }
            params = {k: v for k, v in params.items() if v}

            response = requests.get(
                f"{self.TMDB_API_BASE}/search/tv",
                headers=headers,
                params=params,
                timeout=10
            )

            if response.status_code != 200:
                logger.warning(f"TMDB search failed: {response.status_code}")
                return None

            results = response.json().get('results', [])
            if results:
                # Return the first (most relevant) result
                return results[0].get('id')

        except Exception as e:
            logger.error(f"TMDB search error: {e}")

        return None

    def _get_season_episodes(self, series_id: int, season: int) -> List[TMDBEpisodeInfo]:
        """
        Get episode information for a season.

        Args:
            series_id: TMDB series ID
            season: Season number

        Returns:
            List of TMDBEpisodeInfo objects
        """
        try:
            headers = self._get_headers()
            params = {'api_key': self.api_key} if not self.api_read_access_token else {}

            response = requests.get(
                f"{self.TMDB_API_BASE}/tv/{series_id}/season/{season}",
                headers=headers,
                params=params,
                timeout=10
            )

            if response.status_code != 200:
                logger.warning(f"TMDB season fetch failed: {response.status_code}")
                return []

            data = response.json()
            episodes = []

            for ep in data.get('episodes', []):
                episodes.append(TMDBEpisodeInfo(
                    season_number=ep.get('season_number', season),
                    episode_number=ep.get('episode_number', 0),
                    name=ep.get('name', ''),
                    runtime=ep.get('runtime', 0),
                    air_date=ep.get('air_date'),
                ))

            return episodes

        except Exception as e:
            logger.error(f"TMDB season fetch error: {e}")
            return []

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {'accept': 'application/json'}
        if self.api_read_access_token:
            headers['Authorization'] = f'Bearer {self.api_read_access_token}'
        return headers

    def _compare_runtimes(
        self,
        expected_runtimes: List[int],
        detected_durations: List[float],
        commercial_adjusted: bool = False,
    ) -> ValidationResult:
        """
        Compare expected and detected runtimes.

        Args:
            expected_runtimes: Expected runtimes in minutes
            detected_durations: Detected durations in minutes
            commercial_adjusted: Whether durations were adjusted by subtracting commercial time

        Returns:
            ValidationResult with confidence adjustment
        """
        if not expected_runtimes or not detected_durations:
            return ValidationResult(
                is_valid=True,
                confidence_adjustment=0.0,
                expected_runtimes=expected_runtimes,
                detected_durations=detected_durations,
                message="Insufficient data for comparison"
            )

        # Check if counts match
        if len(expected_runtimes) != len(detected_durations):
            logger.info(
                f"Episode count mismatch: expected {len(expected_runtimes)}, "
                f"detected {len(detected_durations)}"
            )

        # Compare runtimes for matching episodes
        match_count = 0
        total_compared = min(len(expected_runtimes), len(detected_durations))
        deviation_sum = 0.0

        for i in range(total_compared):
            expected = expected_runtimes[i]
            detected = detected_durations[i]

            if expected > 0:
                deviation = abs(detected - expected) / expected

                if deviation <= self.runtime_tolerance:
                    match_count += 1
                    logger.debug(
                        f"Episode {i + 1}: runtime match "
                        f"(expected: {expected}m, detected: {detected:.1f}m)"
                    )
                else:
                    logger.debug(
                        f"Episode {i + 1}: runtime mismatch "
                        f"(expected: {expected}m, detected: {detected:.1f}m, "
                        f"deviation: {deviation:.1%})"
                    )

                deviation_sum += deviation

        # Calculate confidence adjustment
        # Add note about commercial adjustment to messages
        adj_note = " (commercial-adjusted)" if commercial_adjusted else ""

        if total_compared > 0:
            match_ratio = match_count / total_compared
            avg_deviation = deviation_sum / total_compared

            if match_ratio >= 0.8:
                # Good match - boost confidence
                confidence_adjustment = 0.1
                is_valid = True
                message = f"Good runtime match ({match_count}/{total_compared} episodes){adj_note}"
            elif match_ratio >= 0.5:
                # Partial match - small boost
                confidence_adjustment = 0.05
                is_valid = True
                message = f"Partial runtime match ({match_count}/{total_compared} episodes){adj_note}"
            else:
                # Poor match - reduce confidence
                confidence_adjustment = -0.1
                is_valid = False
                message = f"Poor runtime match ({match_count}/{total_compared} episodes){adj_note}"
        else:
            confidence_adjustment = 0.0
            is_valid = True
            message = "No episodes to compare"

        return ValidationResult(
            is_valid=is_valid,
            confidence_adjustment=confidence_adjustment,
            expected_runtimes=expected_runtimes,
            detected_durations=detected_durations,
            message=message
        )

    def get_series_episode_runtimes(
        self,
        title: str,
        season: int,
        start_episode: int = 1,
        num_episodes: int = 10
    ) -> Tuple[List[int], str]:
        """
        Get expected episode runtimes for a series.

        Args:
            title: Series title
            season: Season number
            start_episode: First episode number to fetch (1-indexed)
            num_episodes: Number of episodes to fetch

        Returns:
            Tuple of (list of runtimes in minutes, status message)
        """
        if not self.is_available():
            return [], "TMDB not available"

        logger.debug(f"TMDB lookup: title='{title}', season={season}, start_ep={start_episode}, count={num_episodes}")

        series_id = self._search_series(title)
        if not series_id:
            logger.debug(f"TMDB: Series '{title}' not found")
            return [], f"Series '{title}' not found on TMDB"

        logger.debug(f"TMDB: Found series_id={series_id} for '{title}'")

        episodes = self._get_season_episodes(series_id, season)
        if not episodes:
            logger.debug(f"TMDB: No episodes found for season {season}")
            return [], f"No episodes found for season {season}"

        logger.debug(f"TMDB: Season {season} has {len(episodes)} episodes")

        # Get the specific episodes we need (start_episode is 1-indexed)
        ep_start_idx = start_episode - 1
        ep_end_idx = ep_start_idx + num_episodes

        if ep_start_idx >= len(episodes):
            msg = f"Episodes {start_episode}-{start_episode + num_episodes - 1} not in TMDB (season has {len(episodes)} episodes)"
            logger.debug(f"TMDB: {msg}")
            return [], msg

        requested_episodes = episodes[ep_start_idx:ep_end_idx]
        if len(requested_episodes) < num_episodes:
            available = [ep.episode_number for ep in requested_episodes]
            missing_start = start_episode + len(requested_episodes)
            missing_end = start_episode + num_episodes - 1
            msg = f"Only found episodes {available}, missing E{missing_start}-E{missing_end}"
            logger.debug(f"TMDB: {msg}")

        # Extract runtimes, noting which episodes lack runtime data
        runtimes = []
        missing_runtime = []
        for ep in requested_episodes:
            if ep.runtime:
                runtimes.append(ep.runtime)
                logger.debug(f"TMDB: E{ep.episode_number} '{ep.name}' runtime={ep.runtime}m")
            else:
                runtimes.append(0)  # Placeholder
                missing_runtime.append(ep.episode_number)
                logger.debug(f"TMDB: E{ep.episode_number} '{ep.name}' has no runtime data")

        if missing_runtime:
            msg = f"Episodes {missing_runtime} have no runtime data in TMDB"
            logger.debug(f"TMDB: {msg}")
            # Filter out zero runtimes
            runtimes = [r for r in runtimes if r > 0]
            if not runtimes:
                return [], msg

        return runtimes, f"Found {len(runtimes)} episode runtimes"
