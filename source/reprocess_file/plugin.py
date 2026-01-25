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
import threading
import time
from pathlib import Path

from unmanic.libs.unplugins.settings import PluginSettings

logger = logging.getLogger("Unmanic.Plugin.reprocess_file")


def delayed_create_task(abspath, library_id, max_retries=10, delay=1):
    """
    Create a task with retry logic, waiting for any existing task to complete.

    When this plugin runs during post-processing, the current task still exists
    in the database (it gets deleted after the plugin returns). This function
    runs in a background thread and retries task creation until the original
    task is deleted and the new task can be created.

    :param abspath: Absolute path to the file to add to the task queue
    :param library_id: Target library ID for the new task
    :param max_retries: Maximum number of retry attempts
    :param delay: Delay in seconds between retry attempts
    :return: True if task was created, False otherwise
    """
    from unmanic.libs.task import Task

    for attempt in range(max_retries):
        time.sleep(delay)
        task = Task()
        if task.create_task_by_absolute_path(abspath, task_type='local', library_id=library_id):
            logger.info(f"Successfully created task for '{abspath}' in library {library_id}")
            return True
        logger.debug(f"Attempt {attempt + 1}/{max_retries}: Task creation failed for '{abspath}', retrying...")

    logger.error(f"Failed to create task for '{abspath}' in library {library_id} after {max_retries} attempts")
    return False

class Settings(PluginSettings):
    settings = {
        "target_library": "Select",
        "reprocess_based_on_task_status": True,
        "status_that_adds_file_to_queue": "Failed",
        "change_suffix": True,
        "new_suffix": "",
        "modify_path": True,
        "path_map": "",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "target_library": self.__set_target_library_form_settings(),
            "reprocess_based_on_task_status":  {
                "label": "Check this option to only add the file back to the queue if it's completion status matches your configured result.  Otherwise the file is always added back to the task queue",
            },
            "status_that_adds_file_to_queue": self.__set_status_that_adds_file_to_queue_form_settings(),
            "change_suffix":  {
                "label": "Check this option to process a file with the same name, but a different suffix - after checking this you'll be able to enter a new suffix",
            },
            "new_suffix": self.__set_new_suffix_form_settings(),
            "modify_path":  {
                "label": "Check this option to replace a component in the file path - after checking this you'll enter a mapping of old leading path:new leading path",
            },
            "path_map": self.__set_path_map_form_settings(),
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

    def __set_new_suffix_form_settings(self):
        values = {
            "label": "Specify a new suffix for the file that is to be reprocessed",
            "description": "multi-suffix formats ok, e.g., .language.srt",
            "input_type": "textarea",
        }
        if not self.get_setting('change_suffix'):
            values["display"] = 'hidden'
        return values

    def __set_path_map_form_settings(self):
        values = {
            "label": "Specify a path map translation to be made",
            "description": "for example, if you want to map /library/TVShows in a path like /library/TVShows/Showname/Season X/Showname - SXEY - Episode Title.mp4 to /Moved Shows, enter the map as /library/TVShows:/Moved Shows here",
            "input_type": "textarea",
        }
        if not self.get_setting('modify_path'):
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
    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    reprocess_all = not settings.get_setting("reprocess_based_on_task_status")
    change_suffix = settings.get_setting("change_suffix")
    if change_suffix:
        new_suffix = settings.get_setting("new_suffix")

    modify_path = settings.get_setting("modify_path")
    if modify_path:
        path_map = settings.get_setting("path_map")

    logger.debug(f"reprocess_all: {reprocess_all}")

    if not reprocess_all:
        reprocess_which = settings.get_setting("status_that_adds_file_to_queue")

    if reprocess_all or (reprocess_which == "failed" and not data.get("task_processing_success")) or (reprocess_which == "success" and data.get("task_processing_success")):

        # Get library
        target_library_id = settings.get_setting('target_library')

        # Get the original source file
        abspath = Path(data.get('source_data').get('abspath'))
        if change_suffix:
            abspath = abspath.with_suffix(new_suffix)

        if modify_path:
            abspath_parts_list = list(abspath.parts)
            old_path_parts = list(Path(path_map.split(':')[0]).parts)
            new_path_parts = list(Path(path_map.split(':')[1]).parts)
            new_parts_list = new_path_parts + abspath_parts_list[len(old_path_parts):]
            abspath = Path(*new_parts_list)

        logger.debug(f"abspath: {abspath}")

        if target_library_id and abspath:

            # Add source file to the target library's queue using a background thread.
            # This is necessary because the current task still exists in the database
            # when this plugin runs (it's deleted after the plugin returns). The background
            # thread waits for the current task to be deleted before creating the new one.
            thread = threading.Thread(
                target=delayed_create_task,
                args=(str(abspath), int(target_library_id)),
                daemon=True
            )
            thread.start()
            logger.info(f"Started background task to add '{abspath}' to library {target_library_id}")

        else:

            logger.error(f"Unable to create task for file '{abspath}' in library {target_library_id}")

    return data
