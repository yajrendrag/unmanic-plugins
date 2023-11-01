#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    unmanic-plugins.plugin.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     31 Oct 2023, (5:00 PM)

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

from unmanic.libs.unplugins.settings import PluginSettings

from rename_file.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.rename_file")

class Settings(PluginSettings):
    settings = {
        "append_video_resolution":      False,
        "append_audio_codec":           False,
        "append_audio_channel_layout":  False,
        "append_audio_language":        False,
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "append_video_resolution": {
                "label": "Check this option if you want to append video resolution to file name",
            },
            "append_audio_codec": {
                "label": "Check this option if you want to append audio codec name to file name",
            },
            "append_audio_channel_layout": {
                "label": "Check this option if you want to append audio channel layout to file name",
            },
            "append_audio_language": {
                "label": "Check this option if you want to append audio language to file name",
            }
        }

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
    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    status = data.get('task_processing_success')
    logger.debug("status: '{}'".format(status))

    if status:
        abspath = data.get('source_data').get('abspath')
        append_video_resolution = settings.get_setting('append_video_resolution')
        append_audio_codec = settings.get_setting('append_audio_codec')
        append_audio_channel_layout = settings.get_setting('append_audio_channel_layout')
        append_audio_language = settings.get_setting('append_audio_language')

        logger.debug("abspath: '{}', append_video_resolution: '{}', append_audio_codec: '{}', append_audio_channel_layout: '{}', append_audio_language: '{}'".format(abspath, append_video_resolution, append_audio_codec, append_audio_channel_layout, append_audio_language))

        probe = Probe(logger, allowed_mimetypes=['video'])
        if not probe.file(abspath):
            # File probe failed, skip the rest of this test
            logger.error("probe failed for file: '{}'; cannot append to filename".format(abspath))
            return data
        else:
            streams = probe.get_probe()["streams"]

        vcodec = [streams[i]["codec_name"] for i in range(len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'video']
        logger.debug("vcodec: '{}'".format(vcodec))

        try:
            vcodec = vcodec[0]
        except IndexError:
             logger.error("Aborting rename - could not find video stream in file: '{}'".format(abspath))
             return data

        if append_video_resolution:
            vrezw = [streams[i]["width"] for i in range(len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'video']
            vrezh = [streams[i]["height"] for i in range(len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'video']
            try:
                vrezw = vrezw[0]
                vrezh = vrezh[0]
            except IndexError:
                vrez = ''
                logger.info("Not including video resolution - could not extract video resolution from file: '{}'".format(abspath))
            else:
                vrez = str(vrezw) + "x" + str(vrezh)
        else:
            vrez = ''

        if append_audio_codec or append_audio_channel_layout or append_audio_language:
            astreams_default = [i for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio' and "disposition" in streams[i] and "default" in streams[i]["disposition"] and streams[i]["disposition"] == 1]
            astreams_first = [i for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio']
            logger.debug("astreams_default: '{}', astreams_first: '{}'".format(astreams_default, astreams_first))
            if astreams_default:
                astream = astreams_default[0]
            elif astreams_first:
                astream = astreams_first[0]
            else:
                astream = ""
                logger.info("no identified audio stream for file: '{}'".format(abspath))
        else:
            astream = ""
            logger.info("no audio options configured to be in renamed file: '{}'".format(abspath))

        if astream:
            if append_audio_codec:
                try:
                     acodec = streams[astream]["codec_name"]
                except:
                    acodec = ''
                    logger.info("Not including audio codec - could not extract audio codec from file: '{}'".format(abspath))
            else:
                acodec = ''

            if append_audio_channel_layout:
                try:
                    channel_layout = streams[astream]["channel_layout"]
                except:
                    channel_layout = ''
                    logger.info("Not including channel layout - could not extract channel layout from file: '{}'".format(abspath))
                else:
                    if "(side)" in channel_layout: channel_layout = channel_layout.replace("(side)","")
            else:
                channel_layout = ''

            if append_audio_language:
                try:
                    audio_language = streams[astream]["tags"]["language"]
                except:
                    audio_language = ''
                    logger.info("Not including video resolution - could not extract audio language from file: '{}'".format(abspath))
            else:
                audio_language = ''
        else:
            acodec = ''
            channel_layout = ''
            audio_language = ''

        name_extension = ""
        for i in vcodec, vrez, acodec, channel_layout, audio_language:
            if i: name_extension +=  "." + i

        basefile = os.path.splitext(abspath)[0]
        suffix = os.path.splitext(abspath)[1]
        newpath = basefile + name_extension + suffix
        logger.debug("basefile: '{}', suffix: '{}', newpath: '{}'".format(basefile, suffix, newpath))
        os.rename (abspath, newpath)


    return data

