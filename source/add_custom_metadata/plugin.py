#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     10 July 2023, (20:38 PM)

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

from add_custom_metadata.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.add_custom_metadata")


class Settings(PluginSettings):
    settings = {
        "custom_metadata":         "",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "custom_metadata":               {
                "label": "Enter custom metadata pairs (comma delimited pairs of tag:value)",
            }
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

    :param data:
    :return:

    """
    # Default to no FFMPEG command required. This prevents the FFMPEG command from running if it is not required
    data['exec_command'] = []
    data['repeat'] = False

    # Get the path to the file
    abspath = data.get('file_in')
    outpath = data.get('file_out')
    file_type = os.path.splitext(str(abspath))

    # Get file probe
    probe_data = Probe(logger, allowed_mimetypes=['audio', 'video'])

    if probe_data.file(abspath):
        probe_streams = probe_data.get_probe()["streams"]
        probe_format = probe_data.get_probe()["format"]
    else:
        logger.info("Probe data failed - Possibly not a valid file to process - '{}'".format(abspath))
        return data

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath)]
    custom_metadata = settings.get_setting('custom_metadata').replace(" ","")
    if file_type[1] == '.mkv':
        cm_list = list(custom_metadata.split(","))
        for i in range(0,len(cm_list)):
            ffmpeg_args += ['-metadata', str(cm_list[i].replace(":","="))]
        ffmpeg_args += ['-c', 'copy', str(outpath)]
    elif file_type[1] == '.mp4':
        ffmpeg_args += ['-metadata', 'comment='+str(custom_metadata), '-c', 'copy', str(outpath)]
    else:
        logger.info("'{}'container doesn't accept custom metadata fields".format(file_type))
    logger.debug("ffmpeg args: '{}'".format(ffmpeg_args))

    # Apply ffmpeg args to command
    if file_type[1] == '.mkv' or file_type[1] == '.mp4':
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe_data)
        data['command_progress_parser'] = parser.parse_progress
