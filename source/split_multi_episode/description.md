# Split Multi-Episode Files

Automatically detects and splits multi-episode video files (e.g., "S01E01-E03.mkv") into individual episode files using multiple detection techniques.

## Features

- **Two-phase detection architecture** - Phase 1 narrows search to expected boundary regions; Phase 2 runs detectors within those windows
- **Raw detection clustering** - Multiple detectors contribute evidence that gets clustered; multi-detector agreement beats single high-confidence detections
- **LLM Precision Mode** - For clean files without commercials, uses dense sampling with TMDB-predicted windows and logo-centric split logic
- **TMDB validation** - Validates detected episode durations against The Movie Database
- **Lossless splitting** - Uses FFmpeg stream copy for fast, quality-preserving extraction
- **Smart naming** - Automatically parses source filenames and generates proper episode names

## Detection Methods

| Method | Description | Use Case |
|--------|-------------|----------|
| Chapter Detection | Uses chapter markers (e.g., "Episode 1", "Commercial 1") | Files with proper chapter metadata |
| Silence Detection | Finds silence gaps between episodes | Most broadcast recordings |
| Black Frame Detection | Detects black frames at episode boundaries | Most broadcast recordings |
| Scene Change Detection | Detects dramatic visual transitions using FFmpeg scene filter | Clean transitions without A/V gaps |
| Speech Detection | Uses Whisper to detect "Stay tuned", "Next time on" phrases | Broadcast with announcer cues |
| Audio Fingerprinting | Finds recurring theme music using Chromaprint | Series with consistent intro music |
| Image Hash Detection | Finds recurring intro sequences using perceptual hashing | Series with consistent visual intros |
| LLM Vision | Uses Ollama to detect credits, logos, title cards | Universal fallback, precision mode |

## How Detection Works

### Phase 1: Window Determination

The plugin first determines narrow search windows where episode boundaries are expected:

1. **Chapter markers** - If chapters exist, uses them to estimate boundary regions
2. **TMDB runtimes** - If enabled, uses expected episode durations to calculate window centers
3. **Equal division** - Falls back to dividing file duration by expected episode count

Windows are typically 10 minutes wide (±5 minutes from expected boundary).

### Phase 2: Boundary Detection

Within each window, enabled detectors scan for boundary evidence:

- **Silence detector** - Returns all silence gaps, scored by duration (duration × 10)
- **Black frame detector** - Returns all black frames, scored by duration (duration × 10)
- **Scene change detector** - Returns all scene changes, scored by magnitude (score × 100)
- **Speech detector** - Returns episode-end phrases ("stay tuned", etc.), scored at 50
- **LLM detector** - Returns credits/logo/outro transitions, scored by run length

### Raw Detection Clustering

All detections from all detectors are clustered together per window:

- Detections within 60 seconds of each other form a cluster
- Cluster score = sum of individual scores + diversity bonus
- Diversity bonus: 1.5^(num_detectors - 1) rewards multi-detector agreement
- Example: low-conf black_frame + low-conf silence at same time beats high-conf black_frame alone

The best cluster per window becomes the episode boundary.

## LLM Precision Mode

For **clean files without commercials** (DVD rips, streaming content), Precision Mode provides highly accurate splitting:

### When to Use

- Files without commercial breaks
- TMDB has accurate runtime data for the series
- Standard detection methods produce inconsistent results

### How It Works

1. **Window sizing** - 4-minute windows around TMDB-predicted boundaries
   - Asymmetric (default): -3m/+1m (more backward coverage for cumulative drift)
   - Symmetric: ±2m (when TMDB runtimes are accurate)
2. **Dense sampling** - Analyzes frames every 2 seconds (~66 frames per window)
3. **Sequential processing** - After each boundary, adjusts subsequent windows by the cumulative timing drift
4. **Logo-centric logic** - Prioritizes network/production logos as boundary markers
5. **Boundary filtering** - Excludes logos that appear after credits transition (next episode's intro)

### Fallback Chain (Buffer Mode)

If no detections in primary window:
1. Expand backward 1.5 minutes (boundaries often earlier than predicted)
2. Expand forward 1.5 minutes
3. Fall back to normal mode (10-minute window, 10-second intervals)
4. If still nothing found, abort rather than make unreliable split

### Pattern Mode

For shows with complex credits/logo sequences, you can specify an exact pattern to match:

**Pattern syntax:**
- `c` = credits detection
- `l` = logo detection
- `s` = split point (where to cut)
- `-` = separator

**Example:** `c-l-c-s-l`
- Matches: credits → logo → credits → **[SPLIT HERE]** → logo
- The split occurs right before the second logo

**Ignore Pattern Logic:**

Only detection types mentioned in the pattern are considered. Other detections are filtered out.

**Example:** `l-l-s`
- Only considers logos; all credits detections are ignored
- Useful when credits are being falsely detected on non-credit frames
- Splits after the 2nd logo block

**Pattern Grouping Buffer:**

Detections within the grouping buffer (default 10 seconds) are merged into a single "block".

**Example:** With a 10-second buffer, five logo detections at 48.0m, 48.1m, 48.2m, 48.3m, 48.4m become one logo block. A second group of logos at 49.0m, 49.1m becomes a second block. The pattern `l-l-s` then matches two logo blocks and splits after the second block (at 49.1m).

**Matching behavior:**
- Full match: If all pattern elements are found in order, splits at the `s` position
- Partial match: If pattern is `c-l-c-s-l` but only `c-l-l` detected, splits before the first `l` where the pattern broke
- No match: Expands window once (backward then forward), then fails with error

**When to use:**
- Shows with alternating credits/logo patterns (c-l-c-l sequences)
- When the buffer approach splits at the wrong logo
- Complex end sequences that need precise pattern matching

Note: When a pattern is specified, the Post-Credits Buffer setting is ignored.

### Requirements

- LLM Detection must be enabled
- TMDB Validation must be enabled with valid API credentials
- TMDB must have runtime data for the episodes

## Dependencies

Dependencies are automatically installed via `init.d/install-deps.sh`:

- **FFmpeg/FFprobe** - Video processing (should be pre-installed in Unmanic)
- **Chromaprint** (`libchromaprint-tools`) - Audio fingerprinting
- **imagehash** / **Pillow** - Perceptual image hashing
- **requests** - HTTP client for TMDB API
- **parse-torrent-title** - Filename parsing
- **faster-whisper** (optional) - Speech detection for episode-end phrases
- **ollama** (optional) - LLM vision detection client
- **nvidia-cublas-cu12** / **nvidia-cudnn-cu12** (optional) - GPU acceleration for speech detection in containers

## Configuration

### Detection Methods

| Setting | Default | Description |
|---------|---------|-------------|
| Enable Chapter Detection | On | Use chapter markers to detect episode boundaries |
| Enable Silence Detection | On | Detect silence gaps between episodes |
| Enable Black Frame Detection | On | Detect black frames that may indicate episode breaks |
| Enable Scene Change Detection | Off | Detect dramatic visual transitions using FFmpeg |
| Enable Image Hash Detection | Off | Find recurring intro/outro sequences (CPU intensive) |
| Enable Audio Fingerprint Detection | Off | Detect recurring intro music using Chromaprint |
| Enable LLM Vision Detection | Off | Use Ollama vision model to detect credits, logos, title cards |
| Enable Speech Detection | Off | Use Whisper to detect episode-end phrases |
| Enable TMDB Validation | Off | Validate detected runtimes against TMDB episode data |

### LLM Settings (when enabled)

| Setting | Default | Description |
|---------|---------|-------------|
| Ollama Host | `http://localhost:11434` | URL of Ollama API endpoint. Can be a remote server (e.g., `http://192.168.1.100:11434`) |
| LLM Model | `qwen2.5vl:3b` | Vision model to use |
| LLM Precision Mode | Off | Use narrow windows with dense sampling for clean files |
| Symmetric Windows | Off | Use ±2m windows instead of -3m/+1m (only in Precision Mode) |
| Post-Credits Buffer | 15 sec | How far after credits to include logos as boundary markers (5-60 sec) |
| Boundary Pattern | (empty) | Sequence pattern for complex boundaries (e.g., "c-l-c-s-l" or "l-l-s") |
| Minimum Gap Threshold | 10 sec | Minimum gap to consider a natural break between detection blocks (5-30 sec) |

#### LLM Detection Details

The LLM detector analyzes video frames and identifies:
- **Credits** - Cast names, production crew, end credits
- **Logos** - Network logos (HBO, Netflix, BBC), production company logos
- **Title cards** - Episode titles, show titles
- **Outro sequences** - "Next time on", preview content

**Transition detection**: The detector looks for credits=True → credits=False transitions, not just frames with credits. This provides the precise boundary point.

**Dynamic sampling**: Normally samples every 10 seconds. When a logo is detected, switches to 1-second sampling to capture the precise transition, then resumes 10-second sampling.

**Retry logic**: Uses 3×20s retries instead of a single long timeout. Handles Ollama crashes/restarts gracefully.

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
| Minimum Silence Duration | 2.0 sec | Minimum silence duration to consider |
| Minimum Black Duration | 1.0 sec | Minimum black frame duration to consider |
| Scene Change Threshold | 0.3 | Scene change sensitivity (0.1-0.5, lower = more sensitive) |

### Speech Detection Settings (when enabled)

| Setting | Default | Description |
|---------|---------|-------------|
| Whisper Model Size | base | Model size (tiny=fastest, large-v2=most accurate) |

Speech detection listens for episode-end phrases like "Stay tuned", "Next time on", or "Coming up next". The split point is placed AFTER these phrases, at the next black frame or silence gap.

### Output Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Output Naming Pattern | `{title_with_year} - S{season:02d}E{episode:02d}` | Pattern for episode filenames. Variables: `{title}`, `{title_with_year}`, `{season}`, `{episode}`, `{basename}`, `{ext}`. Use `{title_with_year}` to include year when available, or `{title}` for no year. |
| Lossless Stream Copy | On | Use FFmpeg `-c copy` for fast lossless extraction |
| Create Output Folder Hierarchy | Off | Create a folder hierarchy (Parent Folder/Season XX/) for episodes. If disabled, episodes are placed in the same directory as the source file. |
| Parent Folder Pattern | `{original_filename}` | Pattern for parent folder name. Variables: `{original_filename}`, `{title}`, `{title_with_year}`, `{season}` |
| Season Directory Pattern | `Season {season:02d}` | Pattern for season directory name |
| Delete Source After Split | Off | Delete source file after successful split. **Destructive!** |

**Folder Structure (when Create Output Folder Hierarchy is enabled):**

Example for source file `Series Name (2005) S1 E01 - E08 - HEVC - 1080p.mkv`:

With default `{original_filename}` parent pattern:
```
Series Name (2005) S1 E01 - E08 - HEVC - 1080p/
└── Season 01/
    ├── Series Name (2005) - S01E01.mkv
    └── ...
```

With `{title_with_year}` parent pattern:
```
Series Name (2005)/
└── Season 01/
    ├── Series Name (2005) - S01E01.mkv
    └── ...
```

### TMDB Settings (when enabled)

| Setting | Description |
|---------|-------------|
| TMDB API Key | API key from themoviedb.org |
| TMDB API Read Access Token | API read access token (v4 auth) |

TMDB validation compares detected episode durations against expected runtimes. For files with commercial chapter markers, the commercial time is subtracted before comparison so the content-only runtime matches TMDB's content-only runtime.

### Scene Change Settings (when enabled)

| Setting | Default | Description |
|---------|---------|-------------|
| Scene Change Threshold | 0.3 | Sensitivity for scene detection (0.1=very sensitive, 0.5=only major changes) |

## Example Workflow

1. Plugin detects file `S1E1-3 My Show.mkv` (175 min duration)
2. **Phase 1**: TMDB reports ~60 min per episode; creates windows at 60m and 120m (±5 min each)
3. **Phase 2**: Within each window, silence and black frame detectors find candidates
4. **Clustering**: Detections at similar timestamps cluster together; best cluster wins
5. **Validation**: TMDB confirms detected ~60 min runtime per episode
6. Plugin splits into:
   - `S01E01 - My Show.mkv` (59.5 min)
   - `S01E02 - My Show.mkv` (57.9 min)
   - `S01E03 - My Show.mkv` (58.2 min)

## Troubleshooting

**No episodes detected:**
- Ensure the file is long enough (> min file duration setting)
- Try enabling additional detection methods
- Check if chapters exist but use non-standard naming

**Wrong number of episodes detected:**
- Enable TMDB validation to verify against known episode counts
- Check that filename parses correctly (e.g., "S01E01-E03" format)

**Splits at wrong positions:**
- Enable multiple detectors - clustering works best with 2+ methods agreeing
- For clean files without commercials, try LLM Precision Mode
- Check logs for detection scores and cluster information

**LLM detection not working:**
- Ensure Ollama is running and accessible at the configured host (`curl http://localhost:11434/api/tags`)
- Pull the required model: `ollama pull ollama pull qwen2.5vl:3b`
- Check network connectivity if using a remote Ollama server
- Check logs for timeout/retry messages
- Try a smaller model if experiencing crashes
- GPU can become stuck in P8 state.  to avoid this you need to perform some steps on the system where Ollama server is running:
  - ensure you have no zombie ollama processes running (if not sure, restart your host running ollama server)
  - sudo nvidia-smi -lmc 7000,7501
  - # Replace 7501 with your max memory clock (check nvidia-smi -q -d CLOCK)
  - # (Note: 7501 is arbitrary high upper bound; 7000 is the floor to keep memory speed maxed).
  - sudo nvidia-smi -lgc 1500,2100
  - # undo the locks so your GPU doesn't run hot indefinitely - this will allow it to again reach state P8
  - sudo nvidia-smi -rmc
  - sudo nvidia-smi -rgc

**LLM Precision Mode missing boundaries:**
- Check that TMDB has accurate runtime data for your episodes
- Look for "drift adjustment" messages in logs
- If boundaries are consistently early/late, the mode will adapt via drift tracking
