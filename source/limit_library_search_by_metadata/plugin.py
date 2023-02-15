#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    unmanic-plugins.plugin.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     15 Feb 2023, (12:01 AM)

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

from limit_library_search_by_metadata.lib.ffmpeg.probe import Probe

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.limit_library_search_by_metadata")


class Settings(PluginSettings):
    settings = {
        "disallowed_metadata":          '',
        "metadata_value":               '',
        "process_if_does_not_have_matching_metadata": False,
    }
    form_settings = {
        "disallowed_metadata":          {
            "label":       "metadata field name to search for",
            "description": "Metadata field to test; do not process file if this field contains metadata_value per below."
        },
        "metadata_value":          {
            "label":       "do not process files containing this string",
            "description": "A unique, key phrase in the metadata value that inidicates path should not be processed."
        },
        "process_if_does_not_have_matching_metadata": {
            "label":       "Add any files that do not have matching metadata to pending tasks list",
            "description": "If this option is enabled and the file does not contain matching metadata,\n"
                           "this plugin will add the file to Unmanic's pending task list straight away\n"
                           "without executing any subsequent file test plugins.",
        }
    }


def file_has_disallowed_metadata(path, disallowed_metadata, metadata_value):
    """
    Check if the file contains disallowed search metadata

    :return:
    """

    # initialize Probe
    probe_data=Probe(logger, allowed_mimetypes=['video'])

    # Get stream data from probe
    if probe_data.file(path):
        streams = probe_data.get_probe()["streams"][0]

    # If the config is empty (not yet configured) ignore everything
    if not disallowed_metadata:
        logger.debug("Plugin has not yet been configured with disallowed metadata. Blocking everything.")
        return True

    # Check if stream contains disallowed metadata
    if streams and streams[disallowed_metadata] and metadata_value in streams[disallowed_metadata]:
        return True

    logger.debug("File '{}' does not contain disallowed metadata '{}': '{}'.".format(path, disallowed_metadata, metadata_value))
    return False


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

    # initialize Probe
    probe_data=Probe(logger, allowed_mimetypes=['video'])

    # Get the path to the file
    abspath = data.get('path')

    # Get stream data from probe
    if probe_data.file(abspath):
        streams = probe_data.get_probe()["streams"][0]

    # Configure settings object
    settings = Settings(library_id=data.get('library_id'))

    # Get the list of configured metadata to search for
    disallowed_metadata = settings.get_setting('disallowed_metadata')
    metadata_value = settings.get_setting('metadata_value')

    has_disallowed_metadata = file_has_disallowed_metadata(abspath, disallowed_metadata, metadata_value)

    if has_disallowed_metadata:
        # Ignore this file
        data['add_file_to_pending_tasks'] = False
    elif not has_disallowed_metadata and settings.get_setting('process_if_does_not_have_matching_metadata'):
        # Force this file to have a pending task created
        data['add_file_to_pending_tasks'] = True
        logger.debug(
            "File '{}' should be added to task list. " \
            "File does not contain disallowed metadata and plugin is configured to add all non-matching files.".format(abspath))
