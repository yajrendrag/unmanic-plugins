#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    plugins.__init__.py

    Written by:               yajrendrag@gmail.com
    Date:                     09 June 2024, (09:45 AM)

    Copyright:
        Copyright (C) 2024 Jay Gardner

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
from operator import itemgetter
from configparser import NoSectionError, NoOptionError

from unmanic.libs.unplugins.settings import PluginSettings
from unmanic.libs.directoryinfo import UnmanicDirectoryInfo

from stream_arranger.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.stream_arranger")


class Settings(PluginSettings):
    settings = {
        "primary_sort_key":          "channels",
        "channel_sort_direction":    "up",
        "lang_list":                 "",
    }


    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "primary_sort_key": self.__set_primary_sort_key(),
            "channel_sort_direction": self.__set_channel_sort_direction(),
            "lang_list":	{
                "label": "Enter comma delimted list of audio languages to sort by",
            }
        }

    def __set_primary_sort_key(self):
        values = {
            "label":      "Select Primary Sort Key",
            "description":    "Choose Channels or Languages",
            "input_type": "select",
            "select_options": [
                {
                    "value": "channels",
                    "label": "Channels",
                },
                {
                    "value": "languages",
                    "label": "Languages",
                },
            ],
        }
        return values

    def __set_channel_sort_direction(self):
        values = {
            "label":      "Select channels sort direction - ascending or descending",
            "description":    "Choose Ascending or Descending",
            "input_type": "select",
            "select_options": [
                {
                    "value": "up",
                    "label": "Ascending",
                },
                {
                    "value": "down",
                    "label": "Descending",
                },
            ],
        }
        return values

def arrange_streams(settings):
    psk = settings.get_setting('primary_sort_key')
    if not psk:
        psk = settings.settings.get('primary_sort_key')
    csd = settings.get_setting('channel_sort_direction')
    if not csd:
        csd = settings.settings.get('channel_sort_direction')
    ll = settings.get_setting('lang_list')
    if not ll:
        ll = settings.settings.get('lang_list')

    return 'arrange_streams=primary_sort_key={}:channel_sort_direction={}:lang_list={}'.format(psk,csd,ll)

def streams_already_arranged(settings, path):
    directory_info = UnmanicDirectoryInfo(os.path.dirname(path))

    try:
        streams_already_arranged = directory_info.get('stream_arranger', os.path.basename(path))
    except NoSectionError as e:
        streams_already_arranged = ''
    except NoOptionError as e:
        streams_already_arranged = ''
    except Exception as e:
        logger.debug("Unknown exception {}.".format(e))
        streams_already_arranged = ''

    if streams_already_arranged:
        logger.debug("File's streams were previously arranged with {}.".format(streams_already_arranged))
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
    if not settings.get_setting('lang_list') or not settings.get_setting('primary_sort_key') or not settings.get_setting('channel_sort_direction'):
        logger.debug("Plugin has not yet been fully configured. Blocking everything.")
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

    if not streams_already_arranged(settings, abspath):
        logger.info("File '{}' has not previously had streams arranged by streams_arranger plugin".format(abspath))
        # Mark this file to be added to the pending tasks
        data['add_file_to_pending_tasks'] = True
        logger.info("File '{}' should be added to task list. Probe found streams require processing.".format(abspath))
    else:
        logger.info("File '{}' has previously had streams arranged by streams_arranger plugin - proceeding to next plugin test".format(abspath))

    return data

def arrange_audio_streams(streams, primary_sort_key, channel_sort_direction, langs):
    astreams=[{'index': i, 'channels': streams[i]['channels'], 'language': streams[i]['tags']['language']} for i in range(len(streams)) if streams[i]['codec_type'] == 'audio' and 'channels' in streams[i] and 'tags' in streams[i] and 'language' in streams[i]['tags']]
    if primary_sort_key == 'languages' and channel_sort_direction == 'down':
        astreams=sorted(astreams, key=itemgetter('channels', 'language'), reverse=True)
    else:
        astreams=sorted(astreams, key=itemgetter('channels', 'language'))
    if primary_sort_key == 'channels' and channel_sort_direction == 'down':
        channels=sorted(list(set([astreams[i]['channels'] for i in range(len(astreams))])), reverse=True)
    else:
        channels=sorted(list(set([astreams[i]['channels'] for i in range(len(astreams))])))

    logger.debug("astreams: '{}'".format(astreams))
    logger.debug("channels: '{}'".format(channels))

    all_astreams = [i for i in range(len(streams)) if streams[i]['codec_type'] == 'audio']
    astream_order=[]
    if primary_sort_key == 'languages':
        for c in channels:
            for i in range(len(astreams)):
                if astreams[i]['channels'] == c: astream_order += [astreams[i]['index']]
    else:
        for l in langs:
            for i in range(len(astreams)):
               if astreams[i]['language'] == l: astream_order += [astreams[i]['index']]

    logger.debug("astream_order: '{}'".format(astream_order))
    leftover_streams = list(set(all_astreams) - set(astream_order))
    logger.debug("leftover_streams: '{}'".format(leftover_streams))
    astream_order += leftover_streams
    astream_index_order = [all_astreams.index(i) for i in astream_order]
    logger.debug("astream_index_order: '{}'".format(astream_index_order))
    return astream_index_order

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

    primary_sort_key = settings.get_setting('primary_sort_key')
    channel_sort_direction = settings.get_setting('channel_sort_direction')
    langs = settings.get_setting('lang_list')
    langs = list(langs.split(','))
    langs = [langs[i].strip() for i in range(0,len(langs))]
    if langs == ['']: langs = []
    if not settings.get_setting('lang_list') or not settings.get_setting('primary_sort_key') or not settings.get_setting('channel_sort_direction'):
        logger.error("Plugin has not yet been fully configured. Aborting.")
        return data

    if not streams_already_arranged(settings, data.get('file_in')):

        audio_stream_order = arrange_audio_streams(streams, primary_sort_key, channel_sort_direction, langs)

        # Set ffmpeg args
        ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-map', '0:v', '-c:v', 'copy']
        for stream in audio_stream_order:
            ffmpeg_args += ['-map', '0:a:'+str(stream), '-c:a:'+str(stream), 'copy']
        ffmpeg_args += ['-map', '0:s?', '-c:s', 'copy', '-map', '0:d?', '-c:d', 'copy', '-map', '0:t?', '-c:t', 'copy', '-y', str(outpath)]

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
        directory_info.set('stream_arranger', os.path.basename(destination_file), arrange_streams(settings))
        directory_info.save()
        logger.info("Arrange streams processed for '{}' and recorded in .unmanic file.".format(destination_file))

    return data
