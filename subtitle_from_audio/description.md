---

This plugin creates SRT subtitle files from a video file's audio stream using
[WhisperX](https://github.com/m-bain/whisperX) for speech-to-text transcription
with word-level forced alignment and optional speaker diarization.

##### Improvements over standard Whisper

- **VAD pre-segmentation** eliminates hallucinations from silence and background noise
- **Word-level forced alignment** via wav2vec2 provides precise per-word timestamps,
  eliminating subtitle timing drift
- **Batched inference** via faster-whisper (CTranslate2 backend) for faster processing
  and lower VRAM usage
- **Built-in speaker diarization** via pyannote.audio assigns speakers to words

##### Configuration

- **Whisper Model** -- select model size (tiny through large-v3); larger models are
  more accurate but require more VRAM
- **Compute Type** -- float16 for GPU, int8 for low VRAM or CPU, float32 for maximum
  precision
- **Device** -- CUDA (GPU) or CPU
- **Audio Language** -- language of the audio stream to select and transcribe
- **Fallback Behavior** -- when the configured language stream is not found: transcribe
  the first available stream, or translate it to English
- **Skip Commercials** -- skip chapters marked as commercials in MKV files
- **Speaker Diarization** -- enable speaker identification with configurable label
  formats (none, numbered, or em-dash for speaker changes)
- **Batch Size / Beam Size** -- tune for speed vs accuracy tradeoff
- **Subtitle Formatting** -- max characters per line, max/min subtitle duration
- **VAD Thresholds** -- fine-tune voice activity detection sensitivity

##### Reference
Uses WhisperX Speech Recognition

https://github.com/m-bain/whisperX

##### Requirements

- NVIDIA GPU with CUDA support recommended (CPU mode available but slow)
- HuggingFace token (`HF_TOKEN` environment variable) required for speaker diarization
