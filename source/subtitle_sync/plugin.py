#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     3 January 2025, (2:40 AM)

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
import os
import iso639
import ffmpeg
import mimetypes
import re
import difflib
import glob

from unmanic.libs.unplugins.settings import PluginSettings
from unmanic.libs.directoryinfo import UnmanicDirectoryInfo

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.subtitle_sync")

duration = 3600.00

class Settings(PluginSettings):
    settings = {
        "sub_languages_to_sync":       'eng',
        "prefer_mc_or_st":             'Stereo',
    }

    form_settings = {
        "sub_languages_to_sync": {
            "label": "Enter comma delimited list of subtitle languages to sync - use 2 or 3 letter codes as you like - the plugin will find the corresponding language",
        },
        "prefer_mc_or_st": {
            "input_type": "select",
            "select_options": [
                {
                    "value": "stereo",
                    "label": "Stereo",
                },
                {
                    "value": "mc",
                    "label": "Multichannel",
                },
            ],
        },
    }

def synced_subtitles(abspath):
    return f"synced_subtitles={abspath}"

def subtitle_already_synced(settings, path):
    directory_info = UnmanicDirectoryInfo(os.path.dirname(path))

    try:
        subtitle_already_synced = directory_info.get('subtitle_sync', os.path.basename(path))
    except NoSectionError as e:
        subtitle_already_synced = ''
    except NoOptionError as e:
        subtitle_already_synced = ''
    except Exception as e:
        logger.debug("Unknown exception {}.".format(e))
        subtitle_already_synced = ''

    if subtitle_already_synced:
        logger.debug(f"File {path} subtitle was previously synced with {subtitle_already_synced}.")
        return True

    # Default to...
    return False

def get_probe(f):
    try:
        p = ffmpeg.probe(f)
    except ffmpeg.Error as e:
        p = e.stdout.decode('utf8').replace('\n','')
    return(p)

def get_sub_language(settings, abspath):
    basefile = os.path.splitext(os.path.splitext(abspath)[0])[0]
    logger.debug("basefile: {basefile}")

    sub_languages_to_sync = settings.get_setting("sub_languages_to_sync")
    sub_languages_to_sync = list(sub_languages_to_sync.split(','))
    sub_languages_to_sync = [sub_languages_to_sync[i].strip() for i in range(len(sub_languages_to_sync))]
    sub_languagas_to_sync_iso639 = [iso639.Language.match(j) for j in sub_languages_to_sync]
    logger.debug(f"Subtitle languages to sync: {sub_languages_to_sync}")

    lang_srt = [li for li in difflib.ndiff(basefile, glob.glob(glob.escape(basefile) + '*.*[a-z].srt')[0]) if li[0] != ' ']
    lang = ''.join([i.replace('+ ','') for i in lang_srt]).replace('.srt','').replace('.','')
    return lang, sub_languagas_to_sync_iso639, sub_languages_to_sync, basefile

def file_is_subtitle(probe):
    streams = probe['streams']
    type = [streams[i]['codec_type'] for i in range(len(streams)) if 'codec_type' in streams[i] and streams[i]['codec_type'] == 'subtitle']
    if streams and type and 'subtitle' in type:
        return True
    else:
        return False

def matching_astream_in_video_file(lang, sub_languages_to_sync_iso639, abspath, basefile):
    global duration

    mimetypes.add_type('video/mastroska', 'mkv')
    astream = []
    video_file = ""
    video_suffix_list = [k for k in mimetypes.types_map if 'video/' in mimetypes.types_map[k]]
    if lang and iso639.Language.match(lang) in sub_languages_to_sync_iso639:
        logger.info (f"Language code {lang} subtitle stream found in file {abspath}")
        sfx=[s for s in video_suffix_list if os.path.exists(basefile + s)]
        logger.debug(f"sfx: {sfx}, basefile: {basefile}")
        if sfx:
            video_file = basefile + sfx[0]
            probe = get_probe(video_file)
            if probe:
                streams = ffmpeg.probe(video_file)['streams']
                astreams = [i for i in range(len(streams)) if 'codec_type' in streams[i] and streams[i]['codec_type'] == 'audio']
                astream = [s for s in range(len(streams)) if 'codec_type' in streams[s] and streams[s]['codec_type'] == 'audio' and 'tags' in streams[s] and
                           'language' in streams[s]['tags'] and streams[s]['tags']['language'] == lang]
                try:
                    duration = float(ffmpeg.probe(video_file)['format']['duration'])
                except KeyError:
                    logger.error(f"duration not available - ETA counter will not function")
                    duration = 0.0

    return astream, astreams, video_file

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
    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # Get the path to the file
    abspath = data.get('path')

    # Check if subtitles already synced
    if subtitle_already_synced(settings, abspath):
        logger.info(f"File {abspath} has already been subtitle synced")
        return

    # Check if file is ffprobe-able
    probe = get_probe(abspath)
    if not probe:
        logger.error(f"File {abspath} not did not return ffprobe data - aborting")
        return

    if file_is_subtitle(probe):
        logger.info(f"File {abspath} is a subtitle file - search for matching language audio stream and sync")
    else:
        logger.error(f"File {abspath} is not a subtitle file or had no streams - not adding file to task queue")
        return data

    # Extract subtitle language from file of the form: "/path/to/video/file.lang.srt" and find corresponding video files of form "/path/to/video/file.video_suffix"
    lang, sub_languagas_to_sync_iso639, sub_languages_to_sync, basefile = get_sub_language(settings, abspath)

    astream, astreams, video_file = matching_astream_in_video_file(lang, sub_languages_to_sync_iso639, abspath, basefile)
    if astream and video_file:
        logger.info(f"Video file {video_file} exists with audio stream matching subtitle language - Adding file {abspath} to task queue for subtitle syncing")
        data['add_file_to_pending_tasks'] = True
    else:
        logger.info(f"Unable to identify a video file associated with subtitle file {abspath} - not adding file to task list") 

    return data

def parse_progress(line_text):
    global duration

    match = re.search(r'^.*(\d*).*%.*$', line_text)
    if match and (duration > 0.0):
        percent=match.group(1)
    else:
        progress = ''

    return {
        'percent': progress
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
    # Default to no FFMPEG command required. This prevents the FFMPEG command from running if it is not required
    data['exec_command'] = []
    data['repeat'] = False

    # Get the path to the file
    abspath = data.get('file_in')
    file_out = data.get('file_out')
    original_file_path = data.get('original_file_path')

    # Get settings
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # Check if subtitles already synced
    if subtitle_already_synced(settings, abspath):
        logger.info(f"File {abspath} has already been subtitle synced")
        return

    # Check if file is ffprobe-able
    probe = get_probe(abspath)
    if not probe:
        logger.error(f"File {abspath} not did not return ffprobe data - aborting")
        return

    if file_is_subtitle(probe):
        logger.info(f"File {abspath} is a subtitle file - search for matching language audio stream and sync")
    else:
        logger.error(f"File {abspath} is not a subtitle file or had no streams - do not process file")
        return data

    # Extract subtitle language from file of the form: "/path/to/video/file.lang.srt" and find corresponding video files of form "/path/to/video/file.video_suffix"
    lang, sub_languages_to_sync_iso639, sub_languages_to_sync, basefile = get_sub_language(settings, abspath)

    astream, astreams, video_file = matching_astream_in_video_file(lang, sub_languages_to_sync_iso639, abspath, basefile)
    if astream and video_file:
        logger.info(f"Video file {video_file} exists with audio stream (astream: {astream}) matching language of subtitle file - sync the subtitle stream to the audio")
    else:
        logger.error(f"no matching stream identified for {lang} audio in {abspath}")
        return

    mc_st = settings.get_setting('prefer_mc_or_st')

    # select preferred audio stream in corresponding video file 
    preferred_audio_stream = astream[0]
    if len(astream) > 1:
        streams = ffmpeg.probe(video_file)['streams']
        stream_channels = [streams[astream[i]]['channels'] for i in range(len(astream))]
        for i in range(len(stream_channels)):
            if stream_channels[i] == 2 and mc_st == 'stereo':
                preferred_audio_stream = astream[i]
                break
            elif mc_st != 'stereo' and stream_channels[i] != 2:
                preferred_audioa_stream = astream[i]
                break

    ffs_args = [video_file, '-i', abspath, '--refstream', f"a:{preferred_audio_stream}", '--no-fix-framerate', '-o', file_out]

    # Apply ffmpeg args to command
    data['exec_command'] = ['ffs']
    data['exec_command'] += ffs_args

    logger.debug("command: '{}'".format(data['exec_command']))

    # Set the parser
    data['command_progress_parser'] = parse_progress

    #data['file_out'] = None

    return data

def on_postprocessor_task_results(data):
    """
    Runner function - provides a means for additional postprocessor functions based on the task success.

    The 'data' object argument includes:
        task_processing_success         - Boolean, did all task processes complete successfully.
        file_move_processes_success     - Boolean, did all postprocessor movement tasks complete successfully.
        destination_files               - List containing all file paths created by postprocessor file movements.
        source_data                     - Dictionary containing data pertaining to the original source file.

    :param data:
    :return:

    """

    if data.get('task_processing_success'):

        # Loop over the destination_files list and update the directory info file for each one
        for destination_file in data.get('destination_files'):
            directory_info = UnmanicDirectoryInfo(os.path.dirname(destination_file))
            directory_info.set('subtitle_sync', os.path.basename(destination_file), synced_subtitles(destination_file))
            directory_info.save()
            logger.debug(f"Synced subtitle for {destination_file}.")

    return data
