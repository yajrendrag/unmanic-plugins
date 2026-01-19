#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Split Multi-Episode Files

This plugin detects and splits multi-episode MKV files into individual
episode files using a multi-technique detection pipeline including:
- Chapter markers
- Silence detection
- Black frame detection
- Perceptual image hashing
- Audio fingerprinting
- LLM vision analysis (via Ollama)
- TMDB runtime validation
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
)
from split_multi_episode.lib.validation import TMDBValidator
from split_multi_episode.lib.splitter import EpisodeSplitter
from split_multi_episode.lib.naming import EpisodeNamer

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.split_multi_episode")


class Settings(PluginSettings):
    settings = {
        # Detection Methods
        "enable_chapter_detection": True,
        "enable_silence_detection": True,
        "enable_black_frame_detection": True,
        "enable_image_hash_detection": False,
        "enable_audio_fingerprint_detection": False,
        "enable_llm_detection": False,
        "enable_tmdb_validation": False,

        # LLM Settings
        "llm_ollama_host": "http://localhost:11434",
        "llm_model": "llava:7b-v1.6-mistral-q4_K_M",
        "llm_frames_per_boundary": 5,

        # Duration Constraints
        "min_episode_length_minutes": 15,
        "max_episode_length_minutes": 90,
        "min_file_duration_minutes": 30,

        # Detection Parameters
        "silence_threshold_db": -30,
        "silence_min_duration": 2.0,
        "black_min_duration": 1.0,
        "confidence_threshold": 0.7,
        "require_multiple_detectors": True,

        # Output Settings
        "output_naming_pattern": "S{season:02d}E{episode:02d} - {basename}",
        "copy_streams_lossless": True,
        "create_season_directory": False,
        "season_directory_pattern": "Season {season:02d}",
        "delete_source_after_split": False,
        "tmdb_api_key": "",
        "tmdb_api_read_access_token": "",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)

        self.form_settings = {
            # Detection Methods
            "enable_chapter_detection": {
                "label": "Enable Chapter Detection",
                "description": "Use chapter markers to detect episode boundaries (highest reliability)",
            },
            "enable_silence_detection": {
                "label": "Enable Silence Detection",
                "description": "Detect silence gaps between episodes",
            },
            "enable_black_frame_detection": {
                "label": "Enable Black Frame Detection",
                "description": "Detect black frames that may indicate episode breaks",
            },
            "enable_image_hash_detection": {
                "label": "Enable Image Hash Detection",
                "description": "Use perceptual hashing to find recurring intro/outro sequences (CPU intensive)",
            },
            "enable_audio_fingerprint_detection": {
                "label": "Enable Audio Fingerprint Detection",
                "description": "Detect recurring intro music patterns",
            },
            "enable_llm_detection": {
                "label": "Enable LLM Vision Detection",
                "description": "Use Ollama vision model to detect credits, title cards (requires Ollama)",
            },
            "enable_tmdb_validation": {
                "label": "Enable TMDB Validation",
                "description": "Validate detected runtimes against TMDB episode data",
            },

            # LLM Settings
            "llm_ollama_host": self._llm_setting("Ollama Host", "URL of Ollama API endpoint"),
            "llm_model": self._llm_setting("LLM Model", "Vision model to use (e.g., llava:7b)"),
            "llm_frames_per_boundary": self._llm_setting(
                "Frames per Boundary",
                "Number of frames to analyze at each potential boundary",
                "slider",
                {"min": 1, "max": 10, "step": 1}
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
            "silence_threshold_db": {
                "label": "Silence Threshold (dB)",
                "description": "Audio level threshold for silence detection",
                "input_type": "slider",
                "slider_options": {"min": -60, "max": -10, "step": 5},
            },
            "silence_min_duration": self._detection_setting(
                "enable_silence_detection",
                "Minimum Silence Duration (seconds)",
                "Minimum silence duration to detect"
            ),
            "black_min_duration": self._detection_setting(
                "enable_black_frame_detection",
                "Minimum Black Duration (seconds)",
                "Minimum black frame duration to detect"
            ),
            "confidence_threshold": {
                "label": "Confidence Threshold",
                "description": "Minimum confidence score to split at a boundary (0.0-1.0)",
                "input_type": "slider",
                "slider_options": {"min": 0.5, "max": 0.95, "step": 0.05},
            },
            "require_multiple_detectors": {
                "label": "Require Multiple Detectors",
                "description": "Require at least 2 detection methods to agree before splitting",
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
            "tmdb_api_key": self._tmdb_setting("TMDB API Key", "API key for TMDB validation"),
            "tmdb_api_read_access_token": self._tmdb_setting(
                "TMDB API Read Access Token",
                "API read access token for TMDB (v4 auth)"
            ),
        }

    def _llm_setting(self, label, description, input_type="text", extra=None):
        setting = {
            "label": label,
            "description": description,
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
        }
        if not self.get_setting('enable_tmdb_validation'):
            setting["display"] = "hidden"
        return setting

    def _detection_setting(self, parent_setting, label, description):
        setting = {
            "label": label,
            "description": description,
        }
        if not self.get_setting(parent_setting):
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
    """Run the detection pipeline and store results."""
    from unmanic.libs.task import TaskDataStore

    worker_log.append("Starting multi-episode detection analysis...")

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
    require_multiple = settings.get_setting('require_multiple_detectors')

    # Run enabled detectors
    all_boundaries = []

    # Chapter detection
    if settings.get_setting('enable_chapter_detection'):
        worker_log.append("Running chapter detection...")
        chapter_detector = ChapterDetector(
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        boundaries = chapter_detector.detect(probe_data)
        if boundaries:
            worker_log.append(f"  Found {len(boundaries)} boundaries from chapters")
            all_boundaries.append(boundaries)

    # Silence detection
    silence_regions = []
    if settings.get_setting('enable_silence_detection'):
        worker_log.append("Running silence detection...")
        silence_detector = SilenceDetector(
            silence_threshold_db=settings.get_setting('silence_threshold_db'),
            min_silence_duration=settings.get_setting('silence_min_duration'),
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        boundaries = silence_detector.detect(file_in, total_duration)
        if boundaries:
            worker_log.append(f"  Found {len(boundaries)} boundaries from silence")
            all_boundaries.append(boundaries)
        silence_regions = silence_detector.get_raw_silence_regions(file_in)

    # Black frame detection
    if settings.get_setting('enable_black_frame_detection'):
        worker_log.append("Running black frame detection...")
        black_detector = BlackFrameDetector(
            min_black_duration=settings.get_setting('black_min_duration'),
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        boundaries = black_detector.detect(file_in, total_duration)
        if boundaries:
            # Enhance with silence data if available
            if silence_regions:
                boundaries = black_detector.enhance_with_silence(boundaries, silence_regions)
            worker_log.append(f"  Found {len(boundaries)} boundaries from black frames")
            all_boundaries.append(boundaries)

    # Image hash detection
    if settings.get_setting('enable_image_hash_detection'):
        worker_log.append("Running image hash detection...")
        hash_detector = ImageHashDetector(
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        if hash_detector.is_available():
            boundaries = hash_detector.detect(file_in, total_duration)
            if boundaries:
                worker_log.append(f"  Found {len(boundaries)} boundaries from image hashing")
                all_boundaries.append(boundaries)
        else:
            worker_log.append("  Image hash detection unavailable (missing dependencies)")

    # Audio fingerprint detection
    if settings.get_setting('enable_audio_fingerprint_detection'):
        worker_log.append("Running audio fingerprint detection...")
        audio_detector = AudioFingerprintDetector(
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        boundaries = audio_detector.detect(file_in, total_duration)
        if boundaries:
            worker_log.append(f"  Found {len(boundaries)} boundaries from audio fingerprinting")
            all_boundaries.append(boundaries)

    # LLM vision detection
    if settings.get_setting('enable_llm_detection'):
        worker_log.append("Running LLM vision detection...")
        llm_detector = LLMDetector(
            ollama_host=settings.get_setting('llm_ollama_host'),
            model=settings.get_setting('llm_model'),
            frames_per_boundary=settings.get_setting('llm_frames_per_boundary'),
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        if llm_detector.is_available():
            boundaries = llm_detector.detect(file_in, total_duration)
            if boundaries:
                worker_log.append(f"  Found {len(boundaries)} boundaries from LLM analysis")
                all_boundaries.append(boundaries)
        else:
            worker_log.append("  LLM detection unavailable (Ollama not running)")

    # Merge boundaries
    if not all_boundaries:
        worker_log.append("No episode boundaries detected")
        data['worker_log'] = worker_log
        return data

    worker_log.append("Merging detection results...")
    merger = BoundaryMerger(
        confidence_threshold=confidence_threshold,
        require_multiple_detectors=require_multiple,
        min_episode_length=min_ep_length,
        max_episode_length=max_ep_length
    )
    merged_boundaries = merger.merge(all_boundaries, total_duration)

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

    # Convert to split points
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
