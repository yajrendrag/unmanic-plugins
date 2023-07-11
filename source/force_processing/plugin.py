#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     10 July 2023, (19:14 PM)

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

from force_processing.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.force_processing")

class Settings(PluginSettings):
    settings = {
        "check_for_valid_ffprobe_data":         False,
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "check_for_valid_ffprobe_data":              {
                "label": "if true, checks for valid ffprobe data before adding file to processing queue",
            }
    }

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
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    if settings.get_setting('check_for_valid_ffprobe_data'):
        # Get the path to the file
        abspath = data.get('path')

        # Get file probe
        probe_data = Probe(logger, allowed_mimetypes=['audio', 'video'])

        # Get stream data from probe
        if probe_data.file(abspath):
            probe_streams = probe_data.get_probe()["streams"]
            probe_format = probe_data.get_probe()["format"]
            data['add_file_to_pending_tasks'] = True
        else:
            logger.info("Probe data failed - Blocking everything.")
            data['add_file_to_pending_tasks'] = False
    else:
        data['add_file_to_pending_tasks'] = True

    logger.debug("Queue status is: {}".format(data['add_file_to_pending_tasks']))
    return data
