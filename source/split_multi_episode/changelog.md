
*<span style="color:#56adda">0.2.2</span>**

- Change: LLM Precision Mode windows widened to 4 minutes total
  - Asymmetric mode: -3m/+1m (more backward coverage for cumulative drift)
  - Symmetric mode: ±2m (for accurate TMDB timing)
  - ~120 frames at 2-second sampling

- Add: "Symmetric Windows" checkbox for LLM Precision Mode
  - Default (unchecked): asymmetric -3m/+1m windows
  - Checked: symmetric ±2m windows
  - Use symmetric when TMDB runtimes closely match actual content
  - Use asymmetric (default) when episodes tend to run shorter than TMDB predicts

- Add: "Ignore pattern" logic for Boundary Pattern setting
  - Only detection types mentioned in the pattern are considered
  - Example: l-l-s means only consider logos, ignore all credits, split after 2nd logo block
  - Useful when credits are being falsely detected on non-credit frames

- Add: "Pattern Grouping Buffer" setting (1-15 seconds, default 10)
  - Groups detections within this many seconds into a single "block"
  - Pattern matching works on blocks, not individual detections
  - Example: 5 logo detections within 10 seconds become 1 logo block
  - Helps with intermittent detections (logos that flicker or repeat)
  - Only visible when LLM Precision Mode is enabled

*<span style="color:#56adda">0.2.1</span>**

- Change: LLM Precision Mode now uses asymmetric windows (-3m/+0.5m instead of ±1.1m)
  - More backward coverage since episodes are typically shorter than TMDB predicts
  - Cumulative drift compounds across episodes, making later boundaries progressively earlier
  - 3.5-minute total window with ~105 frames at 2-second sampling

- Fix: LLM Precision Mode now uses LAST frame timestamps instead of midpoints/centers
  - With 2-second intervals, use actual frame timestamps not interpolation
  - Credits transition: uses last credits=True frame
  - Logo: uses last logo=True frame in the boundary group
  - Logos within 15 seconds after credits are included (end logo marking boundary)

- Remove: "Confidence Threshold" setting (now handled internally by clustering algorithm)

- Add: "Post-Credits Buffer" setting for LLM Precision Mode (5-60 seconds slider, default 15)
  - Controls how far after credits transition to include logos as part of the boundary
  - Some shows have longer gaps between credits end and network logo
  - Increase if splits are occurring before the actual episode end

- Add: "Boundary Pattern" setting for LLM Precision Mode (alternative to buffer)
  - Specify exact sequence pattern like "c-l-c-s-l" where c=credits, l=logo, s=split point
  - Example: c-l-c-s-l means split before the 2nd logo (after credits-logo-credits sequence)
  - Purely sequence-based matching (order matters, timing gaps don't)
  - Partial matching: if pattern is c-l-c-s-l but only c-l-l detected, splits before 1st l
  - Expansion tries backward then forward, then fails (no normal mode fallback)
  - Useful for shows with complex credits/logo patterns that buffer can't handle

- Fix: LLM Precision Mode now shows progress in GUI gauge
  - Progress updates after each frame is analyzed (not just after each window)
  - Sub-window progress tracking for smooth progress during long scans
  - ETC timer now updates during window processing

**<span style="color:#56adda">0.2.0</span>**
- New: LLM Precision Mode for clean files without commercials
  - Narrow 2.2-minute windows centered on TMDB-predicted boundaries (±1.1m)
  - Dense 2-second sampling interval (~66 frames per window)
  - Sequential window processing with drift adjustment:
    - After each boundary is found, subsequent windows shift by the cumulative drift
    - Example: if episode 1 ends 30s early, window 2 shifts 30s earlier
    - Handles TMDB runtimes that don't perfectly match actual content
    - Logs drift adjustments and total cumulative drift
  - Logo-centric split logic with boundary filtering:
    - When credits detected: uses only logos AT or BEFORE the credits transition
    - When no credits: detects logo clumps and uses first clump only
    - Logos after the boundary (next episode intro) are excluded
  - Auto-expansion when no detections found in primary window:
    - First expands backward 1.5 minutes (cumulative timing errors make boundaries earlier)
    - Then expands forward 1.5 minutes if still nothing found
  - Final fallback to normal mode (10-minute window, 10-second intervals):
    - Scans only the far regions not already covered by precision mode
    - If still no detections, aborts with error rather than making unreliable split
  - Falls back to credits transitions, then window center
  - Requires both LLM and TMDB to be enabled
  - Best for DVD rips and streaming content with accurate TMDB runtimes

- Change: Default LLM model changed to qwen2.5vl:3b (better stability than 7b)

**<span style="color:#56adda">0.1.0</span>**
- Improve: TMDB validation now subtracts commercial time before comparing
  - Files with commercial markers: durations adjusted by subtracting commercial time per episode
  - Comparison reflects content-only runtime vs TMDB's content-only runtime
  - Message indicates "(commercial-adjusted)" when adjustment was applied
  - Fixes misleading "Poor runtime match" for files with commercials

- Remove: "Frames per Boundary" LLM setting (was unused dead code)
- Remove: "Split at Credits/Outro End" LLM setting (now redundant with transition detection)

- Fix: LLM raw detection now returns TRANSITIONS for credits/outro
  - Previously returned every credits=True frame, clustering averaged to middle of credits
  - Now detects credits=True→False transitions and returns the transition point
  - Boundary is at midpoint between last credits frame and first non-credits frame
  - Score based on run length (run_length * 20) - longer credit runs = higher confidence
  - Requires 3+ consecutive True frames for credits/outro (filters noise)

- Fix: LLM logo detection now returns each logo frame (not transition-based)
  - Logos are brief/intermittent - networks splash logos between shows
  - Each logo=True frame becomes a detection with score=30
  - Multiple logo frames in proximity naturally cluster together
  - Previously required 3+ consecutive frames which never happens for logos

- Improve: Fine sampling mode now stays active for 10 seconds (was 5)
  - Gives more time to capture logo transitions after initial detection
  - Helps when logos appear intermittently across multiple frames

- Improve: Ollama API requests now include stability parameters
  - temperature=0.1 (more deterministic, less random sampling)
  - top_k=40 (limit token selection pool)
  - num_predict=150 (limit response length)
  - May reduce "failed to sample token" crashes

- Improve: LLM detector retry logic for Ollama instability
  - Changed from 1×60s timeout to 3×20s retries
  - Handles Ollama crashes/restarts (panic: failed to sample token)
  - Retries on HTTP 500 and connection errors with brief pauses
  - Fails faster on individual timeouts, recovers when Ollama restarts

- Major: Refactored to raw detection clustering architecture
  - Detectors now return ALL raw detections via `detect_raw_in_windows()`, not just "best" per window
  - Clustering combines raw detections across all detectors per window
  - Multi-detector agreement at same timestamp beats single high-confidence detection
  - Example: low-conf black_frame + low-conf LLM at 187m > high-conf black_frame alone at 184m

- Change: Boundary detectors with raw clustering support
  - silence: All silences scored by duration (duration * 10)
  - black_frame: All black frames scored by duration (duration * 10)
  - scene_change: All scene changes scored by magnitude (scene_score * 100)
  - speech: Episode-end phrases ("stay tuned", etc.) scored at 50
  - llm_vision: Each credits/logo/outro frame scored by sampling interval

- Note: Pattern detectors (image_hash, audio_fingerprint) not using raw clustering
  - These detect recurring intros at episode STARTS, not boundaries
  - Different use case from boundary detection

- Change: LLM detector scoring based on time represented
  - Each credits/logo/outro frame scored by sampling interval
  - 10s interval frame = 10 points, 1s interval frame = 1 point
  - Credits, logo, outro are separate indicators that cluster independently
  - Natural clustering replaces arbitrary "3+ consecutive frames = strong" logic

- Change: Cluster scoring formula (RawDetectionClusterer)
  - Sum of individual detection scores
  - Detector diversity bonus: 1.5^(num_detectors - 1)
  - Proximity penalty: tighter clusters score higher
  - 60-second clustering tolerance window

- Simplify: Plugin combining logic greatly reduced
  - Removed 400+ lines of manual cluster logic in plugin.py
  - Detection runner now returns best clustered boundary per window
  - Plugin just uses the result directly

**<span style="color:#56adda">0.0.18</span>**
- Feature: Dynamic LLM sampling rate based on logo detection
  - Normal sampling: every 10 seconds
  - When logo detected: switches to 1-second sampling for precision
  - Captures precise logo→non-logo transition
  - Resumes 10-second sampling after transition captured
  - Logs show `[FINE]` prefix during high-frequency sampling

- Feature: Strong logo detection as independent boundary indicator
  - 3+ consecutive logo=True frames (at 1s intervals) = strong logo
  - Strong logo→no-logo transition gets confidence 0.90
  - Works independently of credits detection
  - Useful when no strong credits transition is found

- Improve: Combining logic now prefers high-confidence LLM over black_frame
  - High-confidence LLM (>=0.88) indicates strong credits or logo transition
  - LLM's precise transition time is used instead of black_frame's time
  - Black_frame may detect a different black frame (scene change, not boundary)
  - Falls back to black_frame only when LLM confidence is low

- Improve: TMDB lookup debugging and consistency
  - Added detailed debug logging for TMDB title parsing and lookups
  - Logs parsed title, series_id, episodes found, and runtimes
  - Specific error messages when episodes are missing or lack runtime data
  - Phase 1 (window calculation) and validation now use same title parsing
  - Prevents inconsistent TMDB results between phases

- Fix: TMDB episode range handling
  - Now passes start_episode directly to get exact episodes needed
  - Handles cases where file is S2E5-8 but TMDB only has partial season data
  - Logs specific warnings about which episodes couldn't be found

**<span style="color:#56adda">0.0.17</span>**
- Feature: LLM now detects network/production logos (HBO, Netflix, BBC, etc.)
  - Logo detection added to LLM prompt alongside credits, intro, outro
  - Logo on/near transition acts as confirmation, boosting confidence

- Improve: Transition strength now considered for better accuracy
  - Strong transition: 3+ consecutive credits=True frames → credits=False (conf 0.88-0.92)
  - Weak transition: 1-2 frames of credits=True → ignored as noise
  - Logo confirmation: logo on last credits frame or within 2 frames after = +0.04 confidence
  - Single isolated credits=True frames after logo are ignored (likely intro misdetected)
  - Metadata includes `credits_run_length`, `logo_confirms`

- Improve: Accurate search window calculation using TMDB + commercial chapter data
  - Extracts actual commercial duration per episode from chapter markers (Commercial 1, 2, 3...)
  - Episode total = TMDB runtime + episode's actual commercial time
  - Any discrepancy vs file duration is pro-rated proportionally across episodes
  - Window centers are now at the true calculated boundary position
  - Falls back to estimated commercials when chapter data unavailable

**<span style="color:#56adda">0.0.16</span>**

- Fix: LLM detection hanging - use REST API instead of ollama library
  - The ollama Python library's timeout only applies to connection, not request duration
  - Switched to direct REST API calls with proper 60-second request timeout
  - Now properly times out and continues if a single frame query gets stuck

- Improve: LLM now detects credits→non-credits TRANSITION for much better accuracy
  - Instead of using "last frame with credits", looks for where credits=True changes to credits=False
  - This transition aligns precisely with the actual episode boundary
  - Example: credits=True at 59.1m, 59.3m → credits=False at 59.6m = boundary at 59.45m
  - Transition detection gets high confidence (0.88); no transition gets low confidence (0.54)
  - Metadata includes `transition_detected`, `last_credits_at`, `first_non_credits_at`

- Improve: Smarter multi-detector agreement handling
  - Clusters with BOTH black_frame AND silence now get +0.20 confidence boost
  - A clear A/V gap (black screen + silence) is a very reliable episode boundary

- Fix: LLM credits constraint logic simplified and improved
  - LLM constraint ignored when winning cluster has black+silence agreement
  - LLM constraint requires >= 0.7 confidence (only transition detections qualify)
  - Removed arbitrary 2-minute distance check (transition detection handles this naturally)
  - Logs clearly show when and why LLM constraint is ignored

- Change: "Split at Credits End" is now an override/nuclear option
  - Documented as "Force Split at Credits End"
  - When enabled, bypasses all normal detection logic and trusts LLM completely
  - Use only when normal multi-detector agreement fails to converge

- Fix: Speech detection CUDA fallback now works during transcription
  - Previously, CPU fallback only triggered if model loading failed
  - Now also catches CUDA errors during actual transcription (e.g., missing libcublas.so.12)
  - Automatically reloads model on CPU and retries transcription

- Fix: GPU speech detection now works in containers without system CUDA libraries
  - NVIDIA container runtime provides GPU access but not CUDA math libraries (libcublas, libcudnn)
  - Now installs nvidia-cublas-cu12 and nvidia-cudnn-cu12 via pip in init.d script
  - Preloads these libraries at module load time so ctranslate2/faster-whisper can find them
  - Falls back gracefully to CPU if nvidia pip packages aren't available

**<span style="color:#56adda">0.0.15</span>**
- Fix: Filename parsing now correctly extracts title from before episode info
  - Fixed in both EpisodeNamer and TMDBValidator modules
 
**<span style="color:#56adda">0.0.14</span>**
- Fix: Filename parsing now correctly extracts title from before episode info
  - Regex fallback was incorrectly choosing quality/codec metadata (after S##E##) as title
  - Now prefers the content before episode info, which is the standard naming convention
  - Example: "Show Name S1E1-6 COMBiNED WEBRip 480p" now correctly parses title as "Show Name"
- Fix: PTN field mapping corrected for quality and source
  - PTN's 'resolution' (480p, 1080p) now maps to our 'quality' field
  - PTN's 'quality' (WEBRip, BluRay) now maps to our 'source' field
  - This ensures source info like WEBRip is preserved in output filenames
- Add: "Split at Credits End" option for LLM credit detection
  - New setting `llm_split_at_credits_end` under LLM Vision Detection
  - When enabled, splits immediately 2 seconds after detected credits end
  - Bypasses searching for black frame/silence after credits
  - Useful when episodes transition directly without clear A/V markers
  - Default behavior (disabled) still extends window to find next split characteristic

**<span style="color:#56adda">0.0.13</span>**
- Fix: LLM credits constraint now enforced in combining logic
  - If LLM detects credits, boundary must be AFTER the credits end
  - Prevents splitting in the middle of credits when black_frame is detected before credits
  - Looks for first black_frame or silence after LLM's credits_detected_at time
  - If credits extend to window edge, automatically extends search by 60 seconds
  - Runs targeted black_frame and silence scans in the extended region

**<span style="color:#56adda">0.0.12</span>**
- Add: GUI progress gauge for detection phase via PluginChildProcess
  - Detection methods now run in a child process with progress reporting
  - GUI gauge shows cumulative progress across all detection methods
  - Each method's completion updates the gauge proportionally
- Refactor: Detection logic extracted into separate detection_runner module
  - Cleaner separation of concerns
  - Enables parallel execution and progress reporting
- Remove: "Require Multiple Detectors" setting (no longer applicable)
  - Windowed architecture makes single-detector results reliable
  - Phase 1 already narrows search to expected boundary regions
  - Black frame detection alone in a window is sufficient

**<span style="color:#56adda">0.0.11</span>**
- Add: Progress tracking for detection phase
  - Shows which detection method is running (e.g., "[2/6] Running black_frame...")
  - Logs completion percentage after each method
  - Split phase already has FFmpeg progress via exec_command
- Improve: Worker log now shows detailed detection progress

**<span style="color:#56adda">0.0.10</span>**
- Add: Speech detection using faster-whisper for episode-end phrase detection
  - Detects phrases like "stay tuned", "next time on", "coming up next"
  - These indicate the episode content has ended
  - Split point should be AFTER the phrase, at the next black/silent scene
  - Ideal split: within 30 seconds after the phrase (preview content ends)
  - Beyond 30 seconds: confidence decreases (risk of cutting into next episode)
  - Configurable model size (tiny, base, small, medium, large-v2)
- Add: Episode-end constraint logic in boundary combining
  - If boundary is before detected phrase, adjusts to next black_frame/silence after phrase
  - Prefers results within 30 seconds, penalizes results beyond 60 seconds

**<span style="color:#56adda">0.0.9</span>**
- Improve: LLM detection now runs within search windows (not full file)
  - Samples every 10 seconds for precise credit detection
  - Finds END of credits (last frame with credits + offset)
  - Much faster than full-file scanning
- Improve: Black frame detection now takes priority in combining logic
  - Clusters with black_frame are preferred over those without
  - When black_frame is in winning cluster, use its exact time (not average)
  - Black_frame confidence boosted by 0.15 for episode boundary detection
- Fix: TMDB runtimes now used even when they slightly exceed file duration

**<span style="color:#56adda">0.0.8</span>**
- Add: Scene change detection using FFmpeg's scene filter
  - Detects dramatic visual transitions between episodes
  - Configurable threshold (0.1-0.5, lower = more sensitive)
  - Runs within search windows for efficient detection
  - Weights results by scene change magnitude and proximity to window center

**<span style="color:#56adda">0.0.7</span>**
- Optimize: Silence and black frame detection now scan only search windows
  - Uses FFmpeg `-ss` and `-t` to seek directly to each window
  - Dramatically faster detection (minutes instead of full file scan time)
  - Each ~10 minute window scans in seconds instead of scanning entire file

**<span style="color:#56adda">0.0.6</span>**
- Major: Refactored to two-phase detection architecture
  - Phase 1: Determine narrow search windows using chapter marks, TMDB runtimes, or equal division
  - Phase 2: Run detectors only within those windows for focused, accurate boundary detection
- Add: New `SearchWindowDeterminer` module for Phase 1 window calculation
- Add: `detect_in_windows()` method to silence and black frame detectors
- Change: Search windows are 10 minutes wide (5 min each side of expected boundary)
- Change: Results from multiple detectors within a window are combined (averaged if agreeing)
- Improve: Much more accurate boundary detection by focusing on expected regions

**<span style="color:#56adda">0.0.5</span>**
- Change: Standalone detection is now automatic based on detection type (not configurable)
  - 'chapter' (true episode chapters): standalone - always reliable
  - 'silence_guided' (episode count from filename): standalone - uses known count
  - 'chapter_commercial': NOT standalone - needs confirmation
  - 'silence' (estimation-based): NOT standalone - needs confirmation
  - 'black_frame': NOT standalone - needs confirmation
- Remove: `standalone_detection_methods` setting (now automatic)

**<span style="color:#56adda">0.0.4</span>**
- Add: Configurable `standalone_detection_methods` setting for tiered detection hierarchy
- Add: Silence detection now uses "silence_guided" source when guided by episode count
- Fix: Boundary merger respects standalone methods that can work without confirmation
- Fix: Proper tier system - standalone methods (chapter, silence_guided) don't require multiple detectors

**<span style="color:#56adda">0.0.3</span>**
- Fix: Extract expected episode count from filename (e.g., S2E5-8 = 4 episodes) to guide detection
- Fix: Silence detection now uses episode count for accurate boundary detection instead of estimation
- Fix: Commercial chapter markers are now treated as approximate regions, not exact boundaries
- Fix: When silence/black detection is enabled, use those for precise boundaries instead of commercial markers
- Improve: TMDB runtimes fetched early to provide additional context to detectors

**<span style="color:#56adda">0.0.2</span>**
- cache the results from silence detection so the 2 step silence detection doesn't have to rerun the detection a 2nd time.
- remove TaskDataStore use and use the data object to modify the file movement behavior

**<span style="color:#56adda">0.0.1</span>**
- Initial release
- Chapter-based episode detection
- Silence and black frame detection
- Image hash detection for recurring intros
- Audio fingerprint detection
- LLM vision detection via Ollama
- TMDB runtime validation
- Lossless FFmpeg extraction
