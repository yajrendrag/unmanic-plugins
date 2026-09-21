#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     21 September 2026, (5:25 PM)

    Copyright:
        Copyright (C) 2025 Jay Gardner

        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

"""
"""
    Convert bitmap subs to srt

    This plugin detects bitmap subtitle streams (hdmv_pgs_subtitle, dvd_subtitle)
    in video files and extracts them as SRT text files using Tesseract OCR.

    lib/bitmap_subs.py decodes the subtitle images and lib/subtitle_ocr.py runs
    Tesseract on them and writes the SRT files. Each stream is converted by
    lib/convert_stream.py in its own process, which is registered with the Unmanic
    worker so the GUI shows progress, elapsed time and time remaining, and so pause
    and terminate apply to it and its Tesseract processes.

    The SRT files are created in the task cache during the worker stage and copied
    next to the final output file(s) in the postprocessor task results stage, after
    Unmanic (or a plugin such as mover2) has moved the file to its destination.
    Converted files are recorded in Unmanic's file metadata database.

"""
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from unmanic.libs.unplugins.settings import PluginSettings

from convert_bitmap_subs_to_srt.lib.ffmpeg import Probe
from convert_bitmap_subs_to_srt.lib import bitmap_subs, subtitle_ocr

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.convert_bitmap_subs_to_srt")

# Task data store key for the SRT files created by the worker
SRT_FILES_KEY = 'srt_files'

# Helper script that converts one stream in its own process
CONVERT_STREAM_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib', 'convert_stream.py')


class Settings(PluginSettings):
    settings = {
        "languages_to_extract": "",
        "tesseract_language": "auto",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)

        self.form_settings = {
            "languages_to_extract": {
                "label": "Subtitle languages to extract (comma-separated, leave empty for all)",
                "description": "E.g., 'eng,fre,spa'. Leave empty to extract all bitmap subtitles.",
            },
            "tesseract_language": {
                "label": "Tesseract OCR language",
                "description": "'auto' picks the language from each subtitle stream's language tag "
                               "(falls back to eng). Or give a Tesseract language code (e.g., eng, deu, fra, spa); "
                               "multiple languages can be specified with '+' (e.g., eng+fra).",
            },
        }


def get_bitmap_streams(probe):
    """
    Get all supported bitmap subtitle streams from probe data.

    :param probe: Probe object with file info
    :return: List of bitmap stream info dicts
    """
    bitmap_streams = []
    streams = probe.get('streams', [])

    subtitle_index = 0
    for stream in streams:
        if stream.get('codec_type') != 'subtitle':
            continue

        codec_name = stream.get('codec_name', '').lower()
        if bitmap_subs.is_supported(codec_name):
            bitmap_streams.append({
                'index': stream.get('index'),
                'subtitle_index': subtitle_index,
                'codec_name': codec_name,
                'tags': stream.get('tags', {}),
            })
        subtitle_index += 1

    return bitmap_streams


def filter_streams_by_language(streams, languages_filter):
    """
    Filter streams by language settings.

    :param streams: List of stream info dicts
    :param languages_filter: Comma-separated language codes or empty for all
    :return: Filtered list of streams
    """
    if not languages_filter or not languages_filter.strip():
        return streams

    languages = [lang.strip().lower() for lang in languages_filter.split(',') if lang.strip()]
    if not languages:
        return streams

    filtered = []
    for stream in streams:
        lang = stream.get('tags', {}).get('language', '').lower()
        if lang in languages:
            filtered.append(stream)

    return filtered


def generate_output_suffix(stream, stream_counter, used_suffixes):
    """
    Generate the SRT filename suffix from the stream's language and title tags.

    The SRT file is named '<video name>.<suffix>.srt', e.g. 'movie.eng.Forced.srt'.

    :param stream: Stream info dict
    :param stream_counter: Counter for streams without language tag
    :param used_suffixes: Set of already used suffixes
    :return: Tuple of (suffix, updated_counter)
    """
    tags = stream.get('tags', {})
    language = tags.get('language', '').lower()
    title = tags.get('title', '')

    # Build suffix
    suffix_parts = []

    if language:
        suffix_parts.append(language)
    else:
        suffix_parts.append(str(stream_counter))
        stream_counter += 1

    if title:
        # Clean title for filename
        clean_title = re.sub(r'[\s/\\]', '-', title)
        clean_title = re.sub(r'[^\w\-.]', '', clean_title)
        if clean_title:
            suffix_parts.append(clean_title)

    suffix = '.'.join(suffix_parts)

    # Handle duplicates
    unique_suffix = suffix
    dup_counter = 1
    while unique_suffix in used_suffixes:
        unique_suffix = f"{suffix}.{dup_counter}"
        dup_counter += 1

    used_suffixes.add(unique_suffix)
    return unique_suffix, stream_counter


def already_converted(file_metadata):
    """
    Check the file metadata database for a previous conversion of this file.

    :param file_metadata: UnmanicFileMetadata helper bound to the current file or task
    :return: Boolean
    """
    try:
        record = file_metadata.get()
    except Exception as e:
        logger.debug(f"Unable to read file metadata: {e}")
        return False
    if record.get('converted'):
        logger.debug(f"File's bitmap subtitles were previously converted: {record.get('languages')}")
        return True
    return False


def mark_converted(file_metadata, source_path, languages, srt_files):
    """
    Record the conversion in the file metadata database.

    The record is set on both the source file and the destination file(s), so neither
    is queued again by a later library scan. Unmanic commits the record once the
    postprocessor has finished.

    :param file_metadata: UnmanicFileMetadata helper bound to the current task
    :param source_path: Path of the original source file
    :param languages: List of converted stream languages
    :param srt_files: List of SRT file names written next to the first destination file
    """
    record = {
        'converted': True,
        'languages': languages,
        'srt_files': srt_files,
    }
    try:
        file_metadata.set(record)
        file_metadata.set(record, use_source_scope=True)
        logger.info(f"Bitmap subtitle conversion for '{source_path}' recorded in file metadata.")
    except Exception as e:
        logger.error(f"Error recording conversion in file metadata: {e}")


class ProgressReporter:
    """
    Reports progress to the Unmanic GUI through the worker's progress parser and
    checks whether the task has been cancelled.

    Each stream gets an equal share of the progress bar, which fills as its OCR batches finish.
    The helper process for the current stream is registered with the worker, which gives
    the GUI its elapsed time (for the time remaining estimate) and CPU/memory stats, and
    lets Unmanic pause or terminate it along with its Tesseract processes.
    """

    def __init__(self, data, stream_count):
        self.parser = data.get('command_progress_parser')
        self.stream_count = max(1, stream_count)
        self.stream_number = 0
        # One start time for all streams, so the elapsed time does not restart with each helper process
        self.start_time = time.time()
        self.cancelled = False

    def update(self, stream_number, images_done, images_total, pid=None):
        """
        Send the overall percentage to the worker.

        :return: False if the task has been cancelled
        """
        if self.parser is None:
            return True
        fraction = images_done / images_total if images_total else 1
        percent = int((stream_number + fraction) / self.stream_count * 100)
        try:
            status = self.parser(str(percent), pid=pid, proc_start_time=self.start_time) or {}
        except Exception as e:
            logger.debug(f"Unable to report progress: {e}")
            return True
        if status.get('killed'):
            self.cancelled = True
        return not self.cancelled

    def finish(self):
        """Clear the progress so it does not carry over to the next runner."""
        if self.parser is None:
            return
        try:
            self.parser(None, unset=True)
        except Exception as e:
            logger.debug(f"Unable to clear progress: {e}")


def convert_stream(file_in, stream, languages, work_dir, output_path, progress, stream_number):
    """
    Convert one stream to an SRT file in a helper process, relaying its progress to the worker.

    :return: Number of subtitles written, or None if the conversion failed or was cancelled
    """
    args = {
        'file_in':   file_in,
        'stream':    stream,
        'languages': languages,
        'work_dir':  work_dir,
        'output':    output_path,
    }
    stderr_path = os.path.join(work_dir, f"convert_stream_{stream['index']}.err")
    with open(stderr_path, 'w+') as stderr_file:
        proc = subprocess.Popen([sys.executable, CONVERT_STREAM_SCRIPT, json.dumps(args)],
                                stdout=subprocess.PIPE, stderr=stderr_file, text=True)
        cue_count = None
        try:
            for line in proc.stdout:
                parts = line.split()
                if len(parts) == 3 and parts[0] == 'PROGRESS':
                    if not progress.update(stream_number, int(parts[1]), int(parts[2]), pid=proc.pid):
                        break
                elif len(parts) == 2 and parts[0] == 'RESULT':
                    cue_count = int(parts[1])
        finally:
            if progress.cancelled and proc.poll() is None:
                proc.terminate()
            proc.wait()

        # Negative codes mean killed by a signal. The helper exits with 128 + signal number when it
        # catches SIGTERM itself.
        if proc.returncode < 0 or proc.returncode == 128 + signal.SIGTERM:
            # Normally Unmanic terminating the worker before our next progress check
            logger.info(f"Conversion of stream {stream['index']} was terminated")
            progress.cancelled = True
        if progress.cancelled:
            return None
        if proc.returncode != 0:
            stderr_file.seek(0)
            logger.error(f"Converting {stream['codec_name']} stream {stream['index']} failed: "
                         f"{stderr_file.read().strip()[-1000:]}")
            return None
    return cue_count


def run_extraction_process(data, streams, settings):
    """
    Run the bitmap subtitle extraction and OCR conversion process.

    The SRT files are written to a folder in the task cache. They are copied to
    their final location by on_postprocessor_task_results.

    :param data: Plugin data dict
    :param streams: List of bitmap stream info to extract
    :param settings: Plugin settings
    :return: Tuple of (list of dicts describing the SRT files ('path', 'suffix', 'language'),
             boolean that is True if the task was cancelled)
    """
    file_in = data.get('file_in')

    # Keep the SRT files in the task cache directory until the postprocessor runs
    srt_dir = os.path.join(os.path.dirname(data.get('file_out')), 'convert_bitmap_subs_to_srt')
    os.makedirs(srt_dir, exist_ok=True)

    # Get Tesseract language setting
    tess_lang_setting = settings.get_setting('tesseract_language') or 'auto'

    try:
        installed_languages = subtitle_ocr.available_languages()
    except Exception as e:
        logger.error(f"Tesseract is not available ({e}). Please ensure the init.d script ran successfully.")
        return [], False

    # Track used suffixes and stream counter for unnamed streams
    used_suffixes = set()
    stream_counter = 1
    srt_files = []
    progress = ProgressReporter(data, len(streams))

    # Create temp directory for intermediate files
    with tempfile.TemporaryDirectory(prefix='bitmap_sub_extract_') as temp_dir:
        for stream_number, stream in enumerate(streams):
            if not progress.update(stream_number, 0, 1):
                break

            stream_index = stream['index']
            codec_name = stream['codec_name']
            language = stream.get('tags', {}).get('language', '')

            logger.info(f"Processing {codec_name} stream {stream_index} (subtitle:{stream['subtitle_index']}), "
                        f"language: {language or 'unknown'}")

            # Generate output filename
            suffix, stream_counter = generate_output_suffix(stream, stream_counter, used_suffixes)
            output_path = os.path.join(srt_dir, f"{suffix}.srt")

            tess_lang, missing = subtitle_ocr.resolve_languages(tess_lang_setting, language, installed_languages)
            if missing:
                logger.warning(f"Tesseract language(s) not installed: {', '.join(missing)}. Using '{tess_lang}'.")
            logger.debug(f"Converting stream {stream_index} with Tesseract language '{tess_lang}'")

            helper_stream = {k: stream[k] for k in ('index', 'subtitle_index', 'codec_name')}
            cue_count = convert_stream(file_in, helper_stream, tess_lang, temp_dir, output_path, progress,
                                       stream_number)
            if progress.cancelled:
                break

            if cue_count:
                logger.info(f"Successfully converted {codec_name} stream {stream_index} ({cue_count} subtitles) to {output_path}")
                srt_files.append({
                    'path':     output_path,
                    'suffix':   suffix,
                    'language': language or f"stream{stream_index}",
                })
            elif cue_count == 0:
                logger.warning(f"No text was recognised in stream {stream_index}")
                if os.path.exists(output_path):
                    os.remove(output_path)

    progress.finish()
    if progress.cancelled:
        logger.info(f"Task was cancelled. Stopped converting subtitles for '{data.get('original_file_path')}'.")
        return [], True
    return srt_files, False


def on_library_management_file_test(data, task_data_store=None, file_metadata=None, **kwargs):
    """
    Runner function - enables additional actions during the library management file tests.

    The 'data' object argument includes:
        library_id                      - The library that the current task is associated with
        path                            - String containing the full path to the file being tested.
        issues                          - List of currently found issues for not processing the file.
        add_file_to_pending_tasks       - Boolean, is the file currently marked to be added to the queue for processing.
        priority_score                  - Integer, an additional score that can be added to set the position of the new task in the task queue.
        shared_info                     - Dictionary, information provided by previous plugin runners.

    :param data:
    :return:
    """
    # Configure settings object
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    abspath = data.get('path')

    if file_metadata is None:
        logger.error("This version of Unmanic does not provide the file metadata database. "
                     "The plugin cannot track converted files, so no files will be queued.")
        return data

    # Check if already converted
    if already_converted(file_metadata):
        logger.debug(f"File '{abspath}' has previously had bitmap subtitles converted.")
        return data

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if 'ffprobe' in data.get('shared_info', {}):
        if not probe.set_probe(data.get('shared_info', {}).get('ffprobe')):
            return data
    elif not probe.file(abspath):
        return data

    # Set probe to shared info for subsequent runners
    if 'shared_info' not in data:
        data['shared_info'] = {}
    data['shared_info']['ffprobe'] = probe.get_probe()

    # Get bitmap subtitle streams
    bitmap_streams = get_bitmap_streams(probe)

    if not bitmap_streams:
        logger.debug(f"File '{abspath}' does not contain bitmap subtitle streams.")
        return data

    # Filter by language settings
    languages_filter = settings.get_setting('languages_to_extract')
    filtered_streams = filter_streams_by_language(bitmap_streams, languages_filter)

    if not filtered_streams:
        logger.debug(f"File '{abspath}' has bitmap subtitle streams but none match language filter.")
        return data

    # Mark file for processing
    data['add_file_to_pending_tasks'] = True
    logger.debug(f"File '{abspath}' should be added to task list. Found {len(filtered_streams)} bitmap subtitle streams to extract.")

    return data


def on_worker_process(data, task_data_store=None, file_metadata=None, **kwargs):
    """
    Runner function - enables additional configured processing jobs during the worker stages of a task.

    The 'data' object argument includes:
        task_id                 - Integer, unique identifier of the task.
        worker_log              - Array, the log lines that are being tailed by the frontend.
        library_id              - Number, the library that the current task is associated with.
        exec_command            - Array, a subprocess command that Unmanic should execute.
        command_progress_parser - Function, a function that Unmanic can use to parse the STDOUT of the command.
        file_in                 - String, the source file to be processed by the command.
        file_out                - String, the destination that the command should output.
        original_file_path      - String, the absolute path to the original file.
        repeat                  - Boolean, should this runner be executed again once completed.

    :param data:
    :return:
    """
    # Default to no command - we'll run our own subprocess
    data['exec_command'] = []
    data['repeat'] = False

    # Configure settings
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    file_in = data.get('file_in')
    original_file_path = data.get('original_file_path')

    if task_data_store is None or file_metadata is None:
        logger.error("This version of Unmanic does not provide the task data store and file metadata database.")
        return data

    # Check if already converted
    if already_converted(file_metadata):
        logger.debug(f"File '{original_file_path}' has previously had bitmap subtitles converted.")
        return data

    # Probe the file
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(file_in):
        logger.debug(f"Could not probe file: {file_in}")
        return data

    # Get bitmap subtitle streams
    bitmap_streams = get_bitmap_streams(probe)

    if not bitmap_streams:
        logger.debug(f"No bitmap subtitle streams found in '{file_in}'")
        return data

    # Filter by language settings
    languages_filter = settings.get_setting('languages_to_extract')
    filtered_streams = filter_streams_by_language(bitmap_streams, languages_filter)

    if not filtered_streams:
        logger.debug(f"No bitmap subtitle streams match language filter in '{file_in}'")
        return data

    # Add log message for UI
    worker_log = data.get('worker_log', [])
    worker_log.append(f"Found {len(filtered_streams)} bitmap subtitle stream(s) to extract and convert to SRT")
    data['worker_log'] = worker_log

    # Run the extraction process
    srt_files, cancelled = run_extraction_process(data, filtered_streams, settings)

    if cancelled:
        worker_log.append("Task was cancelled. Subtitle conversion stopped.")
    elif srt_files:
        # Hand the SRT files to on_postprocessor_task_results, which copies them to the destination
        task_data_store.set_runner_value(SRT_FILES_KEY, srt_files)
        worker_log.append(f"Successfully converted {len(srt_files)} subtitle stream(s). "
                          "The SRT files will be written next to the output file after file movement.")
    else:
        worker_log.append("No subtitles were successfully extracted")

    data['worker_log'] = worker_log

    return data


def on_postprocessor_task_results(data, task_data_store=None, file_metadata=None, **kwargs):
    """
    Runner function - provides a means for additional postprocessor functions based on the task success.

    The 'data' object argument includes:
        task_processing_success         - Boolean, did all task processes complete successfully.
        file_move_processes_success     - Boolean, did all postprocessor movement tasks complete successfully.
        destination_files               - List containing all file paths created by postprocessor file movements.
        source_data                     - Dictionary containing data pertaining to the original source file.

    The SRT files created by on_worker_process are copied next to every destination file,
    so they end up wherever Unmanic or a mover plugin (e.g. mover2) put the output file.

    :param data:
    :return:
    """
    if task_data_store is None or file_metadata is None:
        return data

    srt_files = task_data_store.get_runner_value(SRT_FILES_KEY, default=[], runner='on_worker_process')
    if not srt_files:
        return data

    source_path = data.get('source_data', {}).get('abspath')

    # Only write the SRT files if the task was successful
    if not data.get('task_processing_success'):
        logger.warning(f"Task for '{source_path}' failed. The converted SRT files will not be written.")
        return data

    # Write next to each output file. Fall back to the source file location if nothing was moved.
    destinations = []
    for destination in data.get('destination_files') or []:
        if destination and destination not in destinations:
            destinations.append(destination)
    if not destinations:
        logger.warning(f"No destination files were reported for '{source_path}'. Writing SRT files next to the source file.")
        destinations = [source_path]

    written = []
    for destination in destinations:
        base_path = os.path.splitext(destination)[0]
        for srt in srt_files:
            if not os.path.exists(srt['path']):
                logger.error(f"Converted SRT file is missing from the task cache: {srt['path']}")
                continue
            output_path = f"{base_path}.{srt['suffix']}.srt"
            try:
                shutil.copyfile(srt['path'], output_path)
            except Exception as e:
                logger.error(f"Unable to write SRT file '{output_path}': {e}")
                continue
            logger.info(f"Wrote SRT file '{output_path}'")
            written.append(output_path)

    if written:
        first_base = os.path.splitext(destinations[0])[0]
        mark_converted(
            file_metadata,
            source_path,
            [srt['language'] for srt in srt_files],
            [os.path.basename(p) for p in written if p.startswith(first_base + '.')],
        )

    return data
