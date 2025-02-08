#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.plugin.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     08 Feb 2025, (10:43 AM)

    Copyright:
        Copyright (C) 2025 Jay Gardner

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
import ffmpeg

from unmanic.libs.unplugins.settings import PluginSettings

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.ignore_files_with_matching_ffprobe_data")


class Settings(PluginSettings):
    settings = {
        "stream_field":            '',
        "disallowed_values":          '',
        "force_processing_if_no_disallowed_values": False,
    }
    form_settings = {
        "stream_field":            {
            "label":       "field to match against",
            "description": "A JSONata query to match name of the mediainfo field to match against with the search strings below."
        },
        "disallowed_values":          {
            "label":       "Search strings",
            "description": "A comma separated list of strings to match agianst the JSONata query results."
        },
        "force_processing_if_no_disallowed_values":   {
            "label": "if checked, this plugin will force the plugin to immediately add the file to the task list when no disallowed values are found, otherwise if not checked, additional plugins can continue to test the file"
        },
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)


def file_contains_disallowed_values(probe, stream_field, disallowed_values):
    """
    Check if the file contains any values in the list of values being searched for

    :return:
    """
    # If the config is empty (not yet configured) ignore everything
    if not disallowed_values:
        logger.debug("Plugin has not yet been configured with a list of values to allow. Blocking everything.")
        return False

    # Require a list of probe streams to continue
    try:
        file_probe_streams = probe["streams"]
    except:
        return False

    # If the config is empty (not yet configured) ignore everything
    if not disallowed_values:
        logger.debug("Plugin has not yet been configured with allowed values. Blocking everything.")
        return False

    try:
        expr = jsonata.Jsonata(stream_field)
        discovered_values = expr.evaluate(probe)
    except KeyError as e:
        logger.debug("Failed to match the JSONata query keys to in the ffprobe data of the file '%s'.", file_path)
        return False
    except ValueError as e:
        logger.debug("Failed to match the JSONata query value to in the ffprobe data of the file '%s'.", file_path)
        return False

    for disallowed_value in disallowed_values.split(','):
        # Ignore empty values (if plugin is configured with a trailing ','
        if disallowed_value and discovered_values and disallowed_value in discovered_values:
            logger.debug("File '%s' contains one of the configured values '%s'.", file_path, disallowed_value)
            return True

    # File does not contain disallowed values
    logger.debug("File '%s' does not contain one of the specified values '%s'.", file_path, disallowed_values)
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
    try:
        probe = ffmpeg.probe(abspath)
    except:
        logger.error(f"File {abspath} cannot be probed - exiting")

    # Get the list of configured values to search for
    stream_field = settings.get_setting('stream_field')
    disallowed_values = settings.get_setting('disallowed_values')
    force_processing_if_no_disallowed_values = settings.get_setting('force_processing_if_no_disallowed_values')

    in_disallowed_values = file_contains_disallowed_values(probe, stream_field, disallowed_values)
    if in_disallowed_values:
        # Ingore this file
        data['add_file_to_pending_tasks'] = False
        logger.debug(
            "File '%s' should not be added to task list. "
            "File contains specified mediainfo data.", abspath)
    elif not in_disallowed_values:
        #  Force this file to have a pending task created
        if force_processing_if_no_disallowed_values:
            data['add_file_to_pending_tasks'] = True
            logger.debug(
                "File '%s' should be added to task list. "
                "File does not contain specified mediainfo data and option to force_processing_if_no_disallowed_values is checked.", abspath)
