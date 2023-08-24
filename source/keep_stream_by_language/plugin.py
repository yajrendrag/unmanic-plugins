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
import os
from configparser import NoSectionError, NoOptionError

from unmanic.libs.unplugins.settings import PluginSettings
from unmanic.libs.directoryinfo import UnmanicDirectoryInfo

from keep_stream_by_language.lib.ffmpeg import StreamMapper, Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.keep_stream_by_language")


class Settings(PluginSettings):
    settings = {
        "audio_languages":       '',
        "subtitle_languages":    '',
        "keep_undefined":        True,
    }


    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "audio_languages": {
                "label": "Enter comma delimited list of audio languages to keep",
            },
            "subtitle_languages": {
                "label": "Enter comma delimited list of subtitle languages to keep",
            },
            "keep_undefined":	{
                "label": "check to keep streams with no language tags or streams with undefined/uknown language tags",
            }
        }

class PluginStreamMapper(StreamMapper):
    def __init__(self):
        super(PluginStreamMapper, self).__init__(logger, ['audio','subtitle'])
        self.settings = None

    def set_settings(self, settings):
        self.settings = settings

    def same_streams(self, streams):
        audio_language_config_list = self.settings.get_setting('audio_languages')
        alcl = list(audio_language_config_list.split(','))
        alcl = [alcl[i].strip() for i in range(0,len(alcl))]
        alcl.sort()
        if alcl == ['']: alcl = []
        subtitle_language_config_list = self.settings.get_setting('subtitle_languages')
        slcl = list(subtitle_language_config_list.split(','))
        slcl = [slcl[i].strip() for i in range(0,len(slcl))]
        slcl.sort()
        if slcl == ['']: slcl = []
        audio_streams_list = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == "audio"]
        audio_streams_list.sort()
        subtitle_streams_list = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == "subtitle"]
        subtitle_streams_list.sort()
        logger.debug("audio config list: '{}', audio streams in file: '{}'".format(alcl, audio_streams_list))
        logger.debug("subtitle config list: '{}', subtitle streams in file: '{}'".format(slcl, subtitle_streams_list))
        if alcl == audio_streams_list and slcl == subtitle_streams_list:
            return True
        else:
            return False

    def test_tags_for_search_string(self, codec_type, stream_tags, stream_id):
        keep_undefined  = self.settings.get_setting('keep_undefined')
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
                    # Found a matching language. Process this stream to keep it
                    return True
        elif keep_undefined:
            return True
            logger.warning(
                "Stream '{}' in file '{}' has no language tag, but keep_undefined is checked. add to queue".format(stream_id, self.input_file))

        else:
            logger.warning(
                "Stream '{}' in file '{}' has no language tag. Ignoring".format(stream_id, self.input_file))
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

def kept_streams(settings):
    al = settings.get_setting('audio_languages')
    if not al:
        al = settings.settings.get('audio_languages')
    sl = settings.get_setting('subtitle_languages')
    if not sl:
        sl = settings.settings.get('subtitle_languages')
    ku = settings.get_setting('keep_undefined')
    if not ku:
        ku = settings.settings.get('keep_undefined')

    return 'kept_streams=audio_langauges={}:subtitle_languages={}:keep_undefined={}'.format(al, sl, ku)

def file_streams_already_kept(settings, path):
    directory_info = UnmanicDirectoryInfo(os.path.dirname(path))

    try:
        streams_already_kept = directory_info.get('keep_streams_by_language', os.path.basename(path))
    except NoSectionError as e:
        streams_already_kept = ''
    except NoOptionError as e:
        streams_already_kept = ''
    except Exception as e:
        logger.debug("Unknown exception {}.".format(e))
        streams_already_kept = ''

    if streams_already_kept:
        logger.debug("File's streams were previously kept with {}.".format(streams_already_kept))
        return True

    # Default to...
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

    if not file_streams_already_kept(settings, abspath):
        logger.debug("File '{}' has not previously had streams kept by keep_streams_by_language plugin".format(abspath))
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

def keep_languages(mapper, ct, language_list, streams, keep_undefined):
    codec_type = ct[0]
    languages = list(filter(None, language_list.split(',')))
    languages = [languages[i].strip() for i in range(0,len(languages))]
    streams_list = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == ct]
    for i, language in enumerate(streams_list):
        language = language.strip()
        if language and language.lower() and not (keep_undefined and language.lower() == "und") and language.lower() in languages:
            mapper.stream_encoding += ['-c:{}:{}'.format(codec_type, i), 'copy']
            mapper.stream_mapping += ['-map', '0:{}:{}'.format(codec_type, i)]

def keep_undefined(mapper, streams):
    audio_streams_list = [i for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == "audio"]
    subtitle_streams_list = [i for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == "subtitle"]
    stream_iterator(mapper, subtitle_streams_list, streams, 's')
    stream_iterator(mapper, audio_streams_list, streams, 'a')

def stream_iterator(mapper, stream_list, streams, codec):
    for i in range(0, len(stream_list)):
        try:
            lang = streams[stream_list[i]]["tags"]["language"]
        except KeyError:
            mapadder(mapper, stream_list[i], codec)
        else:
            if lang == 'und':
                mapadder(mapper, stream_list[i], codec)

def mapadder(mapper, stream, codec):
    mapper.stream_mapping += ['-map', '0:{}:{}'.format(codec, stream)]
    mapper.stream_encoding += ['-c:{}:{}'.format(codec, stream), 'copy']

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
    else:
        probe_streams = probe.get_probe()["streams"]

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    keep_undefined_lang_tags = settings.get_setting('keep_undefined')

    if not file_streams_already_kept(settings, data.get('file_in')):
        # Get stream mapper
        mapper = PluginStreamMapper()
        mapper.set_settings(settings)
        mapper.set_probe(probe)

        # Set the input file
        mapper.set_input_file(abspath)

        if mapper.streams_need_processing():
            # Set the output file
            mapper.set_output_file(data.get('file_out'))

            # clear stream mappings, copy all video
            mapper.stream_mapping = ['-map', '0:v']
            mapper.stream_encoding = ['-c:v', 'copy']

            # keep specific language streams if present
            keep_languages(mapper, 'audio', settings.get_setting('audio_languages'), probe_streams, keep_undefined_lang_tags)
            keep_languages(mapper, 'subtitle', settings.get_setting('subtitle_languages'), probe_streams, keep_undefined_lang_tags)

            # keep undefined language streams if present
            if keep_undefined_lang_tags:
                keep_undefined(mapper, probe_streams)

            # Get generated ffmpeg args
            ffmpeg_args = mapper.get_ffmpeg_args()
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
        task_processing_success         - Boolean, did all task processes complete successfully.
        file_move_processes_success     - Boolean, did all postprocessor movement tasks complete successfully.
        destination_files               - List containing all file paths created by postprocessor file movements.
        source_data                     - Dictionary containing data pertaining to the original source file.

    :param data:
    :return:

    """
    # We only care that the task completed successfully.
    # If a worker processing task was unsuccessful, dont mark the file streams as kept
    # TODO: Figure out a way to know if a file's streams were kept but another plugin was the
    #   cause of the task processing failure flag
    if not data.get('task_processing_success'):
        return data

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # Loop over the destination_files list and update the directory info file for each one
    for destination_file in data.get('destination_files'):
        directory_info = UnmanicDirectoryInfo(os.path.dirname(destination_file))
        directory_info.set('keep_streams_by_language', os.path.basename(destination_file), kept_streams(settings))
        directory_info.save()
        logger.debug("Keep streams by language already processed for '{}'.".format(destination_file))

    return data
