#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Written by:               yajrendrag <yajdude@gmail.com>
    Date:                     1 March 2026

    Copyright:
        Unmanic plugin code Copyright (C) 2026 Jay Gardner

        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

"""
import gc
import glob
import json
import logging
import os
import shutil
import subprocess
import tempfile
import warnings

from unmanic.libs.unplugins.settings import PluginSettings

from subtitle_from_audio.lib.ffmpeg import Probe

# Suppress specific warnings
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

# Configure plugin logger
logger = logging.getLogger("Unmanic.Plugin.subtitle_from_audio")


class Settings(PluginSettings):
    settings = {
        "whisper_model":        "large-v2",
        "compute_type":         "float16",
        "device":               "cuda",
        "audio_language":       "en",
        "fallback_no_lang_stream": "transcribe",
        "skip_commercials":     True,
        "enable_diarization":   True,
        "speaker_label_format": "none",
        "batch_size":           16,
        "beam_size":            5,
        "max_chars_per_line":   42,
        "max_subtitle_duration": 7,
        "min_subtitle_duration": 1,
        "vad_onset":            0.500,
        "vad_offset":           0.363,
    }

    def __init__(self, *args, **kwargs):
        super(Settings, self).__init__(*args, **kwargs)
        self.form_settings = {
            "whisper_model":        self.__set_whisper_model_form_settings(),
            "compute_type":         self.__set_compute_type_form_settings(),
            "device":               self.__set_device_form_settings(),
            "audio_language":       self.__set_audio_language_form_settings(),
            "fallback_no_lang_stream": self.__set_fallback_form_settings(),
            "skip_commercials":     self.__set_skip_commercials_form_settings(),
            "enable_diarization":   self.__set_enable_diarization_form_settings(),
            "speaker_label_format": self.__set_speaker_label_format_form_settings(),
            "batch_size":           self.__set_batch_size_form_settings(),
            "beam_size":            self.__set_beam_size_form_settings(),
            "max_chars_per_line":   self.__set_max_chars_per_line_form_settings(),
            "max_subtitle_duration": self.__set_max_subtitle_duration_form_settings(),
            "min_subtitle_duration": self.__set_min_subtitle_duration_form_settings(),
            "vad_onset":            self.__set_vad_onset_form_settings(),
            "vad_offset":           self.__set_vad_offset_form_settings(),
        }

    def __set_whisper_model_form_settings(self):
        return {
            "label":       "Whisper Model",
            "description": "Model size — larger models are more accurate but require more VRAM.",
            "input_type":  "select",
            "select_options": [
                {"value": "tiny",     "label": "tiny (~1 GB VRAM)"},
                {"value": "base",     "label": "base (~1 GB VRAM)"},
                {"value": "small",    "label": "small (~2 GB VRAM)"},
                {"value": "medium",   "label": "medium (~5 GB VRAM)"},
                {"value": "large-v2", "label": "large-v2 (~10 GB VRAM)"},
                {"value": "large-v3", "label": "large-v3 (~10 GB VRAM)"},
                {"value": "turbo",    "label": "turbo (~6 GB VRAM, faster)"},
            ],
        }

    def __set_compute_type_form_settings(self):
        return {
            "label":       "Compute Type",
            "description": "float16 for GPU, int8 for low VRAM or CPU, float32 for max precision.",
            "input_type":  "select",
            "select_options": [
                {"value": "float16", "label": "float16 (GPU default)"},
                {"value": "int8",    "label": "int8 (low VRAM / CPU)"},
                {"value": "float32", "label": "float32 (max precision)"},
            ],
        }

    def __set_device_form_settings(self):
        return {
            "label":       "Device",
            "description": "CUDA (GPU) or CPU. CPU will be very slow.",
            "input_type":  "select",
            "select_options": [
                {"value": "cuda", "label": "CUDA (GPU)"},
                {"value": "cpu",  "label": "CPU"},
            ],
        }

    def __set_audio_language_form_settings(self):
        return {
            "label":       "Audio Language",
            "description": "Language of the audio stream to select and transcribe (ISO 639-1 code).",
            "input_type":  "select",
            "select_options": [
                {"value": "en", "label": "English"},
                {"value": "es", "label": "Spanish"},
                {"value": "fr", "label": "French"},
                {"value": "de", "label": "German"},
                {"value": "it", "label": "Italian"},
                {"value": "pt", "label": "Portuguese"},
                {"value": "ja", "label": "Japanese"},
                {"value": "ko", "label": "Korean"},
                {"value": "zh", "label": "Chinese"},
                {"value": "ru", "label": "Russian"},
                {"value": "ar", "label": "Arabic"},
                {"value": "hi", "label": "Hindi"},
                {"value": "nl", "label": "Dutch"},
                {"value": "sv", "label": "Swedish"},
                {"value": "pl", "label": "Polish"},
            ],
        }

    def __set_fallback_form_settings(self):
        return {
            "label":       "Fallback When Language Stream Missing",
            "description": "What to do when the configured language stream is not found.",
            "input_type":  "select",
            "select_options": [
                {"value": "transcribe", "label": "Transcribe (auto-detect language)"},
                {"value": "translate",  "label": "Translate to English"},
            ],
        }

    def __set_skip_commercials_form_settings(self):
        return {
            "label":       "Skip Commercial Chapters",
            "description": "Skip chapters marked as commercials in MKV files.",
            "input_type":  "checkbox",
        }

    def __set_enable_diarization_form_settings(self):
        return {
            "label":       "Enable Speaker Diarization",
            "description": "Identify and label different speakers. Requires HF_TOKEN environment variable.",
            "input_type":  "checkbox",
        }

    def __set_speaker_label_format_form_settings(self):
        return {
            "label":       "Speaker Label Format",
            "sub_setting": True,
            "description": "How to display speaker labels in subtitles (only when diarization is enabled).",
            "input_type":  "select",
            "select_options": [
                {"value": "none",     "label": "None (no visible labels)"},
                {"value": "numbered", "label": "Numbered ([Speaker 1]:)"},
                {"value": "em_dash",  "label": "Em-dash (— for speaker changes)"},
            ],
        }

    def __set_batch_size_form_settings(self):
        return {
            "label":       "Batch Size",
            "description": "WhisperX batch size. Lower values use less VRAM.",
            "input_type":  "slider",
            "slider_options": {
                "min": 1,
                "max": 64,
                "step": 1,
            },
        }

    def __set_beam_size_form_settings(self):
        return {
            "label":       "Beam Size",
            "description": "Beam search size. Higher values are more accurate but slower.",
            "input_type":  "slider",
            "slider_options": {
                "min": 1,
                "max": 20,
                "step": 1,
            },
        }

    def __set_max_chars_per_line_form_settings(self):
        return {
            "label":       "Max Characters Per Line",
            "description": "Maximum number of characters per subtitle line.",
            "input_type":  "slider",
            "slider_options": {
                "min": 20,
                "max": 80,
                "step": 1,
            },
        }

    def __set_max_subtitle_duration_form_settings(self):
        return {
            "label":       "Max Subtitle Duration (seconds)",
            "description": "Maximum seconds a single subtitle stays on screen.",
            "input_type":  "slider",
            "slider_options": {
                "min": 3,
                "max": 15,
                "step": 1,
            },
        }

    def __set_min_subtitle_duration_form_settings(self):
        return {
            "label":       "Min Subtitle Duration (seconds)",
            "description": "Minimum seconds for subtitle display.",
            "input_type":  "slider",
            "slider_options": {
                "min": 0.5,
                "max": 5,
                "step": 0.5,
            },
        }

    def __set_vad_onset_form_settings(self):
        return {
            "label":       "VAD Onset Threshold",
            "description": "Voice activity detection onset threshold (0.0-1.0).",
            "input_type":  "slider",
            "slider_options": {
                "min": 0.0,
                "max": 1.0,
                "step": 0.01,
            },
        }

    def __set_vad_offset_form_settings(self):
        return {
            "label":       "VAD Offset Threshold",
            "description": "Voice activity detection offset threshold (0.0-1.0).",
            "input_type":  "slider",
            "slider_options": {
                "min": 0.0,
                "max": 1.0,
                "step": 0.001,
            },
        }


def srt_already_created(original_file_path):
    """
    Check if an SRT file already exists for the given source file.
    Looks for <basename>.srt and <basename>.<lang>.srt patterns.
    """
    import langcodes

    directory = os.path.dirname(original_file_path)
    basename = os.path.splitext(os.path.basename(original_file_path))[0]

    # Check for <basename>.srt
    simple_srt = os.path.join(directory, basename + '.srt')
    if os.path.isfile(simple_srt):
        logger.info("SRT already exists: '{}'".format(simple_srt))
        return True

    # Check for <basename>.<lang>.srt patterns
    pattern = os.path.join(directory, basename + '.*.srt')
    for match in glob.glob(pattern):
        # Extract the middle part between basename and .srt
        match_basename = os.path.basename(match)
        middle = match_basename[len(basename) + 1:-4]  # strip basename. and .srt
        try:
            langcodes.find(middle)
            logger.info("SRT already exists with language tag: '{}'".format(match))
            return True
        except LookupError:
            continue

    return False


def on_library_management_file_test(data, **kwargs):
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
            return
    elif not probe.file(abspath):
        return

    # Set file probe to shared info for subsequent file test runners
    if 'shared_info' not in data:
        data['shared_info'] = {}
    data['shared_info']['ffprobe'] = probe.get_probe()

    # Check if SRT already exists
    if not srt_already_created(abspath):
        data['add_file_to_pending_tasks'] = True
        logger.info("File '{}' added to task list — no SRT exists.".format(abspath))
    else:
        logger.info("File '{}' skipped — SRT already exists.".format(abspath))

    return data


def get_commercial_chapters(file_path):
    """Extract chapter information and identify commercial breaks."""
    logger.info("Checking for commercial chapters...")
    abs_path = os.path.abspath(file_path)
    cmd = [
        'ffprobe',
        '-i', abs_path,
        '-print_format', 'json',
        '-show_chapters',
        '-loglevel', 'error',
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        commercial_segments = []
        if 'chapters' in data:
            for chapter in data['chapters']:
                title = chapter.get('tags', {}).get('title', '')
                if 'commercial' in title.lower():
                    start_time = float(chapter['start_time'])
                    end_time = float(chapter['end_time'])
                    commercial_segments.append({
                        'start': start_time,
                        'end':   end_time,
                        'title': title,
                    })
                    logger.info("  Found commercial: '{}' ({:.1f}s - {:.1f}s)".format(title, start_time, end_time))
        if commercial_segments:
            logger.info("Found {} commercial chapter(s)".format(len(commercial_segments)))
        else:
            logger.info("No commercial chapters found")
        return commercial_segments
    except subprocess.CalledProcessError as e:
        logger.error("Could not read chapters: {}".format(e.stderr))
        return []
    except json.JSONDecodeError:
        logger.error("Could not parse chapter data")
        return []


def is_in_commercial(time_sec, commercial_segments):
    """Check if a given time falls within a commercial segment."""
    for seg in commercial_segments:
        if seg['start'] <= time_sec <= seg['end']:
            return True
    return False


def _find_audio_stream_index(file_path, language):
    """
    Use ffprobe to find the first audio stream matching the given language.
    Returns the absolute stream index or None if not found.
    """
    # Map short language codes to ISO 639-2/B (3-letter) for ffprobe matching
    lang_map = {
        'en': 'eng', 'es': 'spa', 'fr': 'fre', 'de': 'ger', 'it': 'ita',
        'pt': 'por', 'ja': 'jpn', 'ko': 'kor', 'zh': 'chi', 'ru': 'rus',
        'ar': 'ara', 'hi': 'hin', 'nl': 'dut', 'sv': 'swe', 'pl': 'pol',
    }
    lang_3 = lang_map.get(language, language)

    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'stream=index,codec_type:stream_tags=language',
        '-of', 'json',
        os.path.abspath(file_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        for stream in data.get('streams', []):
            if stream.get('codec_type') != 'audio':
                continue
            stream_lang = stream.get('tags', {}).get('language', '')
            if stream_lang == lang_3:
                return stream['index'], lang_3
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
        pass
    return None, lang_3


def extract_audio(file_path, output_audio_path, language, fallback):
    """
    Extract audio stream from file to WAV format.
    Probes for the first audio stream matching the configured language.
    Falls back to the first audio stream if not found.
    Returns the task type ('transcribe' or 'translate') and whether language was found.
    """
    logger.info("Extracting audio from {}...".format(file_path))
    abs_path = os.path.abspath(file_path)

    stream_index, lang_3 = _find_audio_stream_index(file_path, language)

    if stream_index is not None:
        map_arg = '0:{}'.format(stream_index)
        logger.info("Found audio stream index {} with language '{}'.".format(stream_index, lang_3))
    else:
        logger.info("No audio stream with language '{}' found, using first audio stream (fallback='{}').".format(
            lang_3, fallback))

    # Build ffmpeg command
    if stream_index is not None:
        cmd = [
            'ffmpeg',
            '-fflags', '+genpts',
            '-i', abs_path,
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            '-avoid_negative_ts', 'make_zero',
            '-map', map_arg,
            '-y',
            output_audio_path,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("Audio extraction complete (language: {}).".format(lang_3))
            return 'transcribe', True
        except subprocess.CalledProcessError as e:
            logger.error("Failed to extract language-matched stream: {}".format(e.stderr))
            # Fall through to fallback below

    # Fallback: use first audio stream
    cmd_fallback = [
        'ffmpeg',
        '-fflags', '+genpts',
        '-i', abs_path,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-avoid_negative_ts', 'make_zero',
        '-map', '0:a:0',
        '-y',
        output_audio_path,
    ]
    try:
        subprocess.run(cmd_fallback, check=True, capture_output=True, text=True)
        logger.info("Audio extraction complete (first audio stream, fallback='{}').".format(fallback))
        return fallback, False
    except subprocess.CalledProcessError as e2:
        logger.error("Failed to extract audio: {}".format(e2.stderr))
        raise


def set_model(settings):
    """
    Try loading the configured model on CUDA with VRAM fallback.
    Returns (model_name, compute_type, device).
    """
    import torch
    import whisperx

    model_name = settings.get_setting('whisper_model')
    compute_type = settings.get_setting('compute_type')
    device = settings.get_setting('device')
    batch_size = settings.get_setting('batch_size')

    model_order = ['tiny', 'base', 'small', 'medium', 'turbo', 'large-v2', 'large-v3']
    try:
        model_index = model_order.index(model_name)
    except ValueError:
        model_index = len(model_order) - 1
        model_name = model_order[model_index]

    if device == 'cuda':
        while model_index >= 0:
            try:
                test_model = whisperx.load_model(
                    model_order[model_index], device='cuda',
                    compute_type=compute_type,
                )
                del test_model
                gc.collect()
                torch.cuda.empty_cache()
                model_name = model_order[model_index]
                logger.info("Model '{}' fits in VRAM.".format(model_name))
                return model_name, compute_type, device
            except (torch.cuda.OutOfMemoryError, RuntimeError):
                logger.info("Model '{}' too large for VRAM, trying smaller...".format(model_order[model_index]))
                model_index -= 1
                gc.collect()
                torch.cuda.empty_cache()

        # All CUDA attempts failed — fall back to CPU
        logger.error("Insufficient GPU resources, switching to CPU with medium model.")
        return 'medium', 'int8', 'cpu'
    else:
        return model_name, compute_type, device


def format_timestamp(seconds):
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return "{:02d}:{:02d}:{:02d},{:03d}".format(hours, minutes, secs, millis)


def split_subtitle_lines(text, max_chars_per_line=42):
    """Split subtitle text into max 2 lines with reasonable word breaks."""
    words = text.split()
    if len(text) <= max_chars_per_line:
        return text

    mid_point = len(text) // 2
    best_split = 0
    min_diff = float('inf')

    current_len = 0
    for i, word in enumerate(words):
        current_len += len(word) + (1 if i > 0 else 0)
        diff = abs(current_len - mid_point)
        if diff < min_diff and current_len <= max_chars_per_line * 1.5:
            min_diff = diff
            best_split = i + 1

    if best_split == 0:
        best_split = len(words) // 2

    line1 = ' '.join(words[:best_split])
    line2 = ' '.join(words[best_split:])
    return "{}\n{}".format(line1, line2)


def build_subtitle_cues(word_segments, speaker_map, settings, commercial_segments):
    """
    Build subtitle cues from word-level aligned data.

    Each word in word_segments has: {'word': str, 'start': float, 'end': float, 'speaker': str (optional)}

    Returns a list of cue dicts: {'start': float, 'end': float, 'text': str, 'speaker': str or None}
    """
    max_chars = settings.get_setting('max_chars_per_line')
    max_duration = settings.get_setting('max_subtitle_duration')
    min_duration = settings.get_setting('min_subtitle_duration')
    skip_commercials = settings.get_setting('skip_commercials')
    enable_diarization = settings.get_setting('enable_diarization')
    label_format = settings.get_setting('speaker_label_format')
    max_chars_total = max_chars * 2  # 2 lines

    # Sentence-ending punctuation
    sentence_end = {'.', '!', '?'}
    clause_end = {',', ';', ':'}

    cues = []
    current_words = []
    current_text = ""
    current_start = None
    current_speaker = None

    def flush_cue():
        nonlocal current_words, current_text, current_start, current_speaker
        if not current_words:
            return
        cue_start = current_words[0].get('start', current_start)
        cue_end = current_words[-1].get('end', cue_start + min_duration)

        # Enforce minimum duration
        if cue_end - cue_start < min_duration:
            cue_end = cue_start + min_duration

        text = current_text.strip()

        # Skip if in commercial
        if skip_commercials and commercial_segments:
            mid_time = (cue_start + cue_end) / 2
            if is_in_commercial(mid_time, commercial_segments):
                current_words = []
                current_text = ""
                current_start = None
                current_speaker = None
                return

        # Apply speaker labels
        display_text = text
        if enable_diarization and speaker_map and label_format != 'none':
            speaker = current_words[0].get('speaker', current_speaker)
            if label_format == 'numbered' and speaker:
                # Map SPEAKER_XX to a simple number
                speaker_num = speaker_map.get(speaker, speaker)
                display_text = "[Speaker {}]: {}".format(speaker_num, text)
            elif label_format == 'em_dash':
                # Add em-dash if speaker changed from previous cue
                if cues and speaker:
                    prev_speaker = cues[-1].get('_speaker')
                    if prev_speaker and prev_speaker != speaker:
                        display_text = "\u2014 {}".format(text)

            cues.append({
                'start':    cue_start,
                'end':      cue_end,
                'text':     display_text,
                '_speaker': current_words[0].get('speaker', current_speaker),
            })
        else:
            cues.append({
                'start':    cue_start,
                'end':      cue_end,
                'text':     display_text,
                '_speaker': None,
            })

        current_words = []
        current_text = ""
        current_start = None
        current_speaker = None

    for word_info in word_segments:
        word = word_info.get('word', '').strip()
        if not word:
            continue

        w_start = word_info.get('start')
        w_end = word_info.get('end')

        # Skip words without timestamps (alignment failure)
        if w_start is None or w_end is None:
            continue

        # Check if adding this word would exceed limits
        candidate_text = (current_text + " " + word).strip() if current_text else word
        candidate_duration = w_end - (current_words[0]['start'] if current_words else w_start)

        should_break = False
        break_reason = None

        if len(candidate_text) > max_chars_total:
            should_break = True
            break_reason = 'chars'
        elif candidate_duration > max_duration:
            should_break = True
            break_reason = 'duration'

        if should_break and current_words:
            flush_cue()

        # Start new cue if needed
        if not current_words:
            current_start = w_start

        current_words.append(word_info)
        current_text = (current_text + " " + word).strip() if current_text else word
        current_speaker = word_info.get('speaker', current_speaker)

        # Check for natural break points (sentence / clause boundaries)
        if current_words and len(current_text) >= max_chars * 0.6:
            last_char = word[-1] if word else ''
            if last_char in sentence_end:
                flush_cue()
            elif last_char in clause_end and len(current_text) >= max_chars:
                flush_cue()

    # Flush remaining words
    flush_cue()

    # Ensure min_subtitle_duration doesn't push past next cue's start
    for i in range(len(cues) - 1):
        if cues[i]['end'] > cues[i + 1]['start']:
            cues[i]['end'] = cues[i + 1]['start']

    return cues


def generate_srt(cues, output_srt_path, max_chars_per_line):
    """Write subtitle cues to an SRT file."""
    logger.info("Generating SRT file: {}".format(output_srt_path))
    with open(output_srt_path, 'w', encoding='utf-8') as f:
        for idx, cue in enumerate(cues, start=1):
            start_ts = format_timestamp(cue['start'])
            end_ts = format_timestamp(cue['end'])
            text = split_subtitle_lines(cue['text'], max_chars_per_line)
            f.write("{}\n".format(idx))
            f.write("{} --> {}\n".format(start_ts, end_ts))
            f.write("{}\n\n".format(text))
    logger.info("SRT saved with {} subtitles.".format(len(cues)))


def run_whisperx_pipeline(data, settings, file_path, output_srt_path, log_queue, prog_queue):
    """
    Main WhisperX pipeline: extract audio, transcribe, align, diarize, generate SRT.
    Runs inside a PluginChildProcess.
    """
    import torch
    import whisperx

    model_name = settings.get_setting('whisper_model')
    compute_type = settings.get_setting('compute_type')
    device = settings.get_setting('device')
    audio_language = settings.get_setting('audio_language')
    fallback = settings.get_setting('fallback_no_lang_stream')
    skip_commercials = settings.get_setting('skip_commercials')
    enable_diarization = settings.get_setting('enable_diarization')
    batch_size = settings.get_setting('batch_size')
    beam_size = settings.get_setting('beam_size')
    max_chars = settings.get_setting('max_chars_per_line')
    vad_onset = settings.get_setting('vad_onset')
    vad_offset = settings.get_setting('vad_offset')

    tmp_audio_path = None
    try:
        # Step 0: Detect commercial chapters
        log_queue.put("=== Detecting chapters ===")
        prog_queue.put(2)
        commercial_segments = []
        if skip_commercials:
            commercial_segments = get_commercial_chapters(file_path)

        # Step 1: Extract audio
        log_queue.put("=== Extracting audio ===")
        prog_queue.put(5)
        tmp_dir = '/tmp/unmanic'
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_fd, tmp_audio_path = tempfile.mkstemp(suffix='.wav', dir=tmp_dir)
        os.close(tmp_fd)
        task, lang_found = extract_audio(file_path, tmp_audio_path, audio_language, fallback)
        prog_queue.put(10)

        # Step 2: Determine model with VRAM fallback
        log_queue.put("=== Loading WhisperX model ===")
        model_name, compute_type, device = set_model(settings)
        log_queue.put("Using model='{}', compute='{}', device='{}'".format(model_name, compute_type, device))
        prog_queue.put(15)

        # Step 3: Transcribe
        log_queue.put("=== Transcribing audio ===")
        asr_options = {"beam_size": beam_size}
        vad_options = {"vad_onset": vad_onset, "vad_offset": vad_offset}
        model = whisperx.load_model(
            model_name,
            device=device,
            compute_type=compute_type,
            asr_options=asr_options,
            vad_options=vad_options,
        )

        audio = whisperx.load_audio(tmp_audio_path)

        transcribe_kwargs = {
            "batch_size": batch_size,
        }
        # Set language and task based on whether we found the target stream
        if lang_found:
            transcribe_kwargs["language"] = audio_language
        if task == 'translate':
            transcribe_kwargs["task"] = "translate"

        result = model.transcribe(audio, **transcribe_kwargs)
        detected_language = result.get("language", audio_language)
        log_queue.put("Transcription complete. Detected language: {}".format(detected_language))
        prog_queue.put(45)

        # Free transcription model
        del model
        gc.collect()
        if device == 'cuda':
            torch.cuda.empty_cache()

        # Step 4: Word-level alignment
        log_queue.put("=== Aligning words ===")
        align_language = audio_language if lang_found else detected_language
        try:
            model_a, metadata = whisperx.load_align_model(
                language_code=align_language,
                device=device,
            )
            result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                audio,
                device,
                return_char_alignments=False,
            )
            log_queue.put("Word alignment complete.")
        except Exception as e:
            log_queue.put("Word alignment failed ({}), using segment-level timestamps.".format(str(e)))
        finally:
            if 'model_a' in dir():
                del model_a
            gc.collect()
            if device == 'cuda':
                torch.cuda.empty_cache()
        prog_queue.put(65)

        # Step 5: Speaker diarization (optional)
        speaker_map = {}
        if enable_diarization:
            hf_token = os.environ.get('HF_TOKEN')
            if hf_token:
                log_queue.put("=== Performing speaker diarization ===")
                try:
                    from whisperx.diarize import DiarizationPipeline
                    diarize_model = DiarizationPipeline(
                        token=hf_token,
                        device=device,
                    )
                    diarize_segments = diarize_model(tmp_audio_path)
                    result = whisperx.assign_word_speakers(diarize_segments, result)

                    # Build speaker number map
                    speakers_seen = set()
                    for seg in result.get("segments", []):
                        for w in seg.get("words", []):
                            sp = w.get("speaker")
                            if sp:
                                speakers_seen.add(sp)
                    for i, sp in enumerate(sorted(speakers_seen), start=1):
                        speaker_map[sp] = i

                    log_queue.put("Diarization complete. Found {} speaker(s).".format(len(speakers_seen)))
                except Exception as e:
                    log_queue.put("Diarization failed ({}), continuing without speaker labels.".format(str(e)))
                finally:
                    if 'diarize_model' in dir():
                        del diarize_model
                    gc.collect()
                    if device == 'cuda':
                        torch.cuda.empty_cache()
            else:
                log_queue.put("HF_TOKEN not set, skipping diarization.")
        prog_queue.put(80)

        # Step 6: Collect all words from aligned segments
        log_queue.put("=== Building subtitles ===")
        all_words = []
        for seg in result.get("segments", []):
            words = seg.get("words", [])
            if words:
                all_words.extend(words)
            else:
                # Fallback: no word-level data, use segment as a single "word"
                all_words.append({
                    'word':    seg.get('text', '').strip(),
                    'start':   seg.get('start'),
                    'end':     seg.get('end'),
                    'speaker': seg.get('speaker'),
                })

        log_queue.put("Collected {} words from {} segments.".format(len(all_words), len(result.get("segments", []))))
        prog_queue.put(85)

        # Step 7: Build subtitle cues
        cues = build_subtitle_cues(all_words, speaker_map, settings, commercial_segments)
        log_queue.put("Built {} subtitle cues.".format(len(cues)))
        prog_queue.put(90)

        # Step 8: Write SRT
        generate_srt(cues, output_srt_path, max_chars)
        log_queue.put("SRT file created: {}".format(output_srt_path))
        prog_queue.put(100)

    finally:
        if tmp_audio_path and os.path.exists(tmp_audio_path):
            os.remove(tmp_audio_path)
            log_queue.put("Temporary audio file cleaned up.")


def on_worker_process(data, **kwargs):
    """
    Runner function - enables additional configured processing jobs during the worker stages of a task.

    The 'data' object argument includes:
        task_id                 - Integer, unique identifier of the task.
        worker_log              - Array, the log lines that are being tailed by the frontend. Can be left empty.
        library_id              - Number, the library that the current task is associated with.
        exec_command            - Array, a subprocess command that Unmanic should execute. Can be empty.
        current_command         - Array, shared list for updating the worker's "current command" text in the UI (last entry wins).
        command_progress_parser - Function, a function that Unmanic can use to parse the STDOUT of the command to collect progress stats. Can be empty.
        file_in                 - String, the source file to be processed by the command.
        file_out                - String, the destination that the command should output (may be the same as the file_in if necessary).
        original_file_path      - String, the absolute path to the original file.
        repeat                  - Boolean, should this runner be executed again once completed with the same variables.

    :param data:
    :return:

    """
    from unmanic.libs.unplugins.child_process import PluginChildProcess

    # Default to no FFMPEG command required
    data['exec_command'] = []
    data['repeat'] = False

    # Get the path to the file
    abspath = data.get('file_in')
    original_file_path = data.get('original_file_path')

    # Get file probe
    probe_data = Probe(logger, allowed_mimetypes=['video'])
    if not probe_data.file(abspath):
        logger.debug("Probe failed for '{}', skipping.".format(abspath))
        return data

    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    # Check if SRT already exists for the original file
    if srt_already_created(original_file_path):
        logger.info("SRT already exists for '{}', skipping.".format(original_file_path))
        return data

    # Determine output SRT path — write alongside the cache file_in
    output_srt_path = str(os.path.splitext(abspath)[0] + '.srt')

    # Run the WhisperX pipeline in a child process
    proc = PluginChildProcess(plugin_id="subtitle_from_audio", data=data)

    def child_work(log_queue, prog_queue):
        run_whisperx_pipeline(data, settings, abspath, output_srt_path, log_queue, prog_queue)

    success = proc.run(child_work)

    if success:
        logger.info("WhisperX pipeline completed successfully.")
    else:
        logger.error("WhisperX pipeline failed.")

    return data


def on_postprocessor_task_results(data, **kwargs):
    """
    Runner function - provides a means for additional postprocessor functions based on the task success.

    The 'data' object argument includes:
        library_id                      - The library that the current task is associated with.
        task_id                         - Integer, unique identifier of the task.
        task_type                       - String, "local" or "remote".
        final_cache_path                - The path to the final cache file that was then used as the source for all destination files.
        task_processing_success         - Boolean, did all task processes complete successfully.
        file_move_processes_success     - Boolean, did all postprocessor movement tasks complete successfully.
        destination_files               - List containing all file paths created by postprocessor file movements.
        source_data                     - Dictionary containing data pertaining to the original source file.
        start_time                      - Float, UNIX timestamp when the task began.
        finish_time                     - Float, UNIX timestamp when the task completed.

    :param data:
    :return:

    """
    if not data.get('task_processing_success'):
        return data

    if data.get('library_id'):
        settings = Settings(library_id=data.get('library_id'))
    else:
        settings = Settings()

    audio_language = settings.get_setting('audio_language')

    # Map 2-letter to 3-letter language codes for SRT naming
    lang_map = {
        'en': 'eng', 'es': 'spa', 'fr': 'fre', 'de': 'ger', 'it': 'ita',
        'pt': 'por', 'ja': 'jpn', 'ko': 'kor', 'zh': 'chi', 'ru': 'rus',
        'ar': 'ara', 'hi': 'hin', 'nl': 'dut', 'sv': 'swe', 'pl': 'pol',
    }
    lang_3 = lang_map.get(audio_language, audio_language)

    # Find the SRT generated during worker process
    # It should be alongside the source file (original_file_path) or the cache file
    abspath = data.get('source_data', {}).get('abspath', '')
    source_srt = os.path.splitext(abspath)[0] + '.srt'

    # Also check cache path (where worker wrote the SRT)
    cache_path = data.get('final_cache_path', '')
    cache_srt = os.path.splitext(cache_path)[0] + '.srt' if cache_path else ''

    # Determine which source SRT exists
    srt_source = None
    if cache_srt and os.path.isfile(cache_srt):
        srt_source = cache_srt
    elif os.path.isfile(source_srt):
        srt_source = source_srt

    if not srt_source:
        logger.error("No SRT file found to copy (checked '{}' and '{}').".format(cache_srt, source_srt))
        return data

    # Copy to destination alongside each destination file
    destination_files = data.get('destination_files', [])
    for destfile in destination_files:
        dest_base = os.path.splitext(destfile)[0]
        dest_srt = "{}.{}.srt".format(dest_base, lang_3)
        try:
            shutil.copy2(srt_source, dest_srt)
            logger.info("SRT copied to '{}'".format(dest_srt))
        except Exception as e:
            logger.error("Failed to copy SRT to '{}': {}".format(dest_srt, e))

    return data
