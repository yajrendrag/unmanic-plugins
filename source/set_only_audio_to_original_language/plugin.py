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
import PTN
import requests
import string
import re
import iso639

yr = re.compile(r'\d\d\d\d')

from unmanic.libs.unplugins.settings import PluginSettings

from set_only_audio_to_original_language.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.reorder_audio_streams2")

class Settings(PluginSettings):
    settings = {
        "library_type":	"",
        "tmdb_api_key":    "",
        "tmdb_api_read_access_token":    "",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "library_type": self.__set_library_type_form_settings(),
            "tmdb_api_key": self.__set_tmdb_api_key_form_settings(),
            "tmdb_api_read_access_token": self.__set_tmdb_api_read_access_token_form_settings(),
        }

    def __set_tmdb_api_read_access_token_form_settings(self):
        values = {
            "label":      "enter your tmdb (the movie database) api api read access token",
            "input_type": "textarea",
        }
        return values

    def __set_tmdb_api_key_form_settings(self):
        values = {
            "label":      "enter your tmdb (the movie database) api key",
            "input_type": "textarea",
        }
        return values

    def __set_library_type_form_settings(self):
        values = {
            "label":      "Select Library type - TV or Movies",
            "description":    "The plugin can only be run on a single type of content - TV or Movies per library.",
            "input_type": "select",
            "select_options": [
                {
                    "value": "TV",
                    "label": "TV",
                },
                {
                    "value": "Movies",
                    "label": "Movies",
                },
            ],
        }
        return values

def unique_title_test(vres, video_file, title_field, title):
    matched_result = 0
    count = 0
    same_langs = []
    if len(vres) > 1:
        logger.info("More than one result was found - trying to narrow to one by exact match on title: '{}', file: '{}'".format(title, video_file))
        for i in range(len(vres)):
            if title_field in vres[i]: logger.debug("i: '{}', video.json()[results][i]'{}': '{}', title: '{}'".format(i, title_field, vres[i][title_field], title)) 
            if title_field in vres[i] and vres[i][title_field].translate(str.maketrans('', '', string.punctuation)) == title.translate(str.maketrans('', '', string.punctuation)):
                count += 1
                matched_result = i
                same_langs.append(vres[i]["original_language"])
    if all(i == same_langs[0] for i in same_langs):
        count = 1
    return count, matched_result

def get_original_language(video_file, streams, data):
    basename = os.path.basename(video_file)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    library_type = settings.get_setting("library_type")
    tmdb_api_key = settings.get_setting("tmdb_api_key")
    tmdb_api_read_access_token = settings.get_setting("tmdb_api_read_access_token")
    if library_type == "Movies":
        tmdburl = 'https://api.themoviedb.org/3/search/movie?query='
    else:
        tmdburl = 'https://api.themoviedb.org/3/search/tv?query='
    parsed_info = PTN.parse(basename)
    headers = {'accept': 'application/json', 'Authentication': 'Bearer ' + tmdb_api_read_access_token}

    try:
        title = parsed_info["title"]
    except KeyError:
        title = ""
        logger.error("Error Parsing title from file: '{}'".format(video_file))

    try:
        year = parsed_info["year"]
    except KeyError:
        year = ""
        logger.info("Error Parsing year from file: '{}'".format(video_file))

    try:
        excess = parsed_info["excess"]
    except KeyError:
        excess = []
        logger.info("Error Parsing excess from file: '{}'".format(video_file))

    year2 = []
    if year and excess:
        if isinstance(excess, str):
            year2 = excess
        elif isinstance(excess, list):
            year2 = [i for i in parsed_info["excess"] if yr.match(i) is not None]
            if year2: year2 = year2[0]
        logger.debug("year2: '{}'".format(year2))
        try:
            if yr.match(year2) is None:
                year2 = []
        except TypeError:
            logger.debug("TypeError: year2: '{}'".format(year2))
            year2 = []

    logger.debug("parsed info: '{}'".format(parsed_info))

    page = 1
    if year:
        if library_type == "Movies":
            vurl = tmdburl + title + '&primary_release_year=' + str(year) + '&api_key=' + tmdb_api_key
        else:
            vurl = tmdburl + title + '&first_air_date_year=' + str(year) + '&api_key=' + tmdb_api_key
    else:
        # urls reduce to the same thing when no year is part of the query
        vurl = tmdburl + title + '&api_key=' + tmdb_api_key

    try:
        video = requests.request("GET", vurl + '&page=' + str(page), headers=headers)
        logger.debug("video results len: '{}', year2: '{}'".format(len(video.json()["results"]), year2))
        if len(video.json()["results"]) == 0 and year and year2:
            vurl = vurl.replace(str(year), str(year2))
            video = requests.request("GET", vurl + '&page=' + str(page), headers=headers)
        vres = video.json()["results"]
        pages = video.json()["total_pages"]
        for i in range(2, pages + 1):
            vres += requests.request("GET", vurl + '&page=' + str(i), headers=headers).json()["results"]
    except:
        logger.error("Error requesting video info from tmdb. Aborting")
        return []

    logger.debug("video.json: '{}'".format(vres))

    matched_result = 0
    if library_type == "Movies":
        title_field = "title"
    else:
        title_field = "name"
    if len(vres) > 1:
        count, matched_result = unique_title_test(vres, video_file, title_field, title)
        count_o, matched_result_o = unique_title_test(vres, video_file, "original_"+title_field, title)
        if count != 1 and count_o != 1:
            logger.error("Could not match to exact title - Aborting; title: '{}', file'{}'".format(title, video_file))
            return []
        elif count_o == 1 and count != 1:
            matched_result = matched_result_o

    try:
        if len(vres[matched_result]["original_language"]) == 2:
            lang = iso639.Language.from_part1(vres[matched_result]["original_language"])
        elif len(vres[matched_result]["original_language"]) == 3:
            lang = iso639.Language.from_part3(vres[matched_result]["original_language"])
        original_language = [lang.part3]
        logger.debug("original_language: '{}', file: '{}'".format(original_language, video_file))
    except iso639.language.LanguageNotFoundError:
        logger.error("Error matching original language - Aborting, file: '{}'".format(video_file))
        return []
    else:
        astreams = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio' and "tags" in streams[i] and "language" in streams[i]["tags"]]
        original_audio_position = [i for i in range(len(astreams)) if astreams[i] in original_language]
        if len(original_audio_position) > 1:
            logger.info("Video file '{}' contains '{}' original language streams in '{}'".format(video_file, len(original_audio_position), original_language))

    original_language = [*set(original_language)]
    return original_language

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

    astreams = [streams[i]["index"]  for i in range(len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio' and (("tags" in streams[i] and "language" in streams[i]["tags"] and streams[i]["tags"]["language"] == 'und') or
                ("tags" not in streams[i]) or ("tags" in streams[i] and "language" not in streams[i]["tags"]))]
    if len(astreams) > 1:
        logger.error("Task not added to queue - file has more than 1 undefined/unknown audio stream")
        return data
    elif len(astreams) == 0:
        logger.error("Task not added to queue - file has no audio streams")
        return data

    # file has a single audio stream, get original language
    original_language= []
    basename = os.path.basename(abspath)
    original_language = get_original_language(basename, streams, data)
    if original_language:
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

    astreams = [streams[i]["index"]  for i in range(len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio' and (("tags" in streams[i] and "language" in streams[i]["tags"] and streams[i]["tags"]["language"] == 'und') or
                ("tags" not in streams[i]) or ("tags" in streams[i] and "language" not in streams[i]["tags"]))]
    if len(astreams) > 1:
        logger.error("Metadata not being modified for file: '{}'; file has more than 1 undefined/unknown audio stream".format(abspath))
        return data
    elif len(astreams) == 0:
        logger.error("Metadata not being modified for file: '{}'; file has no undefined/unknown audio streams".format(abspath))
        return data

    # file has a single audio stream, get original language
    original_language= []
    basename = os.path.basename(abspath)
    original_language = get_original_language(basename, streams, data)

    if original_language:
        # modify metadata of audio stream to be the original language
        ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-strict', '-2', '-map', '0', '-c', 'copy', '-disposition:a', '-default']
        suffix = os.path.splitext(abspath)[1]
        if suffix == '.mp4':
            ffmpeg_args += ['-metadata:s:'+str(astreams[0]), 'language='+original_language[0], '-disposition:'+str(astreams[0]), 'default', '-map_chapters', '-1', '-y', str(outfile)]
        else:
            ffmpeg_args += ['-metadata:s:'+str(astreams[0]), 'language='+original_language[0], '-disposition:'+str(astreams[0]), 'default', '-y', str(outfile)]
        logger.debug("ffmpeg_args: '{}'".format(ffmpeg_args))

        # Apply ffmpeg args to command
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe)
        data['command_progress_parser'] = parser.parse_progress

    return data
