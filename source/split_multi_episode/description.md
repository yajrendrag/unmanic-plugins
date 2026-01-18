# Split Multi-Episode Files

Automatically detects and splits multi-episode video files (e.g., "S01E01-E03.mkv") into individual episode files using multiple detection techniques.

## Features

- **Multi-technique detection pipeline** - Uses chapters, silence, black frames, image hashing, audio fingerprinting, and LLM vision analysis
- **TMDB validation** - Validates detected episode durations against The Movie Database
- **Lossless splitting** - Uses FFmpeg stream copy for fast, quality-preserving extraction
- **Smart naming** - Automatically parses source filenames and generates proper episode names
- **Flexible output** - Place episodes in source directory or create season subdirectories

## Detection Methods

| Method | Description | Reliability |
|--------|-------------|-------------|
| Chapter Detection | Uses chapter markers (e.g., "Episode 1", "Commercial 1") | Highest |
| Silence Detection | Finds silence gaps between episodes | High |
| Black Frame Detection | Detects black frames at episode boundaries | Medium |
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
- **ollama** (optional) - LLM vision detection client

## Configuration

### Detection Methods

| Setting | Default | Description |
|---------|---------|-------------|
| Enable Chapter Detection | On | Use chapter markers to detect episode boundaries (highest reliability) |
| Enable Silence Detection | On | Detect silence gaps between episodes |
| Enable Black Frame Detection | On | Detect black frames that may indicate episode breaks |
| Enable Image Hash Detection | Off | Use perceptual hashing to find recurring intro/outro sequences (CPU intensive) |
| Enable Audio Fingerprint Detection | Off | Detect recurring intro music patterns using Chromaprint |
| Enable LLM Vision Detection | Off | Use Ollama vision model to detect credits, title cards (requires Ollama) |
| Enable TMDB Validation | Off | Validate detected runtimes against TMDB episode data |

### LLM Settings (when enabled)

| Setting | Default | Description |
|---------|---------|-------------|
| Ollama Host | `http://localhost:11434` | URL of Ollama API endpoint. Can be a remote server (e.g., `http://192.168.1.100:11434`) |
| LLM Model | `llava:7b-v1.6-mistral-q4_K_M` | Vision model to use |
| Frames per Boundary | 5 | Number of frames to analyze at each potential boundary |

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
| Confidence Threshold | 0.7 | Minimum confidence score to split at a boundary (0.0-1.0) |
| Require Multiple Detectors | On | Require at least 2 detection methods to agree before splitting |

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
- Enable "Require Multiple Detectors" for more accuracy
- Enable TMDB validation to verify against known episode counts

**Splits at wrong positions:**
- Chapter markers may indicate commercials rather than episodes
- Try enabling silence + black frame detection together
- Adjust silence/black frame duration thresholds

**LLM detection not working:**
- Ensure Ollama is running and accessible at the configured host
- Pull the required model: `ollama pull llava:7b-v1.6-mistral-q4_K_M`
- Check network connectivity if using a remote Ollama server
