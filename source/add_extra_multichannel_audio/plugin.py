#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     18 sep 2023, (11:55 PM)

    Copyright:
        Copyright (C) 2023 Jay Gardner

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
from operator import itemgetter

from unmanic.libs.unplugins.settings import PluginSettings

from add_extra_multichannel_audio.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.add_extra_multichannel_audio")


class Settings(PluginSettings):
    settings = {
        "skip_files_less_than_4k_resolution":         False,
        "encoder": "",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "skip_files_less_than_4k_resolution":               {
                "label": "check if you want to skip files with resolutions less than 4k (3840x2160)",
            },
            "encoder": self.__set_encoder_form_settings(),
        }

    def __set_encoder_form_settings(self):
        values = {
            "label":      "Enter encoder",
            "decription": "Select ac3 or libfdk_aac for the encoder - libfdk_aac requires ffmpeg5.x",
            "input_type": "select",
            "select_options": [
                {
                    "value": "ac3",
                    "label": "ac3",
                },
                {
                    "value": "libfdk_aac",
                    "label": "libfdk_aac",
                },
            ],
        }
        return values

def stream_to_ac3_encode(probe_streams, abspath):
    try:
        streams_list = [i for i in range(0, len(probe_streams)) if "codec_type" in probe_streams[i] and probe_streams[i]["codec_type"] == 'audio' and probe_streams[i]["codec_name"] in ["truehd", "eac3", "dts"]]
        # below returns the audio stream with the maximum number of audio channels > 5, it's audio stream #, and absolute stream # as a tuple, and final index selects key number 1 from the tuple (audio stream #)
        audio_stream_to_encode = max([(probe_streams[streams_list[i]]["channels"], i, ind) for i,ind in enumerate(streams_list) if probe_streams[streams_list[i]]["channels"] >= 6], key = itemgetter(0))[1]
        absolute_stream_num = max([(probe_streams[streams_list[i]]["channels"], i, ind) for i,ind in enumerate(streams_list) if probe_streams[streams_list[i]]["channels"] >= 6], key = itemgetter(0))[2]
        new_audio_stream = len([i for i in range(0, len(probe_streams)) if "codec_type" in probe_streams[i] and probe_streams[i]["codec_type"] == 'audio'])
    except:
        logger.error("Error finding audio stream to encode")
        return 0, 0, 0
    existing_ac3_stream = [i for i in range(0, len(probe_streams)) if "codec_type" in probe_streams[i] and probe_streams[i]["codec_type"] == 'audio' and probe_streams[i]["codec_name"] == 'ac3' and probe_streams[i]["channels"] == 6]
    ac3_stream_exists_already = [existing_ac3_stream[i] for i in range(0, len(existing_ac3_stream)) if "tags" in probe_streams[existing_ac3_stream[i]] and "language" in probe_streams[existing_ac3_stream[i]]["tags"] and probe_streams[existing_ac3_stream[i]]["tags"]["language"] in probe_streams[absolute_stream_num]["tags"]["language"]]
    if ac3_stream_exists_already == []:
        return audio_stream_to_encode, new_audio_stream, absolute_stream_num
    else:
        logger.info("6 channel ac3 stream with matching language already exists, skipping file '{}'".format(abspath))
        return 0,0,0

def on_library_management_file_test(data):
    """
    Runner function - enables additional actions during the library management file tests.

    The 'data' object argument includes:
        path                            - String containing the full path to the file being tested.
        issues                          - List of currently found issues for not processing the file.
        add_file_to_pending_tasks       - Boolean, is the file currently marked to be added to the queue for processing.

    :param data:
    :return:

    """
    # Get the path to the file
    abspath = data.get('path')

    # Get file probe
    probe_data = Probe(logger, allowed_mimetypes=['audio', 'video'])

    # Get stream data from probe
    if probe_data.file(abspath):
        probe_streams = probe_data.get_probe()["streams"]
        probe_format = probe_data.get_probe()["format"]
    else:
        logger.debug("Probe data failed - Blocking everything.")
        data['add_file_to_pending_tasks'] = False
        return data

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # Check if configured to skip files with resolution less than 4k, skip file if so
    if settings.get_setting('skip_files_less_than_4k_resolution'):
        for stream in range(0, len(probe_streams)):
            if probe_streams[stream]["codec_type"] == "video":
                width = probe_streams[stream]["width"]
                height = probe_streams[stream]["height"]
                if int(width) < 3840 or int(height) < 2160:
                    logger.info("resolution is less than 4k, skipping file per configured instruction - width x height: '{}'x'{}'".format(width, height))
                    return data

    stream_to_encode, new_audio_stream, absolute_stream_num = stream_to_ac3_encode(probe_streams, abspath)
    if new_audio_stream:
        data['add_file_to_pending_tasks'] = True
        logger.info("Multichannel audio stream '{}' is being encoded as extra ac3 audio channel '{}'".format(stream_to_encode, new_audio_stream))
    else:
        data['add_file_to_pending_tasks'] = False
        logger.info("do not add file '{}' to task list - no multichannel audio streams found or one already exists with same language as lossless audio stream".format(abspath))

    return data


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

    :param data:
    :return:

    """
    # Default to no FFMPEG command required. This prevents the FFMPEG command from running if it is not required
    data['exec_command'] = []
    data['repeat'] = False

    # Get the path to the file
    abspath = data.get('file_in')
    outpath = data.get('file_out')

    # Get file probe
    probe_data = Probe(logger, allowed_mimetypes=['audio', 'video'])

    if probe_data.file(abspath):
        probe_streams = probe_data.get_probe()["streams"]
        probe_format = probe_data.get_probe()["format"]
    else:
        logger.debug("Probe data failed - Nothing to encode - '{}'".format(abspath))
        return data

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    stream_to_encode, new_audio_stream, absolute_stream_num = stream_to_ac3_encode(probe_streams, abspath)
    encoder = settings.get_setting('encoder')
    channels = '6'
    if new_audio_stream:
        # Get generated ffmpeg args
        ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-strict', '-2', '-map', '0', '-c', 'copy']
        if "bit_rate" in probe_streams[absolute_stream_num]:
            bitrate = int(probe_streams[absolute_stream_num]["bit_rate"])
            if bitrate > 640000:
                bit_rate = '640k'
            else:
                bit_rate = str(int(int(bitrate)/1000)) + 'k'
        else:
            bit_rate = '640k'

        sfx = os.path.splitext(abspath)[1]
        if sfx == '.mkv':
            ffmpeg_args += ['-map', '0:a:'+str(stream_to_encode), '-c:a:'+str(new_audio_stream), encoder, '-ac', channels, '-b:a:'+str(new_audio_stream), bit_rate, '-metadata:s:a:'+str(new_audio_stream), 'title="ac3 5.1 surround"', '-y', str(outpath)]
        else:
            ffmpeg_args += ['-map', '0:a:'+str(stream_to_encode), '-c:a:'+str(new_audio_stream), encoder, '-ac', channels, '-b:a:'+str(new_audio_stream), bit_rate, '-metadata:s:a:'+str(new_audio_stream), 'title="ac3 5.1 surround"', '-dn', '-map_metadata:c', '-1', '-y', str(outpath)]

        logger.debug("ffmpeg args: '{}'".format(ffmpeg_args))

        # Apply ffmpeg args to command
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe_data)
        data['command_progress_parser'] = parser.parse_progress
