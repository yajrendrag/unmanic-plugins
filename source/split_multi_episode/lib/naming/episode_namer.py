#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Episode naming and output filename generation.

Generates appropriate filenames for split episodes based on
source filename parsing and configurable naming patterns.
"""

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.episode_namer")

try:
    import PTN
    PTN_AVAILABLE = True
except ImportError:
    PTN_AVAILABLE = False


@dataclass
class ParsedFilename:
    """Parsed information from a video filename."""
    title: str
    season: Optional[int]
    episode: Optional[int]
    year: Optional[int]
    quality: Optional[str]
    codec: Optional[str]
    source: Optional[str]
    group: Optional[str]
    extension: str
    original_filename: str


class EpisodeNamer:
    """
    Generates output filenames for split episodes.

    Parses the source filename to extract series information
    and generates appropriately named episode files.
    """

    # Default naming pattern
    # Available variables: {title}, {season}, {episode}, {year}, {quality}, {ext}
    DEFAULT_PATTERN = "S{season:02d}E{episode:02d} - {basename}"

    def __init__(
        self,
        naming_pattern: str = None,
        preserve_quality_info: bool = True,
    ):
        """
        Initialize the episode namer.

        Args:
            naming_pattern: Pattern for generating episode filenames
            preserve_quality_info: Include quality/codec info in output names
        """
        self.naming_pattern = naming_pattern or self.DEFAULT_PATTERN
        self.preserve_quality_info = preserve_quality_info

    def parse_filename(self, file_path: str) -> ParsedFilename:
        """
        Parse a video filename to extract series information.

        Args:
            file_path: Path to the video file

        Returns:
            ParsedFilename with extracted information
        """
        basename = os.path.basename(file_path)
        name, ext = os.path.splitext(basename)

        # Try PTN first
        if PTN_AVAILABLE:
            try:
                parsed = PTN.parse(basename)
                # PTN may return a list for episode ranges (e.g., [5, 6, 7, 8] for E5-8)
                episode = parsed.get('episode')
                if isinstance(episode, list):
                    episode = episode[0] if episode else None
                # PTN field mapping:
                # - PTN 'resolution' (480p, 1080p, etc.) -> our 'quality'
                # - PTN 'quality' (WEBRip, BluRay, etc.) -> our 'source'
                # - PTN 'codec' (H.265, x264, etc.) -> our 'codec'
                return ParsedFilename(
                    title=parsed.get('title', name),
                    season=parsed.get('season'),
                    episode=episode,
                    year=parsed.get('year'),
                    quality=parsed.get('resolution'),
                    codec=parsed.get('codec'),
                    source=parsed.get('quality'),  # PTN's 'quality' is WEBRip/BluRay, which is our 'source'
                    group=parsed.get('group'),
                    extension=ext,
                    original_filename=basename
                )
            except Exception as e:
                logger.debug(f"PTN parsing failed: {e}")

        # Fallback regex parsing
        return self._parse_with_regex(name, ext, basename)

    def _parse_with_regex(self, name: str, ext: str, basename: str) -> ParsedFilename:
        """
        Parse filename using regex patterns.

        Handles formats like:
        - "Show Name S01E01" (title before)
        - "S01E01-E03 Show Name" (title after, episode range)
        - "S01E01-03 Show Name" (title after, episode range)
        - "Show Name 1x01" (title before)

        Args:
            name: Filename without extension
            ext: File extension
            basename: Full filename with extension

        Returns:
            ParsedFilename with extracted information
        """
        title = name
        season = None
        episode = None
        year = None
        quality = None
        codec = None
        source = None
        group = None

        # Try patterns in order of specificity

        # Pattern for episode range: S01E01-E03 or S01E01-03 (with title before OR after)
        range_pattern = re.compile(
            r'[Ss](\d+)[Ee](\d+)\s*[-–]\s*[Ee]?(\d+)',
            re.IGNORECASE
        )
        range_match = range_pattern.search(name)

        if range_match:
            season = int(range_match.group(1))
            episode = int(range_match.group(2))  # Start episode

            # Title is typically BEFORE the episode info (S##E##)
            # The content AFTER is usually quality/codec/source metadata
            before = name[:range_match.start()].strip(' ._-')
            after = name[range_match.end():].strip(' ._-')

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

            logger.debug(f"Parsed with range pattern: season={season}, ep={episode}, title='{title}'")
        else:
            # Pattern 2: Standard S01E01 (title before OR after)
            se_pattern = re.compile(r'[Ss](\d+)[Ee](\d+)', re.IGNORECASE)
            se_match = se_pattern.search(name)
            if se_match:
                season = int(se_match.group(1))
                episode = int(se_match.group(2))

                # Title is typically BEFORE the episode info (S##E##)
                # The content AFTER is usually quality/codec/source metadata
                before = name[:se_match.start()].strip(' ._-')
                after = name[se_match.end():].strip(' ._-')

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

                logger.debug(f"Parsed with S##E## pattern: season={season}, ep={episode}, title='{title}'")
            else:
                # Pattern 3: 1x01 format
                x_pattern = re.compile(r'(\d+)[Xx](\d+)')
                x_match = x_pattern.search(name)
                if x_match:
                    season = int(x_match.group(1))
                    episode = int(x_match.group(2))

                    # Title is typically BEFORE the episode info
                    before = name[:x_match.start()].strip(' ._-')
                    after = name[x_match.end():].strip(' ._-')

                    # Prefer the "before" part as the title (standard naming convention)
                    if before and len(before) >= 3:
                        title = before
                    elif after:
                        title = after
                    elif before:
                        title = before

        # Extract year
        year_pattern = re.compile(r'\b(19\d{2}|20\d{2})\b')
        year_match = year_pattern.search(name)
        if year_match:
            year = int(year_match.group(1))

        # Extract quality
        quality_pattern = re.compile(r'\b(2160p|1080p|720p|480p|4K)\b', re.IGNORECASE)
        quality_match = quality_pattern.search(name)
        if quality_match:
            quality = quality_match.group(1)

        # Extract codec
        codec_pattern = re.compile(r'\b(x264|x265|HEVC|H\.?264|H\.?265|AV1)\b', re.IGNORECASE)
        codec_match = codec_pattern.search(name)
        if codec_match:
            codec = codec_match.group(1)

        # Extract source
        source_pattern = re.compile(r'\b(BluRay|BDRip|WEB-DL|WEBRip|HDTV|DVDRip)\b', re.IGNORECASE)
        source_match = source_pattern.search(name)
        if source_match:
            source = source_match.group(1)

        # Clean up title
        title = title.replace('.', ' ').replace('_', ' ').strip()
        title = re.sub(r'\s+', ' ', title)

        return ParsedFilename(
            title=title or name,
            season=season,
            episode=episode,
            year=year,
            quality=quality,
            codec=codec,
            source=source,
            group=group,
            extension=ext,
            original_filename=basename
        )

    def generate_episode_name(
        self,
        parsed: ParsedFilename,
        episode_number: int,
        season_override: Optional[int] = None,
        start_episode_override: Optional[int] = None,
    ) -> str:
        """
        Generate the output filename for a specific episode.

        Args:
            parsed: Parsed source filename
            episode_number: Episode number (1-based) within the split
            season_override: Optional season number override
            start_episode_override: Optional starting episode number

        Returns:
            Generated filename
        """
        season = season_override if season_override is not None else (parsed.season or 1)
        start_ep = start_episode_override if start_episode_override is not None else (parsed.episode or 1)
        episode = start_ep + episode_number - 1

        # Build basename (title with optional quality info)
        basename_parts = [parsed.title]
        if self.preserve_quality_info:
            if parsed.quality:
                basename_parts.append(parsed.quality)
            if parsed.codec:
                basename_parts.append(parsed.codec)
            if parsed.source:
                basename_parts.append(parsed.source)

        basename = ' '.join(basename_parts)

        # Format the naming pattern
        try:
            filename = self.naming_pattern.format(
                title=parsed.title,
                season=season,
                episode=episode,
                year=parsed.year or '',
                quality=parsed.quality or '',
                codec=parsed.codec or '',
                source=parsed.source or '',
                basename=basename,
                ext=parsed.extension.lstrip('.'),
            )
        except KeyError as e:
            logger.warning(f"Invalid naming pattern key: {e}")
            filename = f"S{season:02d}E{episode:02d} - {basename}"

        # Ensure we have the correct extension
        if not filename.endswith(parsed.extension):
            filename += parsed.extension

        # Clean up the filename
        filename = self._sanitize_filename(filename)

        return filename

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a filename by removing or replacing invalid characters.

        Args:
            filename: Filename to sanitize

        Returns:
            Sanitized filename
        """
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '')

        # Replace multiple spaces with single space
        filename = re.sub(r'\s+', ' ', filename)

        # Remove leading/trailing spaces and dots
        filename = filename.strip(' .')

        return filename

    def get_naming_function(
        self,
        source_path: str,
        season_override: Optional[int] = None,
        start_episode_override: Optional[int] = None,
    ):
        """
        Get a naming function for use with the splitter.

        Args:
            source_path: Path to the source video file
            season_override: Optional season number override
            start_episode_override: Optional starting episode number

        Returns:
            Function that takes episode number and returns filename
        """
        parsed = self.parse_filename(source_path)

        def naming_func(episode_number: int) -> str:
            return self.generate_episode_name(
                parsed,
                episode_number,
                season_override,
                start_episode_override
            )

        return naming_func

    def generate_all_names(
        self,
        source_path: str,
        num_episodes: int,
        season_override: Optional[int] = None,
        start_episode_override: Optional[int] = None,
    ) -> List[str]:
        """
        Generate all episode filenames for a split operation.

        Args:
            source_path: Path to the source video file
            num_episodes: Number of episodes to generate names for
            season_override: Optional season number override
            start_episode_override: Optional starting episode number

        Returns:
            List of generated filenames
        """
        parsed = self.parse_filename(source_path)
        names = []

        for i in range(num_episodes):
            name = self.generate_episode_name(
                parsed,
                i + 1,
                season_override,
                start_episode_override
            )
            names.append(name)

        return names

    def detect_episode_range(self, file_path: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Detect if the filename indicates a range of episodes.

        For example: "Show S01E01-E03" indicates episodes 1-3.

        Args:
            file_path: Path to the video file

        Returns:
            Tuple of (start_episode, end_episode) or (None, None)
        """
        basename = os.path.basename(file_path)

        # Pattern: S01E01-E03 or S01E01-03
        range_pattern = re.compile(
            r'[Ss](\d+)[Ee](\d+)\s*[-–]\s*[Ee]?(\d+)',
            re.IGNORECASE
        )
        match = range_pattern.search(basename)

        if match:
            start_ep = int(match.group(2))
            end_ep = int(match.group(3))
            return (start_ep, end_ep)

        return (None, None)
