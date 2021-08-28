#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.plugin.py

    Written by:               Josh.5 <jsunnex@gmail.com>
    Date:                     12 Aug 2021, (6:08 PM)

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

from encoder_video_hevc_nvenc.lib.ffmpeg import StreamMapper, Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.encoder_video_hevc_nvenc")


class Settings(PluginSettings):
    settings = {
        "advanced":              False,
        "hw_decoding":           False,
        "preset":                "medium",
        "profile":               "main",
        "max_muxing_queue_size": 2048,
        "main_options":          "-hwaccel cuda\n"
                                 "-hwaccel_device 0\n"
                                 "-threads 2\n",
        "advanced_options":      "-strict -2\n"
                                 "-max_muxing_queue_size 2048\n",
        "custom_options":        "-preset medium\n"
                                 "-profile:v main\n"
                                 "-pix_fmt p010le\n"
                                 "-rc:v vbr_hq\n"
                                 "-qmin 0\n"
                                 "-rc-lookahead 32\n"
                                 "-spatial_aq:v 1\n"
                                 "-aq-strength:v 8\n"
                                 "-a53cc 0\n"
                                 "-b:v:0 4M\n",
        "keep_container":        True,
        "dest_container":        "mkv",
    }

    def __init__(self):
        self.form_settings = {
            "advanced":              {
                "label": "Write your own FFmpeg params",
            },
            "hw_decoding":           self.__set_hw_decoding_checkbox_form_settings(),
            "max_muxing_queue_size": self.__set_max_muxing_queue_size_form_settings(),
            "preset":                self.__set_preset_form_settings(),
            "profile":               self.__set_profile_form_settings(),
            "main_options":          self.__set_main_options_form_settings(),
            "advanced_options":      self.__set_advanced_options_form_settings(),
            "custom_options":        self.__set_custom_options_form_settings(),
            "keep_container":        {
                "label": "Keep the same container",
            },
            "dest_container":        self.__set_destination_container(),
        }

    def __set_hw_decoding_checkbox_form_settings(self):
        values = {
            "label":      "Enable NVDEC HW Accelerated Decoding?",
            "input_type": "checkbox",
        }
        if self.get_setting('advanced'):
            values["display"] = 'hidden'
        return values

    def __set_max_muxing_queue_size_form_settings(self):
        values = {
            "label":          "Max input stream packet buffer",
            "input_type":     "slider",
            "slider_options": {
                "min": 1024,
                "max": 10240,
            },
        }
        if self.get_setting('advanced'):
            values["display"] = 'hidden'
        return values

    def __set_preset_form_settings(self):
        values = {
            "label":          "NVENC Encoder Quality Preset",
            "input_type":     "select",
            "select_options": [
                {
                    'value': "fast",
                    'label': "Fast",
                },
                {
                    'value': "medium",
                    'label': "Medium",
                },
                {
                    'value': "slow",
                    'label': "Slow",
                },
                {
                    'value': "lossless",
                    'label': "Lossless (slowest)",
                },
            ],
        }
        if self.get_setting('advanced'):
            values["display"] = 'hidden'
        return values

    def __set_profile_form_settings(self):
        values = {
            "label":          "Profile",
            "input_type":     "select",
            "select_options": [
                {
                    'value': "main",
                    'label': "Main",
                },
                {
                    'value': "main10",
                    'label': "Main10",
                },
                {
                    'value': "rext",
                    'label': "Range Extended",
                },
            ],
        }
        if self.get_setting('advanced'):
            values["display"] = 'hidden'
        return values

    def __set_main_options_form_settings(self):
        values = {
            "label":      "Write your own custom main options",
            "input_type": "textarea",
        }
        if not self.get_setting('advanced'):
            values["display"] = 'hidden'
        return values

    def __set_advanced_options_form_settings(self):
        values = {
            "label":      "Write your own custom advanced options",
            "input_type": "textarea",
        }
        if not self.get_setting('advanced'):
            values["display"] = 'hidden'
        return values

    def __set_custom_options_form_settings(self):
        values = {
            "label":      "Write your own custom video options",
            "input_type": "textarea",
        }
        if not self.get_setting('advanced'):
            values["display"] = 'hidden'
        return values

    def __set_destination_container(self):
        values = {
            "label":          "Set the output container",
            "input_type":     "select",
            "select_options": [
                {
                    'value': "mkv",
                    'label': ".mkv - Matroska",
                },
                {
                    'value': "avi",
                    'label': ".avi - AVI (Audio Video Interleaved)",
                },
                {
                    'value': "mov",
                    'label': ".mov - QuickTime / MOV",
                },
                {
                    'value': "mp4",
                    'label': ".mp4 - MP4 (MPEG-4 Part 14)",
                },
            ],
        }
        if self.get_setting('keep_container'):
            values["display"] = 'hidden'
        return values


class PluginStreamMapper(StreamMapper):
    def __init__(self):
        super(PluginStreamMapper, self).__init__(logger, 'video')

    def test_stream_needs_processing(self, stream_info: dict):
        if stream_info.get('codec_name').lower() in ['h265', 'hevc']:
            return False
        return True

    def custom_stream_mapping(self, stream_info: dict, stream_id: int):
        settings = Settings()

        if settings.get_setting('advanced'):
            stream_encoding = ['-c:v:{}'.format(stream_id), 'hevc_nvenc']
            stream_encoding += settings.get_setting('custom_options').split()
        else:
            stream_encoding = [
                '-c:v:{}'.format(stream_id), 'hevc_nvenc',
                '-profile:v:{}'.format(stream_id), settings.get_setting('profile'),
                '-preset', settings.get_setting('preset'),
            ]

        return {
            'stream_mapping':  ['-map', '0:v:{}'.format(stream_id)],
            'stream_encoding': stream_encoding,
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
    # Get the path to the file
    abspath = data.get('path')

    # Get file probe
    probe = Probe(logger)
    probe.file(abspath)

    # Get stream mapper
    mapper = PluginStreamMapper()
    mapper.set_probe(probe)

    if mapper.streams_need_processing():
        # Mark this file to be added to the pending tasks
        data['add_file_to_pending_tasks'] = True
        logger.debug("File '{}' should be added to task list. Probe found streams require processing.".format(abspath))
    else:
        logger.debug("File '{}' does not contain streams require processing.".format(abspath))

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
    # Default to not run the FFMPEG command unless streams are found to be converted
    data['exec_command'] = []
    data['repeat'] = False

    # Get the path to the file
    abspath = data.get('file_in')

    # Get file probe
    probe = Probe(logger)
    probe.file(abspath)

    # Get stream mapper
    mapper = PluginStreamMapper()
    mapper.set_probe(probe)

    if mapper.streams_need_processing():
        settings = Settings()

        # Build ffmpeg args and add them to the return data
        data['exec_command'] = [
            'ffmpeg',
            '-hide_banner',
            '-loglevel',
            'info',
            '-strict', '-2',
        ]

        if settings.get_setting('advanced'):
            data['exec_command'] += settings.get_setting('main_options').split()
        else:
            # Enable HW decoding?
            if settings.get_setting('hw_decoding'):
                # TODO: Find the device. Add config option to select from available GPUs
                data['exec_command'] += [
                    '-hwaccel', 'cuda',
                    '-hwaccel_device', '0',
                ]

            # Set threads as one for slow conversions - produces better quality
            if settings.get_setting('preset') in ['fast', 'medium']:
                data['exec_command'] += ['-threads', '4']
            else:
                data['exec_command'] += ['-threads', '1']

        # Add file in
        data['exec_command'] += ['-i', abspath]

        if settings.get_setting('advanced'):
            data['exec_command'] += settings.get_setting('advanced_options').split()
        else:
            data['exec_command'] += ['-max_muxing_queue_size', str(settings.get_setting('max_muxing_queue_size'))]

        # Add the stream mapping and the encoding args
        data['exec_command'] += mapper.get_stream_mapping()
        data['exec_command'] += mapper.get_stream_encoding()

        split_file_out = os.path.splitext(data.get('file_out'))
        if settings.get_setting('keep_container'):
            # Do not remux the file. Keep the file out in the same container
            split_file_in = os.path.splitext(abspath)
            data['file_out'] = "{}{}".format(split_file_out[0], split_file_in[1])
        else:
            # Force the remux to the configured container
            data['file_out'] = "{}.{}".format(split_file_out[0], settings.get_setting('dest_container'))

        data['exec_command'] += ['-y', data.get('file_out')]

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe)

        data['command_progress_parser'] = parser.parse_progress

    return data