#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     5 Oct 2023, (11:40 AM)
 
    Copyright:
        Copyright (C) 2021 Jay Gardner

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

from unmanic.libs.unplugins.settings import PluginSettings

from set_original_audio_to_first_audio_stream.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.set_original_audio_to_first_audio_stream")

lang_codes = [('aa', 'aar'), ('ab', 'abk'), ('af', 'afr'), ('ak', 'aka'), ('am', 'amh'), ('ar', 'ara'), ('an', 'arg'), ('as', 'asm'), ('av', 'ava'), ('ae', 'ave'), ('ay', 'aym'), ('az', 'aze'), ('ba', 'bak'), ('bm', 'bam'), ('be', 'bel'), ('bn', 'ben'), ('bi', 'bis'), ('bo', 'bod / tib*'), ('bs', 'bos'), ('br', 'bre'), ('bg', 'bul'), ('ca', 'cat'), ('cs', 'ces / cze*'), ('ch', 'cha'), ('ce', 'che'), ('cu', 'chu'), ('cv', 'chv'), ('kw', 'cor'), ('co', 'cos'), ('cr', 'cre'), ('cy', 'cym / wel*'), ('da', 'dan'), ('de', 'deu / ger*'), ('dv', 'div'), ('dz', 'dzo'), ('el', 'ell / gre*'), ('en', 'eng'), ('eo', 'epo'), ('et', 'est'), ('eu', 'eus / baq*'), ('ee', 'ewe'), ('fo', 'fao'), ('fa', 'fas / per*'), ('fj', 'fij'), ('fi', 'fin'), ('fr', 'fra / fre*'), ('fy', 'fry'), ('ff', 'ful'), ('gd', 'gla'), ('ga', 'gle'), ('gl', 'glg'), ('gv', 'glv'), ('gn', 'grn'), ('gu', 'guj'), ('ht', 'hat'), ('ha', 'hau'), ('he', 'heb'), ('hz', 'her'), ('hi', 'hin'), ('ho', 'hmo'), ('hr', 'hrv'), ('hu', 'hun'), ('hy', 'hye / arm*'), ('ig', 'ibo'), ('io', 'ido'), ('ii', 'iii'), ('iu', 'iku'), ('ie', 'ile'), ('ia', 'ina'), ('id', 'ind'), ('ik', 'ipk'), ('is', 'isl / ice*'), ('it', 'ita'), ('jv', 'jav'), ('ja', 'jpn'), ('kl', 'kal'), ('kn', 'kan'), ('ks', 'kas'), ('ka', 'kat / geo*'), ('kr', 'kau'), ('kk', 'kaz'), ('km', 'khm'), ('ki', 'kik'), ('rw', 'kin'), ('ky', 'kir'), ('kv', 'kom'), ('kg', 'kon'), ('ko', 'kor'), ('kj', 'kua'), ('ku', 'kur'), ('lo', 'lao'), ('la', 'lat'), ('lv', 'lav'), ('li', 'lim'), ('ln', 'lin'), ('lt', 'lit'), ('lb', 'ltz'), ('lu', 'lub'), ('lg', 'lug'), ('mh', 'mah'), ('ml', 'mal'), ('mr', 'mar'), ('mk', 'mkd / mac*'), ('mg', 'mlg'), ('mt', 'mlt'), ('mn', 'mon'), ('mi', 'mri / mao*'), ('ms', 'msa / may*'), ('my', 'mya / bur*'), ('na', 'nau'), ('nv', 'nav'), ('nr', 'nbl'), ('nd', 'nde'), ('ng', 'ndo'), ('ne', 'nep'), ('nl', 'nld / dut*'), ('nn', 'nno'), ('nb', 'nob'), ('no', 'nor'), ('ny', 'nya'), ('oc', 'oci'), ('oj', 'oji'), ('or', 'ori'), ('om', 'orm'), ('os', 'oss'), ('pa', 'pan'), ('pi', 'pli'), ('pl', 'pol'), ('pt', 'por'), ('ps', 'pus'), ('qu', 'que'), ('rm', 'roh'), ('ro', 'ron / rum*'), ('rn', 'run'), ('ru', 'rus'), ('sg', 'sag'), ('sa', 'san'), ('si', 'sin'), ('sk', 'slk / slo*'), ('sl', 'slv'), ('se', 'sme'), ('sm', 'smo'), ('sn', 'sna'), ('sd', 'snd'), ('so', 'som'), ('st', 'sot'), ('es', 'spa'), ('sq', 'sqi / alb*'), ('sc', 'srd'), ('sr', 'srp'), ('ss', 'ssw'), ('su', 'sun'), ('sw', 'swa'), ('sv', 'swe'), ('ty', 'tah'), ('ta', 'tam'), ('tt', 'tat'), ('te', 'tel'), ('tg', 'tgk'), ('tl', 'tgl'), ('th', 'tha'), ('ti', 'tir'), ('to', 'ton'), ('tn', 'tsn'), ('ts', 'tso'), ('tk', 'tuk'), ('tr', 'tur'), ('tw', 'twi'), ('ug', 'uig'), ('uk', 'ukr'), ('ur', 'urd'), ('uz', 'uzb'), ('ve', 'ven'), ('vi', 'vie'), ('vo', 'vol'), ('wa', 'wln'), ('wo', 'wol'), ('xh', 'xho'), ('yi', 'yid'), ('yo', 'yor'), ('za', 'zha'), ('zh', 'zho / chi*'), ('zu', 'zul')]

class Settings(PluginSettings):
    settings = {
        "reorder_additional_audio_streams":    False,
        "library_type":	"",
        "tmdb_api_key":    "",
        "tmdb_api_read_access_token":    "",
        "Search String": "",
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "reorder_additional_audio_streams": {
                "label": "Check this option if you want to reorder audio streams in addition to the original audio stream",
            },
            "library_type": self.__set_library_type_form_settings(),
            "tmdb_api_key": {
                "label": "enter your tmdb (the movie database) api key",
            },
            "tmdb_api_read_access_token": {
                "label": "enter your tmdb (the movie database) api api read access token",
            },
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

    if library_type == "TV":
        try:
            season = parsed_info["season"]
        except KeyError:
            season = ""
            logger.info("Error Parsing season from file: '{}'".format(video_file))

        try:
            episode = parsed_info["episode"]
        except KeyError:
            episode = ""
            logger.info("Error Parsing episode from file: '{}'".format(video_file))

        logger.debug("parsed info: '{}'".format(parsed_info))

    if year:
        if library_type == "Movies":
            video = requests.request("GET", tmdburl + title + '&primary_release_year=' + str(year) + '&api_key=' + tmdb_api_key, headers=headers)
        else:
            video = requests.request("GET", tmdburl + title + '&first_air_date_year=' + str(year) + '&api_key=' + tmdb_api_key, headers=headers)
    else:
        if library_type == "Movies":
            video = requests.request("GET", tmdburl + title + '&api_key=' + tmdb_api_key, headers=headers)
        else:
            video = requests.request("GET", tmdburl + title + '&api_key=' + tmdb_api_key, headers=headers)
    try:
        results = video.json()["results"]
    except:
        logger.error("Error requesting video info from tmdb. Aborting")
        return []

    logger.debug("video.json: '{}'".format(video.json()))

    matched_result = 0
    count = 0
    if len(video.json()["results"]) > 1:
        logger.info("More than one result was found - trying to narrow to one by exact match on title")
        for i in range(len(video.json()["results"])):
            if "original_name" in video.json()["results"][i]: logger.debug("i: '{}', video.json()[results][i][original_name]: '{}', title: '{}'".format(i, video.json()["results"][i]["original_name"], title)) 
            if "original_name" in video.json()["results"][i] and video.json()["results"][i]["original_name"] == title:
                count += 1
                matched_result = i
        if count != 1:
            logger.error("Could not match to exact title - Aborting")
            return []

    try:
        original_language = [lang_codes[i][1] for i in range(len(lang_codes)) if video.json()["results"][matched_result]["original_language"] == lang_codes[i][0]]
        logger.debug("original_language: '{}'".format(original_language))
        for i in range(len(original_language)):
            if '/' in original_language[i]: original_language[i] = original_language.split(' / ')[0]
    except:
        logger.error("Error matching original language - Aborting.")
        return []
    else:
        astreams = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio' and "tags" in streams[i] and "language" in streams[i]["tags"]]
        original_audio_position = [i for i in range(len(astreams)) if astreams[i] == original_language[0]]
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

    reorder_additional_audio_streams = settings.get_setting('reorder_additional_audio_streams')
    basename = os.path.basename(abspath)
    original_language = get_original_language(basename, streams, data)
    astreams = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio' and "tags" in streams[i] and "language" in streams[i]["tags"]]
    if (original_language == [] or original_language[0] == "") and not reorder_additional_audio_streams:
        logger.error("Task not added to queue - original language not identified for file: '{}'".format(abspath))
        data['add_file_to_pending_tasks'] = False
        return data
    else:
        if (original_language[0] in astreams) or (original_language[0] not in astreams and reorder_additional_audio_streams):
            logger.info("File '{}' added to task queue - original language identified and is in file or reordering additional streams.".format(abspath))
            data['add_file_to_pending_tasks'] = True
        else:
            logger.error("Task not added to queue - original language not in audio streams of file '{}' or not reordering additional streams".format(abspath))
            data['add_file_to_pending_tasks'] = False
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

    original_language = get_original_language(abspath, streams, data)
    logger.debug("original language: '{}'".format(original_language))
    reorder_additional_audio_streams = settings.get_setting('reorder_additional_audio_streams')
    if reorder_additional_audio_streams:
        additional_langauges_to_reorder = settings.get_setting('Search String')
        altr = list(additional_langauges_to_reorder.split(','))
        altr = [altr[i].strip() for i in range(len(altr))]
        # if altr contains the original_language, remove it since the original_language will appear first anyway
        altr = [altr[i] for i in range(len(altr)) if altr[i] != original_language[0]]

    original_audio_position = []
    new_audio_position = []
    astreams = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == 'audio' and "tags" in streams[i] and "language" in streams[i]["tags"]]
    astream_order = [i for i in range(len(astreams))]
    logger.debug("astreams: '{}', astream_order: '{}".format(astreams, astream_order))
    original_astream_order = astream_order[:]
    if original_language:
        original_audio_position = [i for i in range(len(astreams)) if astreams[i] == original_language[0]]
        new_audio_position = original_audio_position[:]
    if reorder_additional_audio_streams:
        additional_audio_position = [i for i in range(len(astreams)) for j in range(len(altr)) if astreams[i] == altr[j]]
        new_audio_position += additional_audio_position[:]
    logger.debug("new audio position: '{}'".format(new_audio_position))
    [astream_order.remove(new_audio_position[i]) for i in range(len(new_audio_position))]
    new_audio_position += astream_order
    logger.debug("new audio position: '{}'; original_astream_order: '{}'".format(new_audio_position, original_astream_order))

    if new_audio_position != original_astream_order:
        # stream order changed, remap audio streams
        ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-strict', '-2', '-map', '0:v', '-c:v', 'copy', '-disposition:a', '-default']
        for i in range(len(new_audio_position)):
            if i == 0:
                ffmpeg_args += ['-map', '0:a:'+str(new_audio_position[i]), '-c:a:'+str(new_audio_position[i]), 'copy', '-disposition:a:0', 'default']
            else:
                ffmpeg_args += ['-map', '0:a:'+str(new_audio_position[i]), '-c:a:'+str(new_audio_position[i]), 'copy']
        ffmpeg_args += ['-map', '0:s?', '-c:s', 'copy', '-map', '0:d?', '-c:d', 'copy', '-map', '0:t?', '-c:t', 'copy', '-y', str(outfile)]
        logger.debug("ffmpeg_args: '{}'".format(ffmpeg_args))

        # Apply ffmpeg args to command
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe)
        data['command_progress_parser'] = parser.parse_progress

    return data

