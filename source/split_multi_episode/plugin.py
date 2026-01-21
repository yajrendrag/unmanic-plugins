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
        "llm_model": "llava:7b-v1.6-mistral-q4_K_M",
        "llm_frames_per_boundary": 5,

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

        # Detection Parameters
        "confidence_threshold": 0.7,

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
            "llm_model": self._llm_setting("LLM Model", "Vision model to use (e.g., llava:7b)"),
            "llm_frames_per_boundary": self._llm_setting(
                "Frames per Boundary",
                "Number of frames to analyze at each potential boundary",
                "slider",
                {"min": 1, "max": 10, "step": 1}
            ),

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

            # Detection Parameters
            "confidence_threshold": {
                "label": "Confidence Threshold",
                "description": "Minimum confidence score to split at a boundary (0.0-1.0)",
                "input_type": "slider",
                "slider_options": {"min": 0.5, "max": 0.95, "step": 0.05},
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
    confidence_threshold = settings.get_setting('confidence_threshold')

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
            if parsed_info.title:
                runtimes = tmdb_validator.get_series_episode_runtimes(
                    parsed_info.title,
                    parsed_info.season or 1,
                    num_episodes=expected_episode_count or 10
                )
                if runtimes:
                    ep_offset = (start_ep - 1) if start_ep else 0
                    if ep_offset < len(runtimes):
                        expected_runtimes = runtimes[ep_offset:ep_offset + expected_episode_count]
                        worker_log.append(f"  TMDB runtimes: {expected_runtimes} minutes")

    # Get chapter information if enabled
    chapter_boundaries = None
    chapter_info = {}
    if settings.get_setting('enable_chapter_detection'):
        worker_log.append("  Analyzing chapters...")
        chapter_detector = ChapterDetector(
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        boundaries = chapter_detector.detect(probe_data)
        if boundaries:
            if boundaries[0].source == 'chapter_commercial':
                # Commercial markers - extract timing info for window refinement
                chapter_info['commercial_1_times'] = [b.end_time for b in boundaries[:-1]]
                chapter_boundaries = [(b.start_time, b.end_time) for b in boundaries]
                worker_log.append(f"    Found commercial markers for {len(boundaries)} episode regions")
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
    )

    # Refine windows with commercial chapter info if available
    if chapter_info.get('commercial_1_times'):
        search_windows = window_determiner.refine_windows_with_chapters(
            search_windows, chapter_info
        )

    if not search_windows:
        worker_log.append("Could not determine search windows")
        data['worker_log'] = worker_log
        return data

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
        window_results = {i: [] for i in range(len(search_windows))}
        episode_end_markers = {i: None for i in range(len(search_windows))}
    else:
        # Unpack results (convert string keys back to int)
        window_results = {
            int(k): [tuple(r) for r in v]
            for k, v in detection_result.get('window_results', {}).items()
        }
        episode_end_markers = {
            int(k): v
            for k, v in detection_result.get('episode_end_markers', {}).items()
        }

    # ========== Combine Results Per Window ==========
    worker_log.append("Combining results per window...")

    final_boundaries = []
    prev_end = 0.0

    for i, window in enumerate(search_windows):
        results = window_results[i]

        if not results:
            # No detections - use window center
            boundary_time = window.center_time
            confidence = 0.3
            worker_log.append(f"  Window {i+1}: no detections, using center {boundary_time/60:.1f}m")
        else:
            # Find clusters of agreeing detectors first, then pick the best cluster
            # This prevents a single high-proximity result from overriding agreement

            # Build clusters: group detectors within 60 seconds of each other
            clusters = []
            used = set()

            # Sort by time to make clustering easier
            sorted_results = sorted(results, key=lambda x: x[0])

            for idx, (r_time, r_conf, r_meta) in enumerate(sorted_results):
                if idx in used:
                    continue

                # Start a new cluster with this result
                cluster = [(r_time, r_conf, r_meta)]
                used.add(idx)

                # Find all other results within 60 seconds
                for idx2, (r2_time, r2_conf, r2_meta) in enumerate(sorted_results):
                    if idx2 in used:
                        continue
                    if abs(r2_time - r_time) < 60:
                        cluster.append((r2_time, r2_conf, r2_meta))
                        used.add(idx2)

                clusters.append(cluster)

            # Score each cluster: detectors agreeing + confidence + proximity to center
            # Black frame is a strong indicator of episode boundaries - prefer clusters with it
            window_half = (window.end_time - window.start_time) / 2

            def cluster_has_black_frame(cluster):
                return any(c[2].get('source') == 'black_frame' for c in cluster)

            def score_cluster(cluster):
                num_detectors = len(cluster)
                # Boost black_frame confidence by 0.15 when calculating avg
                boosted_confs = []
                for c in cluster:
                    conf = c[1]
                    if c[2].get('source') == 'black_frame':
                        conf = min(0.95, conf + 0.15)  # Boost black_frame
                    boosted_confs.append(conf)
                avg_conf = sum(boosted_confs) / num_detectors
                avg_time = sum(c[0] for c in cluster) / num_detectors

                # Calculate proximity to window center (0-1 scale)
                distance_from_center = abs(avg_time - window.center_time)
                proximity = 1.0 - (distance_from_center / window_half) if window_half > 0 else 0.5
                proximity = max(0, proximity)  # Clamp to 0 if outside window

                # Weighted score: 30% detector count, 30% confidence, 40% proximity
                return (num_detectors * 0.3) + (avg_conf * 0.3) + (proximity * 0.4)

            # Prefer clusters that contain black_frame detection
            clusters_with_black = [c for c in clusters if cluster_has_black_frame(c)]
            clusters_to_consider = clusters_with_black if clusters_with_black else clusters

            if clusters_with_black:
                worker_log.append(f"    Found {len(clusters_with_black)} cluster(s) with black_frame")

            best_cluster = None
            best_cluster_score = -1

            for cluster in clusters_to_consider:
                cluster_score = score_cluster(cluster)

                if cluster_score > best_cluster_score:
                    best_cluster_score = cluster_score
                    best_cluster = cluster

            # Use the winning cluster
            if best_cluster and len(best_cluster) > 1:
                # Multiple detectors agree
                # If black_frame is in cluster, use its time (most precise for cut point)
                # Otherwise use average time
                black_frame_result = None
                for c in best_cluster:
                    if c[2].get('source') == 'black_frame':
                        black_frame_result = c
                        break

                if black_frame_result:
                    # Use black_frame time - it marks the exact transition point
                    boundary_time = black_frame_result[0]
                    avg_conf = sum(c[1] for c in best_cluster) / len(best_cluster)
                    confidence = min(0.95, avg_conf * 1.1)  # Boost for agreement
                    sources = [c[2].get('source', 'unknown') for c in best_cluster]
                    worker_log.append(
                        f"  Window {i+1}: {len(best_cluster)} detectors agree, using black_frame at {boundary_time/60:.1f}m "
                        f"(conf={confidence:.2f}, sources={sources})"
                    )
                else:
                    # No black_frame - use average time
                    avg_time = sum(c[0] for c in best_cluster) / len(best_cluster)
                    avg_conf = sum(c[1] for c in best_cluster) / len(best_cluster)
                    boundary_time = avg_time
                    confidence = min(0.95, avg_conf * 1.1)  # Boost for agreement
                    sources = [c[2].get('source', 'unknown') for c in best_cluster]
                    worker_log.append(
                        f"  Window {i+1}: {len(best_cluster)} detectors agree at {boundary_time/60:.1f}m "
                        f"(conf={confidence:.2f}, sources={sources})"
                    )
            else:
                # Single detector or no cluster
                # Prefer black_frame over other detectors (strong boundary signal)
                black_frame_results = [r for r in results if r[2].get('source') == 'black_frame']
                if black_frame_results:
                    # Use black_frame even if other detectors have higher confidence
                    best_result = black_frame_results[0]
                    worker_log.append(
                        f"  Window {i+1}: using black_frame at {best_result[0]/60:.1f}m "
                        f"(conf={best_result[1]:.2f}, preferred over higher-confidence singles)"
                    )
                else:
                    # No black_frame - pick highest confidence
                    best_result = max(results, key=lambda x: x[1])
                    worker_log.append(
                        f"  Window {i+1}: best single at {best_result[0]/60:.1f}m "
                        f"(conf={best_result[1]:.2f}, source={best_result[2].get('source', 'unknown')})"
                    )
                boundary_time = best_result[0]
                confidence = best_result[1]

        # Apply LLM credits constraint
        # If LLM detected credits, the boundary must be AFTER the credits end
        llm_results = [r for r in results if r[2].get('source') == 'llm_vision']
        if llm_results:
            # Get the credits_detected_at time (where LLM last saw credits)
            llm_result = llm_results[0]
            credits_end_time = llm_result[2].get('credits_detected_at')

            if credits_end_time and boundary_time < credits_end_time:
                # Boundary is BEFORE credits end - need to adjust
                # Look for black_frame or silence AFTER the credits
                later_results = [r for r in results
                                 if r[0] >= credits_end_time and r[2].get('source') in ('black_frame', 'silence')]

                # If credits are near window edge and no results after, extend search
                if not later_results and credits_end_time >= window.end_time - 30:
                    # Credits extend to edge of window - scan beyond for black/silence
                    worker_log.append(
                        f"  Window {i+1}: Credits at window edge ({credits_end_time/60:.1f}m), "
                        f"extending search by 60s..."
                    )

                    # Import detectors for extended scan
                    from split_multi_episode.lib.detection import BlackFrameDetector, SilenceDetector
                    from split_multi_episode.lib.detection.search_window import SearchWindow

                    # Create extended window starting from credits end
                    extended_start = credits_end_time
                    extended_end = min(credits_end_time + 60, total_duration)

                    extended_window = SearchWindow(
                        start_time=extended_start,
                        end_time=extended_end,
                        center_time=(extended_start + extended_end) / 2,
                        confidence=0.5,
                        source='extended_for_credits',
                        episode_before=window.episode_before,
                        episode_after=window.episode_after,
                        metadata={'extended': True}
                    )

                    # Quick scan for black_frame in extended region
                    try:
                        black_detector = BlackFrameDetector(
                            min_black_duration=settings.get_setting('black_min_duration'),
                            min_episode_length=min_ep_length,
                            max_episode_length=max_ep_length
                        )
                        extended_black = black_detector.detect_in_windows(
                            file_in, [extended_window], total_duration, None
                        )
                        if extended_black and extended_black[0][0] > 0:
                            later_results.append((extended_black[0][0], extended_black[0][1],
                                                  {'source': 'black_frame', 'extended': True}))
                            worker_log.append(
                                f"    Found black_frame at {extended_black[0][0]/60:.1f}m in extended region"
                            )
                    except Exception as e:
                        worker_log.append(f"    Extended black_frame scan failed: {e}")

                    # Quick scan for silence in extended region if no black found
                    if not later_results:
                        try:
                            silence_detector = SilenceDetector(
                                silence_threshold_db=settings.get_setting('silence_threshold_db'),
                                min_silence_duration=settings.get_setting('silence_min_duration'),
                                min_episode_length=min_ep_length,
                                max_episode_length=max_ep_length
                            )
                            extended_silence = silence_detector.detect_in_windows(
                                file_in, [extended_window], total_duration
                            )
                            if extended_silence and extended_silence[0][0] > 0:
                                later_results.append((extended_silence[0][0], extended_silence[0][1],
                                                      {'source': 'silence', 'extended': True}))
                                worker_log.append(
                                    f"    Found silence at {extended_silence[0][0]/60:.1f}m in extended region"
                                )
                        except Exception as e:
                            worker_log.append(f"    Extended silence scan failed: {e}")

                if later_results:
                    # Prefer black_frame, then silence, closest to credits end
                    black_later = [r for r in later_results if r[2].get('source') == 'black_frame']
                    silence_later = [r for r in later_results if r[2].get('source') == 'silence']

                    if black_later:
                        best_later = min(black_later, key=lambda x: x[0])
                    elif silence_later:
                        best_later = min(silence_later, key=lambda x: x[0])
                    else:
                        best_later = min(later_results, key=lambda x: x[0])

                    old_time = boundary_time
                    boundary_time = best_later[0]
                    time_after_credits = boundary_time - credits_end_time
                    extended_note = " (from extended scan)" if best_later[2].get('extended') else ""
                    worker_log.append(
                        f"  Window {i+1}: Adjusted from {old_time/60:.1f}m to {boundary_time/60:.1f}m "
                        f"({time_after_credits:.0f}s after LLM credits end at {credits_end_time/60:.1f}m, "
                        f"source={best_later[2].get('source', 'unknown')}{extended_note})"
                    )
                else:
                    # No black_frame/silence after credits - use LLM boundary time
                    # (which is credits_detected_at + 5s from the LLM detector)
                    old_time = boundary_time
                    boundary_time = llm_result[0]  # LLM's suggested boundary time
                    worker_log.append(
                        f"  Window {i+1}: Adjusted from {old_time/60:.1f}m to {boundary_time/60:.1f}m "
                        f"(using LLM boundary, no black/silence after credits at {credits_end_time/60:.1f}m)"
                    )

        # Apply episode-end marker constraint from speech detection
        # If we detected "Stay tuned" etc., boundary should be AFTER that phrase,
        # ideally at a black/silent scene within 30 seconds of the phrase end
        if episode_end_markers.get(i) is not None:
            phrase_end_time = episode_end_markers[i]

            if boundary_time < phrase_end_time:
                # Boundary is BEFORE the episode-end phrase - need to adjust
                # Look for black_frame or silence AFTER the phrase, preferring within 30 seconds
                later_results = [r for r in results if r[0] >= phrase_end_time]

                if later_results:
                    # Score results: prefer black_frame, prefer within 30 seconds
                    def score_result(r):
                        time_after_phrase = r[0] - phrase_end_time
                        is_black = r[2].get('source') == 'black_frame'
                        is_silence = r[2].get('source') == 'silence'

                        # Base score from confidence
                        score = r[1]

                        # Prefer black_frame and silence (strong boundary signals)
                        if is_black:
                            score += 0.3
                        elif is_silence:
                            score += 0.2

                        # Prefer results within 30 seconds (ideal range)
                        if time_after_phrase <= 30:
                            score += 0.2 * (1 - time_after_phrase / 30)  # Max bonus at phrase end
                        else:
                            # Penalize results beyond 30 seconds (might be cutting into next episode)
                            penalty = min(0.3, (time_after_phrase - 30) / 60 * 0.3)
                            score -= penalty

                        return score

                    # Find best result AFTER phrase
                    best_later = max(later_results, key=score_result)
                    time_after = best_later[0] - phrase_end_time

                    old_time = boundary_time
                    boundary_time = best_later[0]
                    worker_log.append(
                        f"  Window {i+1}: Adjusted from {old_time/60:.1f}m to {boundary_time/60:.1f}m "
                        f"({time_after:.0f}s after episode-end phrase, "
                        f"source={best_later[2].get('source', 'unknown')})"
                    )
                else:
                    # No results after phrase - use 5 seconds after phrase end
                    old_time = boundary_time
                    boundary_time = phrase_end_time + 5.0
                    worker_log.append(
                        f"  Window {i+1}: Adjusted from {old_time/60:.1f}m to {boundary_time/60:.1f}m "
                        f"(5s after episode-end phrase at {phrase_end_time/60:.1f}m)"
                    )
            elif boundary_time > phrase_end_time + 60:
                # Boundary is more than 60 seconds after phrase - might be too late
                # Look for something closer to the phrase
                closer_results = [r for r in results
                                  if phrase_end_time <= r[0] <= phrase_end_time + 60]
                if closer_results:
                    # Prefer black_frame/silence within 30 seconds
                    black_close = [r for r in closer_results
                                   if r[2].get('source') == 'black_frame' and r[0] <= phrase_end_time + 30]
                    if black_close:
                        best_close = black_close[0]
                    else:
                        best_close = min(closer_results, key=lambda x: x[0] - phrase_end_time)

                    old_time = boundary_time
                    boundary_time = best_close[0]
                    worker_log.append(
                        f"  Window {i+1}: Adjusted from {old_time/60:.1f}m to {boundary_time/60:.1f}m "
                        f"(closer to episode-end phrase at {phrase_end_time/60:.1f}m)"
                    )

        # Create episode boundary
        from split_multi_episode.lib.detection.boundary_merger import MergedBoundary
        final_boundaries.append(MergedBoundary(
            start_time=prev_end,
            end_time=boundary_time,
            confidence=confidence,
            sources=[r[2].get('source', 'unknown') for r in results] if results else ['fallback'],
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

    # TMDB validation
    if settings.get_setting('enable_tmdb_validation'):
        worker_log.append("Validating against TMDB...")
        tmdb_validator = TMDBValidator(
            api_key=settings.get_setting('tmdb_api_key'),
            api_read_access_token=settings.get_setting('tmdb_api_read_access_token')
        )
        if tmdb_validator.is_available():
            durations = [b.end_time - b.start_time for b in merged_boundaries]
            result = tmdb_validator.validate(file_in, durations)
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
