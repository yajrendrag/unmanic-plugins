#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.plugin.py

    Written by:               Josh.5 <jsunnex@gmail.com>
    Date:                     4 June 2022, (6:08 PM)

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

"""
TODO:
    - Add support for 2-pass libx264 and libx265
    - Add support for VAAPI 264
    - Add support for NVENC 264/265
    - Add advanced input forms for building custom ffmpeg queries
    - Add support for source bitrate matching on basic mode
"""

import logging
import os
import humanfriendly

from video_transcoder.lib import plugin_stream_mapper
from video_transcoder.lib.ffmpeg import Parser, Probe
from video_transcoder.lib.global_settings import GlobalSettings
from video_transcoder.lib.encoders.libx import LibxEncoder
from video_transcoder.lib.encoders.qsv import QsvEncoder
from video_transcoder.lib.encoders.vaapi import VaapiEncoder

from unmanic.libs.unplugins.settings import PluginSettings
from unmanic.libs.directoryinfo import UnmanicDirectoryInfo

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.video_transcoder")

default_resolutions = {
    '480p_sdtv':   {
        'width':  854,
        'height': 480,
        'label':  "480p (SDTV)",
    },
    '576p_sdtv':   {
        'width':  1024,
        'height': 576,
        'label':  "576p (SDTV)",
    },
    '720p_hdtv':   {
        'width':  1280,
        'height': 720,
        'label':  "720p (HDTV)",
    },
    '1080p_hdtv':  {
        'width':  1920,
        'height': 1080,
        'label':  "1080p (HDTV)",
    },
    'dci_2k_hdtv': {
        'width':  2048,
        'height': 1080,
        'label':  "DCI 2K (HDTV)",
    },
    '1440p':       {
        'width':  2560,
        'height': 1440,
        'label':  "1440p (WQHD)",
    },
    '4k_uhd':      {
        'width':  3840,
        'height': 2160,
        'label':  "4K (UHD)",
    },
    'dci_4k':      {
        'width':  4096,
        'height': 2160,
        'label':  "DCI 4K",
    },
    '8k_uhd':      {
        'width':  8192,
        'height': 4608,
        'label':  "8k (UHD)",
    },
}

class Settings(PluginSettings):

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.settings = self.__build_settings_object()
        self.encoders = {
            "libx265":    LibxEncoder(self),
            "libx264":    LibxEncoder(self),
            "hevc_qsv":   QsvEncoder(self),
            "h264_qsv":   QsvEncoder(self),
            "hevc_vaapi": VaapiEncoder(self),
        }

        self.global_settings = GlobalSettings(self)
        self.form_settings = self.__build_form_settings_object()

    def __build_form_settings_object(self):
        """
        Build a form input config for all the plugin settings
        This input changes dynamically based on the encoder selected

        :return:
        """
        return_values = {}
        for setting in self.settings:
            # Fetch currently configured encoder
            # This should be done every loop as some settings my change this value
            selected_encoder = self.encoders.get(self.get_setting('video_encoder'))
            # Disable form by default
            setting_form_settings = {
                "display": "hidden"
            }
            # First check if selected_encoder object has form settings method
            if hasattr(selected_encoder, 'get_{}_form_settings'.format(setting)):
                getter = getattr(selected_encoder, 'get_{}_form_settings'.format(setting))
                if callable(getter):
                    setting_form_settings = getter()
            # Next check if global_settings object has form settings method
            elif hasattr(self.global_settings, 'get_{}_form_settings'.format(setting)):
                getter = getattr(self.global_settings, 'get_{}_form_settings'.format(setting))
                if callable(getter):
                    setting_form_settings = getter()
            # Apply form settings
            return_values[setting] = setting_form_settings
        return return_values

    def __encoder_settings_object(self):
        """
        Returns a list of encoder settings for FFmpeg

        :return:
        """
        # Fetch all encoder settings from encoder libs
        libx_options = LibxEncoder.options()
        qsv_options = QsvEncoder.options()
        vaapi_options = VaapiEncoder.options()
        return {
            **libx_options,
            **qsv_options,
            **vaapi_options
        }

    def __build_settings_object(self):
        # Global and main config options
        global_settings = GlobalSettings.options()
        main_options = global_settings.get('main_options')
        encoder_selection = global_settings.get('encoder_selection')
        encoder_settings = self.__encoder_settings_object()
        advanced_input_options = global_settings.get('advanced_input_options')
        output_settings = global_settings.get('output_settings')
        integrated_filter_settings = global_settings.get('integrated_filter_settings')
        resolution_settings = global_settings.get('resolution_settings')
        filter_settings = global_settings.get('filter_settings')
        return {
            **main_options,
            **encoder_selection,
            **encoder_settings,
            **advanced_input_options,
            **output_settings,
            **integrated_filter_settings,
            **resolution_settings,
            **filter_settings,
        }


def file_marked_as_force_transcoded(path):
    directory_info = UnmanicDirectoryInfo(os.path.dirname(path))
    try:
        has_been_force_transcoded = directory_info.get('video_transcoder', os.path.basename(path))
    except NoSectionError as e:
        has_been_force_transcoded = ''
    except NoOptionError as e:
        has_been_force_transcoded = ''
    except Exception as e:
        logger.debug("Unknown exception %s.", e)
        has_been_force_transcoded = ''

    if has_been_force_transcoded == 'force_transcoded':
        # This file has already has been force transcoded
        return True

    # Default to...
    return False

def get_test_resolution(settings):
    target_resolution = settings.get('target_resolution')
    # Set the target resolution
    #custom_resolutions = settings.get('custom_resolutions')
    test_resolution = {
        'width':  default_resolutions.get(target_resolution, {}).get('width'),
        'height': default_resolutions.get(target_resolution, {}).get('height'),
    }
    #if custom_resolutions:
    #    test_resolution = {
    #        'width':  settings.get_setting('{}_width'.format(target_resolution)),
    #        'height': settings.get_setting('{}_height'.format(target_resolution)),
    #    }
    return test_resolution


def get_video_stream_data(streams):
    width = 0
    height = 0
    video_stream_index = 0

    for stream in streams:
        if stream.get('codec_type') == 'video':
            width = stream.get('width', stream.get('coded_width', 0))
            height = stream.get('height', stream.get('coded_height', 0))
            video_stream_index = stream.get('index')
            break

    return width, height, video_stream_index

def check_file_size_under_min_file_size(path, minimum_file_size):
    file_stats = os.stat(os.path.join(path))
    logger.debug("actual file size: '{}', minimum file size to be transcoded: '{}'".format(file_stats.st_size, humanfriendly.parse_size(minimum_file_size)))
    if int(humanfriendly.parse_size(minimum_file_size)) < int(file_stats.st_size):
        return False
    return True

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

    # Get file probe
    probe = Probe.init_probe(data, logger, allowed_mimetypes=['video'])
    if not probe:
        # File not able to be probed by ffprobe
        return

    # Get stream mapper
    mapper = plugin_stream_mapper.PluginStreamMapper()
    mapper.set_default_values(settings, abspath, probe)

    # Check if this file needs to be processed
    if mapper.streams_need_processing():
        if file_marked_as_force_transcoded(abspath) and mapper.forced_encode:
            logger.debug(
                "File '%s' has been previously marked as forced transcoded. Plugin found streams require processing, but will ignore this file.",
                abspath)
            return
        # Mark this file to be added to the pending tasks
        data['add_file_to_pending_tasks'] = True
        logger.debug("File '%s' should be added to task list. Plugin found streams require processing.", abspath)
    else:
        logger.debug("File '%s' does not contain streams require processing.", abspath)


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
    # Default to no FFMPEG command required. This prevents the FFMPEG command from running if it is not required
    data['exec_command'] = []
    data['repeat'] = False

    # Get settings
    settings = Settings(library_id=data.get('library_id'))

    # Get the path to the file
    abspath = data.get('file_in')

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(abspath):
        # File probe failed, skip the rest of this test
        return

    logger.debug("Worker settings test: resolution_settings: '{}'".format(settings.get_setting('resolution_settings')))

    # Get video width and height
    vid_width, vid_height, video_stream_index = get_video_stream_data(probe.get('streams', []))

    # Get integrated ignore settings
    integrated_ignore = settings.get_setting('integrated_ignore')
    # Get the test resolution
#    test_resolution = get_test_resolution(settings.get_setting('resolution_settings'))
    test_resolution = settings.get_setting('ignore_files_over_rez')

    # Get max file size
    min_file_size = settings.get_setting('ignore_files_under_size')

#    limit_label = default_resolutions.get(settings.get_setting('resolution_settings').get('ignore_files_over_rez'), {}).get('label')
    limit_width = default_resolutions.get(test_resolution).get('width')
    limit_height = default_resolutions.get(test_resolution).get('height')
    limit_label = default_resolutions.get(test_resolution).get('label')

    logger.debug("probe data: width - '{}', height - '{}', stream - '{}'".format(vid_width, vid_height, video_stream_index))
    logger.debug("test_resolution: '{}'".format(test_resolution))
    logger.debug("limit label: '{}'".format(limit_label))
    logger.debug("limit width: '{}'".format(limit_width))
    logger.debug("limit height: '{}'".format(limit_height))

    # Get stream mapper
    mapper = plugin_stream_mapper.PluginStreamMapper()
    mapper.set_default_values(settings, abspath, probe)

    # Check if this file needs to be processed
    if mapper.streams_need_processing():
        if file_marked_as_force_transcoded(abspath) and mapper.forced_encode:
            # Do not process this file, it has been force transcoded once before
            return

        # Set the output file
        if settings.get_setting('keep_container'):
            # Do not remux the file. Keep the file out in the same container
            mapper.set_output_file(data.get('file_out'))
        else:
            # Force the remux to the configured container
            container_extension = settings.get_setting('dest_container')
            split_file_out = os.path.splitext(data.get('file_out'))
            new_file_out = "{}.{}".format(split_file_out[0], container_extension.lstrip('.'))
            mapper.set_output_file(new_file_out)
            data['file_out'] = new_file_out

        # Get generated ffmpeg args
        logger.debug("integrated ignore filters: rez: '{}', size: '{}'".format(test_resolution, min_file_size))

        ffmpeg_args = mapper.get_ffmpeg_args()

#        logger.debug("ffmpeg args: '%s'", ffmpeg_args)

        # check if file should be ignored
        logger.debug("Integrated Ignore Filter: '{}'".format(integrated_ignore))
        logger.debug("vid_width: '{}', limit_width: '{}', vid_height: '{}', limit_height: '{}'".format(vid_width, limit_width, vid_height, limit_height))
        if integrated_ignore and (int(vid_width) > int(limit_width) or int(vid_height) > int(limit_height) or check_file_size_under_min_file_size(abspath, min_file_size)):
            # file should be ignored:
            ignoring_file = True
            output_path = data.get('file_out')
            ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', abspath, '-map', '0', '-c', 'copy', output_path]
            logger.warning("file '{}' is being stream copied as it is over the specified resolution or under the minimum size".format(abspath))
        else:
            ignoring_file = False

        # Apply ffmpeg args to command
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args
        logger.debug("ffmpeg args '%s'", ffmpeg_args)

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe)
        data['command_progress_parser'] = parser.parse_progress

        if settings.get_setting('force_transcode') and not ignoring_file:
            cache_directory = os.path.dirname(data.get('file_out'))
            if not os.path.exists(cache_directory):
                os.makedirs(cache_directory)
            with open(os.path.join(cache_directory, '.force_transcode'), 'w') as f:
                f.write('')

    return


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
    # Get settings
    settings = Settings(library_id=data.get('library_id'))

    # Get the original file's absolute path
    original_source_path = data.get('source_data', {}).get('abspath')
    if not original_source_path:
        logger.error("Provided 'source_data' is missing the source file abspath data.")
        return

    # Mark the source file to be ignored on subsequent scans if 'force_transcode' was enabled
    if settings.get_setting('force_transcode'):
        cache_directory = data.get('final_cache_path')
        if os.path.exists(os.path.join(cache_directory, '.force_transcode')):
            directory_info = UnmanicDirectoryInfo(os.path.dirname(original_source_path))
            directory_info.set('video_transcoder', os.path.basename(original_source_path), 'force_transcoded')
            directory_info.save()
            logger.debug("Ignore on next scan written for '%s'.", original_source_path)
