#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    unmanic-plugins.plugin.py

    Written by:               mmenanno
    Date:                     16 Jun 2024, (9:19 AM)

    Copyright:
        Copyright (C) 2024 Michael Menanno

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
import subprocess
import xml.etree.cElementTree as ET

from unmanic.libs.unplugins.settings import PluginSettings

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.mkvpropedit")


class Settings(PluginSettings):
    settings = {
        "add_track_statistics_tags": True,
        "add_encode_source_to_global_tags": False,
        "remove_title_tag": False,
        "other_args": ""
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "add_track_statistics_tags":   {
                "label": "Add Track Statistics Tags",
            },
            "add_encode_source_to_global_tags":        {
                "label": "Add Encode Source To Global Tags",
            },
            "remove_title_tag": {
                "label": "Remove Title Tag",
            },
            "other_args":           {
                "label": "Other Arguments",
            },
        }


def on_worker_process(data):
    """
    Runner function - enables additional configured processing jobs during the worker stages of a task.

    The 'data' object argument includes:
        worker_log              - Array, the log lines that are being tailed by the frontend. Can be left empty.
        library_id              - Number, the library that the current task is associated with.
        exec_command            - Array, a subprocess command that Unmanic should execute. Can be empty.
        command_progress_parser - Function, a function that Unmanic can use to parse the STDOUT of the command to collect progress stats. Can be empty.
        file_in                 - String, the source file to be processed by the command.
        file_out                - String, the destination that the command should output (may be the same as the file_in if necessary).
        original_file_path      - String, the absolute path to the original file.
        repeat                  - Boolean, should this runner be executed again once completed with the same variables.

    :param data:
    :return:

    """
    # Get required settings and filenames
    settings = Settings(library_id=data.get('library_id'))
    original_filename = os.path.basename(data.get('original_file_path'))
    tags_filename = os.path.splitext(data.get('file_in'))[0] + '_tags.xml'
    add_track_statistics_tags = settings.get_setting('add_track_statistics_tags')
    remove_title_tag = settings.get_setting('remove_title_tag')
    add_encode_source_to_global_tags = settings.get_setting('add_encode_source_to_global_tags')
    other_args = settings.get_setting('other_args')

    def is_mkv_file():
        # Check if the filename ends with '.mkv' (case-insensitive)
        return original_filename.lower().endswith('.mkv')

    def is_mkvpropedit_installed():
        try:
            # Run the command 'mkvpropedit --version' and capture the output
            result = subprocess.run(['mkvpropedit', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Check if the command was successful
            if result.returncode == 0:
                logger.debug(result.stdout)  # Print the version information
                return True

            logger.error("mkvpropedit is not installed or not available in the PATH.")
            logger.error(result.stderr)  # Print the error message
            return False
        except FileNotFoundError:
            logger.error("mkvpropedit is not installed or not available in the PATH.")
            return False

    def create_xml_tags_file():
        # Building an XML file structured like this to use for global tag creation:
        # <Tags>
        #     <Tag>
        #     <Simple>
        #         <Name>Encode source</Name>
        #         <String>Very.Fake.Movie.2020.REMUX.1080p.Blu-ray.AVC.DTS-HD.MA.5.1-Group</String>
        #     </Simple>
        #     </Tag>
        # </Tags>
        xml_tags = ET.Element("Tags")
        xml_tag = ET.SubElement(xml_tags, "Tag")
        xml_simple = ET.SubElement(xml_tag, "Simple")
        ET.SubElement(xml_simple, "Name").text = "Encode source"
        ET.SubElement(xml_simple, "String").text = original_filename

        tree = ET.ElementTree(xml_tags)
        logger.debug(f'Creating file for global tag creation: {tags_filename}')
        tree.write(tags_filename)

    def process_file():
        # Start off with calling mkvpropedit
        command = ['mkvpropedit']

        # Assemble args
        if add_track_statistics_tags:
            command.append('--add-track-statistics-tags')
        if remove_title_tag:
            command.extend(['-d', 'title'])
        if add_encode_source_to_global_tags:
            create_xml_tags_file()
            command.extend(['--tags', f'global:{tags_filename}'])
        if other_args:
            command.extend(other_args.split())

        # Pass in working file name
        command.append(data.get('file_in'))

        # Execute the command
        if command == ['mkvpropedit', data.get('file_in')]:
            logger.error("No arguments provided for mkvpropedit, skipping...")
            return

        data['exec_command'] = command

    if not is_mkv_file():
        logger.info("File is not an mkv file, skipping mkvpropedit...")
    elif not is_mkvpropedit_installed():
        logger.error("Please install mkvpropedit to proceed.")
    else:
        process_file()

    # mkvpropedit doesn't output to a new file, so pass on the same file we started with
    data['file_out'] = data.get('file_in')

    return data
