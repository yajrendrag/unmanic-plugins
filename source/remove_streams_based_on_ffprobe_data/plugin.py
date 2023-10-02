#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    unmanic-plugins.plugin.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     02 Aug 2023, (2:57 PM)

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

from unmanic.libs.unplugins.settings import PluginSettings

from remove_streams_based_on_ffprobe_data.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.remove_streams_based_on_ffprobe_data")


class Settings(PluginSettings):
    settings = {
        "ffprobe_field":          '',
        "ffprobe_value":               '',
    }
    form_settings = {
        "ffprobe_field":          {
            "label":       "ffprobe field names to search for",
            "description": "comma delimited list of ffprobe fields to search for; remove stream if any field contains corresponding ffprobe_value per below."
        },
        "ffprobe_value":          {
            "label":       "remove stream from video file if an ffprobe_field contain the corresponding value",
            "description": "comma delimited list of values that indicates stream should be removed."
        },
    }


def stream_has_ffprobe_data(path, probe_streams, probe_field, probe_value):
    """
    Check if the stream contains ffprobe_data with ffprobe_value

    :return:
    """

    streams_to_remove = []

    logger.debug("probe_field: '{}', probe_value: '{}'.".format(probe_field, probe_value))

    # Check streams that contain ffprobe_field with ffprobe_value
    streams_to_remove = [probe_streams[i]['index'] for i in range(0, len(probe_streams)) for j in range(0, len(probe_field)) if (probe_field[j].lower() in probe_streams[i] and probe_value[j].lower() in probe_streams[i][probe_field[j].lower()]) or
                         ("tags" in probe_streams[i] and probe_field[j].lower() in probe_streams[i]["tags"] and probe_value[j].lower() in probe_streams[i]["tags"][probe_field[j].lower()])]
    logger.debug("streams to remove: '{}'".format(streams_to_remove))
    streams_to_remove.sort()
    streams_to_remove = [*set(streams_to_remove)]
    logger.debug("streams to remove after sort, set: '{}'".format(streams_to_remove))

    if streams_to_remove == []:
        logger.info("File '{}' does not contain any streams to remove.".format(path))
        return []

    logger.debug("File '{}' has streams to remove - indices: '{}'.".format(path, streams_to_remove))
    return streams_to_remove


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

    # Configure settings object
    settings = Settings(library_id=data.get('library_id'))

    # initialize Probe
    probe_data=Probe(logger, allowed_mimetypes=['video'])

    # Get stream data from probe
    if probe_data.file(abspath):
        probe_streams = probe_data.get_probe()["streams"]
    else:
        logger.error("Probe data failed - Blocking everything.")
        return data

    # Get the list of configured metadata to search for
    ffprobe_field = settings.get_setting('ffprobe_field')
    ffprobe_value = settings.get_setting('ffprobe_value')

    # If the config is empty (not yet configured) ignore everything
    if not ffprobe_field or not ffprobe_value:
        logger.error("Plugin has not yet been configured with ffprobe data to search for. Blocking everything.")
        return data

    # place  input parameters into lists
    probe_field = list(ffprobe_field.split(','))
    probe_field = [probe_field[i].strip() for i in range(0,len(probe_field))]
    probe_field = [i for i in probe_field if i != '']
    probe_value = list(ffprobe_value.split(','))
    probe_value = [probe_value[i].strip() for i in range(0,len(probe_value))]
    probe_value = [i for i in probe_value if i != '']

    # If the config field and values are different lengths ignore everything
    if len(probe_value) != len(probe_field):
        logger.error("Plugin configured with different length field and values: '{}', '{}'. Blocking everything.".format(ffprobe_field, ffprobe_value))
        return data

    streams_to_remove = stream_has_ffprobe_data(abspath, probe_streams, probe_field, probe_value)
    logger.debug("Streams to remove: '{}'".format(streams_to_remove))

    if streams_to_remove != []:
        # process the file by copying all streams except those identified to be removed
        ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-map', '0']
        for stream in range(0, len(streams_to_remove)):
            ffmpeg_args += ['-map', '-0:'+str(streams_to_remove[stream])]
        ffmpeg_args += ['-c', 'copy', '-y', str(outpath)]

        logger.debug("ffmpeg args: '{}'".format(ffmpeg_args))

        # Apply ffmpeg args to command
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe_data)
        data['command_progress_parser'] = parser.parse_progress
