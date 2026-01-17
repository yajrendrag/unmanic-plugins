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
import PTN
import glob
from pathlib import Path

from unmanic.libs.unplugins.settings import PluginSettings
from unmanic.libs.directoryinfo import UnmanicDirectoryInfo

from rename_file.lib.ffmpeg import Probe, Parser

resolution = {
    "640x480": "480p",
    "1280x720": "720p",
    "1920x1080": "1080p",
    "2560x1440": "1440p",
    "3840x2160": "2160p",
    "7680x4320": "4320p",
}

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.rename_file")

class Settings(PluginSettings):
    settings = {
        "modify_name_fields":           True,
        "get_rez_from_height":          False,
        "repl_no_codec":                "",
        "case":                         "",
        "append_video_resolution":      "",
        "append_audio_codec":           "",
        "append_audio_channel_layout":  "",
        "append_audio_language":        "",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "modify_name_fields": {
                 "label": "Check this option if you want replace existing fields names with new values from ffprobe of transcoded file; uncheck if your wish to append new fields to file name from ffprobe metadata",
            },
            "get_rez_from_height": {
                 "label": "check this if you want the resolution named only from the height dimension, e.g., 854x480 (a non standard) would be named 480i or 480p depending on field_order param",
            },
            "repl_no_codec":                 self.__set_repl_no_codec_form_settings(),
            "case":         self.__set_case_form_settings(),
            "append_video_resolution":       self.__set_append_video_resolution_form_settings(),
            "append_audio_codec":            self.__set_append_audio_codec_form_settings(),
            "append_audio_channel_layout":   self.__set_append_audio_channel_layout_form_settings(),
            "append_audio_language":         self.__set_append_audio_language_form_settings(),
        }

    def __set_repl_no_codec_form_settings(self):
        values = {
            "label":      "Check this option if you checked to replace existing fields but your source file has no codec name field, and you wish to add codec name to the new file",
            "input_type": "checkbox",
        }
        if not self.get_setting('modify_name_fields'):
            values["display"] = 'hidden'
        return values

    def __set_case_form_settings(self):
        values = {
            "label":      "Choose case setting for added/replaced file name components",
            "input_type": "select",
            "select_options": [
                {
                    "value": "upper",
                    "label": "uppercase",
                },
                {
                    "value": "lower",
                    "label": "lowercase",
                },
                {
                    "value": "match",
                    "label": "match case",
                },
            ],
        }
        return values

    def __set_append_video_resolution_form_settings(self):
        values = {
            "label":      "Check this option if you want to append video resolution to file name",
            "input_type": "checkbox",
        }
        if self.get_setting('modify_name_fields'):
            values["display"] = 'hidden'
        return values

    def __set_append_audio_codec_form_settings(self):
        values = {
            "label":      "Check this option if you want to append audio codec name to file name",
            "input_type": "checkbox",
        }
        if self.get_setting('modify_name_fields'):
            values["display"] = 'hidden'
        return values

    def __set_append_audio_channel_layout_form_settings(self):
        values = {
            "label":      "Check this option if you want to append audio channel layout to file name",
            "input_type": "checkbox",
        }
        if self.get_setting('modify_name_fields'):
            values["display"] = 'hidden'
        return values

    def __set_append_audio_language_form_settings(self):
        values = {
            "label":      "Check this option if you want to append audio language to file name",
            "input_type": "checkbox",
        }
        if self.get_setting('modify_name_fields'):
            values["display"] = 'hidden'
        return values

def rename_related(abspath, newpath):
    basefile = os.path.splitext(abspath)[0]
    basefile_new = os.path.splitext(newpath)[0]
    related_files = glob.glob(glob.escape(basefile) + '.*')
    logger.debug("related_files: '{}'".format(related_files))
    related_files = [file for file in related_files if os.path.splitext(file)[1] != os.path.splitext(abspath)[1]]
    logger.debug("related_files: '{}'".format(related_files))
    for file in related_files:
        sfx = os.path.splitext(file)[1]
        os.rename(basefile + sfx, basefile_new + sfx)

def set_case(item, case):
    if case == 'upper':
        return item.upper()
    elif case == 'lower':
        return item.lower()

def append(data, settings, abspath, streams):
    case = settings.get_setting('case')
    append_video_resolution = settings.get_setting('append_video_resolution')
    append_audio_codec = settings.get_setting('append_audio_codec')
    append_audio_channel_layout = settings.get_setting('append_audio_channel_layout')
    append_audio_language = settings.get_setting('append_audio_language')
    non_std_rez = settings.get_setting('get_rez_from_height')

    logger.debug("abspath: '{}', append_video_resolution: '{}', append_audio_codec: '{}', append_audio_channel_layout: '{}', append_audio_language: '{}'".format(abspath, append_video_resolution, append_audio_codec, append_audio_channel_layout, append_audio_language))

    vcodec = [streams[i]["codec_name"] for i in range(len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'video']
    logger.debug("vcodec: '{}'".format(vcodec))

    try:
        vcodec = vcodec[0]
    except IndexError:
         logger.error("Aborting rename - could not find video stream in file: '{}'".format(abspath))
         return ""

    if append_video_resolution:
        vrezw = [streams[i]["width"] for i in range(len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'video']
        vrezh = [streams[i]["height"] for i in range(len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'video']
        field_order = [streams[i]["field_order"] for i in range(len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'video']
        try:
            vrezw = vrezw[0]
            vrezh = vrezh[0]
            field_order = field_order[0]
        except IndexError:
            vrez = ''
            logger.info("Not including video resolution - could not extract video resolution from file: '{}'".format(abspath))
        else:
            vrez = str(vrezw) + "x" + str(vrezh)
            try:
                vrez = resolution[vrez]
                if field_order != "progressive": vrez = vrez.replace("p","i")
            except KeyError:
                if not non_std_rez:
                    logger.info("Leaving video resolution as WxH - cannot match to standard resolution: '{}'".format(vrez))
                else:
                    vrez = str(vrezh) + "p"
                    if field_order != "progressive": vrez = vrez.replace("p","i")
                    logger.info("using non standard resolution name - cannot match to standard resolution: '{}'".format(vrez))
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
                if "(side)" in channel_layout:
                    channel_layout = channel_layout.replace("(side)","")
                elif channel_layout == "stereo":
                    channel_layout = "2.0"
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

    case_func = {
        "upper": str.upper,
        "lower": str.lower
    }

    name_extension = ""
    for i in vcodec, vrez, acodec, channel_layout, audio_language:
        if i: name_extension +=  "." + case_func[case](i)

    basefile = os.path.splitext(abspath)[0]
    suffix = os.path.splitext(abspath)[1]
    newpath = basefile + name_extension + suffix
    logger.debug("basefile: '{}', suffix: '{}', newpath: '{}'".format(basefile, suffix, newpath))
    if newpath != abspath:
        os.rename (abspath, newpath)
        logger.debug("abspath: '{}', newpath: '{}'".format(abspath, newpath))
        rename_related(abspath, newpath)
        return newpath
    else:
        logger.info("Newpath = existing path - nothing to rename")
        return ""

def replace(data, settings, abspath, streams):
    case = settings.get_setting('case')
    basename = os.path.basename(abspath)
    dirname = os.path.dirname(abspath)
    parsed_info = PTN.parse(basename, standardise=False)
    logger.debug("Parsed info: '{}'".format(parsed_info))
    non_std_rez = settings.get_setting('get_rez_from_height')

    try:
        codec = parsed_info["codec"]
    except KeyError:
        codec = ""
        logger.error("Error Parsing video codec from file: '{}'".format(abspath))

    try:
        audio = parsed_info["audio"]
    except KeyError:
        audio = ""
        logger.error("Error Parsing audio codec from file: '{}'".format(abspath))

    try:
        rez = parsed_info["resolution"]
    except KeyError:
        rez = ""
        logger.error("Error Parsing resolution from file: '{}'".format(abspath))

    video_stream = [stream for stream in range(len(streams)) if streams[stream]["codec_type"] == "video"]
    try:
        video_codec = streams[video_stream[0]]["codec_name"].upper()
    except:
        video_codec = ""
        logger.info("Error extracting video codec from file: '{}'".format(abspath))

    try:
        vrez_height = streams[video_stream[0]]["height"]
        vrez_width = streams[video_stream[0]]["width"]
        field_order = streams[video_stream[0]]["field_order"]
        logger.debug("h: '{}', w: '{}'".format(vrez_height,vrez_width))
    except:
        vrez_height = ""
        vrez_width = ""
        logger.info("removing resolution from filename, resolution cannot be extracted from file")
        vrez=""
    else:
        vrez = str(vrez_width) + "x" + str(vrez_height)
        try:
            vrez = resolution[vrez]
            if field_order != "progressive": vrez = vrez.replace("p","i")
        except KeyError:
            if not non_std_rez:
                logger.info("Leaving video resolution as WxH - cannot match to standard resolution: '{}'".format(vrez))
            else:
                vrez = str(vrez_height) + "p"
                if field_order != "progressive": vrez = vrez.replace("p","i")
                logger.info("using non standard resolution name - cannot match to standard resolution: '{}'".format(vrez))

    astreams_default = [i for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio' and "disposition" in streams[i] and "default" in streams[i]["disposition"] and streams[i]["disposition"] == 1]
    astreams_first = [i for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio']
    if astreams_default:
        astream = astreams_default[0]
    elif astreams_first:
        astream = astreams_first[0]
    else:
        astream = ""
        logger.info("no identified audio stream for file: '{}'".format(abspath))

    acodec = ''
    if astream:
        audio_codec = streams[astream]["codec_name"] if "codec_name" in streams[astream] else ""
        channel_layout = streams[astream]["channel_layout"] if "channel_layout" in streams[astream] else ""
        channels = streams[astream]["channels"] if "channels" in streams[astream] else ""
        if channel_layout == "stereo" and channels == 2:
            acodec = audio_codec + ' ' + str(channels) + '.0'
        elif channels > 4 and channel_layout:
            acodec = audio_codec + ' ' + str(channel_layout).replace('(side)','')
        elif channels > 4 and not channel_layout:
            acodec = audio_codec.upper() + ' ' + audio if audio_codec.upper() not in audio else audio
    logger.debug("acodec: '{}'".format(acodec))

    case_func = {
        "upper": str.upper,
        "lower": str.lower
    }

    if basename.find(codec) > 0:
        basename = basename.replace(codec, case_func[case](video_codec))
    elif basename.find(codec) < 0 and settings.get_setting('repl_no_codec') and video_codec != "":
        basename_no_sfx = os.path.splitext(basename)[0]
        sfx = os.path.splitext(basename)[1]
        basename = basename_no_sfx + '.' + case_func[case](video_codec) + sfx

    logger.debug("rez: '{}', vrez: '{}'".format(rez, vrez))
    if basename.find(rez) > 0:
        basename = basename.replace(rez, case_func[case](vrez))

    logger.debug("find_audio: '{}'".format(basename.find(audio)))
    if basename.find(audio) > 0:
        basename = basename.replace(audio, case_func[case](acodec))

    newpath = dirname + '/' + basename
    logger.debug("basefile: '{}', suffix: '{}', newpath: '{}'".format(os.path.splitext(abspath)[0], os.path.splitext(abspath)[1], newpath))
    if newpath != abspath:
        os.rename (abspath, newpath)
        rename_related(abspath, newpath)
        return newpath
    else:
        logger.info("Newpath = existing path - nothing to rename")
        return ""

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
    logger.debug("source: '{}'".format(data.get('source_data')))
    logger.debug("destinations: '{}'".format(data.get('destination_files')))

    if status:
        append_or_replace = settings.get_setting('modify_name_fields')
        abspath = data.get('source_data').get('abspath')
        logger.debug("abspath: '{}'".format(abspath))
        destfile = data.get('destination_files')[0]
        logger.debug("destfile: '{}'".format(destfile))

        orig_basename = abspath
        # correct for remuxed or moved files
        if not os.path.isfile(abspath) and os.path.isfile(destfile):
            abspath = destfile

        probe = Probe(logger, allowed_mimetypes=['video'])
        if not probe.file(abspath):
            # File probe failed, skip the rest of this test
            logger.error("probe failed for file: '{}'; cannot append to filename".format(abspath))
            return data
        else:
            streams = probe.get_probe()["streams"]

        newpath=""
        if not append_or_replace:
            newpath = append(data, settings, abspath, streams)
        else:
            newpath = replace(data, settings, abspath, streams)

        if newpath:
            directory_info = UnmanicDirectoryInfo(os.path.dirname(orig_basename))
            path = Path(os.path.join(directory_info, '.unmanic'))
            path.write_text(path.read_text().replace(os.path.basename(orig_basename.lower()), os.path.basename(newpath.lower())))

    return data
