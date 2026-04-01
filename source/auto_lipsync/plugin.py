#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <jay@gardner.us.com>
    Date:                     31 March 2026

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
import subprocess

from unmanic.libs.unplugins.settings import PluginSettings

logger = logging.getLogger("Unmanic.Plugin.auto_lipsync")

PLUGIN_ID = "auto_lipsync"
MODELS_DIR = "/config/.unmanic/models/syncnet"
S3FD_WEIGHTS = os.path.join(MODELS_DIR, "sfd_face.pth")
SYNCNET_WEIGHTS = os.path.join(MODELS_DIR, "syncnet_v2.model")


class Settings(PluginSettings):
    settings = {
        "num_segments":           6,
        "segment_duration":       25,
        "min_confident_segments": 2,
        "min_offset_ms":          40,
        "max_offset_ms":          5000,
        "confidence_threshold":   3.0,
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "num_segments": {
                "label":          "Number of sample segments",
                "description":    "How many evenly-spaced segments to analyse (skipping first/last 10% of the file). "
                                  "More segments = more reliable but slower. Default: 6.",
                "input_type":     "slider",
                "slider_options": {
                    "min":  2,
                    "max":  20,
                    "step": 1,
                },
            },
            "segment_duration": {
                "label":          "Segment duration (seconds)",
                "description":    "Length of each sample segment in seconds. Must be long enough for SyncNet to detect "
                                  "a face track (minimum ~3s). Default: 25s.",
                "input_type":     "slider",
                "slider_options": {
                    "min":  5,
                    "max":  60,
                    "step": 5,
                },
            },
            "min_confident_segments": {
                "label":          "Minimum confident segments",
                "description":    "How many segments must individually exceed the confidence threshold before a "
                                  "correction is applied. Default: 2.",
                "input_type":     "slider",
                "slider_options": {
                    "min":  1,
                    "max":  10,
                    "step": 1,
                },
            },
            "min_offset_ms": {
                "label":          "Minimum offset (ms)",
                "description":    "Minimum detected offset in milliseconds before correction is applied. "
                                  "Default: 40ms (~1 frame at 25fps).",
                "input_type":     "slider",
                "slider_options": {
                    "min":  10,
                    "max":  500,
                    "step": 10,
                },
            },
            "max_offset_ms": {
                "label":          "Maximum offset (ms)",
                "description":    "Safety cap - offsets larger than this are ignored as likely false positives. "
                                  "Default: 5000ms.",
                "input_type":     "slider",
                "slider_options": {
                    "min":  500,
                    "max":  10000,
                    "step": 100,
                },
            },
            "confidence_threshold": {
                "label":          "Confidence threshold",
                "description":    "Minimum SyncNet confidence score to apply correction. "
                                  "Higher values are more conservative. Default: 3.0.",
                "input_type":     "slider",
                "slider_options": {
                    "min":  0.5,
                    "max":  10.0,
                    "step": 0.5,
                },
            },
        }


def get_video_fps(video_path):
    """Get video frame rate using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=r_frame_rate',
        '-of', 'json',
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        info = json.loads(result.stdout)
        if info.get('streams'):
            fps_str = info['streams'][0].get('r_frame_rate', '25/1')
            num, den = fps_str.split('/')
            return float(num) / float(den)
    except Exception as e:
        logger.warning("Failed to get FPS for '%s': %s", video_path, e)
    return 25.0


def file_has_video_and_audio(path):
    """Check if file has both video and audio streams."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'stream=codec_type',
        '-of', 'json',
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        info = json.loads(result.stdout)
        codec_types = [s.get('codec_type') for s in info.get('streams', [])]
        return 'video' in codec_types and 'audio' in codec_types
    except Exception:
        return False


def already_processed(path, file_metadata=None):
    """Check if this file has already been processed by this plugin."""
    if file_metadata:
        try:
            metadata = file_metadata.get()
            if metadata.get('processed'):
                return True
        except Exception as e:
            logger.debug("Unable to read file metadata for '%s': %s", path, e)

    # Fallback to legacy .unmanic files
    try:
        from unmanic.libs.directoryinfo import UnmanicDirectoryInfo
        directory_info = UnmanicDirectoryInfo(os.path.dirname(path))
        result = directory_info.get(PLUGIN_ID, os.path.basename(path))
        if result:
            return True
    except Exception:
        pass

    return False


def _get_duration(video_path):
    """Return video duration in seconds via ffprobe."""
    import subprocess as _sp
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'json',
        video_path,
    ]
    result = _sp.run(cmd, capture_output=True, text=True, timeout=30)
    info = json.loads(result.stdout)
    return float(info['format']['duration'])


def _extract_segment(video_path, start_sec, duration_sec, output_path):
    """Extract a segment (video + audio) from a video file using ffmpeg stream copy."""
    import subprocess as _sp
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start_sec),
        '-i', video_path,
        '-t', str(duration_sec),
        '-map', '0:v:0',
        '-map', '0:a:0',
        '-c', 'copy',
        '-sn',
        output_path,
    ]
    _sp.run(cmd, capture_output=True, timeout=120)
    return output_path


def analyze_sync_child(video_path, result_path, models_dir, num_segments, segment_duration,
                       confidence_threshold, log_queue=None, prog_queue=None):
    """
    Child process function: run SyncNet analysis on sampled segments of a video.

    Extracts *num_segments* evenly-spaced segments (each *segment_duration* seconds long,
    skipping the first and last 10% of the file) and runs SyncNet on each.  Only segments
    whose per-segment confidence exceeds *confidence_threshold* contribute to the final
    median offset.

    Writes a JSON result to *result_path*.
    """
    import json as _json
    import shutil
    import statistics
    import tempfile

    log_queue.put("Starting sampled SyncNet lip sync analysis ...")
    log_queue.put("  Segments: {}, Duration: {}s each".format(num_segments, segment_duration))
    prog_queue.put(2)

    try:
        import torch
        from syncnet_python import SyncNetPipeline
    except ImportError as exc:
        log_queue.put("ERROR: Failed to import required packages: {}".format(exc))
        with open(result_path, 'w') as fp:
            _json.dump({"error": str(exc)}, fp)
        return

    s3fd_path = os.path.join(models_dir, "sfd_face.pth")
    syncnet_path = os.path.join(models_dir, "syncnet_v2.model")

    if not os.path.exists(s3fd_path) or not os.path.exists(syncnet_path):
        msg = "Model weights not found in {}. Ensure the init.d script has run.".format(models_dir)
        log_queue.put("ERROR: " + msg)
        with open(result_path, 'w') as fp:
            _json.dump({"error": msg}, fp)
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    log_queue.put("Loading SyncNet pipeline (device={}) ...".format(device))
    prog_queue.put(5)

    try:
        pipeline = SyncNetPipeline(
            {
                "s3fd_weights":    s3fd_path,
                "syncnet_weights": syncnet_path,
            },
            device=device,
        )
        prog_queue.put(10)

        # --- Determine segment start times ---------------------------
        try:
            total_duration = _get_duration(video_path)
        except Exception as exc:
            log_queue.put("ERROR: Could not determine video duration: {}".format(exc))
            with open(result_path, 'w') as fp:
                _json.dump({"error": "duration probe failed: {}".format(exc)}, fp)
            return

        # Skip first/last 10%
        margin = total_duration * 0.10
        usable_start = margin
        usable_end = total_duration - margin - segment_duration
        if usable_end <= usable_start:
            # Video too short for sampling - just analyse the whole thing
            log_queue.put("Video too short for sampling ({:.0f}s), analysing full file ...".format(total_duration))
            num_segments = 1
            starts = [0]
        else:
            if num_segments == 1:
                starts = [usable_start + (usable_end - usable_start) / 2]
            else:
                step = (usable_end - usable_start) / (num_segments - 1)
                starts = [usable_start + i * step for i in range(num_segments)]

        log_queue.put("Video duration: {:.0f}s, analysing {} segment(s) ...".format(
            total_duration, len(starts)))

        # --- Process each segment ------------------------------------
        all_offsets = []
        all_confs = []
        segments_with_face = 0
        work_dir = tempfile.mkdtemp(prefix="lipsync_")

        try:
            for idx, start in enumerate(starts):
                seg_progress_base = 10 + int(80 * idx / len(starts))
                seg_progress_end = 10 + int(80 * (idx + 1) / len(starts))
                prog_queue.put(seg_progress_base)

                log_queue.put("Segment {}/{}: extracting {:.0f}s at t={:.0f}s ...".format(
                    idx + 1, len(starts), segment_duration, start))

                seg_video = os.path.join(work_dir, "seg_{:03d}.mkv".format(idx))
                try:
                    _extract_segment(video_path, start, segment_duration, seg_video)
                except Exception as exc:
                    log_queue.put("  Segment {} extraction failed: {}".format(idx + 1, exc))
                    continue

                if not os.path.exists(seg_video) or os.path.getsize(seg_video) < 1024:
                    log_queue.put("  Segment {} produced empty file, skipping.".format(idx + 1))
                    continue

                try:
                    offsets, confs, dists, max_conf, min_dist, _, has_face = pipeline.inference(
                        video_path=seg_video,
                    )
                except Exception as exc:
                    log_queue.put("  Segment {} inference failed: {}".format(idx + 1, exc))
                    continue

                if not offsets or not has_face:
                    log_queue.put("  Segment {}: no face detected.".format(idx + 1))
                    continue

                # Best track in this segment
                best_idx = confs.index(max(confs))
                seg_offset = offsets[best_idx]
                seg_conf = confs[best_idx]

                log_queue.put("  Segment {}: offset={} frames, confidence={:.2f}".format(
                    idx + 1, seg_offset, seg_conf))

                all_offsets.append(seg_offset)
                all_confs.append(seg_conf)
                segments_with_face += 1

                prog_queue.put(seg_progress_end)

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        prog_queue.put(92)

        # --- Aggregate results ---------------------------------------
        if not all_offsets:
            log_queue.put("No face tracks detected in any segment.")
            with open(result_path, 'w') as fp:
                _json.dump({"offset_frames": 0, "confidence": 0, "min_dist": 0,
                            "has_face": False, "segments_analysed": len(starts),
                            "segments_with_face": 0}, fp)
            prog_queue.put(100)
            return

        # Filter to only segments that individually meet the confidence threshold
        confident_offsets = []
        confident_confs = []
        for off, conf in zip(all_offsets, all_confs):
            if conf >= confidence_threshold:
                confident_offsets.append(off)
                confident_confs.append(conf)

        num_confident = len(confident_offsets)

        if confident_offsets:
            median_offset = int(round(statistics.median(confident_offsets)))
            mean_conf = statistics.mean(confident_confs)
        else:
            median_offset = int(round(statistics.median(all_offsets)))
            mean_conf = statistics.mean(all_confs)

        log_queue.put(
            "Aggregated: median offset={} frames (from {} confident segment(s)), "
            "mean confident confidence={:.2f}, "
            "{}/{} segments had faces".format(
                median_offset, num_confident, mean_conf,
                segments_with_face, len(starts))
        )

        with open(result_path, 'w') as fp:
            _json.dump({
                "offset_frames":          median_offset,
                "confidence":             float(mean_conf),
                "num_confident_segments": num_confident,
                "has_face":               True,
                "segments_analysed":      len(starts),
                "segments_with_face":     segments_with_face,
                "all_offsets":            all_offsets,
                "all_confidences":        [round(c, 2) for c in all_confs],
            }, fp)
        prog_queue.put(100)

    except Exception as exc:
        import traceback
        log_queue.put("ERROR during SyncNet analysis: {}".format(exc))
        log_queue.put(traceback.format_exc())
        with open(result_path, 'w') as fp:
            _json.dump({"error": str(exc)}, fp)


def on_library_management_file_test(data, task_data_store=None, file_metadata=None):
    """
    Runner function - enables additional actions during the library management file tests.

    The 'data' object argument includes:
        library_id                      - The library that the current task is associated with
        path                            - String containing the full path to the file being tested.
        issues                          - List of currently found issues for not processing the file.
        add_file_to_pending_tasks       - Boolean, is the file currently marked to be added to the queue for processing.
        priority_score                  - Integer, an additional score that can be added to set the position of the new task in the task queue.
        shared_info                     - Dictionary, information provided by previous plugin runners. This can be appended to for subsequent runners.

    :param data:
    :return:

    """
    abspath = data.get('path')

    if already_processed(abspath, file_metadata=file_metadata):
        logger.debug("File already processed by auto_lipsync: %s", abspath)
        return data

    if not file_has_video_and_audio(abspath):
        logger.debug("File lacks video+audio streams, skipping: %s", abspath)
        return data

    data['add_file_to_pending_tasks'] = True
    logger.debug("File '%s' queued for lip sync analysis.", abspath)
    return data


def on_worker_process(data, task_data_store=None, file_metadata=None):
    """
    Runner function - enables additional configured processing jobs during the worker stages of a task.

    The 'data' object argument includes:
        task_id                 - Integer, unique identifier of the task.
        worker_log              - Array, the log lines that are being tailed by the frontend. Can be left empty.
        library_id              - Number, the library that the current task is associated with.
        exec_command            - Array, a subprocess command that Unmanic should execute. Can be empty.
        current_command         - Array, shared list for updating the worker's "current command" text in the UI (last entry wins).
        command_progress_parser - Function, a function that Unmanic can use to parse the STDOUT of the command to collect progress stats. Can be empty.
        file_in                 - String, the source file to be processed by the command.
        file_out                - String, the destination that the command should output (may be the same as the file_in if necessary).
        original_file_path      - String, the absolute path to the original file.
        repeat                  - Boolean, should this runner be executed again once completed with the same variables.

    :param data:
    :return:

    """
    data['exec_command'] = []
    data['repeat'] = False

    file_in = data.get('file_in')
    file_out = data.get('file_out')
    original_file_path = data.get('original_file_path')
    worker_log = data.get('worker_log', [])

    if already_processed(original_file_path, file_metadata=file_metadata):
        worker_log.append("File already processed by auto_lipsync, skipping.")
        data['worker_log'] = worker_log
        return data

    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # ------------------------------------------------------------------
    # Two-pass approach via TaskDataStore:
    #   Pass 1  - Run SyncNet analysis in a child process
    #   Pass 2  - Apply ffmpeg itsoffset correction (if needed)
    # ------------------------------------------------------------------
    from unmanic.libs.task import TaskDataStore

    phase = TaskDataStore.get_task_state("auto_lipsync_phase")

    # ======== PASS 1: SyncNet analysis ================================
    if phase is None:
        worker_log.append("=== Auto Lip Sync: Pass 1 - SyncNet analysis ===")
        data['worker_log'] = worker_log

        from unmanic.libs.unplugins.child_process import PluginChildProcess

        cache_dir = os.path.dirname(file_out)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        result_path = os.path.join(cache_dir, "syncnet_result.json")

        num_segments = settings.get_setting('num_segments')
        segment_duration = settings.get_setting('segment_duration')
        conf_threshold = settings.get_setting('confidence_threshold')

        proc = PluginChildProcess(plugin_id=PLUGIN_ID, data=data)
        success = proc.run(analyze_sync_child, file_in, result_path, MODELS_DIR,
                           num_segments, segment_duration, conf_threshold)

        if not success:
            worker_log.append("SyncNet child process failed.")
            data['worker_log'] = worker_log
            return data

        # Read child-process results
        try:
            with open(result_path) as fp:
                result = json.load(fp)
        except Exception as exc:
            worker_log.append("Failed to read SyncNet results: {}".format(exc))
            data['worker_log'] = worker_log
            return data
        finally:
            if os.path.exists(result_path):
                os.remove(result_path)

        if result.get('error'):
            worker_log.append("SyncNet error: {}".format(result['error']))
            data['worker_log'] = worker_log
            return data

        # --- Evaluate whether correction is needed --------------------
        has_face = result.get('has_face', False)
        offset_frames = result.get('offset_frames', 0)
        confidence = result.get('confidence', 0)
        num_confident = result.get('num_confident_segments', 0)

        # SyncNet internally resamples video to 25fps, so the offset is
        # in 25fps frames regardless of the source video's frame rate.
        syncnet_fps = 25.0
        offset_ms = (offset_frames / syncnet_fps) * 1000.0

        worker_log.append(
            "SyncNet: offset={} frames ({:.1f} ms at {}fps internal), confidence={:.2f}, "
            "confident segments={}"
            .format(offset_frames, offset_ms, int(syncnet_fps), confidence, num_confident)
        )

        min_offset = settings.get_setting('min_offset_ms')
        max_offset = settings.get_setting('max_offset_ms')
        min_confident = settings.get_setting('min_confident_segments')

        skip_reason = None
        if not has_face:
            skip_reason = "no_face"
            worker_log.append("No face detected - cannot perform lip sync analysis.")
        elif num_confident < min_confident:
            skip_reason = "insufficient_confident_segments"
            worker_log.append(
                "Only {} confident segment(s), need at least {}. Skipping correction."
                .format(num_confident, min_confident)
            )
        elif abs(offset_ms) < min_offset:
            skip_reason = "within_tolerance"
            worker_log.append(
                "Offset {:.1f} ms below minimum {} ms, no correction needed."
                .format(abs(offset_ms), min_offset)
            )
        elif abs(offset_ms) > max_offset:
            skip_reason = "exceeded_max"
            worker_log.append(
                "Offset {:.1f} ms exceeds safety cap {} ms, likely false positive."
                .format(abs(offset_ms), max_offset)
            )

        if skip_reason:
            # Mark as processed so we don't re-analyse on the next scan
            if file_metadata:
                file_metadata.set({
                    'processed':  True,
                    'result':     skip_reason,
                    'offset_ms':  round(offset_ms, 1),
                    'confidence': round(confidence, 2),
                }, use_source_scope=True)
            data['worker_log'] = worker_log
            return data

        # Correction is needed - store state and repeat for pass 2
        TaskDataStore.set_task_state("auto_lipsync_phase", "correction")
        TaskDataStore.set_task_state("auto_lipsync_offset_ms", offset_ms)
        TaskDataStore.set_task_state("auto_lipsync_offset_frames", offset_frames)
        TaskDataStore.set_task_state("auto_lipsync_confidence", confidence)

        worker_log.append(
            "Correction needed: {:.1f} ms offset will be applied in pass 2."
            .format(offset_ms)
        )
        data['worker_log'] = worker_log
        data['repeat'] = True
        return data

    # ======== PASS 2: ffmpeg itsoffset correction =====================
    if phase == "correction":
        offset_ms = TaskDataStore.get_task_state("auto_lipsync_offset_ms")
        offset_frames = TaskDataStore.get_task_state("auto_lipsync_offset_frames")
        confidence = TaskDataStore.get_task_state("auto_lipsync_confidence")

        if not offset_ms:
            worker_log.append("No offset stored, nothing to correct.")
            data['worker_log'] = worker_log
            return data

        offset_seconds = abs(offset_ms) / 1000.0

        worker_log.append(
            "=== Auto Lip Sync: Pass 2 - ffmpeg correction ==="
        )
        worker_log.append(
            "Applying {:.1f} ms ({} frame) correction via itsoffset."
            .format(offset_ms, offset_frames)
        )

        # SyncNet offset convention:
        #   positive offset  -> audio leads video  -> delay audio
        #   negative offset  -> audio lags  video  -> delay video (advance audio)
        #
        # ffmpeg -itsoffset applies a delay to the NEXT -i input.

        if offset_ms > 0:
            # Audio is ahead of video: delay the second input (audio source)
            cmd = [
                'ffmpeg',
                '-i', file_in,
                '-itsoffset', str(offset_seconds),
                '-i', file_in,
                '-map', '0:v',
                '-map', '1:a',
                '-map', '0:s?',
                '-map', '0:t?',
                '-c', 'copy',
                '-y',
                file_out,
            ]
        else:
            # Audio is behind video: delay the first input (video source)
            cmd = [
                'ffmpeg',
                '-itsoffset', str(offset_seconds),
                '-i', file_in,
                '-i', file_in,
                '-map', '0:v',
                '-map', '1:a',
                '-map', '1:s?',
                '-map', '1:t?',
                '-c', 'copy',
                '-y',
                file_out,
            ]

        data['exec_command'] = cmd
        data['worker_log'] = worker_log

        # Store for the postprocessor
        TaskDataStore.set_task_state("auto_lipsync_corrected", True)
        TaskDataStore.set_task_state("auto_lipsync_correction_ms", round(offset_ms, 1))
        return data

    return data


def on_postprocessor_task_results(data, task_data_store=None, file_metadata=None):
    """
    Runner function - provides a means for additional postprocessor functions based on the task success.

    The 'data' object argument includes:
        final_cache_path                - The path to the final cache file that was then used as the source for all destination files.
        library_id                      - The library that the current task is associated with.
        task_processing_success         - Boolean, did all task processes complete successfully.
        file_move_processes_success     - Boolean, did all postprocessor movement tasks complete successfully.
        destination_files               - List containing all file paths created by postprocessor file movements.
        source_data                     - Dictionary containing data pertaining to the original source file.

    :param data:
    :return:

    """
    if not data.get('task_processing_success'):
        logger.debug("Task did not succeed; not marking as processed.")
        return data

    if not file_metadata:
        return data

    from unmanic.libs.task import TaskDataStore

    corrected = TaskDataStore.get_task_state("auto_lipsync_corrected")
    correction_ms = TaskDataStore.get_task_state("auto_lipsync_correction_ms")
    confidence = TaskDataStore.get_task_state("auto_lipsync_confidence")

    metadata = {'processed': True}
    if corrected:
        metadata['result'] = 'corrected'
        metadata['correction_ms'] = correction_ms
        metadata['confidence'] = round(confidence, 2) if confidence else None
    else:
        metadata['result'] = 'analyzed'

    # Source scope: keyed to original file fingerprint (covers unchanged-file case)
    file_metadata.set(metadata, use_source_scope=True)
    # Destination scope: keyed to output file fingerprint (covers corrected-file case)
    file_metadata.set(metadata, use_source_scope=False)

    logger.debug("Marked file as processed via file_metadata (corrected=%s).", corrected)
    return data
