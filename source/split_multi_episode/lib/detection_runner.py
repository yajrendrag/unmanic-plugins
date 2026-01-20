#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Detection runner for Phase 2 boundary detection.

This module encapsulates the detection logic so it can be run either
in the main process or in a child process via PluginChildProcess.
"""

import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.detection_runner")


def run_phase2_detection(args: Dict[str, Any], progress) -> Dict[str, Any]:
    """
    Run Phase 2 detection on all enabled methods.

    This function is designed to be called either directly or via
    PluginChildProcess. All inputs/outputs are JSON-serializable.

    Args:
        args: Dict containing:
            - file_path: Path to the video file
            - search_windows: List of window dicts with start_time, end_time, center_time, source
            - total_duration: Total file duration in seconds
            - settings: Dict of relevant settings values
        progress: ProgressTracker instance

    Returns:
        Dict containing:
            - window_results: Dict mapping window index to list of (time, conf, metadata) tuples
            - episode_end_markers: Dict mapping window index to phrase_end_time or None
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

    # Initialize results
    window_results: Dict[int, List] = {i: [] for i in range(num_windows)}
    episode_end_markers: Dict[int, Any] = {i: None for i in range(num_windows)}

    # Run silence detection
    if settings.get('enable_silence_detection'):
        progress.start_method('silence', num_windows)
        detector = SilenceDetector(
            silence_threshold_db=settings['silence_threshold_db'],
            min_silence_duration=settings['silence_min_duration'],
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        results = detector.detect_in_windows(file_path, search_windows, total_duration)
        for i, (boundary_time, confidence, metadata) in enumerate(results):
            window_results[i].append([boundary_time, confidence, metadata])
            progress.log(f"    Window {i+1}: silence at {boundary_time/60:.1f}m (conf={confidence:.2f})")
        progress.complete_method()

    # Run black frame detection
    if settings.get('enable_black_frame_detection'):
        progress.start_method('black_frame', num_windows)
        detector = BlackFrameDetector(
            min_black_duration=settings['black_min_duration'],
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        results = detector.detect_in_windows(file_path, search_windows, total_duration, None)
        for i, (boundary_time, confidence, metadata) in enumerate(results):
            window_results[i].append([boundary_time, confidence, metadata])
            progress.log(f"    Window {i+1}: black at {boundary_time/60:.1f}m (conf={confidence:.2f})")
        progress.complete_method()

    # Run scene change detection
    if settings.get('enable_scene_change_detection'):
        progress.start_method('scene_change', num_windows)
        detector = SceneChangeDetector(
            scene_threshold=settings['scene_change_threshold'],
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        results = detector.detect_in_windows(file_path, search_windows, total_duration)
        for i, (boundary_time, confidence, metadata) in enumerate(results):
            window_results[i].append([boundary_time, confidence, metadata])
            progress.log(f"    Window {i+1}: scene change at {boundary_time/60:.1f}m (conf={confidence:.2f})")
        progress.complete_method()

    # Run image hash detection (full file)
    if settings.get('enable_image_hash_detection'):
        progress.start_method('image_hash', 1)
        detector = ImageHashDetector(
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        boundaries = detector.detect(file_path, total_duration)
        for boundary in boundaries:
            for i, window in enumerate(search_windows):
                if window.start_time <= boundary.end_time <= window.end_time:
                    window_results[i].append([boundary.end_time, boundary.confidence, {
                        'source': 'image_hash',
                        'window_source': window.source,
                    }])
                    progress.log(f"    Window {i+1}: image hash at {boundary.end_time/60:.1f}m")
        progress.complete_method()

    # Run audio fingerprint detection
    if settings.get('enable_audio_fingerprint_detection'):
        progress.start_method('audio_fingerprint', num_windows)
        detector = AudioFingerprintDetector(
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        results = detector.detect_in_windows(file_path, search_windows, total_duration)
        for i, (boundary_time, confidence, metadata) in enumerate(results):
            window_results[i].append([boundary_time, confidence, metadata])
            progress.log(f"    Window {i+1}: audio fingerprint at {boundary_time/60:.1f}m (conf={confidence:.2f})")
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
        results = detector.detect_in_windows(file_path, search_windows, total_duration)
        for i, (boundary_time, confidence, metadata) in enumerate(results):
            if not metadata.get('fallback'):
                window_results[i].append([boundary_time, confidence, metadata])
                credits_at = metadata.get('credits_detected_at', boundary_time)
                progress.log(
                    f"    Window {i+1}: LLM credits at {credits_at/60:.1f}m, "
                    f"boundary at {boundary_time/60:.1f}m (conf={confidence:.2f})"
                )
            else:
                progress.log(f"    Window {i+1}: LLM no credits detected")
        progress.complete_method()

    # Run speech detection
    if settings.get('enable_speech_detection'):
        progress.start_method('speech', num_windows)
        detector = SpeechDetector(
            model_size=settings['speech_model_size'],
            min_episode_length=min_ep_length,
            max_episode_length=max_ep_length
        )
        results = detector.detect_in_windows(file_path, search_windows, total_duration)
        for i, (marker_time, confidence, metadata) in enumerate(results):
            if metadata.get('source') == 'speech_episode_end':
                phrase_end_time = metadata.get('phrase_end_time', marker_time)
                episode_end_markers[i] = phrase_end_time
                progress.log(
                    f"    Window {i+1}: Speech found '{metadata.get('episode_end_phrase', 'preview')}' "
                    f"ending at {phrase_end_time/60:.1f}m (boundary should be AFTER this)"
                )
            else:
                progress.log(f"    Window {i+1}: Speech no episode-end phrases detected")
        progress.complete_method()

    # Convert window_results to serializable format
    # (tuples become lists in JSON anyway, but be explicit)
    serializable_results = {
        str(k): v for k, v in window_results.items()
    }
    serializable_markers = {
        str(k): v for k, v in episode_end_markers.items()
    }

    return {
        'window_results': serializable_results,
        'episode_end_markers': serializable_markers,
    }
