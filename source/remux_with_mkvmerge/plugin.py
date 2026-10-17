#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import re
import shutil
import subprocess

from unmanic.libs.unplugins.settings import PluginSettings

from remux_with_mkvmerge.lib.ffmpeg.probe import ffprobe_file, FFProbeError

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.remux_with_mkvmerge")

# Stream types that mkvmerge must carry over for a remux to be considered safe
CHECKED_STREAM_TYPES = ['video', 'audio', 'subtitle']


class Settings(PluginSettings):
    settings = {
        "target_extensions":       "ts,m2ts,mts",
        "skip_if_streams_dropped": True,
        "fail_on_warnings":        False,
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "target_extensions":       {
                "label":       "File extensions to remux (comma separated)",
                "description": "Only files with these extensions will be remuxed to MKV with mkvmerge.",
            },
            "skip_if_streams_dropped": {
                "label":       "Skip files where mkvmerge would drop video/audio/subtitle streams",
                "description": "Compares the streams found by ffprobe with the tracks identified by mkvmerge. "
                               "If mkvmerge cannot handle a stream, the file is left untouched.",
            },
            "fail_on_warnings":        {
                "label":       "Fail the task if mkvmerge exits with warnings",
                "description": "mkvmerge exits with code 1 when it completes with warnings (common with TS "
                               "timestamp discontinuities). By default these are treated as success.",
            },
        }

    def get_target_extensions(self):
        extensions = self.get_setting('target_extensions') or ''
        return [ext.strip().lstrip('.').lower() for ext in extensions.split(',') if ext.strip()]


def mkvmerge_identify(path):
    """
    Run 'mkvmerge -J' against a file and return the parsed JSON.
    Returns None if mkvmerge could not produce identification output.

    :param path:
    :return:
    """
    try:
        result = subprocess.run(['mkvmerge', '-J', path], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, errors='replace', timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.error("Failed to run mkvmerge identify on '%s' - %s", path, e)
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        logger.error("Unable to parse mkvmerge identify output for '%s' - %s", path, result.stderr.strip())
        return None


def count_ffprobe_streams(path):
    """
    Count the video/audio/subtitle streams that ffprobe finds in a file.
    Streams without a detected codec (eg. PIDs listed in the PMT that carry no data) and
    attached pictures are ignored.
    Returns None if the file could not be probed.

    :param path:
    :return:
    """
    try:
        probe_info = ffprobe_file(path)
    except FFProbeError:
        return None
    counts = {stream_type: 0 for stream_type in CHECKED_STREAM_TYPES}
    for stream in probe_info.get('streams', []):
        codec_type = stream.get('codec_type')
        if codec_type not in counts:
            continue
        if stream.get('codec_name') in (None, '', 'unknown'):
            continue
        if stream.get('disposition', {}).get('attached_pic'):
            continue
        counts[codec_type] += 1
    return counts


def check_file_can_be_remuxed(path, settings):
    """
    Run all checks that determine if a file can (and should) be remuxed with mkvmerge.

    :param path:
    :param settings:
    :return: (bool, reason)
    """
    # Only process the configured file extensions
    extension = os.path.splitext(path)[1].lstrip('.').lower()
    if extension not in settings.get_target_extensions():
        return False, "extension '{}' is not configured for remuxing".format(extension)

    # Ensure mkvmerge is installed
    if not shutil.which('mkvmerge'):
        return False, "mkvmerge is not installed. Restart the Unmanic container to run the plugin's init.d installer"

    # Ensure mkvmerge can read the file
    identify = mkvmerge_identify(path)
    if identify is None:
        return False, "mkvmerge was unable to identify the file"
    if identify.get('errors'):
        return False, "mkvmerge reported errors identifying the file: {}".format('; '.join(identify.get('errors')))
    container = identify.get('container', {})
    if not container.get('recognized'):
        return False, "mkvmerge does not recognise the file's container format"
    if not container.get('supported'):
        return False, "mkvmerge does not support the '{}' container format".format(container.get('type'))

    # Ensure there is a video track that mkvmerge can read
    mkvmerge_counts = {stream_type: 0 for stream_type in CHECKED_STREAM_TYPES}
    for track in identify.get('tracks', []):
        track_type = track.get('type')
        if track_type == 'subtitles':
            track_type = 'subtitle'
        if track_type in mkvmerge_counts:
            mkvmerge_counts[track_type] += 1
    if mkvmerge_counts['video'] < 1:
        return False, "mkvmerge did not find any video tracks it can process"

    # Ensure mkvmerge will not drop any streams that ffprobe can see
    if settings.get_setting('skip_if_streams_dropped'):
        ffprobe_counts = count_ffprobe_streams(path)
        if ffprobe_counts is None:
            return False, "ffprobe was unable to probe the file to compare streams"
        for stream_type in CHECKED_STREAM_TYPES:
            if mkvmerge_counts[stream_type] < ffprobe_counts[stream_type]:
                return False, "mkvmerge would drop {} stream(s) (ffprobe found {}, mkvmerge found {})".format(
                    stream_type, ffprobe_counts[stream_type], mkvmerge_counts[stream_type])

    for warning in identify.get('warnings', []):
        logger.info("mkvmerge identify warning for '%s' - %s", path, warning)

    return True, "file can be remuxed with mkvmerge"


class MkvmergeProgressParser(object):
    """
    Parses mkvmerge 'Progress: NN%' output lines
    """

    def __init__(self):
        self.percent = 0

    def parse_progress(self, line_text):
        match = re.search(r'Progress:\s*(\d+)%', line_text or '')
        if match:
            self.percent = int(match.group(1))
        return {
            'percent': str(self.percent)
        }


def on_library_management_file_test(data, **kwargs):
    """
    Runner function - enables additional actions during the library management file tests.

    The 'data' object argument includes:
        library_id                      - The library that the current task is associated with
        path                            - String containing the full path to the file being tested.
        issues                          - List of currently found issues for not processing the file.
        add_file_to_pending_tasks       - Boolean, is the file currently marked to be added to the queue for processing.
        priority_score                  - Integer, an additional score that can be added to set the position of the new task in the task queue.
        shared_info                     - Dictionary, information provided by previous plugin runners. This can be appended to for subsequent runners.

    If this runner needs persisted file metadata, update the function signature to accept the injected
    `file_metadata` keyword helper:

        from unmanic.libs.metadata import UnmanicFileMetadata

        def on_library_management_file_test(
            data,
            file_metadata: type[UnmanicFileMetadata] | None = None,
        ):
            pass

    Only declare this helper if you actually use it.

    :param data:
    :return:

    """
    abspath = data.get('path')

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    can_remux, reason = check_file_can_be_remuxed(abspath, settings)
    if can_remux:
        data['add_file_to_pending_tasks'] = True
        logger.debug("File '%s' should be added to task list. %s.", abspath, reason)
    else:
        logger.debug("File '%s' will not be remuxed - %s.", abspath, reason)

    return data


def on_worker_process(data, **kwargs):
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

    If this runner needs shared task state or persisted file metadata, update the function signature
    to accept the injected keyword helpers:

        from unmanic.libs.metadata import UnmanicFileMetadata
        from unmanic.libs.task import TaskDataStore

        def on_worker_process(
            data,
            task_data_store: type[TaskDataStore] | None = None,
            file_metadata: type[UnmanicFileMetadata] | None = None,
        ):
            pass

    Declare only the helpers you use. If you only need shared task state, omit `file_metadata`.

    **Shared task & runner state**
    Plugins can store shared, cross‐plugin and even cross‐process state via `TaskDataStore`:

        from unmanic.libs.task import TaskDataStore

        # Store mutable per‐task values:
        TaskDataStore.set_task_state("source_file_size", source_file_size)
        # read it back later (same or other plugin):
        p = TaskDataStore.get_task_state("source_file_size")

        # Store immutable runner‐scoped values:
        TaskDataStore.set_runner_value("probe_info", {...})
        val = TaskDataStore.get_runner_value("probe_info")

    **Spawning your own child process**
    Instead of setting `exec_command`, you can perform complex or Python‐only work in a separate process while still reporting logs & progress:

        import time

        from unmanic.libs.unplugins.child_process import PluginChildProcess

        proc = PluginChildProcess(plugin_id="<your_plugin_id>", data=data)

        def child_work(source_path, log_queue=None, prog_queue=None):
            # PluginChildProcess injects log_queue and prog_queue as keyword args.
            # any positional args should be passed to proc.run(...) first
            log_queue.put(f"Starting work for {source_path}")
            for i in range(10):
                # emit a UI log line:
                log_queue.put(f"step {i}/10 completed")
                # emit progress 0–100:
                prog_queue.put((i + 1) * 10)
                time.sleep(1)

        # Runs child_work in its own process, returns True if exit code==0
        success = proc.run(child_work, data["file_in"])
        if success:
            repaired_cache_path = data["file_out"]
            # Child-process plugins should publish the new cache artifact as
            # both file_out and file_in when later worker plugins in the chain
            # need to consume it.
            data["file_in"] = repaired_cache_path

    In this mode the `PluginChildProcess` helper:
      1. Spawns the child via `multiprocessing.Process`.
      2. Calls your target with `target(*args, **kwargs)` after injecting `log_queue` and `prog_queue` into the keyword arguments.
      3. Registers its PID & start‐time with the worker’s `default_progress_parser`.
      4. Drains `log_queue` → `data["worker_log"]` for UI tail.
      5. Drains `prog_queue` → `command_progress_parser(line_text)` to update the progress bar.
      6. Will unset the child process PID on exit to reset all tracked subprocess metrics in the Unmanic Worker (CPU, memory, progress, etc.).

    When using `PluginChildProcess`, Unmanic does not automatically promote a
    newly created `file_out` into `file_in` for later worker plugins in the
    chain. If your child process creates a new cache artifact that subsequent
    worker plugins should process, update both `data["file_out"]` and
    `data["file_in"]` to that new path.

    :param data:
    :return:

    """
    # Default to no command required
    data['exec_command'] = []
    data['repeat'] = False

    abspath = data.get('file_in')

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    can_remux, reason = check_file_can_be_remuxed(abspath, settings)
    if not can_remux:
        logger.info("Skipping mkvmerge remux of '%s' - %s.", abspath, reason)
        data['worker_log'].append("\nSkipping mkvmerge remux - {}.\n".format(reason))
        return data

    # Set the output file with an MKV extension
    file_out = "{}.mkv".format(os.path.splitext(data.get('file_out'))[0])
    data['file_out'] = file_out

    mkvmerge_args = ['mkvmerge', '-o', file_out, abspath]
    if settings.get_setting('fail_on_warnings'):
        data['exec_command'] = mkvmerge_args
    else:
        # mkvmerge exits with 1 when it completes with warnings. Treat that as success.
        data['exec_command'] = [
            'sh', '-c',
            '"$@"; rc=$?; '
            'if [ "$rc" -eq 1 ]; then echo "mkvmerge completed with warnings (exit code 1)"; exit 0; fi; '
            'exit "$rc"',
            'mkvmerge',
        ] + mkvmerge_args

    data['command_progress_parser'] = MkvmergeProgressParser().parse_progress

    return data
