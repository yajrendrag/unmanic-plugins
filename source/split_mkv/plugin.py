#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     3 Dec 2024, (17:45 PM)

    Copyright:
        Copyright (C) 2024 Jay Gardner

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
import ffmpeg
import hashlib
import shutil
import glob

from unmanic.libs.unplugins.settings import PluginSettings

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.split_mkv")

class Settings(PluginSettings):
    settings = {
        "split_method":          "",
        "chapter_time":          "",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "split_method":        self.__set_split_method_form_settings(),
            "chapter_time":        self.__set_chapter_time_form_settings(),
        }

    def __set_split_method_form_settings(self):
        values = {
            "label":          "Select method of splitting file - chapter marks or time value",
            "label":      "Enter Choice",
            "input_type": "select",
            "select_options": [
                {
                    "value": "chapters",
                    "label": "Chapter Marks",
                },
                {
                    "value": "time",
                    "label": "Time Interval",
                },
                {
                    "value": "combo",
                    "label": "Chapter Marks with fallback of Time Interval",
                },
            ],
        }
        return values

    def __set_chapter_time_form_settings(self):
        values = {
            "label":          "Enter time period in whole minutes upon which to split the file, i.e., each such period will result in another mkv file",
            "input_type":     "textarea",
        }
        if self.get_setting('split_method') == 'chapters':
            values["display"] = 'hidden'
        return values


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

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    split_method = settings.get_setting('split_method')
    if split_method != 'chapters':
        chapter_time = settings.get_setting('chapter_time')

    if split_method == 'chapters' or split_method == 'combo':
        chapters = ffmpeg.probe(abspath, show_chapters=None)['chapters']
        if chapters:
            logger.info("Splitting file '{}' based on presence of '{}' chapters".format(abspath, len(chapters)))
            data['add_file_to_pending_tasks'] = True
            return data
        else:
            if split_method != 'combo':
                logger.info("No chapters found and split_method = chapters. Aborting")
                return data
    if split_method == 'combo' or split_method == 'time':
        logger.info("Splitting file '{}' based on chapter times of '{}' minutes".format(abspath, chapter_time))
        data['add_file_to_pending_tasks'] = True
        return data

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

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # Get the path to the file
    abspath = data.get('file_in')
    outpath = data.get('file_out')
    srcpath = data.get('original_file_path')

    split_method = settings.get_setting('split_method')
    if split_method != 'chapters':
        chapter_time = settings.get_setting('chapter_time')

    if split_method == 'chapters' or split_method == 'combo':
        chapters = ffmpeg.probe(abspath, show_chapters=None)['chapters']
        if chapters:
            logger.info("Splitting file '{}' based on presence of '{}' chapters".format(abspath, len(chapters)))
        else:
            if split_method != 'combo':
                logger.info("No chapters found and split_method = chapters. Aborting")
                return data
    if split_method == 'combo' or split_method == 'time':
        logger.info("Splitting file '{}' based on chapter times of '{}' minutes".format(abspath, chapter_time))

    # Construct command
    split_hash = hashlib.md5(os.path.basename(srcpath).encode('utf8')).hexdigest()
    tmp_dir = os.path.join('/tmp/unmanic/', '{}'.format(split_hash)) + '/'
    split_base = os.path.split(srcpath)[1]
    split_base_noext = os.path.splitext(split_base)[0] + '.split'
    sfx = os.path.splitext(split_base)[1]

    data['exec_command'] = ['mkvmerge']
    if split_method == 'chapters' or (split_method == 'combo' and chapters):
        data['exec_command'] += ['-o', tmp_dir + split_base_noext + sfx, '--split', 'chapters:all', abspath]
        return data
    if split_method == 'combo' or split_method == 'time':
        split_time = str(60 * int(chapter_time)) + 's'
        data['exec_command'] += ['-o', tmp_dir + split_base_noext + sfx, '--split', split_time, abspath]
        return data

def on_postprocessor_task_results(data):
    """
    Runner function - provides a means for additional postprocessor functions based on the task success.

    The 'data' object argument includes:
        final_cache_path                - The path to the final cache file that was then used as the source for all destination files.
        library_id                      - The library that the current task is associated with.
        task_processing_success         - Boolean, did all task processes complete successfully.
        file_move_processes_success     - Boolean, did all postprocessor movement tasks complete successfully.
        destination_files               - List containing all file paths created by postprocessor file movements.
        source_data                     - Dictionary containing data pertaining to the original source file.

    :param data:
    :return:
    """

    # move files from temp dir in cache to destination dir
    logger.info("dest files: '{}'".format(data.get('destination_files')))
    srcpathbase = data.get('source_data')['basename']
    split_hash = hashlib.md5(srcpathbase.encode('utf8')).hexdigest()
    tmp_dir = os.path.join('/tmp/unmanic/', '{}'.format(split_hash)) + '/'
    dest_file = data.get('destination_files')[0]
    dest_dir = os.path.split(dest_file)[0] + '/'
    for f in glob.glob(tmp_dir + "/*.mkv"):
        shutil.copy2(f, dest_dir)

    # remove temp files and directory
    for f in glob.glob(tmp_dir + "/*.mkv"):
        os.remove(f)
    shutil.rmtree(tmp_dir)

    return
