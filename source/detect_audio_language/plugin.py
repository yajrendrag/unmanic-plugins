#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     22 September 2024, (5:45 PM)

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
import hashlib
import os
import whisper
import iso639
from pathlib import Path
import subprocess
import random
from moviepy import *
import shutil
import os
import glob
import torch

from unmanic.libs.unplugins.settings import PluginSettings

from detect_audio_language.lib.ffmpeg import Probe, Parser

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.detect_audio_language")

class Settings(PluginSettings):
    settings = {
        "process_as_multilingual_audio_file": False,
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "process_as_multilingual_audio_file":   {
                "label": "check to process file as multilingual meaning it has multiple languages in the audio streams so the lang tag is the most observed language in the samples.",
            },
        }

def get_audio_streams(probe_streams):

    # Get settings and test astreams for language
    astreams = [i for i in range(len(probe_streams)) if probe_streams[i]['codec_type'] == 'audio' and (('tags' in probe_streams[i] and 'language' in probe_streams[i]['tags'] and probe_streams[i]['tags']['language'] == 'und') or
                                                                                                       ('tags' in probe_streams[i] and 'language' not in probe_streams[i]['tags']) or
                                                                                                       ('tags' not in probe_streams[i]))]
    return astreams

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

    # check if any audio streams have missing audio language tags or are tagged as undefined
    streams_needing_tags = get_audio_streams(probe_streams)
    if streams_needing_tags:
        logger.debug("streams_needing_tags: '{}'".format(streams_needing_tags))
        # Mark this file to be added to the pending tasks
        data['add_file_to_pending_tasks'] = True
        logger.info("File '{}' should be added to task list. File has audio streams without language tags or have language tags of undefined.".format(abspath))
    else:
        logger.info("File '{}' should not be added to the task list.  All audio streams have language tags.".format(abspath))

    return data

def tag_streams(astreams, vid_file, settings):
    # create temporary work space in cache
    src_file_hash = hashlib.md5(os.path.basename(vid_file).encode('utf8')).hexdigest()
    tmp_dir = os.path.join('/tmp/unmanic/', '{}'.format(src_file_hash))
    dir=Path(tmp_dir)
    dir.mkdir(parents=True, exist_ok=True)

    # initialize return array of language metadata tags
    tag_args = []

    # for each audio stream needing a tag, create video file with that single audio stream
    for astream, _ in enumerate(astreams):
        sfx = os.path.splitext(os.path.basename(vid_file))[1]
        temp_sfx = '.mkv'
        output_file = tmp_dir + '/' + str(os.path.splitext(os.path.basename(vid_file))[0]) + '.' + str(astream) + temp_sfx
        command = ['ffmpeg', '-hide_banner', '-loglevel', 'info', '-i', str(vid_file), '-strict', '-2', '-max_muxing_queue_size', '9999', '-map', '0:v:0', '-map', '0:a:'+str(astream), '-map_metadata', '-1', '-c', 'copy', '-y', output_file]
        logger.debug(f"tag_streams output_file: {output_file}")
        logger.debug(f"command: {command}")

        try:
            result = subprocess.run(command, shell=False, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            reason = e.stderr.decode()
            logger.error("Can not create output for audio stream '{}' of file '{}', so skipping stream".format(astream, vid_file))
            continue
        except OSError as e:
            reason = e.stderr.decode()
            logger.error(f"OSError: {reason}, skipping stream")
            continue
        else:
            logger.debug("temp video file to detect language in: '{}".format(output_file))

        lang_tag = detect_language(output_file, tmp_dir, settings)
        if lang_tag:
            lang_tag = iso639.Language.from_part1(lang_tag).part2b
            tag_args += ["-metadata:s:a:"+str(astream), 'language='+lang_tag]
        else:
            logger.error("Language not successfully identified for audio stream '{}' of file '{}', so skipping stream".format(astream, vid_file))

    for f in glob.glob(tmp_dir + "/*.wav"):
        os.remove(f)
    for f in glob.glob(tmp_dir + '/*' + temp_sfx):
        os.remove(f)

    shutil.rmtree(dir, ignore_errors=True)
    return tag_args

def get_model():
    model_order = ['base', 'small', 'medium', 'turbo', 'large']
    model_index = 3
    model = model_order[model_index]
    model_too_big = True
    device = 'cuda'
    while model_too_big:
        try:
            whisper.load_model(model, device='cuda')
        except torch.OutOfMemoryError:
            model_index -= 1
            model_too_big = True
        except RuntimeError:
            model_index = -1
            model_too_big = False
        else:
            model_too_big = False
        finally:
            if model_index == -1:
                logger.error(f"Insufficient GPU resources to run whisper, switching to CPU")
                device = 'cpu'
                model = 'medium'
                model_too_big = False
            else:
                if model_too_big == True:
                    model = model_order[model_index]
                    logger.info(f"model {model_order[model_index + 1]} too big, trying model {model}")
            torch.cuda.empty_cache()
    logger.info(f"model = {model}, device = {device}")
    return model, device

def detect_language(video_file, tmp_dir, settings):
    # Get multilingual process setting
    process_as_multilingual_audio_file = settings.get_setting("process_as_multilingual_audio_file")

    # Load Whisper model
    model_name, device = get_model()
    model = whisper.load_model(model_name, device)
    logger.debug("video_file: '{}'; tmp_dir: '{}'".format(video_file, tmp_dir))

    # Load video and get duration
    video = VideoFileClip(video_file)
    duration = video.duration

    # Define subclip to start 10 minutes into video and end 7 minutes before end
    video = video.subclipped(600, duration-430)
    duration = video.duration - 30

    if duration < 690:
        logger.info("File '{}' too short to process (<11.5 minutes), skipping".format(video_file))
        return None

    # Sample 6 random spots from the trimmed video
    sample_times = sorted(random.sample(range(int(duration)), 6))
    logger.debug("sample_times: '{}'".format(sample_times))

    detected_languages = []

    # Analyze the audio at each of the sample times
    for sample_time in sample_times:

        # Extract 30 seconds of audio clip from the video
        audio_clip = video.subclipped(sample_time, sample_time + 30)
        audio_file = f"{tmp_dir}/sample_{str(sample_time)}.wav"
        audio_clip.audio.write_audiofile(audio_file, codec='pcm_s16le')
        logger.debug("audio_file: '{}'".format(audio_file))

        # Run Whisper to detect language from the audio sample
        n_mels = model.dims.n_mels
        mel = whisper.log_mel_spectrogram(audio_file, n_mels=n_mels).to(model.device)
        _, probs = model.detect_language(mel)
        lang = max(probs, key=probs.get)
        detected_languages.append(lang)
        logger.debug(f"lang {lang} detected in sample {sample_time}")

    # try to force removal of resources left in GPU
    # move model to CPU
    # delete model
    # empty cuda cache
    try:
        model.cpu()
        del model
    except:
        pass
    torch.cuda.empty_cache()

    # if processing as multilingual file, just return language with maximum number of detected ocurrences
    if process_as_multilingual_audio_file:
        lang_ctr = {}
        for lang in set(detected_languages):
            lang_ctr[lang]=detected_languages.count(lang)
        lang_ctr = dict(sorted(lang_ctr.items(), key=lambda item: item[1], reverse=True))
        return next(iter(lang_ctr.keys()))

    # Check if at least 4 of the 6 samples are the same
    if len(set(detected_languages)) == 1:
        return detected_languages[0]
    elif len(set(detected_languages)) == 2 or len(set(detected_languages)) == 3:
        for lang in set(detected_languages):
            if detected_languages.count(lang) >= 4:
                return lang
    return None

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

    # Get the input and output file paths
    abspath = data.get('file_in')
    outfile = data.get('file_out')

    logger.debug(f"worker process output file: {outfile}")

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

    # Find audio streams that need language tags, if any, and add metadata to set the language tags
    streams_needing_tags = get_audio_streams(probe_streams)
    if streams_needing_tags:

        tag_args = tag_streams(streams_needing_tags, abspath, settings)

        if tag_args:
            ffmpeg_args = ['-hide_banner', '-loglevel', 'info', '-i', str(abspath), '-max_muxing_queue_size', '9999', '-map', '0', '-c', 'copy'] + tag_args + [ '-y', outfile]

            # Apply ffmpeg args to command
            data['exec_command'] = ['ffmpeg']
            data['exec_command'] += ffmpeg_args

            logger.debug("command: '{}'".format(data['exec_command']))

            # Set the parser
            parser = Parser(logger)
            parser.set_probe(probe_data)
            data['command_progress_parser'] = parser.parse_progress
        else:
            logger.info("File not processed - no streams identified or duration too short")

    return data

