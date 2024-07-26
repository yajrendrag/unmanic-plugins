#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               Josh.5 <jsunnex@gmail.com>
    Date:                     23 Aug 2021, (20:38 PM)

    Copyright:
        Copyright (C) 2021 Josh Sunnex

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

from convert_multichan_audio_to_2ch.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.convert_multichan_audio_to_2ch")

class Settings(PluginSettings):
    settings = {
        "use_libfdk_aac":         True,
        "keep_mc":                False,

    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "use_libfdk_aac":               {
                "label": "check if you want to use libfdk_aac (requires ffmpeg >= 5), otherwise native aac is used",
            },
            "keep_mc":      {
                "label": "check to keep the multichannel streams, otherwise, they are removed",
            }
        }

def streams_to_stereo_encode(probe_streams):
    audio_stream = -1
    streams = []
    stereo_streams = [probe_streams[i]['tags']['language'] for i in range(len(probe_streams)) if probe_streams[i]['codec_type'] == 'audio' and 'tags' in probe_streams[i] and 'language' in probe_streams[i]['tags'] and probe_streams[i]['channels'] == 2]
    for i in range(0, len(probe_streams)):
        if "codec_type" in probe_streams[i] and probe_streams[i]["codec_type"] == "audio":
            audio_stream += 1
            if  int(probe_streams[i]["channels"]) > 4 and 'tags' in probe_streams[i] and 'language' in probe_streams[i]['tags'] and probe_streams[i]['tags']['language'] not in stereo_streams:
                streams += str(audio_stream)
    return streams


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

    streams = streams_to_stereo_encode(probe_streams)
    if streams != []:
        data['add_file_to_pending_tasks'] = True
        for stream in range(0, len(streams)):
            logger.debug("Audio stream '{}' is multichannel audio - convert stream".format(streams[stream]))
    else:
#        data['add_file_to_pending_tasks'] = False
        logger.debug("do not add file '{}' to task list - no multichannel audio streams".format(abspath))

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

    streams = streams_to_stereo_encode(probe_streams)
    all_astreams=[probe_streams[i]['index'] for i in range(len(probe_streams)) if probe_streams[i]['codec_type'] == 'audio']
    mc_streams= [probe_streams[i]['index'] for i in range(len(probe_streams)) if probe_streams[i]['codec_type'] == 'audio' and probe_streams[i]['channels'] > 2]

    logger.debug("streams: '{}'".format(streams))
    logger.debug("all_astreams: '{}'".format(all_astreams))
    logger.debug("mc_streams: '{}'".format(mc_streams))

    encoder = 'aac'
    if settings.get_setting('use_libfdk_aac'): encoder = 'libfdk_aac'

    keep_mc = settings.get_setting('keep_mc')

    if streams != []:
        # Get generated ffmpeg args
        ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-map', '0:v', '-c:v', 'copy']
        if not keep_mc:
            for stream,abs_stream in enumerate(all_astreams):
                if abs_stream not in mc_streams:
                    ffmpeg_args += ['-map', '0:a:'+str(stream), '-c:a:'+str(stream), 'copy']
                else:
                    rate = str(int(int(probe_streams[abs_stream]['bit_rate'])/(1000 * probe_streams[abs_stream]['channels']))*2) + 'k'
                    ffmpeg_args += ['-map', '0:a:'+str(stream), '-c:a:'+str(stream), encoder, '-ac', '2', '-b:a:'+str(stream), rate]
        else:
            stream_map = {}
            for stream,abs_stream in enumerate(all_astreams):
                ffmpeg_args += ['-map', '0:a:'+str(stream), '-c:a:'+str(stream), 'copy']
                stream_map[stream] = abs_stream
            next_audio_stream_index = len(all_astreams) - 1
            for stream in range(0, len(streams)):
                next_audio_stream_index += 1
                try:
                    rate = str(int(int(probe_streams[stream_map[stream]]['bit_rate'])/(1000 * probe_streams[stream_map[stream]]['channels']))*2) + 'k'
                except KeyError:
                    rate = '128k'
                ffmpeg_args += ['-map', '0:a:'+str(stream), '-c:a:'+str(next_audio_stream_index), encoder, '-ac', '2', '-b:a:'+str(next_audio_stream_index), rate]
        ffmpeg_args += ['-map', '0:s?', '-c:s', 'copy', '-map', '0:d?', '-c:d', 'copy', '-map', '0:t?', '-c:t', 'copy', '-y', str(outpath)]

        logger.debug("ffmpeg args: '{}'".format(ffmpeg_args))

        # Apply ffmpeg args to command
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe_data)
        data['command_progress_parser'] = parser.parse_progress
