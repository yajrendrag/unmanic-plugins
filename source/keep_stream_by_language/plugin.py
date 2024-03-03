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
import iso639

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
        "keep_commentary":       False,
        "fail_safe":             True,
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
                "label": "check to keep streams with no language tags or streams with undefined/unknown language tags",
            },
            "keep_commentary":   {
                "label": "uncheck to discard commentary audio streams regardless of any language tags",
            },
            "fail_safe":   {
                "label": "check to include fail safe check to prevent unintentional deletion of all audio &/or all subtitle streams",
            }
        }

class PluginStreamMapper(StreamMapper):
    def __init__(self):
        super(PluginStreamMapper, self).__init__(logger, ['audio','subtitle'])
        self.settings = None

    def set_settings(self, settings):
        self.settings = settings

    def null_streams(self, streams):
        alcl, audio_streams_list = streams_list(self.settings.get_setting('audio_languages'), streams, 'audio')
        slcl, subtitle_streams_list = streams_list(self.settings.get_setting('subtitle_languages'), streams, 'subtitle')
        if len(alcl) > len(audio_streams_list):
            audio=all(l in alcl for l in audio_streams_list)
        else:
            audio=all(l in audio_streams_list for l in alcl)
        if len(slcl) > len(subtitle_streams_list):
            subtitle=all(l in slcl for l in subtitle_streams_list)
        else:
            subtitle=all(l in subtitle_streams_list for l in slcl)
        if (audio or alcl == ['*'] or audio_streams_list == []) and (subtitle or slcl == ['*'] or subtitle_streams_list == []):
#        if (all(l in audio_streams_list for l in alcl) or alcl == ['*'] or audio_streams_list == []) and (all(l in subtitle_streams_list for l in slcl) or slcl == ['*'] or subtitle_streams_list == []):
            return True
        logger.info("One of the lists of languages does not contain a language matching any streams in the file - the entire stream type would be removed if processed, aborting.\n alcl: '{}', audio streams in file: '{}';\n slcl: '{}', subtitle streams in file: '{}'".format(alcl, audio_streams_list, slcl, subtitle_streams_list))
        return False

    def same_streams(self, streams):
        alcl, audio_streams_list = streams_list(self.settings.get_setting('audio_languages'), streams, 'audio')
        slcl, subtitle_streams_list = streams_list(self.settings.get_setting('subtitle_languages'), streams, 'subtitle')
        if not audio_streams_list or not subtitle_streams_list:
            return False
        logger.debug("audio config list: '{}', audio streams in file: '{}'".format(alcl, audio_streams_list))
        logger.debug("subtitle config list: '{}', subtitle streams in file: '{}'".format(slcl, subtitle_streams_list))
        if (alcl == audio_streams_list or alcl == ['*'])  and (slcl == subtitle_streams_list or slcl == ['*']):
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
            languages = [languages[i].strip() for i in range(len(languages))]
            if '*' not in languages and languages:
                try:
                    languages = [iso639.Language.from_part1(languages[i]).part2b if len(languages[i]) == 2 else iso639.Language.from_part2b(languages[i]).part2b for i in range(len(languages))]
                except iso639.language.LanguageNotFoundError:
                    raise iso639.language.LanguageNotFoundError("config list: ", languages)

            for language in languages:
                language = language.strip()
                try:
                    stream_tag_language = iso639.Language.from_part1(stream_tags.get('language', '').lower()).part2b if len(stream_tags.get('language', '').lower()) == 2 else iso639.Language.from_part2b(stream_tags.get('language', '').lower()).part2b
                except iso639.language.LanguageNotFoundError:
                    raise iso639.language.LanguageNotFoundError("stream tag language: ", stream_tags.get('language', '').lower())
                if language and (language.lower() in stream_tag_language or language.lower() == '*'):
                    return True
        elif keep_undefined:
            logger.warning(
                "Stream '{}' in file '{}' has no language tag, but keep_undefined is checked. add to queue".format(stream_id, self.input_file))
            return True

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

def streams_list(languages, streams, stream_type):
    language_config_list = languages
    lcl = list(language_config_list.split(','))
    lcl = [lcl[i].strip() for i in range(0,len(lcl))]
    lcl.sort()
    if lcl == ['']: lcl = []
    if '*' not in lcl and lcl:
        try:
            lcl = [iso639.Language.from_part1(lcl[i]).part2b if len(lcl[i]) == 2 else iso639.Language.from_part2b(lcl[i]).part2b for i in range(len(lcl))]
        except iso639.language.LanguageNotFoundError:
            raise iso639.language.LanguageNotFoundError("config list: ", lcl)
    try:
        streams_list = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == stream_type]
        streams_list.sort() 
    except KeyError:
        streams_list = []
        logger.info("no '{}' tags in file".format(stream_type))
    if streams_list:
        try:
            streams_list = [iso639.Language.from_part1(streams_list[i]).part2b if len(streams_list[i]) == 2 else iso639.Language.from_part2b(streams_list[i]).part2b for i in range(len(streams_list))]
        except iso639.language.LanguageNotFoundError:
            raise iso639.language.LanguageNotFoundError("streams list: ", streams_list)
    return lcl,streams_list

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
    kc = settings.get_setting('keep_commentary')
    if not kc:
        kc = settings.settings.get('keep_commentary')
    fs = settings.get_setting('fail_safe')
    if not fs:
        fs = settings.settings.get('fail_safe')

    return 'kept_streams=audio_langauges={}:subtitle_languages={}:keep_undefined={}:keep_commentary={}:fail_safe={}'.format(al, sl, ku, kc, fs)

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

    # Get fail-safe setting
    fail_safe = settings.get_setting('fail_safe')

    if not file_streams_already_kept(settings, abspath):
        logger.debug("File '{}' has not previously had streams kept by keep_streams_by_language plugin".format(abspath))
        if fail_safe:
            if not mapper.null_streams(probe_streams):
                logger.debug("File '{}' does not contain streams matching any of the configured languages - if * was configured or the file has no streams of a given type, this check will not prevent the plugin from running for that strem type.".format(abspath))
                return data
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

def keep_languages(mapper, ct, language_list, streams, keep_undefined, keep_commentary):
    codec_type = ct[0].lower()
    languages = list(filter(None, language_list.split(',')))
    languages = [languages[i].lower().strip() for i in range(0,len(languages))]
    if '*' not in languages and languages:
        try:
            languages = [iso639.Language.from_part1(languages[i]).part2b if len(languages[i]) == 2 else iso639.Language.from_part2b(languages[i]).part2b for i in range(len(languages))]
        except iso639.language.LanguageNotFoundError:
            raise iso639.language.LanguageNotFoundError("config list: ", languages)
    streams_list = [streams[i]["tags"]["language"] for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == ct and "tags" in streams[i] and "language" in streams[i]["tags"] and
                    (codec_type == 's' or keep_commentary == True or (keep_commentary == False and ("codec_type" in streams[i] and streams[i]["codec_type"] == ct and "tags" in streams[i] and ("title" in streams[i]["tags"] and
                     "commentary" not in streams[i]["tags"]["title"].lower() or "title" not in streams[i]["tags"]))) or languages == ['*'])]
    try:
        streams_list = [iso639.Language.from_part1(streams_list[i]).part2b if len(streams_list[i]) == 2 else iso639.Language.from_part2b(streams_list[i]).part2b for i in range(len(streams_list))]
    except iso639.language.LanguageNotFoundError:
        raise iso639.language.LanguageNotFoundError("streams language list: ", streams_list)
    if streams_list:
        for i, language in enumerate(streams_list):
            lang = language.lower().strip()
            if lang and not (keep_undefined and lang == "und") and (lang in languages or languages == ['*']):
                logger.debug("keeping language '{}' from '{}' stream '{}.".format(lang, ct, i))
                mapadder(mapper, i, codec_type)

def keep_undefined(mapper, streams, keep_commentary):
    if keep_commentary:
        audio_streams_list = [i for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == "audio" and ("tags" not in streams[i] or ("tags" in streams[i] and "language" not in streams[i]["tags"]))]
    else:
        audio_streams_list = [i for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == "audio" and ("tags" not in streams[i] or ("tags" in streams[i] and "language" not in streams[i]["tags"])) or
                              ("tags" in streams[i] and "title" in streams[i]["tags"] and "commentary" not in streams[i]["tags"]["title"].lower())]
    subtitle_streams_list = [i for i in range(0, len(streams)) if "codec_type" in streams[i] and streams[i]["codec_type"] == "subtitle" and ("tags" not in streams[i] or ("tags" in streams[i] and "language" not in streams[i]["tags"]))]
    stream_iterator(mapper, subtitle_streams_list, streams, 's')
    stream_iterator(mapper, audio_streams_list, streams, 'a')

def stream_iterator(mapper, stream_list, streams, codec):
    for i in range(0, len(stream_list)):
        try:
            lang = streams[stream_list[i]]["tags"]["language"].lower().strip()
        except KeyError:
            logger.debug("keeping untagged stream '{}.".format(i))
            mapadder(mapper, i, codec)
        else:
            if lang == 'und':
                logger.debug("keeping stream '{}' marked as undefined.".format(i))
                mapadder(mapper, i, codec)

def mapadder(mapper, stream, codec):
    mapper.stream_mapping += ['-map', '0:{}:{}'.format(codec, stream)]
    #mapper.stream_encoding += ['-c:{}:{}'.format(codec, stream), 'copy']

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
    keep_commentary = settings.get_setting('keep_commentary')

    if not file_streams_already_kept(settings, data.get('file_in')):
        # Get stream mapper
        mapper = PluginStreamMapper()
        mapper.set_settings(settings)
        mapper.set_probe(probe)

        # Set the input file
        mapper.set_input_file(abspath)

        # Get fail-safe setting
        fail_safe = settings.get_setting('fail_safe')

        # Test for null intersection of configured languages and actual languages
        if fail_safe:
            if not mapper.null_streams(probe_streams):
                logger.info("File '{}' does not contain streams matching any of the configured languages - if * was configured or the file has no streams of a given type, this check will not prevent the plugin from running for that strem type.".format(abspath))
                return data

        if mapper.streams_need_processing():
            # Set the output file
            mapper.set_output_file(data.get('file_out'))

            # clear stream mappings, copy all video
            mapper.stream_mapping = ['-map', '0:v']
            mapper.stream_encoding = []

            # keep specific language streams if present
            keep_languages(mapper, 'audio', settings.get_setting('audio_languages'), probe_streams, keep_undefined_lang_tags, keep_commentary)
            keep_languages(mapper, 'subtitle', settings.get_setting('subtitle_languages'), probe_streams, keep_undefined_lang_tags, keep_commentary)

            # keep undefined language streams if present
            if keep_undefined_lang_tags:
                keep_undefined(mapper, probe_streams, keep_commentary)

            # Get generated ffmpeg args
            mapper.stream_encoding += ['-c', 'copy']
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
