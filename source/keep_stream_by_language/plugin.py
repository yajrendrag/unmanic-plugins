#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               Josh.5 <jsunnex@gmail.com>, senorsmartypants@gmail.com, yajrendrag@gmail.com
    Date:                     30 Sep 2021, (03:45 PM)

    Copyright:
        Copyright (C) 2021 Josh Sunnex

        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

"""
import logging

from unmanic.libs.unplugins.settings import PluginSettings

from keep_stream_by_language.lib.ffmpeg import StreamMapper, Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.keep_stream_by_language")


class Settings(PluginSettings):
    settings = {
        "audio_languages":       '',
        "subtitle_languages":    '',
    }


    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "audio_languages": {
                "label": "Enter comma delimited list of languages to keep",
            },
            "subtitle_languages": {
                "label": "Enter a comma delimted list of Subtitle stream languages to keep",
            }
        }

class PluginStreamMapper(StreamMapper):
    def __init__(self):
        super(PluginStreamMapper, self).__init__(logger, ['audio','subtitle'])
        self.settings = None

    def set_settings(self, settings):
        self.settings = settings

    def same_streams(self, streams):
        # get configured list of audio languages - it's a string of comma delimited languages
        audio_language_config_list = self.settings.get_setting('audio_languages')

        # make them into a list and sort them
        alcl = list(audio_language_config_list.split(','))
        alcl = [alcl[i].strip() for i in range(0,len(alcl))]
        alcl.sort()
        if alcl == ['']: alcl = []

        # elimiate any duplicates
        alcl = [*set(alcl)]

        # same operations as above now on subtitle streams
        subtitle_language_config_list = self.settings.get_setting('subtitle_languages')
        slcl = list(subtitle_language_config_list.split(','))
        slcl = [slcl[i].strip() for i in range(0,len(slcl))]
        slcl.sort()
        if slcl == ['']: slcl = []
        slcl = [*set(slcl)]

        # get audio streams and subtitle streams acutally in the file, sort them, elimiated duplicates
        audio_streams_list = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == "audio"]
        audio_streams_list.sort()
        audio_streams_list = [*set(audio_streams_list)]
        subtitle_streams_list = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == "subtitle"]
        subtitle_streams_list.sort()
        subtitle_streams_list = [*set(subtitle_streams_list)]

        # compare configuration list to see if any configured streams to keep are actually not present in the file, if so
        # remove the configured stream from alcl/slcl lists so the file isn't processed unnecessarily
        langs_not_in_file= [lang for lang in alcl if lang not in audio_streams_list]
        alcl = [i for i in alcl if i not in langs_not_in_file]
        langs_not_in_file= [lang for lang in slcl if lang not in subtitle_streams_list]
        slcl = [i for i in slcl if i not in langs_not_in_file]

        logger.debug("audio config list: '{}', audio streams in file: '{}'".format(alcl, audio_streams_list))
        logger.debug("subtitle config list: '{}', subtitle streams in file: '{}'".format(slcl, subtitle_streams_list))

        # if the remaining alcl/slcl lists are identical to the actual list of audio/subtitle streams in the file, then no need to process the file as keeping the streams would simply
        # be copying the existing streams and is unnecessary
        if alcl == audio_streams_list and slcl == subtitle_streams_list:
            return True
        else:
            return False

    def test_tags_for_search_string(self, codec_type, stream_tags, stream_id):
        # TODO: Check if we need to add 'title' tags
        if stream_tags and True in list(k.lower() in ['language'] for k in stream_tags):
            # check codec and get appropriate language list
            if codec_type == 'audio':
                language_list = self.settings.get_setting('audio_languages')
            else:
                language_list = self.settings.get_setting('subtitle_languages')
            languages = list(filter(None, language_list.split(',')))
            for language in languages:
                language = language.strip()
                if language and language.lower() in stream_tags.get('language', '').lower():
                    # Found a matching language. Process this stream to remove it
                    return True
        else:
            logger.warning(
                "Stream #{} in file '{}' has no 'language' tag. Ignoring".format(stream_id, self.input_file))
        return False

    def test_stream_needs_processing(self, stream_info: dict):
        """Only add streams that have language task that match our list"""
        return self.test_tags_for_search_string(stream_info.get('codec_type', '').lower(), stream_info.get('tags'), stream_info.get('index'))

    def custom_stream_mapping(self, stream_info: dict, stream_id: int):
        """Remove this stream"""
        return {
            'stream_mapping':  [],
            'stream_encoding': [],
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
    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # If the config is empty (not yet configured) ignore everything
    if not settings.get_setting('audio_languages') and not settings.get_setting('subtitle_languages'):
        logger.debug("Plugin has not yet been configured with a list languages to remove allow. Blocking everything.")
        return False

    # Get the path to the file
    abspath = data.get('path')

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(abspath):
        # File probe failed, skip the rest of this test
        return data

    # get all streams
    probe_streams=probe.get_probe()["streams"]

    # Get stream mapper
    mapper = PluginStreamMapper()
    mapper.set_settings(settings)
    mapper.set_probe(probe)

    # Set the input file
    mapper.set_input_file(abspath)

    if mapper.same_streams(probe_streams):
        logger.debug("File '{}' only has same streams as keep configuration specifies - so, does not contain streams that require processing.".format(abspath))
    elif mapper.streams_need_processing():
        # Mark this file to be added to the pending tasks
        data['add_file_to_pending_tasks'] = True
        logger.debug("File '{}' should be added to task list. Probe found streams require processing.".format(abspath))
    else:
        logger.debug("File '{}' does not contain streams that require processing.".format(abspath))

    del mapper

    return data

def keep_languages(mapper, codec_type, language_list):
    languages = list(filter(None, language_list.split(',')))
    for language in languages:
        language = language.strip()
        if language and language.lower() :
            mapper.stream_encoding += ['-c:{}'.format(codec_type), 'copy']
            mapper.stream_mapping += ['-map', '0:{}:m:language:{}?'.format(codec_type, language)]

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

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if not probe.file(abspath):
        # File probe failed, skip the rest of this test
        return data

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # Get stream mapper
    mapper = PluginStreamMapper()
    mapper.set_settings(settings)
    mapper.set_probe(probe)

    # Set the input file
    mapper.set_input_file(abspath)

    if mapper.streams_need_processing():
        # Set the output file
        mapper.set_output_file(data.get('file_out'))

        # clear stream mappings, copy everything
        mapper.stream_mapping = ['-map', '0:v']
        mapper.stream_encoding = ['-c:v', 'copy']
        # set negative stream mappings to remove languages
        keep_languages(mapper, 'a', settings.get_setting('audio_languages'))
        keep_languages(mapper, 's', settings.get_setting('subtitle_languages'))

        # Get generated ffmpeg args
        ffmpeg_args = mapper.get_ffmpeg_args()

        # Apply ffmpeg args to command
        data['exec_command'] = ['ffmpeg']
        data['exec_command'] += ffmpeg_args

        # Set the parser
        parser = Parser(logger)
        parser.set_probe(probe)
        data['command_progress_parser'] = parser.parse_progress

    return data