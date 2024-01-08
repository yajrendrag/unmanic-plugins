#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     5 Oct 2023, (11:40 AM)
 
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
import subprocess
import ffsubsync

from unmanic.libs.unplugins.settings import PluginSettings

from keep_only_video_and_audio_streams.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.keep_only_video_and_audio_streams")

class Settings(PluginSettings):
    settings = {
        "extract_subtitles":      False,
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "extract_subtitles": {
            "label": "Check this option if you want to extract subtitles to the original file directory",
            },
        }

def streams_to_keep(streams):
    image_video_codecs = ['alias_pix','apng','brender_pix','dds','dpx','exr','fits','gif','mjpeg','mjpegb','pam','pbm','pcx','pfm','pgm','pgmyuv','pgx',
                          'photocd','pictor','pixlet','png','ppm','ptx','sgi','sunrast','tiff','vc1image','wmv3image','xbm','xface','xpm','xwd']
    return [streams[i]['index'] for i in range(len(streams)) if streams[i]['codec_type'] in ["video","audio"] and streams[i]['codec_name'] not in image_video_codecs]

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
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(abspath):
        # File probe failed, skip the rest of this test
        return data
    else:
        streams = probe.get_probe()["streams"]

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    all_streams = [streams[i]['index'] for i in range(len(streams))]
    if streams_to_keep(streams) != all_streams:
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

    # Get the path to the input and output files
    abspath = data.get('file_in')
    outfile = data.get('file_out')

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(abspath):
        # File probe failed, skip the rest of this test
        return data
    else:
        streams = probe.get_probe()["streams"]

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    extract_subs = settings.get_setting('extract_subtitles')

    all_streams = [streams[i]['index'] for i in range(len(streams))]
    stk = streams_to_keep(streams)
    if stk != all_streams:

        # set common ffmpeg arguments
        ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-strict', '-2']

        # extract subtitles if enabled
        if extract_subs:
            sub_streams = [streams[i]['index'] for i in range(len(streams)) if streams[i]['codec_type'] in ["subtitle"]]
            mapped_sub_streams = []
            for i in sub_streams:
                sub_language = [streams[i]["tags"]["language"] if streams[i]['codec_type'] in ["subtitle"] and "tags" in streams[i] and "language" in streams[i]["tags"] else i]
                subfile = os.path.splitext(data['original_file_path'])[0] + '.' + str(sub_language[0]) + '.srt'
                ffmpeg_subs_args = ['ffmpeg'] + ffmpeg_args + ['-map', '0:'+str(i), '-c:'+str(i), 'subrip', '-y', str(subfile)]
                logger.debug("subtitle extraction args: '{}'".format(ffmpeg_subs_args))
                es = subprocess.check_call(ffmpeg_subs_args, shell=False)
                if es:
                    logger.error("Subtitle extraction failed - video: '{}', stream: '{}', language: '{}'".format(data['original_file_path'], i, str(sub_language[0])))
                else:
                    ss = subprocess.check_call(['ffs', data['original_file_path'], '-i', subfile, '--no-fix-framerate', '-o', os.path.splitext(subfile)[0]+'-sync.srt'], shell=False)
                    if ss:
                        logger.error("Subtitle sync failed - video: '{}', stream: '{}', language: '{}'".format(data['original_file_path'], i, str(sub_language[0])))

        # stream order changed, remap audio streams
        mapped_streams = []
        for i in stk:
            mapped_streams += ['-map', '0:'+str(i)]
        ffmpeg_args += mapped_streams
        ffmpeg_args += ['-c', 'copy', '-map_chapters', '-1', '-y', str(outfile)]
        logger.debug("ffmpeg_args: '{}'".format(ffmpeg_args))

        # Apply ffmpeg args to command
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe)
        data['command_progress_parser'] = parser.parse_progress

    return data
