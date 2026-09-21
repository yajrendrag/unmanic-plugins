#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    Convert one bitmap subtitle stream to an SRT file.

    Run by the plugin as a separate process so that Unmanic can track it (and the
    Tesseract processes it starts) for elapsed time, CPU/memory stats, pause and
    terminate.

    Usage:
        convert_stream.py '<json arguments>'

    JSON arguments:
        file_in    - Path to the media file
        stream     - Stream info dict ('index', 'subtitle_index', 'codec_name')
        languages  - Tesseract '-l' value
        work_dir   - Directory for temporary files
        output     - Path of the SRT file to write

    Output on stdout, one line each:
        PROGRESS <images_done> <images_total>
        RESULT <number of subtitles written>

    Errors are written to stderr and the exit code is non-zero.
"""
import json
import os
import signal
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bitmap_subs  # noqa: E402
import subtitle_ocr  # noqa: E402


def _terminate(signum, frame):
    # Raising here unwinds ocr_events(), which kills the running Tesseract processes
    raise SystemExit(128 + signum)


def main():
    signal.signal(signal.SIGTERM, _terminate)
    args = json.loads(sys.argv[1])

    def report(images_done, images_total):
        print(f"PROGRESS {images_done} {images_total}", flush=True)
        return True

    report(0, 1)
    events = bitmap_subs.stream_events(args['file_in'], args['stream'], args['work_dir'])
    if not events:
        print("RESULT 0", flush=True)
        return 0

    texts = subtitle_ocr.ocr_events(events, args['languages'], args['work_dir'], progress_callback=report)
    cue_count = subtitle_ocr.write_srt(subtitle_ocr.build_cues(events, texts), args['output'])
    print(f"RESULT {cue_count}", flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
