# Split Multi-Episode Files

Automatically detects and splits multi-episode video files (e.g., "S01E01-E03.mkv") into individual episode files using multiple detection techniques.

Split Multi-Episode works by assuming that the episodes in the multiepisode file are of a similar length and makes a determination of how many episodes are in the file.  It does this in several ways:

- it will simply count the number of episodes in the file baesd on the file name and divide that into the total duration of the file, OR
- it will use chapter markes if andy and if they have "Episode" titles
- it will calculate it from adding the TMDB run times  (& the added time from commerical chapters if the file has commercial chapter marks and if the file is significantly longer than the sum of all of the run times it gets from TMDB).

From this, it creates 10 minute windows around the nominal episode times that it calculated and then analyzes those windows to find the likely end of one episode / beginning of the next episode. Multiple detection techniques
are used and the more of them that cluster together at a certtain time in each 10 minute window, the higher likelihood of that being the episode split time.  It turns out that black frame detection seems to be the most accurate as a single
method of predicting the episode split time and that method is waited higer.

## Features

- **Multi-technique detection pipeline** - Uses chapters, silence, black frames, image hashing, audio fingerprinting, scene changes, speech detection and LLM vision analysis
- **TMDB validation** - Validates detected episode durations against The Movie Database
- **Lossless splitting** - Uses FFmpeg stream copy for fast, quality-preserving extraction
- **Smart naming** - Automatically parses source filenames and generates proper episode names
- **Flexible output** - Place episodes in source directory or create season subdirectories

## Detection Methods

| Method | Description | Reliability |
|--------|-------------|-------------|
| Chapter Detection | Uses chapter markers (e.g., "Episode 1", "Commercial 1") | Highest |
| Silence Detection | Finds silence gaps between episodes | High |
| Black Frame Detection | Detects black frames at episode boundaries | High |
| Scene Change Detection | Detects dramatic visual transitions using FFmpeg scene filter | Medium |
| Speech Detection | Uses Whisper to detect "Stay tuned", "Next time on" phrases | Medium |
| Audio Fingerprinting | Finds recurring theme music using Chromaprint | Medium |
| Image Hash Detection | Finds recurring intro sequences using perceptual hashing | Medium |
| LLM Vision | Uses Ollama to detect credits, title cards, recaps | Medium |

## Dependencies

Dependencies are automatically installed via `init.d/install-deps.sh`:

- **FFmpeg/FFprobe** - Video processing (should be pre-installed in Unmanic)
- **Chromaprint** (`libchromaprint-tools`) - Audio fingerprinting
- **imagehash** / **Pillow** - Perceptual image hashing
- **requests** - HTTP client for TMDB API
- **parse-torrent-title** - Filename parsing
- **faster-whisper** (optional) - Speech detection for episode-end phrases
- **ollama** (optional) - LLM vision detection client

## Configuration

### Detection Methods

| Setting | Default | Description |
|---------|---------|-------------|
| Enable Chapter Detection | On | Use chapter markers to detect episode boundaries (highest reliability) |
| Enable Silence Detection | On | Detect silence gaps between episodes |
| Enable Black Frame Detection | On | Detect black frames that may indicate episode breaks |
| Enable Scene Change Detection | Off | Detect dramatic visual transitions between episodes using FFmpeg |
| Enable Image Hash Detection | Off | Use perceptual hashing to find recurring intro/outro sequences (CPU intensive) |
| Enable Audio Fingerprint Detection | Off | Detect recurring intro music patterns using Chromaprint |
| Enable LLM Vision Detection | Off | Use Ollama vision model to detect credits, title cards (requires Ollama) |
| Enable Speech Detection | Off | Use Whisper to detect "Stay tuned" and preview phrases (requires faster-whisper) |
| Enable TMDB Validation | Off | Validate detected runtimes against TMDB episode data |

### LLM Settings (when enabled)

| Setting | Default | Description |
|---------|---------|-------------|
| Ollama Host | `http://localhost:11434` | URL of Ollama API endpoint. Can be a remote server (e.g., `http://192.168.1.100:11434`) |
| LLM Model | `qwen2.5vl:7b` | Vision model to use |
| Frames per Boundary | 5 | Number of frames to analyze at each potential boundary |

#### Force Split at Credits End (Override Option)

This is an **override option** that bypasses the normal multi-detector agreement logic. When enabled, the plugin will always split at the point where LLM detects credits or outro sequences end, regardless of what other detectors find.

**When to use this option:**
- When normal detection methods consistently fail to converge on correct boundaries
- When the video has unusual structure where credits are the most reliable boundary marker
- As a last resort when other detection combinations don't work for a specific series
- as of v0.0.16 of the plugin LLM detection should be more accurate in detecting ending credits from next epiode intro

### Duration Constraints

| Setting | Default | Description |
|---------|---------|-------------|
| Minimum Episode Length | 15 min | Episodes shorter than this will be merged or ignored |
| Maximum Episode Length | 90 min | Episodes longer than this will trigger warnings |
| Minimum File Duration | 30 min | Only process files longer than this (suggests 2+ episodes) |

### Detection Parameters

| Setting | Default | Description |
|---------|---------|-------------|
| Silence Threshold | -30 dB | Audio level threshold for silence detection |
| Minimum Silence Duration | 2.0 sec | Minimum silence duration to detect |
| Minimum Black Duration | 1.0 sec | Minimum black frame duration to detect |
| Scene Change Threshold | 0.3 | Scene change sensitivity (0.1-0.5, lower = more sensitive) |
| Confidence Threshold | 0.7 | Minimum confidence score to split at a boundary (0.0-1.0) |

#### Confidence Threshold

The confidence threshold determines the minimum score required before the plugin will split at a detected boundary. Each detection method assigns a confidence score (0.0-1.0) based on how strongly the evidence supports an episode boundary at that location.

The default value of **0.7** is a good starting point because:
- It filters out weak or ambiguous detections while accepting reasonably confident boundaries
- Multiple agreeing detectors boost confidence, so boundaries found by 2+ methods typically exceed 0.7
- It's high enough to avoid false positives but low enough that strong single-detector results (like black frames in a search window) can pass

If you're getting **too many false splits**, increase the threshold toward 0.85-0.9. If **valid boundaries are being missed**, try lowering it to 0.6-0.65.

### Speech Detection Settings (when enabled)

| Setting | Default | Description |
|---------|---------|-------------|
| Whisper Model Size | base | Model size for speech detection (tiny=fastest, large-v2=most accurate) |

Speech detection listens for episode-end phrases like "Stay tuned", "Next time on", or "Coming up next" which indicate the episode content has ended. The split point is placed AFTER these phrases, at the next black frame or silence gap.

### Scene Change Settings (when enabled)

| Setting | Default | Description |
|---------|---------|-------------|
| Scene Change Threshold | 0.3 | Sensitivity for scene detection (0.1=very sensitive, 0.5=only major changes) |

### Output Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Output Naming Pattern | `S{season:02d}E{episode:02d} - {basename}` | Pattern for episode filenames. Variables: `{title}`, `{season}`, `{episode}`, `{basename}`, `{ext}` |
| Lossless Stream Copy | On | Use FFmpeg stream copy (`-c copy`) for fast lossless extraction |
| Create Season Directory | Off | Create a season subdirectory (e.g., "Season 01") for split episodes |
| Season Directory Pattern | `Season {season:02d}` | Pattern for season directory name. Variables: `{season}`, `{title}` |
| Delete Source After Split | Off | Delete the multi-episode source file after successful split. **WARNING: Destructive!** |

### TMDB Settings (when enabled)

| Setting | Description |
|---------|-------------|
| TMDB API Key | API key from themoviedb.org |
| TMDB API Read Access Token | API read access token (v4 auth) from themoviedb.org |

To get TMDB API credentials, create an account at [themoviedb.org](https://www.themoviedb.org/) and request an API key in your account settings.

## Example Workflow

1. Plugin detects file `S1E1-3 My Show.mkv` (175 min duration)
2. Chapter detection finds 3 episodes marked as "Episode 1", "Episode 2", "Episode 3"
3. Audio fingerprinting confirms episode boundaries by detecting recurring theme music
4. TMDB validation confirms expected ~60 min runtime per episode
5. Plugin splits into:
   - `S01E01 - My Show.mkv` (59.5 min)
   - `S01E02 - My Show.mkv` (57.9 min)
   - `S01E03 - My Show.mkv` (58.2 min)

## Troubleshooting

**No episodes detected:**
- Ensure the file is long enough (> min file duration setting)
- Try enabling additional detection methods
- Check if chapters exist but use non-standard naming

**Wrong number of episodes detected:**
- Adjust confidence threshold
- Enable TMDB validation to verify against known episode counts

**Splits at wrong positions:**
- Chapter markers may indicate commercials rather than episodes
- Try enabling silence + black frame detection together
- Adjust silence/black frame duration thresholds

**LLM detection not working:**
- Ensure Ollama is running and accessible at the configured host
- Pull the required model: `ollama pull llava:7b-v1.6-mistral-q4_K_M`
- Check network connectivity if using a remote Ollama server
- GPU can become stuck in P8 state.  to avoid this you need to perform some steps on the system where Ollama server is running:
  - ensure you have no zombie ollama processes running (if not sure, restart your host running ollama server)
  - sudo nvidia-smi -lmc 7000,7501
  - # Replace 7501 with your max memory clock (check nvidia-smi -q -d CLOCK)
  - # (Note: 7501 is arbitrary high upper bound; 7000 is the floor to keep memory speed maxed).
  - sudo nvidia-smi -lgc 1500,2100
  - # undo the locks so your GPU doesn't run hot indefinitely - this will allow it to again reach state P8
  - sudo nvidia-smi -rmc
  - sudo nvidia-smi -rgc
