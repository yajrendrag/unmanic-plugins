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

from convert_audio_tolibopus.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.convert_audio_to_libopus")


class Settings(PluginSettings):
    settings = {
        "bit_rate": "64k",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "bit_rate":               {
                "label": "Enter per channel bit rate for stream (default is 64k)",
            },
        }

def s2_encode(probe_streams, settings):
    try:
        streams_list = [i for i in range(0, len(probe_streams)) if "codec_type" in probe_streams[i] and probe_streams[i]["codec_type"] == 'audio' and probe_streams[i]["codec_name"] != 'opus']
        return streams_list
    except:
        logger.info("All audio streams are opus already or there are no audio streams")
        return []

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

    streams_to_encode = s2_encode(probe_streams, settings)
    if streams_to_encode:
        logger.debug("streams_to_encode: '{}'".format(streams_to_encode))

    if streams_to_encode:
        data['add_file_to_pending_tasks'] = True
        for i in range(len(probe_streams)):
            if probe_streams[i] in streams_to_encode:
                stream_encoder = probe_streams[i]["codec_name"]
                logger.info("audio stream '{}' is encoded with '{}' and will be re-encoded as opus replacing the original audio stream".format(i, stream_encoder))
    else:
        logger.info("do not add file '{}' to task list - either all streams are opus already or there are no audio streams".format(abspath))

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

    streams_to_encode = s2_encode(probe_streams, settings)
    br = settings.get_setting('bit_rate')
    br = int(br[:-1])
    encoder = 'libopus'

    logger.debug("streams_to_encode: '{}'".format(stream_to_encode))

    if streams_to_encode:

        # Set initial ffmpeg args
        ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-strict', '-2']

        # set stream maps
        stream_map = ['-map', '0:v', '-c:v', 'copy']

        for i in range(len(probe_streams)):
            if probe_streams[i] in streams_to_encode:
                n_channels = probe_streams[i]["channels"]
                bit_rate = str(n_channels*br)+'k'
                if n_channels == 2:
                    stream_map += ['-map', '0:a:'+str(i), '-c:a:'+str(i), encoder, '-ac:a:'+str(i), str(n_channels), '-b:a:'+str(i), bit_rate]
                elif n_channels == 6:
                    stream_map += ['-map', '0:a:'+str(i), '-c:a:'+str(i), encoder, '-ac:a:'+str(i), str(n_channels), '-b:a:'+str(i), bit_rate, '-mapping_family', '1', '-af', '"channelmap=FL-FL|FR-FR|FC-FC|LFE-LFE|SL-BL|SR-BR:5.1"']
                elif n_channels == 8:
                    stream_map += ['-map', '0:a:'+str(i), '-c:a:'+str(i), encoder, '-ac:a:'+str(i), str(n_channels), '-b:a:'+str(i), bit_rate, '-mapping_family', '1', '-af', '"aformat=channel_layouts=7.1"']

        logger.debug(f"stream_map (before subs, data, att): {stream_map}")

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
