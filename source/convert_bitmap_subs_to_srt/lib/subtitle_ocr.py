#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    OCR decoded bitmap subtitle events with Tesseract and write SRT files.

    Takes the events produced by bitmap_subs. Each image is written as a black on
    white PGM file, and batches of images are passed to Tesseract as a file list so
    the language model only loads once per batch.
"""
import math
import os
import re
import subprocess
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

TESSERACT_BIN = 'tesseract'

# Page segmentation mode 6: a single uniform block of text
TESSERACT_PSM = '6'

# White border added around each image, Tesseract struggles with text touching the edge
IMAGE_PADDING = 12

# Images per Tesseract process. Batches are sized to give roughly BATCHES_PER_WORKER
# progress updates per worker, within these limits.
MIN_BATCH_SIZE = 10
MAX_BATCH_SIZE = 100
BATCHES_PER_WORKER = 8

# Longest a subtitle may stay on screen when the stream gives no end time
DEFAULT_MAX_DURATION_MS = 10000

# Consecutive events with the same text closer than this are merged
MERGE_GAP_MS = 100

# Stream language tags (ISO 639-2 B/T and 639-1) -> Tesseract language codes
LANGUAGE_MAP = {
    'en': 'eng', 'eng': 'eng',
    'de': 'deu', 'deu': 'deu', 'ger': 'deu',
    'fr': 'fra', 'fra': 'fra', 'fre': 'fra',
    'es': 'spa', 'spa': 'spa',
    'it': 'ita', 'ita': 'ita',
    'pt': 'por', 'por': 'por',
    'nl': 'nld', 'nld': 'nld', 'dut': 'nld',
    'pl': 'pol', 'pol': 'pol',
    'ru': 'rus', 'rus': 'rus',
    'ja': 'jpn', 'jpn': 'jpn',
    'zh': 'chi_sim', 'chi': 'chi_sim', 'zho': 'chi_sim',
    'ko': 'kor', 'kor': 'kor',
    'ar': 'ara', 'ara': 'ara',
}

# Latin script languages where a '|' is always a misread 'I'
LATIN_LANGUAGES = {'eng', 'deu', 'fra', 'spa', 'ita', 'por', 'nld', 'pol'}


class OcrError(Exception):
    pass


class OcrCancelled(Exception):
    pass


class _ProcessGroup:
    """
    Tracks the running Tesseract processes so they can all be stopped on cancel.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._procs = set()
        self._stopped = False

    def run(self, args, timeout):
        env = dict(os.environ, OMP_THREAD_LIMIT='1')
        with self._lock:
            if self._stopped:
                raise OcrCancelled()
            proc = subprocess.Popen([TESSERACT_BIN] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, env=env)
            self._procs.add(proc)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise
        finally:
            with self._lock:
                self._procs.discard(proc)
        if self._stopped:
            raise OcrCancelled()
        if proc.returncode != 0:
            raise OcrError(f"tesseract failed: {stderr.strip()[-500:]}")
        return stdout

    def stop(self):
        with self._lock:
            self._stopped = True
            for proc in self._procs:
                try:
                    proc.kill()
                except OSError:
                    pass


def available_languages():
    """
    :return: Set of installed Tesseract language codes
    """
    result = subprocess.run([TESSERACT_BIN, '--list-langs'], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise OcrError(f"tesseract --list-langs failed: {result.stderr.strip()}")
    lines = result.stdout.strip().splitlines()
    # The first line is a header: 'List of available languages in "..." (N):'
    return {line.strip() for line in lines[1:] if line.strip()}


def resolve_languages(setting, stream_language, installed, fallback='eng'):
    """
    Work out the Tesseract '-l' value for a stream.

    :param setting: The plugin setting, e.g. 'auto', 'eng' or 'eng+fra'
    :param stream_language: The stream's language tag, may be empty
    :param installed: Set of installed Tesseract languages
    :param fallback: Language used when nothing else is usable
    :return: Tuple of (language string, list of requested languages that are not installed)
    """
    setting = (setting or '').strip().lower()
    if not setting or setting == 'auto':
        mapped = LANGUAGE_MAP.get((stream_language or '').strip().lower())
        requested = [mapped] if mapped else [fallback]
    else:
        requested = [lang.strip() for lang in setting.split('+') if lang.strip()]

    usable = [lang for lang in requested if lang in installed]
    missing = [lang for lang in requested if lang not in installed]
    if not usable:
        usable = [fallback]
    return '+'.join(usable), missing


def write_pgm(image, path):
    """
    Write a two-colour image as a black on white PGM file.

    :param image: Image dict from bitmap_subs
    :param path: Output path
    """
    pad = IMAGE_PADDING
    width = image['width'] + pad * 2
    blank_row = b'\xff' * width
    side = b'\xff' * pad
    lines = [blank_row] * pad
    for runs in image['rows']:
        row = side + b''.join((b'\x00' if value else b'\xff') * length for value, length in runs) + side
        # Rows can come up short or long if the source data was damaged
        row = row[:width].ljust(width, b'\xff')
        lines.append(row)
    lines.extend([blank_row] * pad)
    with open(path, 'wb') as f:
        f.write(b'P5\n%d %d\n255\n' % (width, len(lines)))
        f.write(b''.join(lines))


def _clean_text(text):
    lines = [line.strip() for line in text.splitlines()]
    return '\n'.join(line for line in lines if line)


def fix_common_errors(text, languages):
    """
    Fix Tesseract's usual misreads of a capital I in subtitle fonts.

    :param text: OCR text
    :param languages: Tesseract '-l' value
    """
    langs = set(languages.split('+'))
    if langs & LATIN_LANGUAGES:
        text = text.replace('|', 'I')
    if 'eng' in langs:
        # 'l' on its own is never an English word
        text = re.sub(r"(?<![\w'])l(?=[\s'.,!?]|$)", 'I', text)
    return text


def _ocr_batch(procs, paths, languages, list_path):
    """
    OCR a batch of images with a single Tesseract process.

    :return: List of texts, one per path
    """
    with open(list_path, 'w') as f:
        f.write('\n'.join(paths) + '\n')
    common = ['stdout', '-l', languages, '--psm', TESSERACT_PSM]
    output = procs.run([list_path] + common, timeout=30 + 10 * len(paths))
    # Tesseract ends each page's text with a form feed
    pages = output.split('\f')
    if len(pages) == len(paths) + 1:
        return [_clean_text(page) for page in pages[:-1]]

    # Page count did not line up, OCR the images one at a time instead
    return [_clean_text(procs.run([path] + common, timeout=60)) for path in paths]


def ocr_events(events, languages, work_dir, workers=None, progress_callback=None):
    """
    OCR every event.

    :param events: Events from bitmap_subs
    :param languages: Tesseract '-l' value
    :param work_dir: Directory for temporary image files
    :param workers: Number of Tesseract processes to run at once
    :param progress_callback: Called as progress_callback(images_done, images_total) after each batch.
                              Returning False stops the OCR and raises OcrCancelled.
    :return: List of texts, one per event
    """
    if workers is None:
        workers = max(1, min(4, (os.cpu_count() or 2) // 2))

    # One image per entry, events with several images are joined top to bottom
    entries = []
    for event_index, event in enumerate(events):
        for image_index, image in enumerate(event['images']):
            path = os.path.join(work_dir, f"ocr_{event_index:06d}_{image_index}.pgm")
            write_pgm(image, path)
            entries.append((event_index, image['y'], image['x'], path))

    batch_size = math.ceil(len(entries) / (workers * BATCHES_PER_WORKER)) if entries else MIN_BATCH_SIZE
    batch_size = max(MIN_BATCH_SIZE, min(MAX_BATCH_SIZE, batch_size))
    batches = [entries[i:i + batch_size] for i in range(0, len(entries), batch_size)]
    results = [None] * len(batches)

    # Batches are submitted as workers free up, so a cancel stops new batches straight away
    procs = _ProcessGroup()
    queued = list(range(len(batches)))
    running = {}
    images_done = 0
    pool = ThreadPoolExecutor(max_workers=workers)

    def submit_next():
        while queued and len(running) < workers:
            n = queued.pop(0)
            list_path = os.path.join(work_dir, f"ocr_list_{n}.txt")
            future = pool.submit(_ocr_batch, procs, [e[3] for e in batches[n]], languages, list_path)
            running[future] = n

    try:
        submit_next()
        while running:
            finished, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in finished:
                n = running.pop(future)
                results[n] = future.result()
                images_done += len(batches[n])
            if progress_callback is not None and progress_callback(images_done, len(entries)) is False:
                raise OcrCancelled()
            submit_next()
    except BaseException:
        # Stop the running Tesseract processes and drop the queued batches
        procs.stop()
        for future in running:
            future.cancel()
        raise
    finally:
        pool.shutdown(wait=True)
        for entry in entries:
            if os.path.exists(entry[3]):
                os.remove(entry[3])

    parts = [[] for _ in events]
    for batch, texts in zip(batches, results):
        for (event_index, y, x, path), text in zip(batch, texts):
            parts[event_index].append((y, x, text))

    return [fix_common_errors('\n'.join(text for _, _, text in sorted(p) if text), languages) for p in parts]


def _srt_time(ms):
    ms = max(0, int(round(ms)))
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def build_cues(events, texts, max_duration_ms=DEFAULT_MAX_DURATION_MS):
    """
    Turn events and their texts into timed cues.

    :return: List of (start_ms, end_ms, text)
    """
    order = sorted(range(len(events)), key=lambda i: events[i]['start'])
    cues = []
    for position, i in enumerate(order):
        start = events[i]['start']
        end = events[i]['end']
        next_start = events[order[position + 1]]['start'] if position + 1 < len(order) else None
        if end is None or end <= start:
            end = start + max_duration_ms
        if next_start is not None and end > next_start:
            end = next_start
        text = texts[i]
        if not text or end <= start:
            continue
        # PGS fades are several display sets showing the same text
        if cues and cues[-1][2] == text and start - cues[-1][1] <= MERGE_GAP_MS:
            cues[-1] = (cues[-1][0], end, text)
            continue
        cues.append((start, end, text))
    return cues


def write_srt(cues, path):
    """
    Write cues to an SRT file.

    :return: Number of cues written
    """
    with open(path, 'w', encoding='utf-8') as f:
        for number, (start, end, text) in enumerate(cues, 1):
            f.write(f"{number}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}\n\n")
    return len(cues)
