#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     8 Nov 2023, (2:15 PM)
 
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
import glob
import difflib
import subprocess
from langcodes.tag_parser import LanguageTagError
from langcodes import *

from unmanic.libs.unplugins.settings import PluginSettings

from add_srt_to_video.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.srt_to_video")

class Settings(PluginSettings):
    settings = {
        "tag_style": "3",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "tag_style": {
                "label":          "Choose Language Tag Style",
                "description":    "Select whether you prefer language tags to be written as either '2 letter' or '3 letter' codes",
                "input_type":     "select",
                "select_options": [
                    {
                        "value": "2",
                        "label": "2 letter",
                    },
                    {   "value": "3",
                        "label": "3 letter",
                    }
                ],
            }
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

    # Get file suffix
    mkv = '.mkv'
    mp4 = '.mp4'
    sfx = os.path.splitext(abspath)[1]
    data['add_file_to_pending_tasks'] = False
    logger.debug("suffix: '{}'".format(sfx))
    if sfx == mkv or sfx == mp4:
        basefile = os.path.splitext(abspath)[0]
        logger.debug("basefile: '{}'".format(basefile))
        logger.debug("glob length: '{}'".format(len(glob.glob(glob.escape(basefile) + '*.*[a-z].srt'))))
        for j in range(len(glob.glob(glob.escape(basefile) + '*.*[a-z].srt'))):
            lang_srt = [li for li in difflib.ndiff(basefile, glob.glob(glob.escape(basefile) + '*.*[a-z].srt')[j]) if li[0] != ' ']
            lang = ''.join([i.replace('+ ','') for i in lang_srt]).replace('.srt','').replace('.','')
            logger.info ("Language code '{}' subtitle file found, adding file to task queue".format(lang))
            data['add_file_to_pending_tasks'] = True
        return data

def check_sub(subfile, encoder, suffix):
    if suffix == '.mkv':
        fmt = 'matroska'
    else:
        fmt = 'mp4'
    try:
        rt = subprocess.check_call(['ffmpeg', '-hide_banner', '-i', subfile, '-map', '0', '-c', encoder, '-y', '-f', fmt, '/dev/null'], shell=False)
    except subprocess.CalledProcessError:
        logger.error("Subtitle file '{}' could not be encoded and will not be added to the source video file".format(subfile))
        rt = 1
    return rt

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

    tag_style = settings.get_setting('tag_style')

    # Get the path to the input and output files
    abspath = data.get('file_in')
    outfile = data.get('file_out')
    srtpath = data.get('original_file_path')

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(abspath):
        # File probe failed, skip the rest of this test
        return data

    # get all streams
    streams=probe.get_probe()["streams"]

    # Get file suffix
    mkv = '.mkv'
    mp4 = '.mp4'
    encoder = 'copy'
    sfx = os.path.splitext(abspath)[1]
    if sfx == mp4: encoder = 'mov_text'

    # Get any existing subtitles
    existing_subtitle_streams_list = [i for i in range(len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == "subtitle"]
    existing_subtitle_streams_list_len = len(existing_subtitle_streams_list)

    # test suffix for video file
    if sfx == mkv or sfx == mp4:
        ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath)]
        ffmpeg_subtitle_args = []
        basefile = os.path.splitext(srtpath)[0]

        # check srt files to skip any that won't encode
        srt_files = glob.glob(glob.escape(basefile) + '*.*[a-z].srt')
        srt_to_skip = []
        for i in range(len(srt_files)):
            it_wont_encode = check_sub(str(srt_files[i]), encoder, sfx)
            if it_wont_encode: srt_to_skip.append(i)
        if srt_to_skip:
            srt_files = [srt_files[i] for i in range(len(srt_files)) if i not in srt_to_skip]

        # get all subtitle files in folder where original video file is, get 2 or 3 letter language code as specified by config, build ffmpeg subtitle args for new streams
        for j in range(len(srt_files)):
            lang_srt = [li for li in difflib.ndiff(basefile, srt_files[j]) if li[0] != ' ']
            # lang = ''.join([i.replace('+ ','') for i in lang_srt]).replace('.srt','').replace('.','')
            langbase = ''.join([i.replace('+ ','') for i in lang_srt])
            langbase_tag = langbase.split('.')[1]

            try:
                lang_tag = standardize_tag(langbase_tag) if Language.get(langbase_tag).is_valid() else ""
            except LanguageTagError:
                lang_tag = ""

            logger.debug(f"lang_tag: {lang_tag}, j: {j}, langbase: {langbase}")

            if lang_tag:
                if tag_style == "2":
                    lang_tag = standardize_tag(lang_tag)
                else:
                    lang_tag = Language.get(standardize_tag(lang_tag)).to_alpha3()
                ffmpeg_args += ['-i', str(srt_files[j])]
                ffmpeg_subtitle_args += ['-map', '{}:s:0'.format(j+1), '-c:s:{}'.format(j+existing_subtitle_streams_list_len), str(encoder), '-metadata:s:s:{}'.format(j+existing_subtitle_streams_list_len), 'language={}'.format(lang_tag)]
            else:
                logger.info(f"Unable to identify language code {langbase_tag} from srt extension {langbase} - skipping stream")

        if ffmpeg_subtitle_args:
        # external subtitle file(s) were found for video file

            # add in any existing subtitle streams
            for i in range(existing_subtitle_streams_list_len-1, -1, -1):
                ffmpeg_subtitle_args = ['-map', '0:s:{}'.format(i), '-c:s:{}'.format(i), 'copy'] + ffmpeg_subtitle_args

            # build rest of ffmpeg_args around ffmpeg_subtitle_args
            ffmpeg_args += ['-max_muxing_queue_size', '9999', '-strict', '-2', '-map', '0:v', '-c:v', 'copy', '-map', '0:a', '-c:a', 'copy'] + ffmpeg_subtitle_args + ['-map', '0:t?', '-c:t', 'copy', '-map', '0:d?', '-c:d', 'copy']
            if sfx == mp4:
                ffmpeg_args += ['-dn', '-map_metadata:c', '-1', '-y', str(outfile)]
            else:
                ffmpeg_args += ['-y', str(outfile)]

            logger.debug("ffmpeg_args: '{}'".format(ffmpeg_args))

            # Apply ffmpeg args to command
            data['exec_command'] = ['ffmpeg']
            data['exec_command'] += ffmpeg_args

            # Set the parser
            parser = Parser(logger)
            parser.set_probe(probe)
            data['command_progress_parser'] = parser.parse_progress

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

    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    status = data.get('task_processing_success')
    logger.debug("status: '{}'".format(status))

    destpath = data.get('destination_files')[0]
    probe = Probe(logger, allowed_mimetypes=['video'])
    if probe.file(destpath):
        probe_streams = probe.get_probe()["streams"]
    else:
        logger.error("Cannot probe destination file so cannot reliably delete srt files.  Source file: {data.get('source_data').get('abspath')}")
        return data

    astreams = [s for s in probe_streams if s.get('codec_type') == 'audio']
    langs = [s.get('tags').get('language') for s in astreams or {}]
    std_langs = [str(Language.get(standardize_tag(lt))) for lt in langs if Language.get(lt).is_valid() or None]

    if status:
        abspath = data.get('source_data').get('abspath')
        basefile = os.path.splitext(abspath)[0]
        srt_files = glob.glob(glob.escape(basefile) + '*.*[a-z].srt')
        logger.debug("basefile in post: '{}'".format(basefile))
        logger.debug("srt files: '{}'".format(srt_files))
        for j in range(len(srt_files)):
            srt_file = srt_files[j]
            lang_srt = [li for li in difflib.ndiff(basefile, srt_files[j]) if li[0] != ' ']
            lang_tag = ''.join([i.replace('+ ','') for i in lang_srt]).replace('.srt','').replace('.','')
            std_lang = str(Language.get(standardize_tag(lang_tag))) if Language.get(lang_tag).is_valid() else None
            if std_lang in std_langs:
                os.remove(srt_file)
                logger.info("srt file '{}' has been added to video file of the same basename; the srt file has been deleted.".format(srt_file))
            else:
                logger.info(f"srt file {srt_file} language was not found in destination file, so not removing")
    return data
