
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
