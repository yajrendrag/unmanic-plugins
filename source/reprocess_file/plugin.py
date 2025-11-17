#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     16 November 2025, (11:00 AM)

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

import logging

from unmanic.libs.unplugins.settings import PluginSettings

logger = logging.getLogger("Unmanic.Plugin.reprocess_file")

class Settings(PluginSettings):
    settings = {
        "target_library": "Select",
        "reprocess_based_on_task_status": True,
        "status_that_adds_file_to_queue": "Failed",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "target_library": self.__set_target_library_form_settings(),
            "reprocess_based_on_task_status":  {
                "label": "Check this option to only add the file back to the queue if it's completion status matches your configured result.  Otherwise the file is always added back to the task queue",
            },
            "status_that_adds_file_to_queue": self.__set_status_that_adds_file_to_queue_form_settings(),
        }

    def __set_target_library_form_settings(self):
        values = {
            "description": "Select the library to send the source file to for additional processing",
            "label": "Target Library",
            "input_type": "select",
            "select_options": self.get_library_options(),
        }
        return values

    def __set_status_that_adds_file_to_queue_form_settings(self):
        values = {
            "description": "Specify which task status - success or failure - is cause for reprocessing the file",
            "label": "Task Status",
            "input_type": "select",
            "select_options": [
                {
                    "value": "success",
                    "label": "Success",
                },
                {
                    "value": "failed",
                    "label": "Failed",
                },
            ],
        }
        if not self.get_setting('reprocess_based_on_task_status'):
            values["display"] = 'hidden'
        return values


    def get_library_options(self):
        from unmanic.libs.library import Library

        options = []
        libraries = Library.get_all_libraries()

        for lib in libraries:
            options.append({
                'value': lib['id'],
                'label': f"{lib['name']} (ID: {lib['id']})"
            })

        return options


def on_postprocessor_task_results(data):
    """
    Add the original source file to another library's pending tasks

    The 'data' object argument includes:
        library_id                      - The library that the current task is associated with.
        task_id                         - Integer, unique identifier of the task.
        task_type                       - String, "local" or "remote".
        final_cache_path                - The path to the final cache file that was then used as the source for all destination files.
        task_processing_success         - Boolean, did all task processes complete successfully.
        file_move_processes_success     - Boolean, did all postprocessor movement tasks complete successfully.
        destination_files               - List containing all file paths created by postprocessor file movements.
        source_data                     - Dictionary containing data pertaining to the original source file.
        start_time                      - Float, UNIX timestamp when the task began.
        finish_time                     - Float, UNIX timestamp when the task completed.

    :param data:
    :return:
    """

    from unmanic.libs import task

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # Get reprocessing settings
    reprocess_all = settings.get_setting("reprocess_based_on_task_status")
    if not reprocess_all:
        reprocess_which = settings.get_setting("status_that_adds_file_to_queue")

    if reprocess_all or (reprocess_which == "failed" and not data.get("task_processing_success")) or (reprocess_which == "success" and data.get("task_processing_success")):

        # Get library
        target_library_id = settings.get('target_library')

        # Get the original source file
        abspath = data.get('source_data').get('abspath')

        if target_library_id and source_file:

            # Add source file to the target library's queue
            task = Task()
            task.create_task_by_absolute_path(abspath, task_type='local', library_id=int(target_library_id))

            logger.info(f"Adding task for file {abspath} in library {target_library_id}")

        else:

            logger.error(f"Unable to create task for file {abspath} in library {target_library_id}")

    return data
