#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Episode splitter using FFmpeg.

Handles the actual extraction of individual episodes from
multi-episode video files using FFmpeg's stream copy.
"""

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple, Callable

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.episode_splitter")


@dataclass
class SplitJob:
    """Represents a single episode extraction job."""
    episode_number: int
    start_time: float       # seconds
    duration: float         # seconds
    input_path: str
    output_path: str
    confidence: float       # detection confidence


@dataclass
class SplitResult:
    """Result of an episode split operation."""
    success: bool
    episode_number: int
    output_path: str
    start_time: float
    duration: float
    file_size: int          # bytes
    error_message: str


class EpisodeSplitter:
    """
    Splits multi-episode files into individual episodes using FFmpeg.

    Uses FFmpeg's stream copy mode (-c copy) for lossless and fast
    extraction. Can optionally re-encode for more accurate cuts.
    """

    def __init__(
        self,
        lossless: bool = True,
        ffmpeg_path: str = "ffmpeg",
    ):
        """
        Initialize the episode splitter.

        Args:
            lossless: Use stream copy (-c copy) for lossless extraction
            ffmpeg_path: Path to FFmpeg executable
        """
        self.lossless = lossless
        self.ffmpeg_path = ffmpeg_path

    def split_episode(
        self,
        job: SplitJob,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> SplitResult:
        """
        Extract a single episode from the source file.

        Args:
            job: SplitJob describing the extraction
            progress_callback: Optional callback for progress updates

        Returns:
            SplitResult with extraction outcome
        """
        logger.info(
            f"Splitting episode {job.episode_number}: "
            f"{job.start_time:.1f}s - {job.start_time + job.duration:.1f}s"
        )

        # Ensure output directory exists
        os.makedirs(os.path.dirname(job.output_path), exist_ok=True)

        # Build FFmpeg command
        cmd = self._build_ffmpeg_command(job)

        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        try:
            # Run FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout per episode
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg failed: {result.stderr}")
                return SplitResult(
                    success=False,
                    episode_number=job.episode_number,
                    output_path=job.output_path,
                    start_time=job.start_time,
                    duration=job.duration,
                    file_size=0,
                    error_message=result.stderr[-500:] if result.stderr else "Unknown error"
                )

            # Verify output file
            if not os.path.exists(job.output_path):
                return SplitResult(
                    success=False,
                    episode_number=job.episode_number,
                    output_path=job.output_path,
                    start_time=job.start_time,
                    duration=job.duration,
                    file_size=0,
                    error_message="Output file not created"
                )

            file_size = os.path.getsize(job.output_path)

            logger.info(
                f"Successfully extracted episode {job.episode_number} "
                f"({file_size / 1024 / 1024:.1f} MB)"
            )

            return SplitResult(
                success=True,
                episode_number=job.episode_number,
                output_path=job.output_path,
                start_time=job.start_time,
                duration=job.duration,
                file_size=file_size,
                error_message=""
            )

        except subprocess.TimeoutExpired:
            logger.error(f"FFmpeg timed out for episode {job.episode_number}")
            return SplitResult(
                success=False,
                episode_number=job.episode_number,
                output_path=job.output_path,
                start_time=job.start_time,
                duration=job.duration,
                file_size=0,
                error_message="FFmpeg timeout"
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return SplitResult(
                success=False,
                episode_number=job.episode_number,
                output_path=job.output_path,
                start_time=job.start_time,
                duration=job.duration,
                file_size=0,
                error_message=str(e)
            )

    def _build_ffmpeg_command(self, job: SplitJob) -> List[str]:
        """
        Build the FFmpeg command for extraction.

        Args:
            job: SplitJob with extraction parameters

        Returns:
            List of command arguments
        """
        cmd = [
            self.ffmpeg_path,
            '-y',  # Overwrite output
            '-ss', str(job.start_time),  # Seek to start (before input for faster seeking)
            '-i', job.input_path,
            '-t', str(job.duration),  # Duration to extract
            '-map', '0',  # Map all streams
        ]

        if self.lossless:
            # Stream copy - fast and lossless but may have slight inaccuracy at cut points
            cmd.extend([
                '-c', 'copy',
                '-avoid_negative_ts', 'make_zero',  # Fix timestamp issues
            ])
        else:
            # Re-encode - slower but accurate cuts
            cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '18',
                '-c:a', 'aac',
                '-b:a', '192k',
            ])

        # Add output path
        cmd.append(job.output_path)

        return cmd

    def split_all(
        self,
        input_path: str,
        output_dir: str,
        split_points: List[Tuple[float, float]],
        naming_func: Callable[[int], str],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[SplitResult]:
        """
        Split a file into multiple episodes.

        Args:
            input_path: Path to the source file
            output_dir: Directory for output files
            split_points: List of (start_time, duration) tuples
            naming_func: Function that takes episode number and returns filename
            progress_callback: Optional callback with (current, total) progress

        Returns:
            List of SplitResult objects
        """
        results = []

        for i, (start_time, duration) in enumerate(split_points):
            episode_num = i + 1
            output_filename = naming_func(episode_num)
            output_path = os.path.join(output_dir, output_filename)

            job = SplitJob(
                episode_number=episode_num,
                start_time=start_time,
                duration=duration,
                input_path=input_path,
                output_path=output_path,
                confidence=1.0  # Confidence not used here
            )

            result = self.split_episode(job)
            results.append(result)

            if progress_callback:
                progress_callback(episode_num, len(split_points))

            # Stop on failure
            if not result.success:
                logger.error(f"Stopping split due to error on episode {episode_num}")
                break

        return results

    def verify_split(
        self,
        result: SplitResult,
        expected_duration_tolerance: float = 0.1
    ) -> bool:
        """
        Verify that a split was successful.

        Args:
            result: SplitResult to verify
            expected_duration_tolerance: Acceptable deviation from expected duration

        Returns:
            True if the split appears valid
        """
        if not result.success:
            return False

        if not os.path.exists(result.output_path):
            logger.error(f"Output file does not exist: {result.output_path}")
            return False

        # Check file size (should be roughly proportional to duration)
        if result.file_size < 1024 * 1024:  # Less than 1MB is suspicious
            logger.warning(f"Output file suspiciously small: {result.file_size} bytes")
            return False

        # Probe the output file to verify duration
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                result.output_path
            ]
            probe_result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if probe_result.returncode == 0:
                import json
                probe_data = json.loads(probe_result.stdout)
                actual_duration = float(probe_data.get('format', {}).get('duration', 0))

                duration_diff = abs(actual_duration - result.duration) / result.duration

                if duration_diff > expected_duration_tolerance:
                    logger.warning(
                        f"Duration mismatch: expected {result.duration:.1f}s, "
                        f"got {actual_duration:.1f}s"
                    )
                    return False

        except Exception as e:
            logger.debug(f"Could not verify output duration: {e}")
            # Don't fail on probe errors - file might still be valid

        return True

    def get_progress_parser(self, total_duration: float) -> Callable[[str], dict]:
        """
        Get a progress parser function for FFmpeg output.

        Args:
            total_duration: Expected total duration of output

        Returns:
            Function that parses FFmpeg output lines and returns progress
        """
        import re

        def parse_progress(line: str) -> dict:
            # Look for time= in FFmpeg output
            time_match = re.search(r'time=(\d+:\d+:\d+\.\d+)', line)
            if time_match:
                time_str = time_match.group(1)
                # Parse time string
                parts = time_str.split(':')
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
                current_time = hours * 3600 + minutes * 60 + seconds

                if total_duration > 0:
                    percent = min(100, int((current_time / total_duration) * 100))
                    return {'percent': str(percent)}

            return {}

        return parse_progress
