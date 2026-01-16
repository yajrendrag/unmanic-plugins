#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     5 Oct 2023, (11:40 AM)

    Copyright:
        Copyright (C) 2023, 2026 Jay Gardner

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
import langcodes

yr = re.compile(r'\d\d\d\d')

from unmanic.libs.unplugins.settings import PluginSettings

from reorder_by_original_language.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.reorder_by_original_language")


def normalize_language_code(code):
    """
    Normalize a language code to its 3-letter (ISO 639-2/3) form for comparison.
    Returns a list of possible 3-letter codes (some languages have multiple valid codes).

    :param code: A language code (2-letter or 3-letter)
    :return: List of normalized 3-letter codes, or empty list if invalid
    """
    if not code:
        return []

    code = code.strip().lower()

    try:
        lang = langcodes.Language.get(code)
        codes = []

        # Get the primary 3-letter code
        try:
            alpha3 = lang.to_alpha3()
            if alpha3:
                codes.append(alpha3.lower())
        except (LookupError, AttributeError):
            pass

        # Some languages have both bibliographic (e.g., 'ger') and terminological (e.g., 'deu') codes
        # langcodes typically returns one, but we should handle known alternates
        # Common alternates mapping
        alternates = {
            'deu': ['ger'],
            'ger': ['deu'],
            'fra': ['fre'],
            'fre': ['fra'],
            'ces': ['cze'],
            'cze': ['ces'],
            'zho': ['chi'],
            'chi': ['zho'],
            'nld': ['dut'],
            'dut': ['nld'],
            'ell': ['gre'],
            'gre': ['ell'],
            'eus': ['baq'],
            'baq': ['eus'],
            'fas': ['per'],
            'per': ['fas'],
            'hye': ['arm'],
            'arm': ['hye'],
            'isl': ['ice'],
            'ice': ['isl'],
            'kat': ['geo'],
            'geo': ['kat'],
            'mkd': ['mac'],
            'mac': ['mkd'],
            'mri': ['mao'],
            'mao': ['mri'],
            'msa': ['may'],
            'may': ['msa'],
            'mya': ['bur'],
            'bur': ['mya'],
            'ron': ['rum'],
            'rum': ['ron'],
            'slk': ['slo'],
            'slo': ['slk'],
            'sqi': ['alb'],
            'alb': ['sqi'],
            'cym': ['wel'],
            'wel': ['cym'],
            'bod': ['tib'],
            'tib': ['bod'],
        }

        for c in list(codes):
            if c in alternates:
                for alt in alternates[c]:
                    if alt not in codes:
                        codes.append(alt)

        return codes if codes else []

    except (LookupError, ValueError):
        # If langcodes can't parse it, return the original if it looks like a 3-letter code
        if len(code) == 3:
            return [code]
        return []


def get_alpha3_from_alpha2(alpha2_code):
    """
    Convert a 2-letter ISO 639-1 code to 3-letter ISO 639-2/3 codes.
    Returns a list of possible 3-letter codes.

    :param alpha2_code: A 2-letter language code
    :return: List of 3-letter codes, or empty list if conversion fails
    """
    return normalize_language_code(alpha2_code)


def codes_match(code1, code2):
    """
    Check if two language codes refer to the same language, regardless of whether
    they are 2-letter or 3-letter codes.

    :param code1: First language code
    :param code2: Second language code
    :return: True if they match, False otherwise
    """
    if not code1 or not code2:
        return False

    code1 = code1.strip().lower()
    code2 = code2.strip().lower()

    # Direct match
    if code1 == code2:
        return True

    # Normalize both and check for overlap
    normalized1 = normalize_language_code(code1)
    normalized2 = normalize_language_code(code2)

    # Also add the original codes to their lists if they're 3-letter
    if len(code1) == 3:
        normalized1.append(code1)
    if len(code2) == 3:
        normalized2.append(code2)

    # Check for any overlap
    return bool(set(normalized1) & set(normalized2))


class Settings(PluginSettings):
    settings = {
        "reorder_original_language":          False,
        "reorder_additional_audio_streams":    False,
        "remove_other_languages":              False,
        "library_type":	"",
        "tmdb_api_key":    "",
        "tmdb_api_read_access_token":    "",
        "Search String": "",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "reorder_original_language": {
                "label": "Check this option if you want to reorder the original language to be the first language",
            },
            "reorder_additional_audio_streams": {
                "label": "Check this option if you want to reorder audio streams in addition to the original audio stream",
            },
            "remove_other_languages": {
                "label": "Check this option if you want to remove languages that are not configured for reordering",
            },
            "library_type": self.__set_library_type_form_settings(),
            "tmdb_api_key": self.__set_tmdb_api_key_form_settings(),
            "tmdb_api_read_access_token": self.__set_tmdb_api_read_access_token_form_settings(),
            "Search String": self.__set_additional_audio_streams_form_settings(),
        }

    def __set_additional_audio_streams_form_settings(self):
        values = {
            "label":      "Enter additional audio streams to reorder in the order you wish them to follow the original audio stream",
            "input_type": "textarea",
        }
        if not self.get_setting('reorder_additional_audio_streams'):
            values["display"] = 'hidden'
        return values

    def __set_tmdb_api_read_access_token_form_settings(self):
        values = {
            "label":      "enter your tmdb (the movie database) api api read access token",
            "input_type": "textarea",
        }
        if not self.get_setting('reorder_original_language'):
            values["display"] = 'hidden'
        return values

    def __set_tmdb_api_key_form_settings(self):
        values = {
            "label":      "enter your tmdb (the movie database) api key",
            "input_type": "textarea",
        }
        if not self.get_setting('reorder_original_language'):
            values["display"] = 'hidden'
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
        if not self.get_setting('reorder_original_language'):
            values["display"] = 'hidden'
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
        # Use langcodes to convert the 2-letter code from TMDB to 3-letter codes
        tmdb_lang_code = vres[matched_result]["original_language"]
        original_language = get_alpha3_from_alpha2(tmdb_lang_code)

        logger.debug("TMDB original_language (2-letter): '{}', converted to 3-letter: '{}', file: '{}'".format(
            tmdb_lang_code, original_language, video_file))

        if not original_language:
            logger.warning("Could not convert language code '{}' using langcodes, file: '{}'".format(
                tmdb_lang_code, video_file))
            return []

    except Exception as e:
        logger.error("Error matching original language - Aborting, file: '{}', error: '{}'".format(video_file, str(e)))
        return []
    else:
        astreams = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio' and "tags" in streams[i] and "language" in streams[i]["tags"]]
        # Use codes_match to find original audio streams (handles both 2-letter and 3-letter codes)
        original_audio_position = [i for i in range(len(astreams)) if any(codes_match(astreams[i], ol) for ol in original_language)]
        if len(original_audio_position) > 1:
            logger.info("Video file '{}' contains '{}' original language streams in '{}'".format(video_file, len(original_audio_position), original_language))

    original_language = [*set(original_language)]
    return original_language


def get_old_and_new_order(streams, reorder_original_language, original_language, settings):
    remove_other_languages = settings.get_setting('remove_other_languages')
    reorder_additional_audio_streams = settings.get_setting('reorder_additional_audio_streams')
    if reorder_additional_audio_streams:
        additional_langauges_to_reorder = settings.get_setting('Search String')
        altr = list(additional_langauges_to_reorder.split(','))
        altr = [altr[i].strip() for i in range(len(altr))]
        # if altr contains the original_language, remove it since the original_language will appear first anyway
        # Use codes_match to properly compare regardless of 2-letter or 3-letter format
        if reorder_original_language:
            altr = [lang for lang in altr if not any(codes_match(lang, ol) for ol in original_language)]

    original_audio_position = []
    new_audio_position = []
    additional_audio_position = []
    astreams = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio' and "tags" in streams[i] and "language" in streams[i]["tags"]]
    astream_order = [i for i in range(len(astreams))]
    logger.debug("astreams: '{}', astream_order: '{}".format(astreams, astream_order))
    original_astream_order = astream_order[:]
    if original_language:
        # Use codes_match to find streams matching original language (handles both 2-letter and 3-letter codes)
        original_audio_position = [i for i in range(len(astreams)) if any(codes_match(astreams[i], ol) for ol in original_language)]
        new_audio_position = original_audio_position[:]
    if reorder_additional_audio_streams:
        # Use codes_match to find streams matching additional languages (handles both 2-letter and 3-letter codes)
        additional_audio_position = [i for i in range(len(astreams)) for lang in altr if codes_match(astreams[i], lang)]
        # Remove duplicates while preserving order
        seen = set(new_audio_position)
        for pos in additional_audio_position:
            if pos not in seen:
                new_audio_position.append(pos)
                seen.add(pos)
    logger.debug("new audio position: '{}'".format(new_audio_position))
    try:
        [astream_order.remove(new_audio_position[i]) for i in range(len(new_audio_position))]
    except ValueError:
        logger.error("Attempt to remove list items from astreams that are not present - astreams: '{}' \n, astream_order: '{}', new_audio_position: '{}', additional_audio_position: '{}', original_astream_order: '{}'\nAborting.".format(
                     astreams, astream_order, new_audio_position, additional_audio_position, original_astream_order))
        return [], []
    if not remove_other_languages:
        new_audio_position += astream_order
    logger.debug("new audio position: '{}'; original_astream_order: '{}'".format(new_audio_position, original_astream_order))
    return new_audio_position, original_astream_order


def stream_has_original_language(astreams, original_language):
    """
    Check if any audio stream matches the original language using proper code comparison.

    :param astreams: List of stream language codes
    :param original_language: List of original language codes
    :return: True if any stream matches original language
    """
    for stream_lang in astreams:
        for orig_lang in original_language:
            if codes_match(stream_lang, orig_lang):
                return True
    return False


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

    original_language= []
    reorder_additional_audio_streams = settings.get_setting('reorder_additional_audio_streams')
    reorder_original_language = settings.get_setting('reorder_original_language')
    basename = os.path.basename(abspath)
    if reorder_original_language:
        original_language = get_original_language(basename, streams, data)
    astreams = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio' and "tags" in streams[i] and "language" in streams[i]["tags"]]
    new_audio_position, original_astream_order = get_old_and_new_order(streams, reorder_original_language, original_language, settings)
    if new_audio_position == [] and original_astream_order == []:
        logger.error("Task not added to queue - error processing stream positions - see above error re: attempting to remove list items from astreams")
        return data
    elif new_audio_position == [] and original_astream_order != []:
        logger.error("Task not added to queue - resulting file would have no audio streams")
        return data
    if (reorder_original_language and (original_language == [] or all(i=="" for i in original_language))) and not reorder_additional_audio_streams:
        logger.error("Task not added to queue - original language not identified for file: '{}'".format(abspath))
        return data
    elif ((reorder_original_language and (stream_has_original_language(astreams, original_language) or (not stream_has_original_language(astreams, original_language) and reorder_additional_audio_streams))) or (not reorder_original_language and reorder_additional_audio_streams)) and new_audio_position != original_astream_order:
        if reorder_original_language:
            logger.info("File '{}' added to task queue - original language identified and is in file or reordering additional streams.".format(abspath))
        else:
            logger.info("File '{}' added to task queue - reordering additional languages only")
        data['add_file_to_pending_tasks'] = True
    else:
        logger.error("Task not added to queue - original language not in audio streams of file '{}' or not reordering additional streams or original language or streams do not require reordering".format(abspath))
        return data
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

    original_language = []
    reorder_original_language = settings.get_setting('reorder_original_language')
    if reorder_original_language:
        original_language = get_original_language(abspath, streams, data)
        logger.debug("original language: '{}'".format(original_language))

    new_audio_position, original_astream_order = get_old_and_new_order(streams, reorder_original_language, original_language, settings)

    if new_audio_position == [] and original_astream_order != []:
        logger.error("Skipping plugin - resulting file will have no audio.")
        logger.debug("new_audio_position: '{}', original_astream_order: '{}'".format(new_audio_position, original_astream_order))
        return data
    if new_audio_position != original_astream_order:
        # stream order changed, remap audio streams
        ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-strict', '-2', '-map', '0:v', '-disposition:a', '-default']
        for i in range(len(new_audio_position)):
            if i == 0:
                ffmpeg_args += ['-map', '0:a:'+str(new_audio_position[i]), '-disposition:a:0', 'default']
            else:
                ffmpeg_args += ['-map', '0:a:'+str(new_audio_position[i])]
        ffmpeg_args += ['-map', '0:s?', '-map', '0:d?', '-map', '0:t?', '-c', 'copy', '-y', str(outfile)]

        logger.debug("ffmpeg_args: '{}'".format(ffmpeg_args))

        # Apply ffmpeg args to command
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe)
        data['command_progress_parser'] = parser.parse_progress

    return data
