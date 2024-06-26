#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    unmanic-plugins.plugin.py

    Written by:               Josh.5 <jsunnex@gmail.com>
    Date:                     23 Jun 2021, (23:09 PM)

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

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.ignore_files_based_on_extension")


class Settings(PluginSettings):
    settings = {
        "disallowed_extensions":          '',
        "add_all_non_matching_extensions": False,
    }
    form_settings = {
        "disallowed_extensions":          {
            "label":       "Only include files that don't have these extensions",
            "description": "A comma separated list of file extensions."
        },
        "add_all_non_matching_extensions": {
            "label":       "Add all non_matching files to pending tasks list",
            "description": "If this option is enabled and the file does not match any of the specified file extensions,\n"
                           "this plugin will add the file to Unmanic's pending task list straight away\n"
                           "without executing any subsequent file test plugins.",
        }
    }


def file_ends_in_disallowed_extensions(path, disallowed_extensions):
    """
    Check if the file is in the disallowed search extensions

    :return:
    """
    # Get the file extension
    file_extension = os.path.splitext(path)[-1][1:]

    # Ensure the file's extension is lowercase
    file_extension = file_extension.lower()

    # If the config is empty (not yet configured) ignore everything
    if not disallowed_extensions:
        logger.debug("Plugin has not yet been configured with a list of file extensions to allow. Blocking everything.")
        return False

    # Check if it ends with one of the disallowed search extensions
    if file_extension and file_extension in disallowed_extensions.split(','):
        logger.debug("File '{}' does end in the disallowed file extensions '{}'.".format(path, disallowed_extensions))
        return True

    logger.debug("File '{}' does not end in the disallowed file extensions '{}'.".format(path, disallowed_extensions))
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
    # Get the path to the file
    abspath = data.get('path')

    # Configure settings object
    settings = Settings(library_id=data.get('library_id'))

    # Get the list of configured extensions to search for
    disallowed_extensions = settings.get_setting('disallowed_extensions')

    in_disallowed_extensions = file_ends_in_disallowed_extensions(abspath, disallowed_extensions)
    if in_disallowed_extensions:
        # Ignore this file
        data['add_file_to_pending_tasks'] = False
    elif not in_disallowed_extensions and settings.get_setting('add_all_non_matching_extensions'):
        # Force this file to have a pending task created
        data['add_file_to_pending_tasks'] = True
        logger.debug(
            "File '{}' should be added to task list. " \
            "File does not match any disallowed file extensions and plugin is configured to add all matching files.".format(abspath))
