#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     23 August 2025, (19:38 PM)

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
import re
import ffmpeg

from unmanic.libs.unplugins.settings import PluginSettings


# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.detect_bars")

class Settings(PluginSettings):
    settings = {
        "border_threshold":         "",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "border_threshold":              {
                "label": "Enter border threshold in pixels - bars smaller than this size will be ignored and file will not be added to queue",
            }
    }

def get_probe(f):
    try:
        p = ffmpeg.probe(f)
    except ffmpeg.Error as e:
        p = e.stdout.decode('utf8').replace('\n','')
    return p

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
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    border_thresh = settings.get_setting('border_threshold')

    # Get the path to the file
    abspath = data.get('path')

    p = get_probe(abspath)
    if p:
        streams = p['streams']
    else:
        logger.error(f"could not probe file {abspath} - aborting")
        return data

    width = [streams[i]['width'] for i in range (len(streams)) if streams[i]['codec_type'] == 'video']
    height = [streams[i]['height'] for i in range (len(streams)) if streams[i]['codec_type'] == 'video']

    out, err = (
        ffmpeg
        .input(input_file, ss=10)  # start 10s in, optional for cropping to main scene
        .output('null', f='null', vf='cropdetect')
        .run(capture_stdout=True, capture_stderr=True)
    )

    crop_regex = re.compile(r'crop=(\d+:\d+:\d+:\d+)')
    crops = crop_regex.findall(err.decode())

    crop_w = crops[-1].split(':')[0]
    crop_h = crops[-1].split(':')[1]

    logger.debug(f"crop width: {crop_w}, crop height: {crop_h}")

    if int(width) - int(crop_w) > int(border_thresh) and int(height) - int(crop_h) > int(border_thresh):
        logger.info(f"video file {abspath} has black bars larger than the threshold; add file to task queue")
        data['add_file_to_pending_tasks'] = True
    else:
        logger.info(f"video file {abspath} does not have black bars or they are less than the threshold; do not add file to task queue")

    return data

