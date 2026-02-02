#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Detection runner for Phase 2 boundary detection.

This module encapsulates the detection logic so it can be run either
in the main process or in a child process via PluginChildProcess.

v0.1.0: Uses raw detection clustering architecture - collects ALL detections
from each detector and clusters them to find the best boundaries.

v0.2.0: Added LLM Precision Mode - narrow windows with dense sampling for
logo-focused detection on clean files.
"""

import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.detection_runner")


def run_phase2_detection(args: Dict[str, Any], progress) -> Dict[str, Any]:
    """
    Run Phase 2 detection on all enabled methods using raw clustering.

    This function collects ALL raw detections from each detector, then
    clusters them per window to find the best boundary.

    Args:
        args: Dict containing:
            - file_path: Path to the video file
            - search_windows: List of window dicts with start_time, end_time, center_time, source
            - total_duration: Total file duration in seconds
            - settings: Dict of relevant settings values
        progress: ProgressTracker instance

    Returns:
        Dict containing:
            - window_boundaries: Dict mapping window index to (time, conf, metadata) or None
            - all_raw_detections: List of all raw detections (for debugging)
    """
    # Import detection modules (done here so child process can import them)
    from split_multi_episode.lib.detection import (
        SilenceDetector,
        BlackFrameDetector,
        SceneChangeDetector,
        ImageHashDetector,
        AudioFingerprintDetector,
        LLMDetector,
        SpeechDetector,
        RawDetectionClusterer,
    )
    from split_multi_episode.lib.detection.search_window import SearchWindow

    # Extract args
    file_path = args['file_path']
    total_duration = args['total_duration']
    settings = args['settings']

    # Reconstruct SearchWindow objects from dicts
    search_windows = [
        SearchWindow(
            start_time=w['start_time'],
            end_time=w['end_time'],
            center_time=w['center_time'],
            confidence=w['confidence'],
            source=w['source'],
            episode_before=w['episode_before'],
            episode_after=w['episode_after'],
            metadata=w['metadata'],
        )
        for w in args['search_windows']
    ]

    num_windows = len(search_windows)
    min_ep_length = settings['min_episode_length']
    max_ep_length = settings['max_episode_length']

    # Check for LLM Precision Mode
    if settings.get('llm_precision_mode'):
        return _run_precision_mode(
            file_path, search_windows, settings, progress
        )

    # Determine enabled methods
    enabled_methods = []
    if settings.get('enable_silence_detection'):
        enabled_methods.append('silence')
    if settings.get('enable_black_frame_detection'):
        enabled_methods.append('black_frame')
    if settings.get('enable_scene_change_detection'):
        enabled_methods.append('scene_change')
    if settings.get('enable_image_hash_detection'):
        enabled_methods.append('image_hash')
    if settings.get('enable_audio_fingerprint_detection'):
        enabled_methods.append('audio_fingerprint')
    if settings.get('enable_llm_detection'):
        enabled_methods.append('llm_vision')
    if settings.get('enable_speech_detection'):
        enabled_methods.append('speech')

    progress.set_methods(enabled_methods)

    # Collect ALL raw detections from all detectors
    all_raw_detections = []

    # Run silence detection
    if settings.get('enable_silence_detection'):
        progress.start_method('silence', num_windows)
        detector = SilenceDetector(
            silence_threshold_db=settings['silence_threshold_db'],
            min_silence_duration=settings['silence_min_duration'],
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        raw_detections = detector.detect_raw_in_windows(file_path, search_windows)
        all_raw_detections.extend(raw_detections)
        progress.log(f"  Silence: {len(raw_detections)} raw detections")
        progress.complete_method()

    # Run black frame detection
    if settings.get('enable_black_frame_detection'):
        progress.start_method('black_frame', num_windows)
        detector = BlackFrameDetector(
            min_black_duration=settings['black_min_duration'],
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        raw_detections = detector.detect_raw_in_windows(file_path, search_windows)
        all_raw_detections.extend(raw_detections)
        progress.log(f"  Black frame: {len(raw_detections)} raw detections")
        progress.complete_method()

    # Run scene change detection
    if settings.get('enable_scene_change_detection'):
        progress.start_method('scene_change', num_windows)
        detector = SceneChangeDetector(
            scene_threshold=settings['scene_change_threshold'],
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        raw_detections = detector.detect_raw_in_windows(file_path, search_windows)
        all_raw_detections.extend(raw_detections)
        progress.log(f"  Scene change: {len(raw_detections)} raw detections")
        progress.complete_method()

    # Run image hash detection (full file) - NOT using raw clustering for pattern detectors
    # Image hash detects recurring intros at episode STARTS, not boundaries
    if settings.get('enable_image_hash_detection'):
        progress.start_method('image_hash', 1)
        detector = ImageHashDetector(
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        boundaries = detector.detect(file_path, total_duration)
        progress.log(f"  Image hash: {len(boundaries)} recurring patterns")
        # Note: Image hash boundaries are intro locations, not split points
        # They're not added to raw detections for clustering
        progress.complete_method()

    # Run audio fingerprint detection - NOT using raw clustering for pattern detectors
    # Audio fingerprint detects recurring intro music, not boundaries
    if settings.get('enable_audio_fingerprint_detection'):
        progress.start_method('audio_fingerprint', num_windows)
        detector = AudioFingerprintDetector(
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        results = detector.detect_in_windows(file_path, search_windows, total_duration)
        progress.log(f"  Audio fingerprint: {len([r for r in results if r[1] > 0.5])} strong patterns")
        # Note: Audio fingerprint finds intros, not split points
        progress.complete_method()

    # Run LLM vision detection
    if settings.get('enable_llm_detection'):
        progress.start_method('llm_vision', num_windows)
        detector = LLMDetector(
            ollama_host=settings['llm_ollama_host'],
            model=settings['llm_model'],
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        raw_detections = detector.detect_raw_in_windows(file_path, search_windows)
        all_raw_detections.extend(raw_detections)

        # Count detection types
        credits_count = len([d for d in raw_detections if d.source == 'llm_credits'])
        logo_count = len([d for d in raw_detections if d.source == 'llm_logo'])
        outro_count = len([d for d in raw_detections if d.source == 'llm_outro'])
        progress.log(f"  LLM vision: {len(raw_detections)} raw detections "
                     f"(credits={credits_count}, logo={logo_count}, outro={outro_count})")
        progress.complete_method()

    # Run speech detection
    if settings.get('enable_speech_detection'):
        progress.start_method('speech', num_windows)
        detector = SpeechDetector(
            model_size=settings['speech_model_size'],
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        raw_detections = detector.detect_raw_in_windows(file_path, search_windows)
        all_raw_detections.extend(raw_detections)
        progress.log(f"  Speech: {len(raw_detections)} episode-end phrases")
        progress.complete_method()

    # Now cluster detections per window
    progress.log(f"Clustering {len(all_raw_detections)} total raw detections across {num_windows} windows...")

    clusterer = RawDetectionClusterer(
        cluster_tolerance=60.0,  # 60 second clustering window
        diversity_weight=1.5,    # Bonus for multiple detector types agreeing
        proximity_weight=0.1,    # Penalty for spread
    )

    window_boundaries: Dict[int, Any] = {}

    for i, window in enumerate(search_windows):
        # Get best boundary for this window
        result = clusterer.get_best_boundary(
            all_raw_detections,
            window_start=window.start_time,
            window_end=window.end_time,
        )

        if result:
            boundary_time, confidence, metadata = result
            metadata['window_source'] = window.source
            window_boundaries[i] = [boundary_time, confidence, metadata]

            sources = metadata.get('sources', [])
            progress.log(
                f"  Window {i+1}: boundary at {boundary_time/60:.2f}m "
                f"(conf={confidence:.2f}, sources={sources})"
            )
        else:
            # Fallback to window center
            window_boundaries[i] = [window.center_time, 0.3, {
                'fallback': True,
                'window_source': window.source,
            }]
            progress.log(f"  Window {i+1}: no detections, using center {window.center_time/60:.2f}m")

    # Convert to serializable format
    serializable_boundaries = {
        str(k): v for k, v in window_boundaries.items()
    }

    # Serialize raw detections for debugging (optional, can be large)
    serializable_raw = [
        {
            'timestamp': d.timestamp,
            'score': d.score,
            'source': d.source,
        }
        for d in all_raw_detections
    ]

    return {
        'window_boundaries': serializable_boundaries,
        'all_raw_detections': serializable_raw,
    }


def _run_precision_mode(
    file_path: str,
    search_windows: List,
    settings: Dict[str, Any],
    progress
) -> Dict[str, Any]:
    """
    Run LLM Precision Mode detection.

    This mode uses:
    - Narrow 2.2-minute windows (from TMDB runtimes)
    - Dense 2-second sampling
    - Logo-centric split logic
    - Sequential window processing with drift adjustment
    - No other detectors

    Windows are processed one at a time. After each boundary is found,
    subsequent windows are adjusted to account for cumulative timing drift.
    This handles cases where TMDB runtimes don't perfectly match actual content.

    Args:
        file_path: Path to the video file
        search_windows: List of SearchWindow objects (narrow precision windows)
        settings: Dict of settings
        progress: ProgressTracker instance

    Returns:
        Dict in same format as run_phase2_detection
    """
    from split_multi_episode.lib.detection import LLMDetector
    from split_multi_episode.lib.detection.search_window import SearchWindow
    from split_multi_episode.lib.detection.black_frame_detector import BlackFrameDetector

    min_ep_length = settings['min_episode_length']
    max_ep_length = settings['max_episode_length']
    num_windows = len(search_windows)

    precision_pattern = settings.get('llm_precision_pattern', '')
    use_black_frames = settings.get('llm_precision_use_black_frames', True) and not precision_pattern

    # Create black frame detector if needed (uses fast windowed detection)
    black_detector = None
    if use_black_frames:
        black_detector = BlackFrameDetector(
            min_black_duration=0.5,  # Short duration for precision
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length,
        )

    # Precision mode only uses LLM
    progress.set_methods(['llm_precision'])
    progress.start_method('llm_precision', num_windows)

    if precision_pattern:
        progress.log(f"LLM Precision Mode: {num_windows} windows, pattern matching '{precision_pattern}'")
    elif use_black_frames:
        progress.log(f"LLM Precision Mode: {num_windows} windows, 2-second sampling + black frame refinement")
    else:
        progress.log(f"LLM Precision Mode: {num_windows} windows, 2-second sampling, sequential with drift adjustment")

    detector = LLMDetector(
        ollama_host=settings['llm_ollama_host'],
        model=settings['llm_model'],
        min_episode_length=min_ep_length,
        max_episode_length=max_ep_length
    )

    # Process windows sequentially with drift adjustment
    # Track cumulative drift: difference between predicted and actual boundary times
    cumulative_drift = 0.0
    window_boundaries: Dict[int, Any] = {}
    failed_windows = []

    for i, window in enumerate(search_windows):
        # Calculate adjusted window times based on cumulative drift
        # If previous episodes were shorter than predicted, this window shifts earlier
        adjusted_center = window.center_time + cumulative_drift
        adjusted_start = window.start_time + cumulative_drift
        adjusted_end = window.end_time + cumulative_drift

        # Ensure we don't go negative
        adjusted_start = max(0, adjusted_start)

        # Log the adjustment if significant
        if abs(cumulative_drift) > 1:
            progress.log(
                f"  Window {i+1}: adjusted by {cumulative_drift:.1f}s drift "
                f"({window.center_time/60:.2f}m → {adjusted_center/60:.2f}m)"
            )

        # Create adjusted window for detection
        adjusted_window = SearchWindow(
            start_time=adjusted_start,
            end_time=adjusted_end,
            center_time=adjusted_center,
            confidence=window.confidence,
            source=window.source,
            episode_before=window.episode_before,
            episode_after=window.episode_after,
            metadata={**window.metadata, 'drift_applied': cumulative_drift},
        )

        # Run detection on this single window
        post_credits_buffer = settings.get('llm_post_credits_buffer', 15)
        precision_pattern = settings.get('llm_precision_pattern', '')
        min_gap_threshold = settings.get('llm_pattern_grouping_buffer', 10)

        # Create progress callback for frame-level updates
        def frame_progress_callback(frames_done, total_frames):
            if total_frames > 0:
                fraction = frames_done / total_frames
                progress.update_sub_progress(fraction)

        results = detector.detect_precision_in_windows(
            file_path, [adjusted_window], post_credits_buffer, precision_pattern,
            progress_callback=frame_progress_callback,
            min_gap_threshold=min_gap_threshold
        )

        if not results:
            # Should not happen, but handle gracefully
            progress.log(f"  Window {i+1}: No result returned")
            window_boundaries[i] = [adjusted_center, 0.0, {
                'source': 'llm_precision_failed',
                'failed': True,
                'error': 'No result returned from detector',
            }]
            failed_windows.append(i + 1)
            progress.update_window_progress(i + 1)
            continue

        boundary_time, confidence, metadata = results[0]

        # Refine with black frame detection if enabled and LLM found something
        if black_detector and not metadata.get('failed'):
            # Search for black frames in a narrow window around the LLM boundary
            search_radius = 4  # seconds each direction
            search_start = max(0, boundary_time - search_radius)
            search_duration = search_radius * 2

            blacks = black_detector._detect_black_in_window(
                file_path, search_start, search_duration
            )

            if blacks:
                # Find the black frame closest to the LLM boundary
                best_black = min(
                    blacks,
                    key=lambda b: abs((b.start_time + b.end_time) / 2 - boundary_time)
                )
                black_midpoint = (best_black.start_time + best_black.end_time) / 2
                distance = abs(black_midpoint - boundary_time)

                # Only use if within 2 seconds of LLM detection
                if distance <= 2.0:
                    original_boundary = boundary_time
                    boundary_time = black_midpoint
                    metadata['black_frame_refined'] = True
                    metadata['black_frame_distance'] = round(distance, 2)
                    metadata['original_llm_boundary'] = original_boundary
                    confidence = min(confidence + 0.05, 0.95)
                    logger.debug(
                        f"Black frame refined: {original_boundary/60:.2f}m -> {boundary_time/60:.2f}m "
                        f"(distance={distance:.2f}s)"
                    )

        # Store result
        window_boundaries[i] = [boundary_time, confidence, metadata]

        # Check if detection failed
        if metadata.get('failed'):
            failed_windows.append(i + 1)
            progress.log(
                f"  Window {i+1}: FAILED - {metadata.get('error', 'No detections found')}"
            )
            # Don't update drift on failure - keep using current drift
            progress.update_window_progress(i + 1)
            continue

        # Calculate drift for this window and update cumulative
        # drift = how much earlier/later the boundary was compared to adjusted prediction
        window_drift = boundary_time - adjusted_center
        cumulative_drift += window_drift

        # Log result with drift info
        source = metadata.get('source', 'unknown')
        from_expansion = ' (from expansion)' if metadata.get('from_expansion') else ''
        drift_info = f", drift={window_drift:+.1f}s" if abs(window_drift) > 1 else ""
        black_info = ' +black' if metadata.get('black_frame_refined') else ''

        if 'logo' in source:
            logo_count = metadata.get('logo_count', 0)
            progress.log(
                f"  Window {i+1}: {boundary_time/60:.2f}m via {logo_count} logos{black_info} "
                f"(conf={confidence:.2f}){from_expansion}{drift_info}"
            )
        elif 'credits' in source:
            progress.log(
                f"  Window {i+1}: {boundary_time/60:.2f}m via credits{black_info} "
                f"(conf={confidence:.2f}){from_expansion}{drift_info}"
            )
        elif 'pattern' in source:
            progress.log(
                f"  Window {i+1}: {boundary_time/60:.2f}m via pattern match "
                f"(conf={confidence:.2f}){from_expansion}{drift_info}"
            )
        else:
            progress.log(
                f"  Window {i+1}: {boundary_time/60:.2f}m fallback "
                f"(conf={confidence:.2f}){drift_info}"
            )

        # Update progress gauge after each window
        progress.update_window_progress(i + 1)

    if failed_windows:
        progress.log(
            f"WARNING: Detection failed for window(s) {failed_windows}. "
            f"File may not be split correctly."
        )

    if abs(cumulative_drift) > 1:
        progress.log(f"  Total cumulative drift: {cumulative_drift:.1f}s")

    progress.complete_method()

    # Convert to serializable format
    serializable_boundaries = {
        str(k): v for k, v in window_boundaries.items()
    }

    return {
        'window_boundaries': serializable_boundaries,
        'all_raw_detections': [],  # No raw detections in precision mode
    }
