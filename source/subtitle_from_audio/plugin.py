#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     6 September 2024, (2:30 PM)

    Copyright:
        Unmanic plugin code Copyright (C) 2024 Jay Gardner
        Portions of this module rely on OpenAI's Whisper Speech Recognition which are governed by their license.

        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

        Whisper Module:
        This Unmanic plugin module uses Whisper by OpenAI (<https://github.com/openai/whisper/>) which is governed by it's own
        license.  The text of this license has accompanied this program.  If for some reason you do not have it, please refer
        to <https://github.com/openai/whisper/blob/main/LICENSE/>.

"""
import logging
import os
import re
from pathlib import Path
import whisper
import iso639
import shutil
import ffmpeg
import torch

from unmanic.libs.unplugins.settings import PluginSettings

from subtitle_from_audio.lib.ffmpeg import Probe

langs = ('Afrikaans', 'Albanian', 'Amharic', 'Arabic', 'Armenian', 'Assamese', 'Azerbaijani', 'Bashkir', 'Basque',
         'Belarusian', 'Bengali', 'Bosnian', 'Breton', 'Bulgarian', 'Burmese', 'Cantonese', 'Castilian', 'Catalan',
         'Chinese', 'Croatian', 'Czech', 'Danish', 'Dutch', 'English', 'Estonian', 'Faroese', 'Finnish', 'Flemish',
         'French', 'Galician', 'Georgian', 'German', 'Greek', 'Gujarati', 'Haitian', 'Haitian Creole', 'Hausa', 'Hawaiian',
         'Hebrew', 'Hindi', 'Hungarian', 'Icelandic', 'Indonesian', 'Italian', 'Japanese', 'Javanese', 'Kannada', 'Kazakh',
         'Khmer', 'Korean', 'Lao', 'Latin', 'Latvian', 'Letzeburgesch', 'Lingala', 'Lithuanian', 'Luxembourgish',
         'Macedonian', 'Malagasy', 'Malay', 'Malayalam', 'Maltese', 'Mandarin', 'Maori', 'Marathi', 'Moldavian', 'Moldovan',
         'Mongolian', 'Myanmar', 'Nepali', 'Norwegian', 'Nynorsk', 'Occitan', 'Panjabi', 'Pashto', 'Persian', 'Polish',
         'Portuguese', 'Punjabi', 'Pushto', 'Romanian', 'Russian', 'Sanskrit', 'Serbian', 'Shona', 'Sindhi', 'Sinhala',
         'Sinhalese', 'Slovak', 'Slovenian', 'Somali', 'Spanish', 'Sundanese', 'Swahili', 'Swedish', 'Tagalog', 'Tajik',
         'Tamil', 'Tatar', 'Telugu', 'Thai', 'Tibetan', 'Turkish', 'Turkmen', 'Ukrainian', 'Urdu', 'Uzbek', 'Valencian',
         'Vietnamese', 'Welsh', 'Yiddish', 'Yoruba')

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.subtitle_from_audio")

duration = 3600.00

class Settings(PluginSettings):
    settings = {
        "audio_stream_lang_to_text": "",
        "audio_stream_to_convert_if_lang_not_present": "",
        "whisper_model": "",
        "whisper_device": ""
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)

        self.form_settings = {
            "audio_stream_lang_to_text": {
                "label": "Enter language of audio stream to save as subtitle text",
            },
            "audio_stream_to_convert_if_lang_not_present": self.__set_handle_stream_not_found_form_settings(),
            "whisper_model": self.__set_whisper_model_form_settings(),
            "whisper_device": self.__set_whisper_device_form_settings(),
        }

    def __set_handle_stream_not_found_form_settings(self):
        values = {
            "description": "Set how plugin should proceed if designated audio stream is not found",
            "label":      "Enter Choice",
            "input_type": "select",
            "select_options": [
                {
                    "value": "abort",
                    "label": "Abort",
                },
                {
                    "value": "pick_first_audio",
                    "label": "Select first audio stream",
                },
            ],
        }
        return values

    def __set_whisper_model_form_settings(self):
        values = {
            "description": "Set the whisper model which dictates GPU memory, model performance, and accuracy",
            "label":      "Enter Choice",
            "input_type": "select",
            "select_options": [
                {
                    "value": "base",
                    "label": "base-1G-7x",
                },
                {
                    "value": "small",
                    "label": "small-2G-4x",
                },
                {
                    "value": "medium",
                    "label": "medium-5G-2x",
                },
                {
                    "value": "large",
                    "label": "large-10G-1x",
                },
                {
                    "value": "turbo",
                    "label": "turbo-6G-8x",
                },
            ],
        }
        return values

    def __set_whisper_device_form_settings(self):
        values = {
            "description": "Set the whisper device",
            "label":      "Enter Choice",
            "input_type": "select",
            "select_options": [
                {
                    "value": "cuda",
                    "label": "CUDA",
                },
                {
                    "value": "cpu",
                    "label": "CPU",
                },
            ],
        }
        return values

def srt_already_created(settings, original_file_path, probe_streams):

    # Get settings and test astreams for language
    audio_language_to_convert = settings.get_setting('audio_stream_lang_to_text')
    audio_stream_to_convert_if_lang_not_present = settings.get_setting('audio_stream_to_convert_if_lang_not_present')
    astreams = [i for i in range(len(probe_streams)) if probe_streams[i]['codec_type'] == 'audio' and 'tags' in probe_streams[i] and 'language' in probe_streams[i]['tags'] and probe_streams[i]['tags']['language'] == audio_language_to_convert]
    if astreams == [] and audio_stream_to_convert_if_lang_not_present == "pick_first_audio":
        first_audio_stream = [i for i in range(len(probe_streams)) if probe_streams[i]['codec_type'] == 'audio'][0]
        try:
            audio_language_to_convert = probe_streams[first_audio_stream]['tags']['language']
        except KeyError:
            audio_language_to_convert = '0'
            logger.info("Using number for language name of srt file - user specified language was not present and user selected to create srt from first audio stream")
    elif astreams == [] and audio_stream_to_convert_if_lang_not_present == "abort":
        logger.info("Aborting... language stream not found and user selected abort")
        return True, ""

    base = os.path.splitext(original_file_path)[0]
    srt_file = base + audio_language_to_convert + '.srt'
    path=Path(srt_file)

    if path.is_file():
        logger.info("File's srt subtitle stream was previously created - '{}' exists.".format(srt_file))
        return True, audio_language_to_convert

    # Default to...
    return False, audio_language_to_convert

def lang_code_to_name(lang):
    try:
        lang_part = "part1" if iso639.Language.match(lang).part1 is not None and lang in iso639.Language.match(lang).part1 else \
                    "part2b" if iso639.Language.match(lang).part2b is not None and lang in iso639.Language.match(lang).part2b else \
                    "part2t" if iso639.Language.match(lang).part2t is not None and lang in iso639.Language.match(lang).part2t else \
                    "part3" if lang in iso639.Language.match(lang).part3 else ""
    except iso639.language.LanguageNotFoundError:
        lang_part = ''

    if lang_part:
        lang_func = {"part1": iso639.Language.from_part1,
                     "part2t": iso639.Language.from_part2t,
                     "part2b": iso639.Language.from_part2b,
                     "part3": iso639.Language.from_part3}

        lang_name=lang_func[lang_part](lang).name
        if lang_name in langs:
            return lang_name

    return ""

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

    # Get file probe
    probe = Probe(logger, allowed_mimetypes=['video'])
    if 'ffprobe' in data.get('shared_info', {}):
        if not probe.set_probe(data.get('shared_info', {}).get('ffprobe')):
            # Failed to set ffprobe from shared info.
            # Probably due to it being for an incompatible mimetype declared above
            return
    elif not probe.file(abspath):
        # File probe failed, skip the rest of this test
        return

    # Set file probe to shared infor for subsequent file test runners
    if 'shared_info' in data:
        data['shared_info'] = {}
    data['shared_info']['ffprobe'] = probe.get_probe()

    probe_streams = probe.get_probe()["streams"]

    # Add task to pending tasks if srt file has not been created &/or if language stream doesn't exist but user selects logic for another stream
    srt_exists, audio_language_to_convert = srt_already_created(settings, abspath, probe_streams)
    if not srt_exists and audio_language_to_convert != "":
        lang_in_model = lang_code_to_name(audio_language_to_convert)
        if lang_in_model:
            # Mark this file to be added to the pending tasks
            data['add_file_to_pending_tasks'] = True
            logger.info("File '{}' should be added to task list. File has not been previously had SRT created.".format(abspath))
        else:
            logger.info("File '{}' should not be added to task list; language code '{}' is not supported by whisper model".format(abspath, audio_language_to_convert))
    else:
        logger.info("File '{}' has previously had SRT created or audio language was not present and user elected to abort.".format(abspath))

    return data

def parse_progress(line_text):
    global duration

    match = re.search(r'(\[.*\s+-->\s+)(\d*:*\d+:\d+.\d+)].*$', line_text)
    if match and (duration > 0.0):
        time_str=match.group(2)
        if time_str.count(':') == 1:
            tc_m, tc_s = time_str.split(':')
            secs = int(tc_m)*60.0 + float(tc_s)
        elif time_str.count(':') == 2:
            tc_h, tc_m, tc_s = time_str.split(':')
            secs = int(tc_h)*3600.0 + int(tc_m)*60.0 + float(tc_s)
        progress = int(round((secs / duration) * 100.0,0))
    else:
        progress = ''

    return {
        'percent': progress
    }

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

    DEPRECIATED 'data' object args passed for legacy Unmanic versions:
        exec_ffmpeg             - Boolean, should Unmanic run FFMPEG with the data returned from this plugin.
        ffmpeg_args             - A list of Unmanic's default FFMPEG args.

    :param data:
    :return:

    """
    global duration
    # Default to no FFMPEG command required. This prevents the FFMPEG command from running if it is not required
    data['exec_command'] = []
    data['repeat'] = False

    # Get the path to the file
    abspath = data.get('file_in')
    original_file_path = data.get('original_file_path')

    # Get file probe
    probe_data = Probe(logger, allowed_mimetypes=['video'])

    # Get stream data from probe
    if probe_data.file(abspath):
        probe_streams = probe_data.get_probe()["streams"]
        probe_format = probe_data.get_probe()["format"]
    else:
        logger.debug("Probe data failed - Blocking everything.")
        return data

    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    srt_exists, audio_language_to_convert = srt_already_created(settings, abspath, probe_streams)
    logger.debug("srt_exists: '{}', audio_language_to_convert: '{}'".format(srt_exists, audio_language_to_convert))

    if not srt_exists and audio_language_to_convert != "":
        lang_in_model = lang_code_to_name(audio_language_to_convert)
        logger.debug("lang_in_model: '{}'".format(lang_in_model))

        if lang_in_model or re.search(fr'[0-9]', audio_language_to_convert):
            try:
                duration = float(probe_format["duration"])
            except KeyError:
                duration = 0.0

            astream = 0
            if not re.search(fr'[0-9]', audio_language_to_convert):
                astreams = [i for i in range(len(probe_streams)) if probe_streams[i]['codec_type'] == 'audio']
                for stream,abs_stream in enumerate(astreams):
                    if 'tags' in probe_streams[abs_stream] and 'language' in probe_streams[abs_stream]['tags'] and probe_streams[abs_stream]['tags']['language'] == audio_language_to_convert:
                        astream = stream
                        logger.debug("astream: '{}'".format(astream))
                        break

            output_dir = os.path.dirname(original_file_path)
            sfx = os.path.splitext(original_file_path)[1]
            ffin = ffmpeg.input(original_file_path)
            tmp_audio = '/tmp/unmanic/'+os.path.basename(original_file_path).replace(sfx,'.wav')
            temp_audio_out = ffmpeg.output(ffin['a:'+str(astream)],tmp_audio,acodec="pcm_s16le",ar="44100",ac="2")
            temp_audio_out.run(overwrite_output=True, quiet=True)

            model = settings.get_setting('whisper_model')
            model_order = ['base', 'small', 'medium', 'turbo', 'large']
            model_index=[i for i in range(len(model_order)) if model_order[i] == model][0]

            device = settings.get_setting("whisper_device")
            model_too_big = True
            while model_too_big:
                try:
                    whisper.load_model(model, device='cuda')
                except torch.OutOfMemoryError:
                    model_index -= 1
                    model = model_order[model_index]
                    print(f"model {model_order[model_index + 1]} too big, trying model {model}")
                    model_too_big = True
                else:
                    model_too_big = False
                finally:
                    if model_index == -1:
                        logger.error(f"Insufficient GPU resources to run whisper, switching to CPU")
                        device = 'cpu'
                        model = 'medium'
                        model_too_big = False
                    torch.cuda.empty_cache()

            if audio_language_to_convert != '0':
                whisper_args = ['--model', model, '--device', device, '--output_dir', output_dir, '--language', lang_in_model, '--output_format', 'srt', tmp_audio]
            else:
                whisper_args = ['--model', model, '--device', device, '--output_dir', output_dir, '--output_format', 'srt', tmp_audio]

            # Apply ffmpeg args to command
            data['exec_command'] = ['whisper']
            data['exec_command'] += whisper_args

            logger.debug("command: '{}'".format(data['exec_command']))

            # Set the parser
            data['command_progress_parser'] = parse_progress

            #data['file_out'] = None

        else:
            logger.info("Aborting - language code '{}' in '{}' is not supported by whisper model".format(audio_language_to_convert, original_file_path))

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

    abspath = data.get('source_data').get('abspath')
    try:
        tmp_audio = '/tmp/unmanic/' + os.path.splitext(os.path.basename(abspath))[0] + '.wav'
    except:
        logger.debug("issue building temp audio file path: os.path.splitext(os.path.basename(abspath))[0]: '{}'".format(os.path.splitext(os.path.basename(abspath))))

    path = Path(tmp_audio)
    if path.is_file():
        os.remove(tmp_audio)
    else:
        logger.debug("temp audio file doesn't exist, so not removing...")

    if not data.get('task_processing_success'):
        return data

    # Configure settings object (maintain compatibility with v1 plugins)
    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    audio_language_to_convert = settings.get_setting('audio_stream_lang_to_text')
    destfile = data.get('destination_files')[0]
    probe_data=Probe(logger, allowed_mimetypes=['video'])
    if probe_data.file(destfile):
        probe_streams=probe_data.get_probe()["streams"]
    else:
        probe_streams=[]
    astreams = []
    for i in range(len(probe_streams)):
        if probe_streams[i]['codec_type'] == 'audio' and 'tags' in probe_streams[i] and 'language' in probe_streams[i]['tags']:
            stream_lang_name = lang_code_to_name(probe_streams[i]['tags']['language'])
            configured_lang_name = lang_code_to_name(audio_language_to_convert)
            if stream_lang_name == configured_lang_name:
                astreams.append(i)
    if astreams == []:
        audio_language_to_convert = '0'
    base = os.path.splitext(abspath)[0]
    srt_file_sans_lang = base + '.srt'
    base_dest = os.path.splitext(destfile)[0]
    srt_file = base_dest + '.' + audio_language_to_convert + '.srt'
    path = Path(srt_file_sans_lang)
    if path.is_file():
        try:
            os.rename(srt_file_sans_lang,srt_file)
        except OSError:
            # avoid invalide cross-device link error
            shutil.copy2(srt_file_sans_lang,srt_file)
    else:
        logger.error("Cannot create srt file.  basename is: '{}' and srt file path should be: '{}'".format(base, srt_file))
    return data
