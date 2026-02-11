#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     06 June 2023

    Copyright:
        Copyright (C) 2023, 2024 Jay Gardner

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
from langcodes.tag_parser import LanguageTagError
from langcodes import *

from unmanic.libs.unplugins.settings import PluginSettings

from convert_multichan_audio_to_2ch.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.convert_multichan_audio_to_2ch")

class Settings(PluginSettings):
    settings = {
        "use_libfdk_aac":            True,
        "encode_all_2_aac":          True,
        "keep_mc":                   False,
        "set_2ch_stream_as_default": False,
        "default_lang":              "",
        "normalize_2_channel_stream": True,
        'I':                           '-16.0',
        'LRA':                         '11.0',
        'TP':                          '-1.5',

    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "use_libfdk_aac":               {
                "label": "check if you want to use libfdk_aac (requires ffmpeg >= 5), otherwise native aac is used",
            },
            "encode_all_2_aac":               {
                "label": "check this if you also want to encode all existing, non-aac, streams to aac using selected encoder - otherwise all other streams left as is",
            },
            "keep_mc":      {
                "label": "check to keep the multichannel streams, otherwise, they are removed",
            },
            "set_2ch_stream_as_default": {
                "label": "check to set the default audio stream as a new 2 channel stream OR an existing audio stream if file contains no multichannel streams and you wish to designate a specific language stream as the default audio stream",
            },
            "default_lang":        self.__set_default_lang_form_settings(),
            "normalize_2_channel_stream": {
                "label": "check this to normalize the resulting 2 channel audio stream - customizeable settings will appear below when checked",
            },
            "I":        self.__set_I_form_settings(),
            "LRA":        self.__set_LRA_form_settings(),
            "TP":        self.__set_TP_form_settings(),
        }

    def __set_default_lang_form_settings(self):
        values = {
            "label":          "A list of languages in your prioritized order to select from that will be set as the default audio stream if such language stream exists in the file",
            "input_type":     "textarea",
        }
        if not self.get_setting('set_2ch_stream_as_default'):
            values["display"] = 'hidden'
        return values

    def __set_I_form_settings(self):
        values = {
            "label":          "Integrated loudness target",
            "input_type":     "slider",
            "slider_options": {
                "min":  -70.0,
                "max":  -5.0,
                "step": 0.1,
            },
        }
        if not self.get_setting('normalize_2_channel_stream'):
            values["display"] = 'hidden'
        return values

    def __set_LRA_form_settings(self):
        values = {
            "label":          "Loudness range",
            "input_type":     "slider",
            "slider_options": {
                "min":  1.0,
                "max":  20.0,
                "step": 0.1,
            },
        }
        if not self.get_setting('normalize_2_channel_stream'):
            values["display"] = 'hidden'
        return values

    def __set_TP_form_settings(self):
        values = {
            "label":          "The maximum true peak",
            "input_type":     "slider",
            "slider_options": {
                "min":  -9.0,
                "max":  0,
                "step": 0.1,
            },
        }
        if not self.get_setting('normalize_2_channel_stream'):
            values["display"] = 'hidden'
        return values

def streams_to_stereo_encode(probe_streams):
    audio_stream = -1
    streams = []
    langs = []
    stereo_streams = [probe_streams[i]['tags']['language'] for i in range(len(probe_streams)) if probe_streams[i]['codec_type'] == 'audio' and
                      'tags' in probe_streams[i] and 'language' in probe_streams[i]['tags'] and probe_streams[i]['channels'] == 2 and
                      (("title" in probe_streams[i]['tags'] and "commentary" not in probe_streams[i]["tags"]["title"].lower()) or ("title" not in probe_streams[i]['tags']))]
    for i in range(0, len(probe_streams)):
        if "codec_type" in probe_streams[i] and probe_streams[i]["codec_type"] == "audio":
            audio_stream += 1
            if  int(probe_streams[i]["channels"]) > 4 and 'tags' in probe_streams[i] and 'language' in probe_streams[i]['tags'] and probe_streams[i]['tags']['language'] not in stereo_streams:
                streams.append(audio_stream)
                langs.append(probe_streams[i]['tags']['language'])

    langs.append(stereo_streams)
    return streams, langs

def streams_to_aac_encode(probe_streams, streams, keep_mc):

    non_aac_streams = [i for i in range(len(probe_streams)) if probe_streams[i]['codec_type'] == 'audio' and probe_streams[i]['codec_name'] != 'aac' and
                       ((keep_mc and probe_streams[i]['channels'] > 2 and i in streams) or
                        (probe_streams[i]['channels'] == 2))]

    return non_aac_streams

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
    probe_data = Probe(logger, allowed_mimetypes=['audio', 'video'])

    # Get stream data from probe
    if probe_data.file(abspath):
        probe_streams = probe_data.get_probe()["streams"]
        probe_format = probe_data.get_probe()["format"]
    else:
        logger.debug("Probe data failed - Blocking everything.")
        data['add_file_to_pending_tasks'] = False
        return data

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    streams, langs = streams_to_stereo_encode(probe_streams)
    encode_all_2_aac = settings.get_setting('encode_all_2_aac')
    keep_mc = settings.get_setting('keep_mc')
    streams_2_aac_encode = []
    if encode_all_2_aac: streams_2_aac_encode = streams_to_aac_encode(probe_streams, streams, keep_mc)

    if streams != [] or streams_2_aac_encode != []:
        data['add_file_to_pending_tasks'] = True
        for stream in range(0, len(streams)):
            logger.debug("Audio stream '{}' is multichannel audio - convert stream".format(streams[stream]))
    else:
#        data['add_file_to_pending_tasks'] = False
        logger.debug("do not add file '{}' to task list - no multichannel audio streams".format(abspath))

    return data

def audio_filtergraph(settings):
    i = settings.get_setting('I')
    lra = settings.get_setting('LRA')
    tp = settings.get_setting('TP')

    return 'loudnorm=I={}:LRA={}:TP={}'.format(i, lra, tp)

def find_def_lang_stream(def_langs, langs):
    try:
        langs = [Language.get(langs[i]).to_tag() for i in range(len(langs))]
        def_langs = [Language.get(def_langs[i]).to_tag() for i in range(len(def_langs))]
    except LanguageTagError:
        logger.info(f"unable to match default language - lookup error.  not setting default language")
        return ""
    def_langs_set = set(def_langs)
    if def_langs_set.isdisjoint(langs):
        logger.info(f"None of the default language choices are present in the file - not setting a default language")
        return ""
    def_langs_index = {item: i for i, item in enumerate(def_langs)}
    in_def_langs = []
    not_in_def_langs = []
    for item in langs:
        if item in def_langs_set:
            in_def_langs.append(item)
        else:
            not_in_def_langs.append(item)
    intersect = [j for j in def_langs for i in langs if j==i]
    if len(intersect) > 0:
        logger.info(f"default language: {intersect[0]}")
        return str(intersect[0])
    else:
        logger.debug(f"None of the default language choices are present in the file - not setting a default language.  Note this point should not have been reached as it was checked above")
        logger.debug(f"def_langs: {def_langs}")
        logger.debug(f"langs: {langs}")
        return ""

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

    # Get the path to the file
    abspath = data.get('file_in')
    outpath = data.get('file_out')

    # Get file probe
    probe_data = Probe(logger, allowed_mimetypes=['audio', 'video'])

    if probe_data.file(abspath):
        probe_streams = probe_data.get_probe()["streams"]
        probe_format = probe_data.get_probe()["format"]
    else:
        logger.debug("Probe data failed - Nothing to encode - '{}'".format(abspath))
        return data

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    keep_mc = settings.get_setting('keep_mc')
    defaudio2ch = settings.get_setting('set_2ch_stream_as_default')
    def2chlang = settings.get_setting('default_lang')
    def_langs = def2chlang.split(',')
    def_langs = [def_langs[i].strip() for i in range(0,len(def_langs))]
    encode_all_2_aac = settings.get_setting('encode_all_2_aac')
    normalize_2_channel_stream = settings.get_setting('normalize_2_channel_stream')

    streams, langs = streams_to_stereo_encode(probe_streams)
    def_lang = find_def_lang_stream(def_langs, langs)
    encode_all_2_aac = settings.get_setting('encode_all_2_aac')
    streams_2_aac_encode = []
    if encode_all_2_aac: streams_2_aac_encode = streams_to_aac_encode(probe_streams, streams, keep_mc)
    all_astreams=[probe_streams[i]['index'] for i in range(len(probe_streams)) if probe_streams[i]['codec_type'] == 'audio']
    mc_streams= [probe_streams[i]['index'] for i in range(len(probe_streams)) if probe_streams[i]['codec_type'] == 'audio' and probe_streams[i]['channels'] > 2]

    logger.debug("streams: '{}'".format(streams))
    logger.debug("all_astreams: '{}'".format(all_astreams))
    logger.debug("mc_streams: '{}'".format(mc_streams))

    encoder = 'aac'
    if settings.get_setting('use_libfdk_aac'): encoder = 'libfdk_aac'

    # set 'copy encoder' to either selected encoder or 'copy' depending on encode_all_2_aac setting
    if encode_all_2_aac:
        copy_enc = encoder
    else:
        copy_enc = 'copy'

    if streams != []:
        # Get generated ffmpeg args
        if defaudio2ch:
            ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-map', '0:v', '-c:v', 'copy', '-disposition:a', '-default-original']
        else:
            ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-map', '0:v', '-c:v', 'copy']

        if not keep_mc:
            for stream,abs_stream in enumerate(all_astreams):
                try:
                    rate = str(int(int(probe_streams[abs_stream]['bit_rate'])/(1000 * probe_streams[abs_stream]['channels']))*2) + 'k'
                except KeyError:
                    rate = '128k'
                try:
                    chnls = probe_streams[abs_stream]['channels']
                except KeyError:
                    chnls = 0
                else:
                    if chnls > 6: chnls = 6

                filter = [f"-filter:a:{stream}", audio_filtergraph(settings)]
                if not normalize_2_channel_stream: filter = []

                if abs_stream in mc_streams:
                    if not defaudio2ch:
                        ffmpeg_args += ['-map', '0:a:'+str(stream), '-c:a:'+str(stream), encoder, '-ac:a:'+str(stream), '2', '-b:a:'+str(stream), rate] + filter + ['-metadata:s:a:'+str(stream), 'title='+"AAC Stereo"]
                    else:
                        if (tags := probe_streams[abs_stream].get("tags")) and isinstance(tags, dict) and Language.get(tags.get("language")).to_tag() == def_lang:
                            ffmpeg_args += ['-map', '0:a:'+str(stream), '-c:a:'+str(stream), encoder, '-ac:a:'+str(stream), '2', '-b:a:'+str(stream), rate] + filter + ['-metadata:s:a:'+str(stream), 'title='+"AAC Stereo", '-disposition:a:'+str(stream), 'default']
                        else:
                            logger.info("cant set default audio stream to new 2 channel stream - language didn't match or stream not tagged")
                            ffmpeg_args += ['-map', '0:a:'+str(stream), '-c:a:'+str(stream), encoder, '-ac:a:'+str(stream), '2', '-b:a:'+str(stream), rate] + filter + ['-metadata:s:a:'+str(stream), 'title='+"AAC Stereo"]
                else:
                    if chnls:
                        r = str(int(int(rate[:-1])/2) * int(chnls)) +'k'
                        ffmpeg_args += ['-map', '0:a:'+str(stream), '-c:a:'+str(stream), copy_enc, '-ac:a:'+str(stream), str(chnls), '-b:a:'+str(stream), r]
                    else:
                        ffmpeg_args += ['-map', '0:a:'+str(stream), '-c:a:'+str(stream), 'copy']
        else:
            stream_map = {}
            for stream,abs_stream in enumerate(all_astreams):
                stream_map[stream] = abs_stream

            next_audio_stream_index = 0

            for stream in range(0, len(streams)):
                next_audio_stream_index += 1
                try:
                    rate = str(int(int(probe_streams[stream_map[stream]]['bit_rate'])/(1000 * probe_streams[stream_map[stream]]['channels']))*2) + 'k'
                except KeyError:
                    rate = '128k'

                filter = [f"-filter:a:{stream}", audio_filtergraph(settings)]
                if not normalize_2_channel_stream: filter = []

                if defaudio2ch:
                    ffmpeg_args += ['-map', '0:a:'+str(stream), '-c:a:'+str(stream), encoder, '-ac:a:'+str(stream), '2', '-b:a:'+str(stream), rate] + filter + ['-metadata:s:a:'+str(stream), 'title='+"AAC Stereo", '-disposition:a:'+str(stream), 'default']
                else:
                     ffmpeg_args += ['-map', '0:a:'+str(stream), '-c:a:'+str(stream), encoder, '-ac:a:'+str(stream), '2', '-b:a:'+str(stream), rate] + filter + ['-metadata:s:a:'+str(stream), 'title='+"AAC Stereo"]

            for stream,abs_stream in enumerate(all_astreams):
                try:
                    chnls = probe_streams[abs_stream]['channels']
                except KeyError:
                    chnls = 0
                else:
                    if chnls > 6: chnls = 6

                filter = [f"-filter:a:{stream + next_audio_stream_index}", audio_filtergraph(settings)]
                if not normalize_2_channel_stream or chnls > 2: filter = []

                try:
                    rate = str(int(int(probe_streams[stream_map[stream]]['bit_rate'])/(1000 * probe_streams[stream_map[stream]]['channels']))*int(chnls)) + 'k'
                except KeyError:
                    rate = '256k'

                if chnls and copy_enc != 'copy':
                    ffmpeg_args += ['-map', '0:a:'+str(stream), '-c:a:'+str(stream + next_audio_stream_index), copy_enc, '-ac:a:'+str(stream + next_audio_stream_index), str(chnls), '-b:a:'+str(stream + next_audio_stream_index), rate] + filter
                else:
                    ffmpeg_args += ['-map', '0:a:'+str(stream), '-c:a:'+str(stream + next_audio_stream_index),  'copy']

        ffmpeg_args += ['-map', '0:s?', '-c:s', 'copy', '-map', '0:d?', '-c:d', 'copy', '-map', '0:t?', '-c:t', 'copy', '-y', str(outpath)]

    if streams == [] and streams_2_aac_encode != []:
        if defaudio2ch:
            ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-map', '0:v', '-c:v', 'copy', '-disposition:a', '-default-original']
        else:
            ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-map', '0:v', '-c:v', 'copy']

        for i,stream in enumerate(streams_2_aac_encode):
            try:
                chnls = probe_streams[stream]['channels']
            except KeyError:
                chnls = 0
            else:
                if chnls > 6: chnls = 6

            filter = [f"-filter:a:{i}", audio_filtergraph(settings)]
            if not normalize_2_channel_stream or copy_enc == 'copy' or chnls > 2: filter = []

            if not defaudio2ch:
                ffmpeg_args += ['-map', '0:a:'+str(i), '-c:a:'+str(i), copy_enc] + filter
            else:
                if (tags := probe_streams[stream].get("tags")) and isinstance(tags, dict) and Language.get(tags.get("language")).to_tag() == def_lang:
                    ffmpeg_args += ['-map', '0:a:'+str(i), '-c:a:'+str(i), copy_enc] + filter + ['-disposition:a:'+str(i), 'default']
                else:
                    logger.info("cant set default audio stream to designated stream - language didn't match or stream not tagged")
                    ffmpeg_args += ['-map', '0:a:'+str(i), '-c:a:'+str(i), copy_enc] + filter

        ffmpeg_args += ['-map', '0:s?', '-c:s', 'copy', '-map', '0:d?', '-c:d', 'copy', '-map', '0:t?', '-c:t', 'copy', '-y', str(outpath)]

    if streams != [] or streams_2_aac_encode != []:

        logger.debug("ffmpeg args: '{}'".format(ffmpeg_args))

        # Apply ffmpeg args to command
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe_data)
        data['command_progress_parser'] = parser.parse_progress
