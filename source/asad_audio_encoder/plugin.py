#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     17 April 2024, (09:00 AM)

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
from humanfriendly import format_size, parse_size
from pymediainfo import MediaInfo

from unmanic.libs.unplugins.settings import PluginSettings

from asad_audio_encoder.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.asad_audio_encoder")

# file_suffix / Encoder Dictionary
suffix = {
    "libfdk_aac": "m4a",
    "libmp3lame": "mp3",
    "libopus": "ogg",
    "libvorbis": "ogg",
    "flac": "flac",
    "alac": "m4a",
}

class Settings(PluginSettings):
    settings = {
        "force_encoding": False,
        "encoder": "libfdk_aac",
        "channel_rate": "0",
        "customize":  False,
        "custom_audio": "",
        "custom_suffix": "",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "force_encoding": {
                "label": "Check this option if you want to force encoding if the encoder already matches the selected encoder",
            },
            "encoder": {
                "label":      "Enter encoder",
                "description": "Select audio encoder for the encoder:",
                "input_type": "select",
                "select_options": [
                    {
                        "value": "libmp3lame",
                        "label": "mp3",
                    },
                    {
                        "value": "libfdk_aac",
                        "label": "libfdk_aac",
                    },
                    {
                        "value": "libopus",
                        "label": "opus",
                    },
                    {
                        "value": "libvorbis",
                        "label": "vorbis",
                    },
                    {
                        "value": "flac",
                        "label": "flac",
                    },
                    {
                        "value": "alac",
                        "label": "alac",
                    },

                ],
            },
                "channel_rate": {
                "label":      "Enter channel bit rate",
                "description": "Select data rate for each channel:",
                "input_type": "select",
                "select_options": [
                    {
                        "value": "32k",
                        "label": "32k",
                    },
                    {
                        "value": "48k",
                        "label": "48k",
                    },
                    {
                        "value": "64k",
                        "label": "64k",
                    },
                    {
                        "value": "96k",
                        "label": "96k",
                    },
                    {
                        "value": "128k",
                        "label": "128k",
                    },
                    {
                        "value": "160k",
                        "label": "160k",
                    },
                    {
                        "value": "keep each stream's existing rate",
                        "label": "keep each stream's existing rate",
                    },
                    {
                        "value": "0",
                        "label": "Default/None",
                    },
                ]
            },
            "customize": {
                "label": "Check this option if you want to add custom audio options &/or use a custom suffix",
            },
            "custom_audio": self.__set_custom_audio_form_settings(),
            "custom_suffix": self.__set_custom_suffix_form_settings(),
        }
    def __set_custom_audio_form_settings(self):
        values = {
            "label":      "Enter additional custom audio options just as you would enter them on the ffmpeg command line",
            "input_type": "textarea",
        }
        if not self.get_setting('customize'):
            values["display"] = 'hidden'
        return values

    def __set_custom_suffix_form_settings(self):
        values = {
            "label":      "Enter a custom suffix to use for file extension - no punctuation",
            "input_type": "textarea",
        }
        if not self.get_setting('customize'):
            values["display"] = 'hidden'
        return values

def s2_encode(streams, probe_format, encoder, force_encoding, channel_rate, abspath):
    try:
        all_audio_streams = [i for i in range(len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio']
    except:
        logger.error("Error finding audio stream to encode")
        return [0,0,0]

    streams_to_encode = [(i, streams[i]["channels"], probe_format["bit_rate"]) for i in range(len(streams))
                         if ("codec_type" in streams[i] and streams[i]["codec_type"] == 'audio' and "codec_name" in streams[i] and streams[i]["codec_name"] != encoder and "bit_rate" in probe_format)
                         or (force_encoding == True and "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio' and "bit_rate" in probe_format)]

    if streams_to_encode != []:
        return streams_to_encode
    else:
        return [0,0,0]

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
    probe_data = Probe(logger, allowed_mimetypes=['audio'])
    
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

    # get encoder, channel_rate & force_encoding
    encoder = settings.get_setting('encoder')
    channel_rate = settings.get_setting('channel_rate')
    force_encoding = settings.get_setting('force_encoding')

    if s2_encode(probe_streams, probe_format, encoder, force_encoder, channel_rate, abspath) != [0,0,0]:
        # Mark this file to be added to the pending tasks
        data['add_file_to_pending_tasks'] = True
        logger.debug("File '{}' should be added to task list. Probe found streams require processing.".format(abspath))
    else:
        logger.debug("File '{}' does not contain streams require processing.".format(abspath))

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
    probe_data = Probe(logger, allowed_mimetypes=['audio'])

    if probe_data.file(abspath):
        probe_streams = probe_data.get_probe()["streams"]
        probe_format = probe_data.get_probe()["format"]
    else:
        logger.debug("Probe data failed - Blocking everything.")
        data['add_file_to_pending_tasks'] = False
        return data

    # Configure settings object (maintain compatibility with v1 plugins)
    settings = Settings(library_id=data.get('library_id'))

    # get settings
    encoder = settings.get_setting('encoder')
    channel_rate = settings.get_setting('channel_rate')
    custom_audio = settings.get_setting('custom_audio')
    custom_suffix = settings.get_setting('custom_suffix')
    force_encoding = settings.get_setting('force_encoding')

    if custom_suffix:
        sfx = custom_suffix
    else:
        sfx = suffix[encoder]

    # Set initial ffmpeg args
    ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-strict', '-2']

    # Build stream maps for audio streams to be encoded
    streams_to_process = s2_encode(probe_streams, probe_format, encoder, force_encoding, channel_rate, abspath)
    if streams_to_process != [0,0,0]:

        all_streams = [i for i in range(len(probe_streams))]
        stream_map = []
        for i,t in enumerate(streams_to_process):
            absolute_stream = t[0]
            channels = t[1]
            bit_rate = t[2]
            if channel_rate != "keep each stream's existing rate":
                bit_rate = str(parse_size(channel_rate) * int(channels))
            stream_map += ['-map', '0:a:'+str(i), '-c:a:'+str(i), encoder, '-ac', str(channels)]
            if channel_rate != "0":
                stream_map += ['-b:a:'+str(i), str(bit_rate)]
            all_streams.remove(absolute_stream)

        for i in range(len(all_streams)):
            stream_map += ['-map', '0:'+str(all_streams[i]), '-c:'+str(all_streams[i]), 'copy']

        ffmpeg_args += stream_map

        logger.debug("custom audio: '{}'".format(custom_audio))

        if custom_audio:
            ffmpeg_args += custom_audio.split()


        data['file_out'] = "{}.{}".format(os.path.splitext(outpath)[0], sfx)

        ffmpeg_args += [str(data['file_out'])]

        logger.debug("ffmpeg_args: '{}'".format(ffmpeg_args))
        logger.debug("fileout=: '{}'".format(data['file_out']))

        # Apply ffmpeg args to command
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe_data)
        data['command_progress_parser'] = parser.parse_progress
