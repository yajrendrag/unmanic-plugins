#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     6 September 2024, (2:30 PM)

    Copyright:
        Copyright (C) 2024 Jay Gardner

        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

"""
import logging
import os
import re
from pathlib import Path
import whisper

from unmanic.libs.unplugins.settings import PluginSettings

from subtitle_from_audio.lib.ffmpeg import Probe

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.extract_srt_subtitles_to_files")

duration = 3600.00

class Settings(PluginSettings):
    settings = {
        "audio_stream_lang_to_text": "",
        "audio_stream_to_convert_if_lang_not_present": ""
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)

        self.form_settings = {
            "audio_stream_lang_to_text": {
                "label": "Enter language of audio stream to save as subtitle text",
            },
            "audio_stream_to_convert_if_lang_not_present": self.__set_handle_stream_not_found_form_settings(),
        }

    def __set_handle_stream_not_found_form_settings(self):
        values = {
            "description": "Set how plugin should proceed if designated audio stream is not found",
            "label":      "Enter Choice",
            "input_type": "select",
            "select_options": [
                {
                    "value": "abort",
                    "label": "Abort",
                },
                {
                    "value": "pick_first_audio",
                    "label": "Select first audio stream",
                },
            ],
        }
        return values

def srt_already_created(settings, original_file_path, probe_streams):

    # Get settings and test astreams for language
    audio_language_to_convert = settings.get_setting('audio_stream_lang_to_text')
    audio_stream_to_convert_if_lang_not_present = settings.get_setting('audio_stream_to_convert_if_lang_not_present')
    astreams = [i for i in range(len(probe_streams)) if probe_streams[i]['codec_type'] == 'audio' and 'tags' in probe_streams[i] and 'language' in probe_streams[i]['tags'] and probe_streams[i]['tags']['language'] == audio_language_to_convert]
    if astreams == [] and audio_stream_to_convert_if_lang_not_present == "pick_first_audio":
        try:
            audio_language_to_convert = probe_streams[i]['tags']['language']
        except KeyError:
            audio_language_to_convert = '0'
            logger.info("Using number for language name of srt file - user specified language was not present and user selected to create srt from first audio stream")
    elif astreams == [] and audio_stream_to_convert_if_lang_not_present == "abort":
        logger.info("Aborting... language stream not found and user selected abort")
        return True, ""

    base = os.path.splitext(original_file_path)[0]
    srt_file = base + audio_language_to_convert + '.srt'
    path=Path(srt_file)

    if path.is_file():
        logger.info("File's srt subtitle stream was previously created - '{}' exists.".format(srt_file))
        return True, audio_language_to_convert

    # Default to...
    return False, audio_language_to_convert

def on_library_management_file_test(data):
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
    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # Get the path to the file
    abspath = data.get('path')

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if 'ffprobe' in data.get('shared_info', {}):
        if not probe.set_probe(data.get('shared_info', {}).get('ffprobe')):
            # Failed to set ffprobe from shared info.
            # Probably due to it being for an incompatible mimetype declared above
            return
    elif not probe.file(abspath):
        # File probe failed, skip the rest of this test
        return

    # Set file probe to shared infor for subsequent file test runners
    if 'shared_info' in data:
        data['shared_info'] = {}
    data['shared_info']['ffprobe'] = probe.get_probe()

    probe_streams = probe.get_probe()["streams"]

    # Add task to pending tasks if srt file has not been created &/or if language stream doesn't exist but user selects logic for another stream
    srt_exists, audio_language_to_convert = srt_already_created(settings, abspath, probe_streams)
    if not srt_exists and audio_language_to_convert != "":
        # Mark this file to be added to the pending tasks
        data['add_file_to_pending_tasks'] = True
        logger.info("File '{}' should be added to task list. File has not been previously had SRT created.".format(abspath))
    else:
        logger.info("File '{}' has previously had SRT created or audio language was not present and user elected to abort.".format(abspath))

    return data

def parse_progress(line_text):
    match = re.search(r'(\[\d+:\d+.\d+\s+-->\s+)(\d+:\d+.\d+)].*$', line_text)
    if match & (duration > 0.0):
        time_str=match.group(2)
        tc_h, tc_m = time_str.split(':')
        secs = int(tc_h)*3600.0 + float(tc_m)*60.0
        progress = (secs / duration) * 100.0
    else:
        progress = ''

    return {
        'percent': progress
    }

def on_worker_process(data):
    """
    Runner function - enables additional configured processing jobs during the worker stages of a task.

    The 'data' object argument includes:
        exec_command            - A command that Unmanic should execute. Can be empty.
        command_progress_parser - A function that Unmanic can use to parse the STDOUT of the command to collect progress stats. Can be empty.
        file_in                 - The source file to be processed by the command.
        file_out                - The destination that the command should output (may be the same as the file_in if necessary).
        original_file_path      - The absolute path to the original file.
        repeat                  - Boolean, should this runner be executed again once completed with the same variables.

    DEPRECIATED 'data' object args passed for legacy Unmanic versions:
        exec_ffmpeg             - Boolean, should Unmanic run FFMPEG with the data returned from this plugin.
        ffmpeg_args             - A list of Unmanic's default FFMPEG args.

    :param data:
    :return:

    """
    global duration
    # Default to no FFMPEG command required. This prevents the FFMPEG command from running if it is not required
    data['exec_command'] = []
    data['repeat'] = False

    # Get the path to the file
    abspath = data.get('file_in')

    # Get file probe
    probe_data = Probe(logger, allowed_mimetypes=['video'])

    # Get stream data from probe
    if probe_data.file(abspath):
        probe_streams = probe_data.get_probe()["streams"]
        probe_format = probe_data.get_probe()["format"]
    else:
        logger.debug("Probe data failed - Blocking everything.")
        return data

    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    srt_exists, audio_language_to_convert = srt_already_created(settings, abspath, probe_streams)
    if not srt_exists and audio_language_to_convert != "":
        try:
            duration = float(probe_format["duration"])
        except KeyError:
            duration = 0.0

        original_file_path = data.get('original_file_path')
        output_dir = os.path.dirname(original_file_path)
        split_original_file_path = os.path.splitext(original_file_path)

        if audio_language_to_convert != '0':
            whisper_args = ['--model', 'small', '--device', 'cuda', '--output_dir', output_dir, '--language', audio_language_to_convert, '--output_format', 'srt', original_file_path]
        else:
            whisper_args = ['--model', 'small', '--device', 'cuda', '--output_dir', output_dir, '--output_format', 'srt', original_file_path]

        # Apply ffmpeg args to command
        data['exec_command'] = ['whisper']
        data['exec_command'] += whisper_args

        logger.debug("command: '{}'".format(data['exec_command']))

        # Set the parser
        data['command_progress_parser'] = parse_progress

        data['file_out'] = None
    return data

def on_postprocessor_task_results(data):
    """
    Runner function - provides a means for additional postprocessor functions based on the task success.

    The 'data' object argument includes:
        task_processing_success         - Boolean, did all task processes complete successfully.
        file_move_processes_success     - Boolean, did all postprocessor movement tasks complete successfully.
        destination_files               - List containing all file paths created by postprocessor file movements.
        source_data                     - Dictionary containing data pertaining to the original source file.

    :param data:
    :return:

    """
    # We only care that the task completed successfully.
    # If a worker processing task was unsuccessful, dont mark the file streams as kept
    # TODO: Figure out a way to know if a file's streams were kept but another plugin was the
    #   cause of the task processing failure flag
    if not data.get('task_processing_success'):
        return data

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    audio_language_to_convert = settings.get_setting('audio_stream_lang_to_text')
    abspath = data.get('source_data').get('abspath')
    base = os.path.splitext(abspath)[0]
    srt_file_sans_lang = base + '.srt'
    srt_file = base + '.' + audio_language_to_convert + '.srt'
    path = Path(srt_file_sans_lang)
    if path.is_file():
        os.rename(srt_file_sans_lang,srt_file)
    else:
        logger.error("Cannot create srt file.  basename is: '{}' and srt file path should be: '{}'".format(base, srt_file))
    return data
