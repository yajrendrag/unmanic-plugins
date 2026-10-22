---

Automatically detects and corrects audio/video lip sync (A/V sync) issues
using **SyncNet** with **S3FD** face detection. When a significant offset is
found, the plugin applies an `ffmpeg -itsoffset` correction to shift the audio
stream without re-encoding.

### How it works

1. **Library scan** &ndash; files with both video and audio streams that have
   not yet been analysed are queued for processing.
2. **Pass 1 &ndash; SyncNet analysis** &ndash; the plugin extracts face tracks
   via S3FD and evaluates audio-visual synchronisation with SyncNet. The result
   is a frame offset and a confidence score.
3. **Pass 2 &ndash; ffmpeg correction** &ndash; if the offset exceeds the
   configured minimum threshold and the confidence is high enough, an
   `ffmpeg -itsoffset` command remuxes the file with the corrected timing.
   Video, audio, subtitles and attachments are stream-copied (no re-encoding).

### Requirements

- **GPU recommended** &ndash; SyncNet runs on CUDA when available, falls back
  to CPU.
- **Model weights** &ndash; downloaded automatically at container startup from
  HuggingFace (`lithiumice/syncnet`). Set `HF_TOKEN` as an environment variable
  in your unmanic compose file/run command if the repo requires authentication.

### Settings

##### <span style="color:DeepSkyBlue">Number of sample segments</span>
How many evenly-spaced segments to extract and analyse (the first and last 10%
of the video are skipped to avoid credits). More segments give more reliable
results but take longer. Default: **6**.

##### <span style="color:DeepSkyBlue">Segment duration (seconds)</span>
Length of each sample segment. Must be long enough for SyncNet to build a face
track (minimum ~3 seconds of a visible face). Default: **25 seconds**.

##### <span style="color:DeepSkyBlue">Minimum confident segments</span>
How many segments must individually exceed the confidence threshold before a
correction is applied. Only offsets from confident segments contribute to the
final median offset. Default: **2**.

##### <span style="color:DeepSkyBlue">Minimum offset (ms)</span>
Offsets smaller than this value are considered acceptable and no correction is
applied. Default: **40 ms** (~1 frame at 25 fps).

##### <span style="color:DeepSkyBlue">Maximum offset (ms)</span>
Safety cap &ndash; offsets larger than this are assumed to be false positives
and are ignored. Default: **5000 ms**.

##### <span style="color:DeepSkyBlue">Confidence threshold</span>
Minimum SyncNet confidence score required before applying a correction. Higher
values are more conservative. Default: **3.0**.
