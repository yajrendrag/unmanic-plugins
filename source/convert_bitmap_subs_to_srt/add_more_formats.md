# Adding more bitmap subtitle formats

Each new format needs a decoder function in `lib/bitmap_subs.py` and an entry in its `DECODERS` table.
Nothing else changes: the stream detection, OCR, SRT writing, progress reporting, output location and metadata
tracking all work for any codec in that table.

Decoders run inside the helper process `lib/convert_stream.py`, not in Unmanic itself, so they must only use the
standard library and the other modules in `lib/`. Anything a decoder prints to stdout is read by the plugin, so log
to stderr instead of printing.

## What a decoder has to do

It takes `(file_in, stream, work_dir)` and returns a list of events:

```python
{'start': ms, 'end': ms or None,
 'images': [{'x', 'y', 'width', 'height', 'rows'}]}
```

- Each image is black-and-white: `rows` is a list of `(value, run_length)` runs per line, where 1 is text and 0 is
  background.
- An event can hold several images, for example a top and a bottom line. They're OCR'd separately and joined top to
  bottom.
- `end` can be `None`. The subtitle then ends when the next one starts, or after 10 seconds at most.

Most of the work is decoding the format's run-length data and deciding which colors are text. The existing
decoders have reusable pieces:

- `read_stream_packets()` gets raw packets and timestamps from any stream through ffprobe.
- `_binarize_pgs_rows()` picks text by brightness, for formats with a full palette.
- `_dvd_text_value()` picks the text color by shape, for formats without a usable palette.

## Formats

| codec_name | Source | Work needed |
|---|---|---|
| `dvb_subtitle` | TV recordings in TS files | The most work, about 200 lines. There are several segment types (page, region, color table, object, end) and 2/4/8-bit pixel data. The color table has brightness and transparency, so `_binarize_pgs_rows()` can be reused. It often has no end times, which is already handled. |
| `xsub` | DivX AVI files | Easy, about 80 lines. Timing is a text header in each packet, with a 4-color palette and run-length data similar to DVD's. |
| `dvd_subtitle` in MP4 | | Already works, since the codec name is the same. |
| `dvb_teletext`, `hdmv_text_subtitle`, ARIB | | These are text, not images, so they don't need OCR. ffmpeg can convert them to SRT directly, so they'd need a separate code path that skips `bitmap_subs`/`subtitle_ocr`. |

## Other steps for any new format

- **Test file:** make one to test with. For DVB, a broadcast recording is easiest. ffmpeg can also re-encode
  existing DVD subtitles to `dvbsub`, because it can convert image subtitles to other image formats, just not text
  to images.
- **Docs:** add the codec to the supported list in `description.md` and the docstring at the top of `bitmap_subs.py`.
  Add a changelog entry and bump the version.
- **Testing:** test on the live server, not with `--test-plugin`, and restart the container after code changes.
