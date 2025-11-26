#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     25 November 2025, (7:40 PM)

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
import os
import subprocess
import logging

def on_postprocessor_task_results(data):
    """
    Runner function - provides a means for additional postprocessor functions based on the task success.

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

    # Was task successful
    success = data.get('task_processing_success ')

    if success:
        # Loop over all destination files created
        destinations = data.get('destination_files')
        for dest in destinations:

            # Get the file extension
            sfx = os.path.splitext(dest)[-1][1:].lower()

            # if the file is an mkv file, add the tracks statistics tags
            if sfx in ['mkv']:
                cmd = ['/usr/bin/mkvpropedit', dest, '--add-track-statistics-tags']
                try:
                    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e: 
                    logger.error(f"Error adding track statistics for file: {dest}.  Reason: {e.stderr}.  Skipping file.")
                    continue
                logger.info(f"File {dest} is an mkv file, adding (or updating if they exist) the tracks statistics")

    return data
