#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     29 Feb 2024, (2:41 PM)

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

from unmanic.libs.unplugins.settings import PluginSettings

from convert_multichannel_audio_to_aac_or_ac3.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.convert_multichannel_audio_to_aac_or_ac3")


class Settings(PluginSettings):
    settings = {
        "bit_rate": "640k",
        "stream_title":  "",
        "encoder":  "",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "bit_rate":               {
                "label": "Enter aggregate bit rate for stream (default is 640k)",
            },
            "stream_title": {
                "label": "Enter a custom stream title for audio language.  Default is a string equal to the encoder used + '5.1 Surround'",
            },
            "encoder": self.__set_encoder_form_settings(),
        }

    def __set_encoder_form_settings(self):
        values = {
            "label":      "Select Encoder",
            "description":    "Choose native aac, libfdk_aac, or ac3 - note libfdk_aac can only be used on systems with ffmpeg 5.x or greater",
            "input_type": "select",
            "select_options": [
                {
                    "value": "aac",
                    "label": "native aac",
                },
                {
                    "value": "libfdk_aac",
                    "label": "libfdk_aac",
                },
                {
                    "value": "ac3",
                    "label": "ac3",
                },
            ],
        }
        return values

def s2_encode(probe_streams, abspath):
    try:
        mc_streams_list = [i for i in range(0, len(probe_streams)) if "codec_type" in probe_streams[i] and probe_streams[i]["codec_type"] == 'audio' and int(probe_streams[i]["channels"]) >= 6 and probe_streams[i]["codec_name"] in ["dts", "truehd", "eac3"]]
        # below returns the audio stream with the maximum number of audio channels > 5, it's audio stream #, and absolute stream # as a tuple, and final index selects key number 1 from the tuple (audio stream #)
        all_astreams = [i for i in range(0, len(probe_streams)) if "codec_type" in probe_streams[i] and probe_streams[i]["codec_type"] == 'audio']
        return mc_streams_list, all_astreams
    except:
        logger.info("No DTS audio streams found to encode")
        return [],[]

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

    stream_to_encode, all_astreams = s2_encode(probe_streams, abspath)
    logger.debug("stream_to_encode: '{}'".format(stream_to_encode))
    logger.debug("all_astreams: '{}'".format(all_astreams))

    encoder = settings.get_setting('encoder')
    if stream_to_encode:
        data['add_file_to_pending_tasks'] = True
        for i in range(len(all_astreams)):
            if all_astreams[i] in stream_to_encode:
                stream_encoder = probe_streams[all_astreams[i]]["codec_name"]
                logger.info("audio stream '{}' is encoded with '{}' and will be re-encoded as '{}' replacing the original audio stream".format(i, stream_encoder, encoder))
    else:
        logger.info("do not add file '{}' to task list - no 6 (or more) channel, dts, truehd, or eac3 audio streams found".format(abspath))

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

    stream_to_encode, all_astreams = s2_encode(probe_streams, abspath)
    bit_rate = settings.get_setting('bit_rate')
    encoder = settings.get_setting('encoder')
    stream_title = settings.get_setting('stream_title')
    logger.debug("stream_title: '{}'".format(stream_title))
    if stream_title == "":
        stream_title = str(encoder) + " 5.1 Surround"

    if stream_to_encode:

        # Set initial ffmpeg args
        ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-strict', '-2']

        # set stream maps
        stream_map = ['-map', '0:v', '-c:v', 'copy']
        for i in range(len(all_astreams)):
            if all_astreams[i] in stream_to_encode:
                stream_map += ['-map', '0:a:'+str(i), '-c:a:'+str(i), encoder, '-ac', '6', '-b:a:'+str(i), bit_rate, '-metadata:s:a:'+str(i), 'title="'+stream_title+'"']
            else:
                stream_map += ['-map', '0:a:'+str(i), '-c:a:'+str(i), 'copy']
        stream_map += ['-map', '0:s?', '-c:s', 'copy', '-map', '0:d?', '-c:d', 'copy', '-map', '0:t?', '-c:t', 'copy']
        ffmpeg_args += stream_map

        # Get suffix and add remove chapters in case of mp4
        sfx = os.path.splitext(abspath)[1]
        if sfx == '.mp4':
            ffmpeg_args += ['-dn', '-map_metadata:c', '-1']

        # Add final ffmpeg_args
        ffmpeg_args += ['-y', str(outpath)]
        logger.debug("ffmpeg args: '{}'".format(ffmpeg_args))

        # Apply ffmpeg args to command
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe_data)
        data['command_progress_parser'] = parser.parse_progress
