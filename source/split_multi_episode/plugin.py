#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     18 January 2026, (00:38 AM)

    Copyright:
        Copyright (C) 2026 Jay Gardner

        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

"""

import json
import logging
import os
import time

from unmanic.libs.unplugins.settings import PluginSettings
from unmanic.libs.directoryinfo import UnmanicDirectoryInfo

from split_multi_episode.lib.ffmpeg import Probe, Parser
from split_multi_episode.lib.detection import (
    ChapterDetector,
    SilenceDetector,
    BlackFrameDetector,
    ImageHashDetector,
    AudioFingerprintDetector,
    LLMDetector,
    BoundaryMerger,
    SearchWindowDeterminer,
    SceneChangeDetector,
    SpeechDetector,
    SearchWindow,
)
from split_multi_episode.lib.validation import TMDBValidator
from split_multi_episode.lib.splitter import EpisodeSplitter
from split_multi_episode.lib.naming import EpisodeNamer
from split_multi_episode.lib.progress import ProgressTracker, run_detection_in_child_process
from split_multi_episode.lib.detection_runner import run_phase2_detection

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.split_multi_episode")


class Settings(PluginSettings):
    settings = {
        # Detection Methods - grouped with their sub-options

        # Chapter Detection
        "enable_chapter_detection": True,

        # Silence Detection + options
        "enable_silence_detection": True,
        "silence_threshold_db": -30,
        "silence_min_duration": 2.0,

        # Black Frame Detection + options
        "enable_black_frame_detection": True,
        "black_min_duration": 1.0,

        # Scene Change Detection + options
        "enable_scene_change_detection": False,
        "scene_change_threshold": 0.3,

        # Image Hash Detection
        "enable_image_hash_detection": False,

        # Audio Fingerprint Detection
        "enable_audio_fingerprint_detection": False,

        # LLM Vision Detection + options
        "enable_llm_detection": False,
        "llm_ollama_host": "http://localhost:11434",
        "llm_model": "qwen2.5vl:3b",
        "llm_precision_mode": False,
        "llm_precision_symmetric_windows": False,
        "llm_post_credits_buffer": 15,
        "llm_precision_pattern": "",
        "llm_pattern_grouping_buffer": 10,

        # Speech Detection + options
        "enable_speech_detection": False,
        "speech_model_size": "base",

        # TMDB Validation + options
        "enable_tmdb_validation": False,
        "tmdb_api_key": "",
        "tmdb_api_read_access_token": "",

        # Duration Constraints
        "min_episode_length_minutes": 15,
        "max_episode_length_minutes": 90,
        "min_file_duration_minutes": 30,

        # Output Settings
        "output_naming_pattern": "S{season:02d}E{episode:02d} - {basename}",
        "copy_streams_lossless": True,
        "create_season_directory": False,
        "season_directory_pattern": "Season {season:02d}",
        "delete_source_after_split": False,
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)

        self.form_settings = {
            # Detection Methods - grouped with their sub-options

            # Chapter Detection
            "enable_chapter_detection": {
                "label": "Enable Chapter Detection",
                "description": "Use chapter markers to detect episode boundaries (highest reliability)",
            },

            # Silence Detection + options
            "enable_silence_detection": {
                "label": "Enable Silence Detection",
                "description": "Detect silence gaps between episodes",
            },
            "silence_threshold_db": self._silence_threshold_setting(),
            "silence_min_duration": self._detection_setting(
                "enable_silence_detection",
                "Minimum Silence Duration (seconds)",
                "Minimum silence duration to detect"
            ),

            # Black Frame Detection + options
            "enable_black_frame_detection": {
                "label": "Enable Black Frame Detection",
                "description": "Detect black frames that may indicate episode breaks",
            },
            "black_min_duration": self._detection_setting(
                "enable_black_frame_detection",
                "Minimum Black Duration (seconds)",
                "Minimum black frame duration to detect"
            ),

            # Scene Change Detection + options
            "enable_scene_change_detection": {
                "label": "Enable Scene Change Detection",
                "description": "Detect dramatic visual transitions between episodes using FFmpeg scene detection",
            },
            "scene_change_threshold": self._scene_threshold_setting(),

            # Image Hash Detection
            "enable_image_hash_detection": {
                "label": "Enable Image Hash Detection",
                "description": "Use perceptual hashing to find recurring intro/outro sequences (CPU intensive)",
            },

            # Audio Fingerprint Detection
            "enable_audio_fingerprint_detection": {
                "label": "Enable Audio Fingerprint Detection",
                "description": "Detect recurring intro music patterns",
            },

            # LLM Vision Detection + options
            "enable_llm_detection": {
                "label": "Enable LLM Vision Detection",
                "description": "Use Ollama vision model to detect credits, title cards (requires Ollama)",
            },
            "llm_ollama_host": self._llm_setting("Ollama Host", "URL of Ollama API endpoint"),
            "llm_model": self._llm_setting("LLM Model", "Vision model to use (e.g., qwen2.5vl:3b)"),
            "llm_precision_mode": self._llm_precision_mode_setting(),
            "llm_precision_symmetric_windows": self._llm_symmetric_windows_setting(),
            "llm_post_credits_buffer": self._llm_post_credits_buffer_setting(),
            "llm_precision_pattern": self._llm_precision_pattern_setting(),
            "llm_pattern_grouping_buffer": self._llm_pattern_grouping_buffer_setting(),

            # Speech Detection + options
            "enable_speech_detection": {
                "label": "Enable Speech Detection",
                "description": "Use Whisper to detect 'Stay tuned' and other preview phrases (requires faster-whisper)",
            },
            "speech_model_size": self._speech_setting(),

            # TMDB Validation + options
            "enable_tmdb_validation": {
                "label": "Enable TMDB Validation",
                "description": "Validate detected runtimes against TMDB episode data",
            },
            "tmdb_api_key": self._tmdb_setting("TMDB API Key", "API key for TMDB validation"),
            "tmdb_api_read_access_token": self._tmdb_setting(
                "TMDB API Read Access Token",
                "API read access token for TMDB (v4 auth)"
            ),

            # Duration Constraints
            "min_episode_length_minutes": {
                "label": "Minimum Episode Length (minutes)",
                "description": "Episodes shorter than this will be merged or ignored",
                "input_type": "slider",
                "slider_options": {"min": 5, "max": 60, "step": 5},
            },
            "max_episode_length_minutes": {
                "label": "Maximum Episode Length (minutes)",
                "description": "Episodes longer than this will trigger warnings",
                "input_type": "slider",
                "slider_options": {"min": 30, "max": 180, "step": 10},
            },
            "min_file_duration_minutes": {
                "label": "Minimum File Duration (minutes)",
                "description": "Only process files longer than this (suggests 2+ episodes)",
                "input_type": "slider",
                "slider_options": {"min": 15, "max": 120, "step": 5},
            },

            # Output Settings
            "output_naming_pattern": {
                "label": "Output Naming Pattern",
                "description": "Pattern for episode filenames. Variables: {title}, {season}, {episode}, {basename}, {ext}",
            },
            "copy_streams_lossless": {
                "label": "Lossless Stream Copy",
                "description": "Use FFmpeg stream copy (-c copy) for fast lossless extraction",
            },
            "create_season_directory": {
                "label": "Create Season Directory",
                "description": "Create a season subdirectory (e.g., 'Season 01') in the source directory for split episodes. If disabled, episodes are placed in the same directory as the source file.",
            },
            "season_directory_pattern": {
                "label": "Season Directory Pattern",
                "description": "Pattern for season directory name. Variables: {season}, {title}",
            },
            "delete_source_after_split": {
                "label": "Delete Source After Split",
                "description": "Delete the multi-episode source file after successfully splitting into individual episodes. WARNING: This is destructive and cannot be undone!",
            },
        }

    def _silence_threshold_setting(self):
        setting = {
            "label": "Silence Threshold (dB)",
            "description": "Audio level threshold for silence detection",
            "input_type": "slider",
            "slider_options": {"min": -60, "max": -10, "step": 5},
            "sub_setting": True,
        }
        if not self.get_setting('enable_silence_detection'):
            setting["display"] = "hidden"
        return setting

    def _llm_setting(self, label, description, input_type="text", extra=None):
        setting = {
            "label": label,
            "description": description,
            "sub_setting": True,
        }
        if input_type != "text":
            setting["input_type"] = input_type
        if extra:
            setting.update(extra)
        if not self.get_setting('enable_llm_detection'):
            setting["display"] = "hidden"
        return setting

    def _llm_precision_mode_setting(self):
        setting = {
            "label": "LLM Precision Mode",
            "description": "Use narrow windows with 2-second sampling for logo-focused detection. "
                          "Requires TMDB for window positioning. Best for clean files without commercials. "
                          "Disables all other detectors when enabled.",
            "sub_setting": True,
        }
        # Only show if both LLM and TMDB are enabled
        if not self.get_setting('enable_llm_detection') or not self.get_setting('enable_tmdb_validation'):
            setting["display"] = "hidden"
        return setting

    def _llm_symmetric_windows_setting(self):
        setting = {
            "label": "Use Symmetric Windows",
            "description": "Use symmetric windows (±2m) instead of asymmetric (-3m/+1m). "
                          "Asymmetric is better when episodes are typically shorter than TMDB predicts. "
                          "Symmetric is better when TMDB timing is accurate.",
            "sub_setting": True,
        }
        # Only show if LLM precision mode is enabled
        if not self.get_setting('enable_llm_detection') or not self.get_setting('llm_precision_mode'):
            setting["display"] = "hidden"
        return setting

    def _llm_post_credits_buffer_setting(self):
        setting = {
            "label": "Post-Credits Buffer (seconds)",
            "description": "How long after credits end to look for logos/bumpers that are part of the episode. "
                          "Increase for shows with longer end sequences (previews, 'next time on', network logos). "
                          "Ignored if Pattern is specified.",
            "input_type": "slider",
            "slider_options": {"min": 5, "max": 60, "step": 5},
            "sub_setting": True,
        }
        # Only show if LLM precision mode is enabled and no pattern specified
        if not self.get_setting('enable_llm_detection') or not self.get_setting('llm_precision_mode'):
            setting["display"] = "hidden"
        elif self.get_setting('llm_precision_pattern'):
            setting["display"] = "hidden"
        return setting

    def _llm_precision_pattern_setting(self):
        setting = {
            "label": "Boundary Pattern",
            "description": "Specify a pattern to match at episode boundaries. "
                          "Codes: c=credits, l=logo, s=split point. "
                          "Only elements in the pattern are considered (others ignored). "
                          "Example: l-l-s (split after 2nd logo, ignoring credits). "
                          "Leave empty to use Post-Credits Buffer instead.",
            "sub_setting": True,
        }
        # Only show if LLM precision mode is enabled
        if not self.get_setting('enable_llm_detection') or not self.get_setting('llm_precision_mode'):
            setting["display"] = "hidden"
        return setting

    def _llm_pattern_grouping_buffer_setting(self):
        setting = {
            "label": "Minimum Gap Threshold (seconds)",
            "description": "Minimum gap between detections to consider a natural break between blocks. "
                          "Gaps smaller than this are ignored (detections stay in same block). "
                          "Default 10s works well with 2-second sampling (6s frame gaps don't split blocks).",
            "input_type": "slider",
            "slider_options": {"min": 5, "max": 30, "step": 1},
            "sub_setting": True,
        }
        # Only show if LLM precision mode is enabled and pattern is set
        if not self.get_setting('enable_llm_detection') or not self.get_setting('llm_precision_mode'):
            setting["display"] = "hidden"
        return setting

    def _tmdb_setting(self, label, description):
        setting = {
            "label": label,
            "description": description,
            "input_type": "textarea",
            "sub_setting": True,
        }
        if not self.get_setting('enable_tmdb_validation'):
            setting["display"] = "hidden"
        return setting

    def _detection_setting(self, parent_setting, label, description):
        setting = {
            "label": label,
            "description": description,
            "sub_setting": True,
        }
        if not self.get_setting(parent_setting):
            setting["display"] = "hidden"
        return setting

    def _scene_threshold_setting(self):
        setting = {
            "label": "Scene Change Threshold",
            "description": "Minimum scene change score to detect (0.1-0.5, lower = more sensitive)",
            "input_type": "slider",
            "slider_options": {"min": 0.1, "max": 0.5, "step": 0.05},
            "sub_setting": True,
        }
        if not self.get_setting('enable_scene_change_detection'):
            setting["display"] = "hidden"
        return setting

    def _speech_setting(self):
        setting = {
            "label": "Whisper Model Size",
            "description": "Model size for speech detection (tiny=fastest, large-v2=most accurate)",
            "input_type": "select",
            "select_options": [
                {"value": "tiny", "label": "Tiny (fastest, least accurate)"},
                {"value": "base", "label": "Base (balanced)"},
                {"value": "small", "label": "Small (better accuracy)"},
                {"value": "medium", "label": "Medium (good accuracy)"},
                {"value": "large-v2", "label": "Large-v2 (best accuracy, slowest)"},
            ],
            "sub_setting": True,
        }
        if not self.get_setting('enable_speech_detection'):
            setting["display"] = "hidden"
        return setting

def file_already_processed(path):
    """Check if this file has already been processed."""
    try:
        directory_info = UnmanicDirectoryInfo(os.path.dirname(path))
        result = directory_info.get('split_multi_episode', os.path.basename(path))
        if result:
            logger.debug(f"File previously processed: {result}")
            return True
    except Exception as e:
        logger.debug(f"Error checking processed status: {e}")
    return False


def mark_file_processed(path, episode_count):
    """Mark a file as having been processed."""
    try:
        directory_info = UnmanicDirectoryInfo(os.path.dirname(path))
        directory_info.set(
            'split_multi_episode',
            os.path.basename(path),
            f"split_{episode_count}_episodes"
        )
        directory_info.save()
        logger.info(f"Marked file as processed: {path}")
    except Exception as e:
        logger.error(f"Error marking file as processed: {e}")


def on_library_management_file_test(data):
    """
    Runner function - tests files to determine if they should be processed.

    Checks:
    - File duration (must be >= min_file_duration_minutes)
    - Quick chapter check for multi-episode indicators
    - Not already processed
    """
    # Configure settings
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    abspath = data.get('path')

    # Check if already processed
    if file_already_processed(abspath):
        logger.debug(f"File already processed: {abspath}")
        return data

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])

    # Check for existing probe in shared_info
    if 'ffprobe' in data.get('shared_info', {}):
        if not probe.set_probe(data.get('shared_info', {}).get('ffprobe')):
            return data
    elif not probe.file(abspath):
        return data

    # Store probe in shared_info for other plugins
    if 'shared_info' not in data:
        data['shared_info'] = {}
    data['shared_info']['ffprobe'] = probe.get_probe()

    # Get duration
    probe_data = probe.get_probe()
    duration = float(probe_data.get('format', {}).get('duration', 0))
    min_duration = settings.get_setting('min_file_duration_minutes') * 60

    if duration < min_duration:
        logger.debug(f"File too short ({duration/60:.1f} min < {min_duration/60:.1f} min): {abspath}")
        return data

    # Quick chapter check if enabled
    if settings.get_setting('enable_chapter_detection'):
        min_ep_length = settings.get_setting('min_episode_length_minutes') * 60
        max_ep_length = settings.get_setting('max_episode_length_minutes') * 60

        chapter_detector = ChapterDetector(
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )

        if chapter_detector.has_multi_episode_chapters(probe_data):
            logger.info(f"File appears to contain multiple episodes (chapters): {abspath}")
            data['add_file_to_pending_tasks'] = True
            return data

    # Check if duration suggests multiple episodes
    max_ep_length = settings.get_setting('max_episode_length_minutes') * 60
    if duration >= max_ep_length * 1.5:  # 1.5x max episode length
        logger.info(f"File duration ({duration/60:.1f} min) suggests multiple episodes: {abspath}")
        data['add_file_to_pending_tasks'] = True

    return data


def on_worker_process(data):
    """
    Runner function - performs the analysis and splitting.

    Uses a two-phase approach via repeat=True:
    - Phase 1: Run detection pipeline, store results in TaskDataStore
    - Phase 2+: Extract episodes one at a time
    """
    from unmanic.libs.task import TaskDataStore

    # Default to no command
    data['exec_command'] = []
    data['repeat'] = False

    # Configure settings
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    file_in = data.get('file_in')
    original_file_path = data.get('original_file_path')
    worker_log = data.get('worker_log', [])

    # Check if already processed
    if file_already_processed(original_file_path):
        worker_log.append("File already processed, skipping")
        data['worker_log'] = worker_log
        return data

    # Check task state for phase
    task_state = TaskDataStore.get_task_state('split_multi_episode_state')

    if task_state is None:
        # Phase 1: Analysis
        return _run_analysis_phase(data, settings, file_in, worker_log)
    else:
        # Phase 2+: Splitting
        return _run_splitting_phase(data, settings, file_in, original_file_path, worker_log, task_state)


def _run_analysis_phase(data, settings, file_in, worker_log):
    """
    Run the two-phase detection pipeline and store results.

    Phase 1: Determine search windows
    - Use chapter info, TMDB runtimes, filename episode count, total duration
    - Create narrow search windows for each expected boundary

    Phase 2: Find exact boundaries within windows
    - Run silence, black frame, etc. detectors within those windows
    - Combine results per window to find the best boundary
    """
    from unmanic.libs.task import TaskDataStore

    worker_log.append("Starting multi-episode detection analysis (two-phase)...")

    # Probe the file
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(file_in):
        worker_log.append("Failed to probe file")
        data['worker_log'] = worker_log
        return data

    probe_data = probe.get_probe()
    total_duration = float(probe_data.get('format', {}).get('duration', 0))

    # Get settings
    min_ep_length = settings.get_setting('min_episode_length_minutes') * 60
    max_ep_length = settings.get_setting('max_episode_length_minutes') * 60

    # Extract expected episode count from filename (e.g., "S2E5-8" = 4 episodes)
    namer = EpisodeNamer()
    start_ep, end_ep = namer.detect_episode_range(file_in)
    expected_episode_count = None
    if start_ep is not None and end_ep is not None:
        expected_episode_count = end_ep - start_ep + 1
        worker_log.append(f"Filename indicates {expected_episode_count} episodes (E{start_ep}-E{end_ep})")
    else:
        worker_log.append("Could not determine episode count from filename")
        data['worker_log'] = worker_log
        return data

    # ========== PHASE 1: Determine Search Windows ==========
    worker_log.append("Phase 1: Determining search windows...")

    # Get TMDB runtimes if enabled
    expected_runtimes = None
    if settings.get_setting('enable_tmdb_validation'):
        tmdb_validator = TMDBValidator(
            api_key=settings.get_setting('tmdb_api_key'),
            api_read_access_token=settings.get_setting('tmdb_api_read_access_token')
        )
        if tmdb_validator.is_available():
            parsed_info = namer.parse_filename(file_in)
            worker_log.append(f"  Parsed title: '{parsed_info.title}', season: {parsed_info.season}, episode: {parsed_info.episode}")
            if parsed_info.title:
                runtimes, tmdb_message = tmdb_validator.get_series_episode_runtimes(
                    parsed_info.title,
                    parsed_info.season or 1,
                    start_episode=start_ep or 1,
                    num_episodes=expected_episode_count or 10
                )
                if runtimes:
                    expected_runtimes = runtimes
                    worker_log.append(f"  TMDB runtimes: {expected_runtimes} minutes")
                else:
                    worker_log.append(f"  TMDB: {tmdb_message}")
            else:
                worker_log.append("  TMDB: Could not parse title from filename")

    # Get chapter information if enabled
    chapter_boundaries = None
    chapter_info = {}
    commercial_times_per_episode = None
    if settings.get_setting('enable_chapter_detection'):
        worker_log.append("  Analyzing chapters...")
        chapter_detector = ChapterDetector(
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        boundaries = chapter_detector.detect(probe_data)
        if boundaries:
            if boundaries[0].source == 'chapter_commercial':
                # Commercial markers - extract commercial times per episode
                # Note: We DON'T set chapter_boundaries here because commercial markers
                # indicate where commercials start, not where episode content ends.
                # Commercial times are only useful when combined with TMDB runtimes.
                chapter_info['commercial_1_times'] = [b.end_time for b in boundaries[:-1]]
                worker_log.append(f"    Found commercial markers for {len(boundaries)} episode regions")

                # Get commercial times per episode for accurate window calculation
                commercial_times_per_episode = chapter_detector.get_commercial_times_per_episode(probe_data)
                if commercial_times_per_episode:
                    worker_log.append(f"    Commercial times per episode: {[f'{t/60:.1f}m' for t in commercial_times_per_episode]}")
            else:
                # True episode chapters - use directly as boundaries
                chapter_boundaries = [(b.start_time, b.end_time) for b in boundaries]
                worker_log.append(f"    Found true episode chapters: {len(boundaries)} episodes")

    # Create search window determiner
    window_determiner = SearchWindowDeterminer(
        total_duration=total_duration,
        expected_episode_count=expected_episode_count,
        min_episode_length=min_ep_length,
        max_episode_length=max_ep_length,
        window_size=300,  # 5 minutes on each side
    )

    # Determine search windows
    search_windows = window_determiner.determine_windows(
        chapter_boundaries=chapter_boundaries,
        tmdb_runtimes=expected_runtimes,
        commercial_times_per_episode=commercial_times_per_episode,
    )

    # Refine windows with commercial chapter info if available
    # Skip if:
    # - We already used TMDB+chapters (commercial times already incorporated)
    # - We don't have TMDB runtimes (commercial markers alone don't help position windows)
    if (chapter_info.get('commercial_1_times') and search_windows and expected_runtimes):
        if not any('tmdb+chapters' in w.source for w in search_windows):
            search_windows = window_determiner.refine_windows_with_chapters(
                search_windows, chapter_info
            )

    if not search_windows:
        worker_log.append("Could not determine search windows")
        data['worker_log'] = worker_log
        return data

    # Check for LLM Precision Mode
    llm_precision_mode = (
        settings.get_setting('llm_precision_mode') and
        settings.get_setting('enable_llm_detection') and
        settings.get_setting('enable_tmdb_validation') and
        expected_runtimes
    )

    if llm_precision_mode:
        # Override search windows with precision windows based on TMDB
        # Asymmetric: -3m/+1m (4m total) - for episodes typically shorter than TMDB predicts
        # Symmetric: ±2m (4m total) - for accurate TMDB timing
        use_symmetric = settings.get_setting('llm_precision_symmetric_windows')

        if use_symmetric:
            PRECISION_WINDOW_BACKWARD = 120  # 2 minutes before predicted boundary
            PRECISION_WINDOW_FORWARD = 120   # 2 minutes after predicted boundary
            window_desc = "symmetric (±2m)"
        else:
            PRECISION_WINDOW_BACKWARD = 180  # 3 minutes before predicted boundary
            PRECISION_WINDOW_FORWARD = 60    # 1 minute after predicted boundary
            window_desc = "asymmetric (-3m/+1m)"

        precision_windows = []
        cumulative_runtime = 0

        for i, runtime in enumerate(expected_runtimes[:-1]):  # Don't need window after last episode
            cumulative_runtime += runtime * 60  # Convert to seconds
            center = cumulative_runtime
            precision_windows.append(SearchWindow(
                start_time=center - PRECISION_WINDOW_BACKWARD,
                end_time=center + PRECISION_WINDOW_FORWARD,
                center_time=center,
                confidence=0.8,
                source='tmdb_precision',
                episode_before=i + 1,
                episode_after=i + 2,
                metadata={},
            ))

        search_windows = precision_windows
        worker_log.append(f"  LLM Precision Mode: Created {len(search_windows)} {window_desc} windows:")
    else:
        worker_log.append(f"  Created {len(search_windows)} search windows:")

    for i, w in enumerate(search_windows):
        worker_log.append(
            f"    Window {i+1}: {w.start_time/60:.1f}-{w.end_time/60:.1f}m "
            f"(center: {w.center_time/60:.1f}m, source: {w.source})"
        )

    # ========== PHASE 2: Find Exact Boundaries Within Windows ==========
    worker_log.append("Phase 2: Finding boundaries within windows...")

    # Prepare args for detection runner (must be JSON-serializable)
    detection_args = {
        'file_path': file_in,
        'total_duration': total_duration,
        'search_windows': [
            {
                'start_time': w.start_time,
                'end_time': w.end_time,
                'center_time': w.center_time,
                'confidence': w.confidence,
                'source': w.source,
                'episode_before': w.episode_before,
                'episode_after': w.episode_after,
                'metadata': w.metadata,
            }
            for w in search_windows
        ],
        'settings': {
            'enable_silence_detection': settings.get_setting('enable_silence_detection'),
            'enable_black_frame_detection': settings.get_setting('enable_black_frame_detection'),
            'enable_scene_change_detection': settings.get_setting('enable_scene_change_detection'),
            'enable_image_hash_detection': settings.get_setting('enable_image_hash_detection'),
            'enable_audio_fingerprint_detection': settings.get_setting('enable_audio_fingerprint_detection'),
            'enable_llm_detection': settings.get_setting('enable_llm_detection'),
            'enable_speech_detection': settings.get_setting('enable_speech_detection'),
            'llm_precision_mode': llm_precision_mode,
            'llm_post_credits_buffer': settings.get_setting('llm_post_credits_buffer'),
            'llm_precision_pattern': settings.get_setting('llm_precision_pattern'),
            'silence_threshold_db': settings.get_setting('silence_threshold_db'),
            'silence_min_duration': settings.get_setting('silence_min_duration'),
            'black_min_duration': settings.get_setting('black_min_duration'),
            'scene_change_threshold': settings.get_setting('scene_change_threshold'),
            'llm_ollama_host': settings.get_setting('llm_ollama_host'),
            'llm_model': settings.get_setting('llm_model'),
            'speech_model_size': settings.get_setting('speech_model_size'),
            'min_episode_length': min_ep_length,
            'max_episode_length': max_ep_length,
        },
    }

    # Run detection in child process with GUI progress reporting
    detection_result = run_detection_in_child_process(
        data=data,
        detection_func=run_phase2_detection,
        detection_args=detection_args,
    )

    if detection_result is None:
        worker_log.append("Detection failed - falling back to window centers")
        window_boundaries = {i: [w.center_time, 0.3, {'fallback': True}]
                            for i, w in enumerate(search_windows)}
    else:
        # Unpack results from raw clustering (convert string keys back to int)
        window_boundaries = {
            int(k): v for k, v in detection_result.get('window_boundaries', {}).items()
        }
        raw_detection_count = len(detection_result.get('all_raw_detections', []))
        worker_log.append(f"  Clustered {raw_detection_count} raw detections")

    # ========== Use Clustered Results Per Window ==========
    worker_log.append("Using clustered results per window...")

    # Check for any failed windows first
    failed_windows = []
    for i, window in enumerate(search_windows):
        result = window_boundaries.get(i)
        if result and result[2].get('failed'):
            failed_windows.append(i + 1)
            error_msg = result[2].get('error', 'Detection failed')
            worker_log.append(f"  Window {i+1}: FAILED - {error_msg}")

    if failed_windows:
        worker_log.append(
            f"ERROR: Detection failed for window(s) {failed_windows}. "
            f"Cannot reliably split file - aborting."
        )
        data['worker_log'] = worker_log
        return data

    final_boundaries = []
    prev_end = 0.0

    for i, window in enumerate(search_windows):
        result = window_boundaries.get(i)

        if not result or result[2].get('fallback'):
            # No detections - use window center
            boundary_time = window.center_time
            confidence = 0.3
            worker_log.append(f"  Window {i+1}: no detections, using center {boundary_time/60:.1f}m")
        else:
            boundary_time, confidence, metadata = result
            sources = metadata.get('sources', ['unknown'])
            num_detectors = metadata.get('num_detectors', 1)
            cluster_score = metadata.get('cluster_score', 0)
            from_expansion = ' (from expansion)' if metadata.get('from_expansion') else ''

            worker_log.append(
                f"  Window {i+1}: boundary at {boundary_time/60:.1f}m "
                f"(conf={confidence:.2f}, {num_detectors} detector(s): {sources}, "
                f"cluster_score={cluster_score:.1f}){from_expansion}"
            )

        # Create episode boundary
        from split_multi_episode.lib.detection.boundary_merger import MergedBoundary
        sources = result[2].get('sources', ['fallback']) if result else ['fallback']
        final_boundaries.append(MergedBoundary(
            start_time=prev_end,
            end_time=boundary_time,
            confidence=confidence,
            sources=sources,
            source_boundaries=[],
            metadata={'window_index': i, 'window_source': window.source}
        ))
        prev_end = boundary_time

    # Add final episode
    if total_duration - prev_end >= min_ep_length * 0.5:
        final_boundaries.append(MergedBoundary(
            start_time=prev_end,
            end_time=total_duration,
            confidence=final_boundaries[-1].confidence if final_boundaries else 0.5,
            sources=['final'],
            source_boundaries=[],
            metadata={'final_episode': True}
        ))

    merged_boundaries = final_boundaries
    worker_log.append(f"Detected {len(merged_boundaries)} episodes")

    if len(merged_boundaries) < 2:
        worker_log.append("Not enough episodes detected for splitting")
        data['worker_log'] = worker_log
        return data

    worker_log.append(f"Detected {len(merged_boundaries)} episodes")

    # TMDB validation - use same parsed info as Phase 1 for consistency
    if settings.get_setting('enable_tmdb_validation'):
        worker_log.append("Validating against TMDB...")
        tmdb_validator = TMDBValidator(
            api_key=settings.get_setting('tmdb_api_key'),
            api_read_access_token=settings.get_setting('tmdb_api_read_access_token')
        )
        if tmdb_validator.is_available():
            durations = [b.end_time - b.start_time for b in merged_boundaries]
            # Use the already-parsed info for consistent title parsing
            parsed_info = namer.parse_filename(file_in)
            result = tmdb_validator.validate(
                file_in,
                durations,
                title_override=parsed_info.title,
                season_override=parsed_info.season or 1,
                start_episode_override=start_ep or 1,
                commercial_times=commercial_times_per_episode,
            )
            worker_log.append(f"  TMDB: {result.message}")
            # Apply confidence adjustments would go here
        else:
            worker_log.append("  TMDB validation unavailable (no API key)")

    # Convert to split points using BoundaryMerger helper methods
    merger = BoundaryMerger()
    split_points = merger.get_split_points(merged_boundaries)
    episode_list = merger.to_episode_list(merged_boundaries)

    # Parse filename for season info (used for output directory)
    namer = EpisodeNamer()
    parsed_info = namer.parse_filename(file_in)

    # Store state for splitting phase
    state = {
        'split_points': split_points,
        'episode_list': episode_list,
        'total_episodes': len(split_points),
        'current_episode': 0,
        'extracted_files': [],
        'parsed_info': {
            'title': parsed_info.title,
            'season': parsed_info.season or 1,
            'episode': parsed_info.episode or 1,
        },
    }
    TaskDataStore.set_task_state('split_multi_episode_state', state)

    # Continue to splitting phase
    data['repeat'] = True
    data['worker_log'] = worker_log
    return data


def _run_splitting_phase(data, settings, file_in, original_file_path, worker_log, task_state):
    """Extract episodes one at a time."""
    from unmanic.libs.task import TaskDataStore

    split_points = task_state['split_points']
    total_episodes = task_state['total_episodes']
    current_episode = task_state['current_episode']
    extracted_files = task_state['extracted_files']
    parsed_info = task_state.get('parsed_info', {})

    # Check if we're done
    if current_episode >= total_episodes:
        worker_log.append(f"All {total_episodes} episodes extracted successfully!")
        worker_log.append(f"Output files: {extracted_files}")

        # Mark as processed (used by postprocessor to detect successful splits)
        mark_file_processed(original_file_path, total_episodes)

        # Delete source file if enabled
        if settings.get_setting('delete_source_after_split'):
            try:
                if os.path.exists(original_file_path):
                    os.remove(original_file_path)
                    worker_log.append(f"Deleted source file: {original_file_path}")
                    logger.info(f"Deleted multi-episode source: {original_file_path}")
            except Exception as e:
                worker_log.append(f"WARNING: Failed to delete source file: {e}")
                logger.error(f"Failed to delete source file {original_file_path}: {e}")

        data['worker_log'] = worker_log
        return data

    # Extract current episode
    start_time, duration = split_points[current_episode]
    episode_num = current_episode + 1

    worker_log.append(f"Extracting episode {episode_num}/{total_episodes}...")
    worker_log.append(f"  Start: {start_time:.1f}s, Duration: {duration:.1f}s")

    # Set up naming
    namer = EpisodeNamer(
        naming_pattern=settings.get_setting('output_naming_pattern'),
        preserve_quality_info=True
    )
    naming_func = namer.get_naming_function(original_file_path)
    output_filename = naming_func(episode_num)

    # Determine output directory
    source_dir = os.path.dirname(original_file_path)

    if settings.get_setting('create_season_directory'):
        # Create season subdirectory
        season_pattern = settings.get_setting('season_directory_pattern')
        season_num = parsed_info.get('season', 1)
        title = parsed_info.get('title', '')

        try:
            season_dir_name = season_pattern.format(
                season=season_num,
                title=title
            )
        except KeyError:
            # Fallback if pattern has invalid variables
            season_dir_name = f"Season {season_num:02d}"

        output_dir = os.path.join(source_dir, season_dir_name)

        # Create directory if it doesn't exist (only on first episode)
        if current_episode == 0 and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
                worker_log.append(f"Created season directory: {output_dir}")
                logger.info(f"Created season directory: {output_dir}")
            except Exception as e:
                worker_log.append(f"WARNING: Failed to create season directory, using source directory: {e}")
                logger.warning(f"Failed to create season directory {output_dir}: {e}")
                output_dir = source_dir
    else:
        # Use same directory as source file
        output_dir = source_dir

    output_path = os.path.join(output_dir, output_filename)

    # Build FFmpeg command
    lossless = settings.get_setting('copy_streams_lossless')

    ffmpeg_args = [
        '-y',
        '-ss', str(start_time),
        '-i', file_in,
        '-t', str(duration),
        '-map', '0',
    ]

    if lossless:
        ffmpeg_args.extend([
            '-c', 'copy',
            '-avoid_negative_ts', 'make_zero',
        ])
    else:
        ffmpeg_args.extend([
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '18',
            '-c:a', 'aac',
            '-b:a', '192k',
        ])

    ffmpeg_args.append(output_path)

    # Set command
    data['exec_command'] = ['ffmpeg'] + ffmpeg_args

    # Set progress parser
    probe = Probe(logger, allowed_mimetypes=['video'])
    if probe.file(file_in):
        parser = Parser(logger)
        parser.duration = duration
        if probe.get('streams'):
            try:
                parser.set_probe(probe)
            except Exception:
                pass
        data['command_progress_parser'] = parser.parse_progress

    # Update state for next iteration
    task_state['current_episode'] = current_episode + 1
    task_state['extracted_files'].append(output_path)
    TaskDataStore.set_task_state('split_multi_episode_state', task_state)

    # Continue splitting
    data['repeat'] = True
    data['worker_log'] = worker_log
    return data


def on_postprocessor_file_movement(data):
    """
    Runner function - configures postprocessor file movements.

    Note: This plugin writes split episode files directly to their final
    destination (source directory or season subdirectory) during the worker
    phase, so the standard Unmanic file movement is not needed for the split
    files. We prevent Unmanic from overwriting the source file by setting
    run_default_file_copy to False when we've successfully split the file.

    The 'data' object argument includes:
        library_id              - Integer, the library that the current task is associated with.
        source_data             - Dictionary, data pertaining to the original source file.
        remove_source_file      - Boolean, should Unmanic remove the original source file after all copy operations are complete.
        copy_file               - Boolean, should Unmanic run a copy operation with the returned data variables.
        file_in                 - String, the converted cache file to be copied by the postprocessor.
        file_out                - String, the destination file that the file will be copied to.
        run_default_file_copy   - Boolean, should Unmanic run the default post-process file movement.
    """
    # Check if this task was a successful split operation
    # The source file path will be in the data
    source_file = data.get('source_data', {}).get('abspath', '')

    if not source_file:
        return data

    # Check if this file was processed by our plugin (via directory info)
    try:
        directory_info = UnmanicDirectoryInfo(os.path.dirname(source_file))
        result = directory_info.get('split_multi_episode', os.path.basename(source_file))
        if result and result.startswith('split_'):
            # File was successfully split - prevent Unmanic from running the default
            # file copy which would overwrite the source file location
            logger.info(f"Split operation completed for {source_file}, disabling default file copy")
            data['run_default_file_copy'] = False
            # Don't remove the source file here - that's handled by the worker phase
            # if delete_source_after_split is enabled
            data['remove_source_file'] = False
    except Exception as e:
        logger.debug(f"Error checking split status in postprocessor: {e}")

    return data


def on_postprocessor_task_results(data):
    """
    Runner function - handles task completion.

    Records completion status and cleans up.
    """
    if not data.get('task_processing_success'):
        return data

    # The file has already been marked as processed in the splitting phase
    # This runner is mainly for additional cleanup if needed

    return data
