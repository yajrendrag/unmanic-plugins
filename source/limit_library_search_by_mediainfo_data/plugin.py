#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.plugin.py

    Written by:               Josh.5 <jsunnex@gmail.com>
    Date:                     16 Feb 2023, (22:23 PM)

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
import json
import logging
import jsonata
from pymediainfo import MediaInfo

from unmanic.libs.unplugins.settings import PluginSettings

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.limit_library_search_by_mediainfo_data")


class Settings(PluginSettings):
    settings = {
        "stream_field":            '',
        "allowed_values":          '',
    }
    form_settings = {
        "stream_field":            {
            "label":       "The mediainfo field to match against",
            "description": "A JSONata query to match name of the mediainfo field to match against with the search strings below."
        },
        "allowed_values":          {
            "label":       "Search strings",
            "description": "A comma separated list of strings to match agianst the JSONata query results."
        }
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)


def file_ends_in_allowed_values(media_info, stream_field, allowed_values):
    """
    Check if the file's video codec is in the list of values being searched for

    :return:
    """
    # If the config is empty (not yet configured) ignore everything
    if not allowed_values:
        logger.debug("Plugin has not yet been configured with a list of values to allow. Blocking everything.")
        return False

    # Require a list of probe streams to continue
    file_path = media_info.general_tracks[0].complete_name
    file_probe_streams = {}
    file_probe_streams["streams"] = media_info.to_data()["tracks"]

    if not file_probe_streams:
        return False

    # If the config is empty (not yet configured) ignore everything
    if not allowed_values:
        logger.debug("Plugin has not yet been configured with allowed values. Blocking everything.")
        return False

    try:
        context = jsonata.Context()
        discovered_values = context(stream_field, file_probe_streams)
    except ValueError as e:
        logger.debug("Failed to match the JSONata query to in the mediainfo data of the file '%s'.", file_path)
        #logger.debug("Exception:", exc_info=e)
        return False

    for allowed_value in allowed_values.split(','):
        # Ignore empty values (if plugin is configured with a trailing ','
        if allowed_value:
            if allowed_value in discovered_values:
                logger.debug("File '%s' contains one of the configured values '%s'.", file_path, allowed_value)
                return True

    # File is not in the allowed video values
    logger.debug("File '%s' does not contain one of the specified values '%s'.", file_path, allowed_values)
    return False


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

    # Get settings
    settings = Settings(library_id=data.get('library_id'))

    # Get the path to the file
    abspath = data.get('path')

    # Get file mediainfo
    try:
        media_info = MediaInfo.parse(abspath)
    except:
        # File not able to be parsed by MediaInfo
        return

    # Get the list of configured values to search for
    stream_field = settings.get_setting('stream_field')
    allowed_values = settings.get_setting('allowed_values')

    in_allowed_values = file_ends_in_allowed_values(media_info, stream_field, allowed_values)
    if in_allowed_values:
        # Force this file to have a pending task created
        data['add_file_to_pending_tasks'] = True
        logger.debug(
            "File '%s' should be added to task list. "
            "File contains specified mediainfo data.", abspath)
    elif not in_allowed_values:
        # Ignore this file
        data['add_file_to_pending_tasks'] = False
        logger.debug(
            "File '%s' should not be added to task list. "
            "File does not contain specified mediainfo data.", abspath)
