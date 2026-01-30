#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM vision-based episode boundary detection.

Uses local Ollama with a vision model (LLaVA) to identify
credits, title cards, and "previously on" sequences.
"""

import base64
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.llm_detector")

# Optional imports
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


@dataclass
class FrameAnalysis:
    """Results of LLM analysis on a frame."""
    timestamp: float
    is_credits: bool
    is_title_card: bool
    is_previously_on: bool
    is_intro: bool
    is_outro: bool
    is_logo: bool  # Network/production company logo (HBO, Netflix, etc.)
    confidence: float
    raw_response: str


@dataclass
class EpisodeBoundary:
    """Represents a detected episode boundary."""
    start_time: float  # seconds
    end_time: float    # seconds
    confidence: float  # 0.0 to 1.0
    source: str        # detection method name
    metadata: dict     # additional info


class LLMDetector:
    """
    Detects episode boundaries using LLM vision analysis.

    Uses Ollama with a vision model to analyze frames and identify
    visual cues like credits, title cards, and recap sequences.
    """

    CONFIDENCE = 0.9

    DEFAULT_PROMPT = """Analyze this frame from a video file. Answer the following questions with YES or NO:

1. Does this frame show credits (cast names, production crew, etc.)?
2. Does this frame show a title card or episode title?
3. Does this frame show a "Previously on..." recap sequence?
4. Does this frame appear to be part of an intro sequence?
5. Does this frame appear to be part of an outro/ending sequence?
6. Does this frame show a network or production company logo (HBO, Netflix, BBC, etc.)?

Respond in this exact format:
CREDITS: YES/NO
TITLE_CARD: YES/NO
PREVIOUSLY_ON: YES/NO
INTRO: YES/NO
OUTRO: YES/NO
LOGO: YES/NO
CONFIDENCE: HIGH/MEDIUM/LOW"""

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        model: str = "llava:7b-v1.6-mistral-q4_K_M",
        min_episode_length: float = 900,
        max_episode_length: float = 5400,
    ):
        """
        Initialize the LLM detector.

        Args:
            ollama_host: Ollama API endpoint
            model: Vision model to use
            min_episode_length: Minimum episode duration in seconds
            max_episode_length: Maximum episode duration in seconds
        """
        self.ollama_host = ollama_host
        self.model = model
        self.min_episode_length = min_episode_length
        self.max_episode_length = max_episode_length

    def is_available(self) -> bool:
        """Check if Ollama is available and the model is loaded."""
        if not REQUESTS_AVAILABLE:
            logger.warning("requests library not available")
            return False

        try:
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=5)
            if response.status_code != 200:
                return False

            # Check if model is available
            models = response.json().get('models', [])
            model_names = [m.get('name', '') for m in models]

            # Check for exact match or partial match
            for name in model_names:
                if self.model in name or name in self.model:
                    return True

            logger.warning(f"Model {self.model} not found in Ollama. Available: {model_names}")
            return False

        except Exception as e:
            logger.debug(f"Ollama not available: {e}")
            return False

    def detect(
        self,
        file_path: str,
        total_duration: float,
        candidate_boundaries: Optional[List[float]] = None
    ) -> List[EpisodeBoundary]:
        """
        Detect episode boundaries using LLM vision analysis.

        Args:
            file_path: Path to the video file
            total_duration: Total duration of the file in seconds
            candidate_boundaries: Optional list of timestamps to analyze
                                  (from other detectors)

        Returns:
            List of EpisodeBoundary objects representing detected episodes
        """
        if not self.is_available():
            logger.warning("LLM detection not available (Ollama not running or model not loaded)")
            return []

        with tempfile.TemporaryDirectory(prefix='split_llm_') as temp_dir:
            # Generate timestamps to analyze
            if candidate_boundaries:
                timestamps = candidate_boundaries
            else:
                # Sample at regular intervals
                timestamps = []
                current = 0.0
                while current < total_duration:
                    timestamps.append(current)
                    current += self.min_episode_length / 2

            logger.info(f"Analyzing {len(timestamps)} timestamps with LLM")

            # Analyze frames at each timestamp
            analyses = []
            for ts in timestamps:
                analysis = self._analyze_timestamp(file_path, ts, temp_dir)
                if analysis:
                    analyses.append(analysis)

            if not analyses:
                logger.debug("No frames could be analyzed")
                return []

            logger.info(f"Successfully analyzed {len(analyses)} frames")

            # Convert analyses to boundaries
            boundaries = self._analyses_to_boundaries(analyses, total_duration)

            logger.info(f"Detected {len(boundaries)} episode boundaries from LLM analysis")
            return boundaries

    def _analyze_timestamp(
        self,
        file_path: str,
        timestamp: float,
        temp_dir: str
    ) -> Optional[FrameAnalysis]:
        """
        Analyze frames around a timestamp using the LLM.

        Args:
            file_path: Path to the video file
            timestamp: Timestamp to analyze
            temp_dir: Temporary directory for frame files

        Returns:
            FrameAnalysis object or None on error
        """
        import time
        extract_start = time.time()

        # Extract frames around the timestamp
        frames = []
        for offset in range(-2, 3):  # -2, -1, 0, 1, 2 seconds
            frame_ts = timestamp + offset
            if frame_ts < 0:
                continue

            frame_path = os.path.join(temp_dir, f'frame_{timestamp:.0f}_{offset}.jpg')

            cmd = [
                'ffmpeg',
                '-ss', str(frame_ts),
                '-i', file_path,
                '-vframes', '1',
                '-q:v', '2',
                '-y',
                frame_path
            ]

            try:
                subprocess.run(cmd, capture_output=True, timeout=30)
                if os.path.exists(frame_path):
                    frames.append(frame_path)
            except Exception:
                pass

        extract_time = time.time() - extract_start

        if not frames:
            logger.debug(f"  Frame extraction failed at {timestamp/60:.1f}m (took {extract_time:.1f}s)")
            return None

        if extract_time > 5:
            logger.warning(f"  Slow frame extraction at {timestamp/60:.1f}m: {extract_time:.1f}s for {len(frames)} frames")

        # Analyze the middle frame (or first available)
        frame_to_analyze = frames[len(frames) // 2] if len(frames) > 1 else frames[0]

        try:
            llm_start = time.time()
            response = self._query_llm(frame_to_analyze)
            llm_time = time.time() - llm_start

            if llm_time > 10:
                logger.warning(f"  Slow LLM response at {timestamp/60:.1f}m: {llm_time:.1f}s")

            if response:
                return self._parse_response(timestamp, response)
        except Exception as e:
            logger.debug(f"LLM analysis failed for timestamp {timestamp}: {e}")

        return None

    def _query_llm(self, frame_path: str) -> Optional[str]:
        """
        Query the LLM with a frame image.

        Uses retry logic to handle Ollama instability - 3 attempts with
        20-second timeout each instead of one 60-second attempt.

        Args:
            frame_path: Path to the frame image

        Returns:
            LLM response text or None on error
        """
        # Read and encode the image
        with open(frame_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        # Use REST API directly - the ollama library's timeout doesn't work for
        # long-running generate requests, only for connection timeouts
        #
        # Retry logic: 3 attempts × 20 seconds each
        # This handles Ollama crashes/restarts better than one long timeout
        max_retries = 3
        timeout_per_attempt = 20

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(
                    f"{self.ollama_host}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": self.DEFAULT_PROMPT,
                        "images": [image_data],
                        "stream": False,
                        # Model parameters to stabilize sampling and reduce crashes
                        "options": {
                            "temperature": 0.1,   # More deterministic (less random sampling)
                            "top_k": 40,          # Limit token selection pool
                            "num_predict": 150,   # Limit response length (ours are short)
                        },
                    },
                    timeout=timeout_per_attempt
                )

                if response.status_code == 200:
                    return response.json().get('response', '')
                elif response.status_code == 500:
                    # Server error - Ollama may have crashed, retry
                    logger.warning(f"Ollama returned 500 (attempt {attempt}/{max_retries})")
                    if attempt < max_retries:
                        import time
                        time.sleep(2)  # Brief pause before retry
                        continue
                else:
                    logger.debug(f"Ollama returned status {response.status_code}")
                    return None

            except requests.exceptions.Timeout:
                logger.warning(f"Ollama request timed out after {timeout_per_attempt}s (attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    import time
                    time.sleep(1)  # Brief pause before retry
                    continue
            except requests.exceptions.ConnectionError:
                logger.warning(f"Ollama connection error (attempt {attempt}/{max_retries}) - server may be restarting")
                if attempt < max_retries:
                    import time
                    time.sleep(3)  # Longer pause for connection issues
                    continue
            except Exception as e:
                logger.debug(f"Ollama REST API failed: {e}")
                return None

        logger.warning(f"Ollama failed after {max_retries} attempts")
        return None

    def _parse_response(self, timestamp: float, response: str) -> FrameAnalysis:
        """
        Parse the LLM response into structured data.

        Args:
            timestamp: Frame timestamp
            response: LLM response text

        Returns:
            FrameAnalysis object
        """
        response_upper = response.upper()

        def extract_bool(key: str) -> bool:
            # Look for "KEY: YES" pattern
            import re
            pattern = rf'{key}:\s*(YES|NO)'
            match = re.search(pattern, response_upper)
            return match.group(1) == 'YES' if match else False

        def extract_confidence() -> float:
            if 'CONFIDENCE: HIGH' in response_upper:
                return 0.9
            elif 'CONFIDENCE: MEDIUM' in response_upper:
                return 0.7
            elif 'CONFIDENCE: LOW' in response_upper:
                return 0.5
            return 0.6  # Default

        return FrameAnalysis(
            timestamp=timestamp,
            is_credits=extract_bool('CREDITS'),
            is_title_card=extract_bool('TITLE_CARD'),
            is_previously_on=extract_bool('PREVIOUSLY_ON'),
            is_intro=extract_bool('INTRO'),
            is_outro=extract_bool('OUTRO'),
            is_logo=extract_bool('LOGO'),
            confidence=extract_confidence(),
            raw_response=response
        )

    def _analyses_to_boundaries(
        self,
        analyses: List[FrameAnalysis],
        total_duration: float
    ) -> List[EpisodeBoundary]:
        """
        Convert frame analyses to episode boundaries.

        Args:
            analyses: List of FrameAnalysis objects
            total_duration: Total file duration

        Returns:
            List of EpisodeBoundary objects
        """
        # Find frames that indicate episode boundaries
        boundary_timestamps = []

        for analysis in analyses:
            # Score this timestamp based on detected features
            is_boundary = (
                analysis.is_credits or
                analysis.is_title_card or
                analysis.is_previously_on or
                analysis.is_intro or
                analysis.is_outro or
                analysis.is_logo
            )

            if is_boundary:
                # Calculate confidence based on what was detected
                confidence = analysis.confidence
                if analysis.is_credits:
                    confidence = max(confidence, 0.85)
                if analysis.is_title_card:
                    confidence = max(confidence, 0.9)
                if analysis.is_previously_on:
                    confidence = max(confidence, 0.85)
                if analysis.is_logo:
                    confidence = max(confidence, 0.80)

                boundary_timestamps.append((analysis.timestamp, confidence, analysis))

        if not boundary_timestamps:
            return []

        # Sort by timestamp
        boundary_timestamps.sort(key=lambda x: x[0])

        # Filter to valid episode boundaries
        boundaries = []
        prev_end = 0.0

        for ts, confidence, analysis in boundary_timestamps:
            episode_duration = ts - prev_end

            # Check if this creates a valid episode
            if episode_duration >= self.min_episode_length:
                boundaries.append(EpisodeBoundary(
                    start_time=prev_end,
                    end_time=ts,
                    confidence=confidence * self.CONFIDENCE,
                    source='llm_vision',
                    metadata={
                        'is_credits': analysis.is_credits,
                        'is_title_card': analysis.is_title_card,
                        'is_previously_on': analysis.is_previously_on,
                        'is_intro': analysis.is_intro,
                        'is_outro': analysis.is_outro,
                        'is_logo': analysis.is_logo,
                    }
                ))
                prev_end = ts

        # Add final episode
        if total_duration - prev_end >= self.min_episode_length:
            boundaries.append(EpisodeBoundary(
                start_time=prev_end,
                end_time=total_duration,
                confidence=self.CONFIDENCE * 0.7,  # Lower confidence for assumed boundary
                source='llm_vision',
                metadata={'final_episode': True}
            ))

        return boundaries

    def detect_in_windows(
        self,
        file_path: str,
        search_windows: List,  # List of SearchWindow objects
        total_duration: float,
    ) -> List[Tuple[float, float, dict]]:
        """
        Find credits/outros within each search window.

        Samples frames within each window and uses LLM to identify
        credits, outros, title cards that indicate episode boundaries.

        Args:
            file_path: Path to the video file
            search_windows: List of SearchWindow objects defining where to search
            total_duration: Total file duration

        Returns:
            List of (boundary_time, confidence, metadata) tuples, one per window
        """
        from typing import Tuple

        if not self.is_available():
            logger.warning("LLM detection not available")
            return [(w.center_time, 0.3, {'source': 'llm_fallback', 'fallback': True})
                    for w in search_windows]

        results = []

        with tempfile.TemporaryDirectory(prefix='split_llm_win_') as temp_dir:
            for window in search_windows:
                # Dynamic sampling: 10 seconds normally, 1 second when logo detected
                COARSE_INTERVAL = 10  # Normal sampling interval
                FINE_INTERVAL = 1     # Fine sampling when logo detected

                logger.debug(
                    f"Analyzing window {window.start_time/60:.1f}-{window.end_time/60:.1f}m "
                    f"with dynamic sampling (coarse={COARSE_INTERVAL}s, fine={FINE_INTERVAL}s)"
                )

                # Analyze frames dynamically - switch to fine sampling on logo detection
                all_analyses = []
                current_ts = window.start_time
                in_fine_mode = False
                fine_mode_start = None

                while current_ts <= window.end_time:
                    analysis = self._analyze_timestamp(file_path, current_ts, temp_dir)
                    if analysis:
                        all_analyses.append((current_ts, analysis))
                        # Log all frames to show the full sequence including transitions
                        mode_indicator = "[FINE]" if in_fine_mode else ""
                        logger.debug(
                            f"  {mode_indicator} Frame at {current_ts/60:.1f}m: credits={analysis.is_credits}, "
                            f"outro={analysis.is_outro}, logo={analysis.is_logo}"
                        )

                        # Dynamic interval logic based on logo detection
                        if analysis.is_logo and not in_fine_mode:
                            # Logo detected - switch to fine sampling
                            in_fine_mode = True
                            fine_mode_start = current_ts
                            logger.debug(f"  -> Logo detected, switching to {FINE_INTERVAL}s sampling")
                            current_ts += FINE_INTERVAL
                        elif in_fine_mode:
                            if not analysis.is_logo:
                                # Logo no longer detected - found the transition
                                logger.debug(
                                    f"  -> Logo ended at {current_ts/60:.1f}m "
                                    f"(was in fine mode for {current_ts - fine_mode_start:.1f}s)"
                                )
                                # Stay in fine mode a bit longer to capture post-logo frames
                                # for transition detection
                                if current_ts - fine_mode_start > 10:
                                    # Been in fine mode for 5+ seconds after logo start,
                                    # and logo is gone - resume coarse
                                    in_fine_mode = False
                                    current_ts += COARSE_INTERVAL
                                else:
                                    current_ts += FINE_INTERVAL
                            else:
                                # Still seeing logo - continue fine sampling
                                current_ts += FINE_INTERVAL
                        else:
                            # No logo, not in fine mode - coarse sampling
                            current_ts += COARSE_INTERVAL
                    else:
                        # Analysis failed - continue with current interval
                        if in_fine_mode:
                            current_ts += FINE_INTERVAL
                        else:
                            current_ts += COARSE_INTERVAL

                logger.debug(f"Analyzed {len(all_analyses)} frames in window")

                if not all_analyses:
                    # No frames could be analyzed - use window center as fallback
                    logger.debug(f"No frames analyzed in window {window.start_time/60:.1f}-{window.end_time/60:.1f}m")
                    results.append((window.center_time, 0.3, {
                        'source': 'llm_fallback',
                        'window_source': window.source,
                        'fallback': True,
                    }))
                    continue

                # Find all logo positions
                logo_positions = []
                for i, (ts, analysis) in enumerate(all_analyses):
                    if analysis.is_logo:
                        logo_positions.append((i, ts))
                        logger.debug(f"  LOGO detected at {ts/60:.1f}m")

                # Find STRONG transitions: 3+ consecutive credits=True → credits=False
                # Also track logo proximity for confirmation
                best_transition = None

                # Count consecutive credits=True runs and find transitions
                i = 0
                while i < len(all_analyses):
                    ts_start, analysis_start = all_analyses[i]

                    if analysis_start.is_credits:
                        # Start of a credits run - count consecutive frames
                        run_start_idx = i
                        run_length = 1
                        logo_in_run = analysis_start.is_logo

                        # Count consecutive credits=True frames
                        j = i + 1
                        while j < len(all_analyses) and all_analyses[j][1].is_credits:
                            if all_analyses[j][1].is_logo:
                                logo_in_run = True
                            run_length += 1
                            j += 1

                        # Check if this run ends with a transition to credits=False
                        if j < len(all_analyses):
                            ts_last_credits = all_analyses[j-1][0]
                            ts_first_non_credits, analysis_after = all_analyses[j]

                            # Check if logo is on last credits frame or 1-2 frames after
                            logo_confirms = logo_in_run
                            if not logo_confirms:
                                # Check if logo is within 2 frames after transition
                                for k in range(j, min(j + 3, len(all_analyses))):
                                    if all_analyses[k][1].is_logo:
                                        logo_confirms = True
                                        break

                            # Determine transition strength
                            is_strong = run_length >= 3

                            if is_strong:
                                transition_time = (ts_last_credits + ts_first_non_credits) / 2

                                # Calculate confidence based on strength and logo confirmation
                                if logo_confirms:
                                    confidence = 0.92  # Strong run + logo = highest confidence
                                else:
                                    confidence = 0.88  # Strong run alone = high confidence

                                logger.debug(
                                    f"  STRONG TRANSITION: {run_length} frames of credits=True "
                                    f"ending at {ts_last_credits/60:.1f}m → credits=False at "
                                    f"{ts_first_non_credits/60:.1f}m (logo_confirms={logo_confirms})"
                                )

                                # Use first strong transition found
                                if best_transition is None:
                                    best_transition = {
                                        'time': transition_time,
                                        'confidence': confidence,
                                        'last_credits_ts': ts_last_credits,
                                        'first_non_credits_ts': ts_first_non_credits,
                                        'run_length': run_length,
                                        'logo_confirms': logo_confirms,
                                    }
                            else:
                                # Weak transition (1-2 frames) - log but don't use unless no strong found
                                logger.debug(
                                    f"  weak transition: {run_length} frame(s) of credits=True "
                                    f"at {ts_last_credits/60:.1f}m (ignored - too short)"
                                )

                        # Move past this run
                        i = j
                    else:
                        i += 1

                # Get logo timestamp for metadata (use last logo if multiple)
                logo_ts = logo_positions[-1][1] if logo_positions else None

                # Also look for STRONG LOGO transitions: 3+ consecutive logo=True → logo=False
                # This is an independent indicator, especially useful during fine (1s) sampling
                best_logo_transition = None
                i = 0
                while i < len(all_analyses):
                    ts_start, analysis_start = all_analyses[i]

                    if analysis_start.is_logo:
                        # Start of a logo run - count consecutive frames
                        logo_run_length = 1
                        j = i + 1
                        while j < len(all_analyses) and all_analyses[j][1].is_logo:
                            logo_run_length += 1
                            j += 1

                        # Check if this run ends with a transition to logo=False
                        if j < len(all_analyses):
                            ts_last_logo = all_analyses[j-1][0]
                            ts_first_non_logo = all_analyses[j][0]

                            # Strong logo = 3+ consecutive frames
                            is_strong_logo = logo_run_length >= 3

                            if is_strong_logo:
                                logo_transition_time = (ts_last_logo + ts_first_non_logo) / 2

                                logger.debug(
                                    f"  STRONG LOGO: {logo_run_length} consecutive frames "
                                    f"ending at {ts_last_logo/60:.1f}m → no-logo at "
                                    f"{ts_first_non_logo/60:.1f}m"
                                )

                                # Use first strong logo transition found
                                if best_logo_transition is None:
                                    best_logo_transition = {
                                        'time': logo_transition_time,
                                        'confidence': 0.90,  # High confidence for strong logo
                                        'last_logo_ts': ts_last_logo,
                                        'first_non_logo_ts': ts_first_non_logo,
                                        'logo_run_length': logo_run_length,
                                    }

                        # Move past this run
                        i = j
                    else:
                        i += 1

                if best_transition:
                    boundary_time = best_transition['time']
                    confidence = best_transition['confidence']

                    logger.debug(
                        f"Window {window.start_time/60:.1f}-{window.end_time/60:.1f}m: "
                        f"strong credits→non-credits transition at {boundary_time/60:.1f}m "
                        f"(run={best_transition['run_length']}, logo_confirms={best_transition['logo_confirms']})"
                    )

                    results.append((boundary_time, confidence, {
                        'source': 'llm_vision',
                        'window_source': window.source,
                        'credits_detected_at': best_transition['last_credits_ts'],
                        'transition_detected': True,
                        'last_credits_at': best_transition['last_credits_ts'],
                        'first_non_credits_at': best_transition['first_non_credits_ts'],
                        'credits_run_length': best_transition['run_length'],
                        'logo_detected_at': logo_ts,
                        'logo_confirms': best_transition['logo_confirms'],
                        'is_credits': True,
                        'is_outro': False,
                    }))
                elif best_logo_transition:
                    # No strong credits transition, but found strong logo transition
                    # This is a reliable boundary indicator on its own
                    boundary_time = best_logo_transition['time']
                    confidence = best_logo_transition['confidence']

                    logger.debug(
                        f"Window {window.start_time/60:.1f}-{window.end_time/60:.1f}m: "
                        f"strong logo→no-logo transition at {boundary_time/60:.1f}m "
                        f"(logo_run={best_logo_transition['logo_run_length']})"
                    )

                    results.append((boundary_time, confidence, {
                        'source': 'llm_vision',
                        'window_source': window.source,
                        'logo_transition_detected': True,
                        'last_logo_at': best_logo_transition['last_logo_ts'],
                        'first_non_logo_at': best_logo_transition['first_non_logo_ts'],
                        'logo_run_length': best_logo_transition['logo_run_length'],
                        'logo_detected_at': logo_ts,
                        'is_credits': False,
                        'is_outro': False,
                    }))
                else:
                    # No strong credits or logo transition - fall back to last credits detection
                    credit_frames = [(ts, a) for ts, a in all_analyses if a.is_credits or a.is_outro]

                    if not credit_frames:
                        # No credits at all - use window center
                        logger.debug(f"No credits detected in window {window.start_time/60:.1f}-{window.end_time/60:.1f}m")
                        results.append((window.center_time, 0.3, {
                            'source': 'llm_fallback',
                            'window_source': window.source,
                            'fallback': True,
                            'logo_detected_at': logo_ts,
                        }))
                        continue

                    # Use last credits detection (old behavior, lower confidence)
                    last_credit_ts, last_analysis = credit_frames[-1]
                    boundary_time = last_credit_ts + COARSE_INTERVAL / 2
                    boundary_time = min(boundary_time, window.end_time)
                    confidence = 0.54  # Lower confidence without strong transition

                    logger.debug(
                        f"Window {window.start_time/60:.1f}-{window.end_time/60:.1f}m: "
                        f"no strong transition found, using last credits at {last_credit_ts/60:.1f}m (lower confidence)"
                    )

                    results.append((boundary_time, confidence, {
                        'source': 'llm_vision',
                        'window_source': window.source,
                        'credits_detected_at': last_credit_ts,
                        'transition_detected': False,
                        'logo_detected_at': logo_ts,
                        'is_credits': last_analysis.is_credits,
                        'is_outro': last_analysis.is_outro,
                    }))

        return results

    def validate_boundaries(
        self,
        file_path: str,
        boundaries: List[EpisodeBoundary]
    ) -> List[EpisodeBoundary]:
        """
        Validate and refine boundaries detected by other methods.

        Analyzes frames at the proposed boundaries to confirm
        they align with visual episode markers.

        Args:
            file_path: Path to the video file
            boundaries: Boundaries from other detectors

        Returns:
            Validated and potentially adjusted boundaries
        """
        if not self.is_available() or not boundaries:
            return boundaries

        validated = []

        with tempfile.TemporaryDirectory(prefix='split_llm_val_') as temp_dir:
            for boundary in boundaries:
                # Analyze frames around the boundary end time
                analysis = self._analyze_timestamp(file_path, boundary.end_time, temp_dir)

                if analysis:
                    is_confirmed = (
                        analysis.is_credits or
                        analysis.is_outro or
                        analysis.is_title_card
                    )

                    if is_confirmed:
                        # Boost confidence
                        new_confidence = min(boundary.confidence + 0.1, 0.95)
                        validated.append(EpisodeBoundary(
                            start_time=boundary.start_time,
                            end_time=boundary.end_time,
                            confidence=new_confidence,
                            source=f"{boundary.source}+llm",
                            metadata={
                                **boundary.metadata,
                                'llm_validated': True,
                                'llm_analysis': {
                                    'is_credits': analysis.is_credits,
                                    'is_title_card': analysis.is_title_card,
                                    'is_outro': analysis.is_outro,
                                }
                            }
                        ))
                    else:
                        # Keep original but note LLM didn't confirm
                        validated.append(EpisodeBoundary(
                            start_time=boundary.start_time,
                            end_time=boundary.end_time,
                            confidence=boundary.confidence * 0.9,  # Slight penalty
                            source=boundary.source,
                            metadata={
                                **boundary.metadata,
                                'llm_validated': False,
                            }
                        ))
                else:
                    # Couldn't analyze, keep original
                    validated.append(boundary)

        return validated

    def detect_raw_in_windows(
        self,
        file_path: str,
        search_windows: List,  # List of SearchWindow objects
    ) -> List:
        """
        Return LLM TRANSITION detections as RawDetection objects.

        Instead of returning every credits=True frame (which would average
        to the middle of the credits), this detects TRANSITIONS where
        credits/logo/outro goes from True to False. The transition point
        is the actual episode boundary.

        Score is based on run length:
        - 3+ consecutive True frames before transition = strong (score = run_length * 20)
        - 1-2 frames = weak, ignored

        Args:
            file_path: Path to the video file
            search_windows: List of SearchWindow objects defining where to search

        Returns:
            List of RawDetection objects for transition points
        """
        from .raw_detection import RawDetection

        if not self.is_available():
            logger.warning("LLM detector not available for raw detection")
            return []

        all_detections = []

        with tempfile.TemporaryDirectory(prefix='split_llm_raw_') as temp_dir:
            for window in search_windows:
                # Dynamic sampling: 10 seconds normally, 1 second when logo detected
                COARSE_INTERVAL = 10
                FINE_INTERVAL = 1

                logger.debug(
                    f"LLM raw detection in window {window.start_time/60:.1f}-{window.end_time/60:.1f}m"
                )

                # First pass: collect all frame analyses for this window
                window_analyses = []
                current_ts = window.start_time
                in_fine_mode = False
                fine_mode_start = None
                current_interval = COARSE_INTERVAL

                while current_ts <= window.end_time:
                    analysis = self._analyze_timestamp(file_path, current_ts, temp_dir)

                    if analysis:
                        window_analyses.append((current_ts, analysis, current_interval))

                        # Log every frame analysis result
                        mode_indicator = "[FINE]" if in_fine_mode else ""
                        logger.debug(
                            f"  {mode_indicator} Frame at {current_ts/60:.1f}m: credits={analysis.is_credits}, "
                            f"outro={analysis.is_outro}, logo={analysis.is_logo}"
                        )

                        # Dynamic interval logic based on logo detection
                        if analysis.is_logo and not in_fine_mode:
                            in_fine_mode = True
                            fine_mode_start = current_ts
                            current_interval = FINE_INTERVAL
                            logger.debug(f"  -> Logo at {current_ts/60:.1f}m, switching to fine sampling")
                        elif in_fine_mode:
                            if not analysis.is_logo:
                                if current_ts - fine_mode_start > 10:
                                    in_fine_mode = False
                                    current_interval = COARSE_INTERVAL
                                    logger.debug(f"  -> Logo ended, resuming coarse sampling")

                        current_ts += current_interval
                    else:
                        # Analysis failed - log and continue with current interval
                        mode_indicator = "[FINE]" if in_fine_mode else ""
                        logger.debug(f"  {mode_indicator} Frame at {current_ts/60:.1f}m: ANALYSIS FAILED")
                        current_ts += current_interval

                # Second pass: find detections
                # Credits/outro: require 3+ consecutive True frames (transition detection)
                # Logo: each logo=True frame is a detection (logos are brief/intermittent)

                # Handle credits and outro - transition detection (3+ consecutive frames)
                for attr_name, source_name in [
                    ('is_credits', 'llm_credits'),
                    ('is_outro', 'llm_outro'),
                ]:
                    i = 0
                    while i < len(window_analyses):
                        ts, analysis, interval = window_analyses[i]

                        if getattr(analysis, attr_name):
                            # Start of a True run - count consecutive frames
                            run_length = 1
                            j = i + 1
                            while j < len(window_analyses) and getattr(window_analyses[j][1], attr_name):
                                run_length += 1
                                j += 1

                            # Check if this run ends with a transition to False
                            if j < len(window_analyses):
                                ts_last_true = window_analyses[j-1][0]
                                ts_first_false = window_analyses[j][0]

                                # Strong transition = 3+ consecutive True frames
                                is_strong = run_length >= 3

                                if is_strong:
                                    # Transition point is midpoint between last True and first False
                                    transition_time = (ts_last_true + ts_first_false) / 2

                                    # Score based on run length - longer runs = higher confidence
                                    score = run_length * 20

                                    all_detections.append(RawDetection(
                                        timestamp=transition_time,
                                        score=score,
                                        source=source_name,
                                        metadata={
                                            'transition': True,
                                            'run_length': run_length,
                                            'last_true_at': ts_last_true,
                                            'first_false_at': ts_first_false,
                                            'window_center': window.center_time,
                                        }
                                    ))

                                    logger.debug(
                                        f"  {source_name} TRANSITION: {run_length} frames "
                                        f"ending at {ts_last_true/60:.1f}m → False at {ts_first_false/60:.1f}m "
                                        f"= boundary at {transition_time/60:.1f}m (score={score})"
                                    )
                                else:
                                    # Weak transition (1-2 frames) - log but don't return
                                    logger.debug(
                                        f"  {source_name} weak: {run_length} frame(s) at {ts_last_true/60:.1f}m (ignored)"
                                    )

                            # Move past this run
                            i = j
                        else:
                            i += 1

                # Handle logo separately - each logo frame is a detection
                # Logos are brief and intermittent (network splashes between shows)
                # Multiple logo frames in proximity will naturally cluster together
                for ts, analysis, interval in window_analyses:
                    if analysis.is_logo:
                        # Score: 30 base, helps logos contribute to clusters
                        # Multiple nearby logos will sum together in clustering
                        score = 30

                        all_detections.append(RawDetection(
                            timestamp=ts,
                            score=score,
                            source='llm_logo',
                            metadata={
                                'sampling_interval': interval,
                                'window_center': window.center_time,
                            }
                        ))

                        logger.debug(
                            f"  llm_logo at {ts/60:.1f}m (score={score})"
                        )

        # Count by source type for logging
        credits_count = len([d for d in all_detections if d.source == 'llm_credits'])
        logo_count = len([d for d in all_detections if d.source == 'llm_logo'])
        outro_count = len([d for d in all_detections if d.source == 'llm_outro'])

        logger.info(
            f"LLM detector: {len(all_detections)} transition detections "
            f"(credits={credits_count}, logo={logo_count}, outro={outro_count})"
        )
        return all_detections

    def _scan_precision_range(
        self,
        file_path: str,
        start_time: float,
        end_time: float,
        temp_dir: str,
        interval: int = 2,
        label: str = "",
        progress_callback: Optional[callable] = None,
    ) -> Tuple[List[Tuple[float, 'FrameAnalysis']], List[float], List[float], List[Tuple[float, int]]]:
        """
        Scan a time range with precision sampling and return analysis results.

        Args:
            file_path: Path to video file
            start_time: Start of range in seconds
            end_time: End of range in seconds
            temp_dir: Temp directory for frames
            interval: Sampling interval in seconds
            label: Label for logging (e.g., "expansion_backward")
            progress_callback: Optional callback(frames_done, total_frames) for progress updates

        Returns:
            Tuple of (window_analyses, logo_timestamps, credits_timestamps, credits_transitions)
        """
        window_analyses = []
        current_ts = start_time

        # Calculate total frames for progress reporting
        total_frames = max(1, int((end_time - start_time) / interval) + 1)
        frames_done = 0

        while current_ts <= end_time:
            analysis = self._analyze_timestamp(file_path, current_ts, temp_dir)
            frames_done += 1

            # Report progress after each frame
            if progress_callback:
                try:
                    progress_callback(frames_done, total_frames)
                except Exception:
                    pass

            if analysis:
                window_analyses.append((current_ts, analysis))
                logger.debug(
                    f"  {label}Frame at {current_ts/60:.1f}m: credits={analysis.is_credits}, "
                    f"outro={analysis.is_outro}, logo={analysis.is_logo}"
                )
            else:
                logger.debug(f"  {label}Frame at {current_ts/60:.1f}m: ANALYSIS FAILED")

            current_ts += interval

        # Collect logo timestamps
        logo_timestamps = [ts for ts, a in window_analyses if a.is_logo]

        # Collect credits timestamps
        credits_timestamps = [ts for ts, a in window_analyses if a.is_credits]

        # Find credits transitions - use LAST credits=True frame as boundary
        # With 2-second intervals, we use actual frame timestamps, not midpoints
        credits_transitions = []
        i = 0
        while i < len(window_analyses):
            ts, analysis = window_analyses[i]
            if analysis.is_credits:
                j = i + 1
                while j < len(window_analyses) and window_analyses[j][1].is_credits:
                    j += 1

                if j < len(window_analyses):
                    ts_last_credits = window_analyses[j-1][0]
                    run_length = j - i
                    # Use last credits frame as the transition point
                    credits_transitions.append((ts_last_credits, run_length))
                    logger.debug(
                        f"  {label}Credits transition: {run_length} frame(s), "
                        f"last credits at {ts_last_credits/60:.1f}m"
                    )
                i = j
            else:
                i += 1

        return window_analyses, logo_timestamps, credits_timestamps, credits_transitions

    def _process_precision_detections(
        self,
        window_analyses: List[Tuple[float, 'FrameAnalysis']],
        logo_timestamps: List[float],
        credits_timestamps: List[float],
        credits_transitions: List[Tuple[float, int]],
        window_source: str,
        expansion_label: str = "",
        post_credits_buffer: int = 15,
    ) -> Optional[Tuple[float, float, dict]]:
        """
        Process precision scan results and return boundary if found.

        Args:
            window_analyses: List of (timestamp, FrameAnalysis) tuples
            logo_timestamps: List of logo detection timestamps
            credits_timestamps: List of credits detection timestamps
            credits_transitions: List of (transition_time, run_length) tuples
            window_source: Source label for the window
            expansion_label: Label if this is from expansion (for metadata)
            post_credits_buffer: Seconds after credits to include logos

        Returns:
            (boundary_time, confidence, metadata) tuple, or None if no detections
        """
        # Find the actual boundary reference from credits (if available)
        credits_boundary = None
        credits_run_length = 0
        if credits_transitions:
            best_transition = max(credits_transitions, key=lambda x: x[1])
            credits_boundary = best_transition[0]
            credits_run_length = best_transition[1]

        # Filter logos to only those relevant to THIS episode's boundary
        # With 2-second intervals, use LAST logo frame as boundary (not center)
        boundary_logos = []
        excluded_logos = []

        if logo_timestamps:
            if credits_boundary is not None:
                # Credits boundary exists - include logos at/before credits AND
                # logos immediately after (within buffer) which are the "end logo"
                boundary_logos = [ts for ts in logo_timestamps if ts <= credits_boundary + post_credits_buffer]
                excluded_logos = [ts for ts in logo_timestamps if ts > credits_boundary + post_credits_buffer]

                if excluded_logos:
                    logger.debug(
                        f"  Filtered out {len(excluded_logos)} logos (>{post_credits_buffer}s after credits) "
                        f"(likely next episode intro): {[f'{t/60:.1f}m' for t in excluded_logos]}"
                    )
            else:
                # No credits boundary - detect clumps and use only first clump
                CLUMP_GAP_THRESHOLD = 15  # seconds

                sorted_logos = sorted(logo_timestamps)
                clumps = [[sorted_logos[0]]]

                for ts in sorted_logos[1:]:
                    if ts - clumps[-1][-1] > CLUMP_GAP_THRESHOLD:
                        clumps.append([ts])
                    else:
                        clumps[-1].append(ts)

                if len(clumps) > 1:
                    boundary_logos = clumps[0]
                    excluded_logos = [ts for clump in clumps[1:] for ts in clump]
                    logger.debug(
                        f"  Found {len(clumps)} logo clumps - using first clump "
                        f"({len(boundary_logos)} logos), excluding later clumps "
                        f"({len(excluded_logos)} logos): {[f'{t/60:.1f}m' for t in excluded_logos]}"
                    )
                else:
                    boundary_logos = logo_timestamps

        if boundary_logos:
            # Use LAST logo frame as boundary (not center)
            # With 2-second intervals, we use actual frame timestamps
            boundary_time = max(boundary_logos)
            confidence = min(0.95, 0.7 + len(boundary_logos) * 0.05)

            # Slightly lower confidence for expansion results
            if expansion_label:
                confidence = confidence * 0.95

            logger.debug(
                f"  {expansion_label}LOGO-BASED: {len(boundary_logos)} logos (of {len(logo_timestamps)} total), "
                f"last logo at {boundary_time/60:.1f}m (confidence={confidence:.2f})"
            )

            return (boundary_time, confidence, {
                'source': f'llm_precision_logo{"_" + expansion_label.strip() if expansion_label else ""}',
                'window_source': window_source,
                'logo_count': len(boundary_logos),
                'logo_timestamps': boundary_logos,
                'total_logos_in_window': len(logo_timestamps),
                'excluded_logos': len(excluded_logos),
                'credits_count': len(credits_timestamps),
                'credits_boundary': credits_boundary,
                'from_expansion': bool(expansion_label),
            })

        elif credits_transitions:
            best_transition = max(credits_transitions, key=lambda x: x[1])
            boundary_time = best_transition[0]
            run_length = best_transition[1]
            confidence = min(0.90, 0.6 + run_length * 0.1)

            # Slightly lower confidence for expansion results
            if expansion_label:
                confidence = confidence * 0.95

            logger.debug(
                f"  {expansion_label}CREDITS-BASED: transition at {boundary_time/60:.1f}m "
                f"(run_length={run_length}, confidence={confidence:.2f})"
            )

            return (boundary_time, confidence, {
                'source': f'llm_precision_credits{"_" + expansion_label.strip() if expansion_label else ""}',
                'window_source': window_source,
                'credits_run_length': run_length,
                'credits_count': len(credits_timestamps),
                'from_expansion': bool(expansion_label),
            })

        return None

    def _parse_pattern(self, pattern: str) -> Tuple[List[str], int]:
        """
        Parse a boundary pattern string into a list of tokens and split index.

        Args:
            pattern: Pattern string like "c-l-c-s-l"

        Returns:
            Tuple of (tokens list without 's', split_index)
            e.g., "c-l-c-s-l" -> (['c', 'l', 'c', 'l'], 3)
        """
        # Filter out spaces and split by hyphen
        pattern = pattern.replace(' ', '').lower()
        tokens = [t for t in pattern.split('-') if t]

        # Find split point index
        split_index = -1
        tokens_without_split = []
        for i, t in enumerate(tokens):
            if t == 's':
                split_index = len(tokens_without_split)
            else:
                tokens_without_split.append(t)

        return tokens_without_split, split_index

    def _match_pattern(
        self,
        detections: List[Tuple[float, str]],  # List of (timestamp, type) where type is 'c' or 'l'
        pattern_tokens: List[str],
        split_index: int,
    ) -> Optional[float]:
        """
        Match detections against a pattern and return the split point timestamp.

        Args:
            detections: List of (timestamp, type) tuples, sorted by timestamp
            pattern_tokens: Pattern tokens without 's' (e.g., ['c', 'l', 'c', 'l'])
            split_index: Where the split point falls in the pattern

        Returns:
            Timestamp to split at, or None if no match
        """
        if not detections or not pattern_tokens:
            return None

        # Try to match the full pattern first
        if len(detections) >= len(pattern_tokens):
            # Check if detections match the pattern
            matches = True
            for i, token in enumerate(pattern_tokens):
                if i >= len(detections):
                    matches = False
                    break
                if detections[i][1] != token:
                    matches = False
                    break

            if matches:
                # Full match - split point is right before the detection at split_index
                if split_index < len(detections):
                    # Split before this detection
                    split_ts = detections[split_index][0]
                    logger.debug(
                        f"  PATTERN FULL MATCH: split before detection at {split_ts/60:.1f}m"
                    )
                    return split_ts
                else:
                    # Split is at the end
                    split_ts = detections[-1][0]
                    logger.debug(
                        f"  PATTERN FULL MATCH: split after last detection at {split_ts/60:.1f}m"
                    )
                    return split_ts

        # Partial match - find the first credits→logo transition
        # The user's logic: if we can't match the full pattern, the credits→logo
        # transition is the key boundary marker. Split before the first logo
        # that follows credits.
        prev_was_credits = False
        for ts, typ in detections:
            if typ == 'c':
                prev_was_credits = True
            elif typ == 'l' and prev_was_credits:
                # Found credits→logo transition, split before this logo
                logger.debug(
                    f"  PATTERN PARTIAL MATCH: credits→logo transition, "
                    f"split before logo at {ts/60:.1f}m"
                )
                return ts

        # No credits→logo transition found - try splitting before first logo
        for ts, typ in detections:
            if typ == 'l':
                logger.debug(
                    f"  PATTERN PARTIAL MATCH: no c→l transition, "
                    f"split before first logo at {ts/60:.1f}m"
                )
                return ts

        return None

    def detect_precision_in_windows(
        self,
        file_path: str,
        search_windows: List,  # List of SearchWindow objects (narrow windows)
        post_credits_buffer: int = 15,  # seconds to look for logos after credits
        precision_pattern: str = "",  # Pattern like "c-l-c-s-l"
        progress_callback: Optional[callable] = None,  # callback(frames_done, total_frames)
    ) -> List[Tuple[float, float, dict]]:
        """
        LLM Precision Mode: Dense sampling in narrow windows for logo-focused detection.

        This mode is designed for clean files (no commercials) where TMDB provides
        accurate runtime estimates. Uses:
        - 2-second sampling intervals (vs 10s in normal mode)
        - No fine/coarse mode switching
        - No "strong" transition requirement
        - Logo-centric split logic OR pattern matching
        - Auto-expansion when no detections found (±1.5 minutes)

        Args:
            file_path: Path to the video file
            search_windows: List of SearchWindow objects (should be narrow windows)
            post_credits_buffer: Seconds after credits to include logos (default 15)
            precision_pattern: Pattern like "c-l-c-s-l" for pattern-based matching.
                              When specified, uses pattern matching instead of buffer logic.
                              If pattern doesn't match, expands once then fails.
            progress_callback: Optional callback(frames_done, total_frames) for progress

        Returns:
            List of (boundary_time, confidence, metadata) tuples, one per window
        """
        from typing import Tuple

        if not self.is_available():
            logger.warning("LLM detection not available for precision mode")
            return [(w.center_time, 0.3, {'source': 'llm_precision_fallback', 'fallback': True})
                    for w in search_windows]

        results = []
        PRECISION_INTERVAL = 2  # 2-second sampling
        EXPANSION_DURATION = 90  # 1.5 minutes expansion in each direction

        # Parse pattern if provided
        pattern_tokens = []
        pattern_split_index = -1
        use_pattern_mode = False

        if precision_pattern:
            precision_pattern = precision_pattern.replace(' ', '').lower()
            if precision_pattern and 's' in precision_pattern:
                pattern_tokens, pattern_split_index = self._parse_pattern(precision_pattern)
                if pattern_tokens and pattern_split_index >= 0:
                    use_pattern_mode = True
                    logger.info(
                        f"Pattern mode: '{precision_pattern}' -> tokens={pattern_tokens}, "
                        f"split at index {pattern_split_index}"
                    )

        with tempfile.TemporaryDirectory(prefix='split_llm_precision_') as temp_dir:
            for window in search_windows:
                logger.debug(
                    f"LLM Precision Mode: window {window.start_time/60:.1f}-{window.end_time/60:.1f}m "
                    f"({PRECISION_INTERVAL}s intervals)"
                )

                # Primary scan of the original window
                window_analyses, logo_timestamps, credits_timestamps, credits_transitions = \
                    self._scan_precision_range(
                        file_path, window.start_time, window.end_time,
                        temp_dir, PRECISION_INTERVAL, "",
                        progress_callback=progress_callback
                    )

                logger.debug(f"  Analyzed {len(window_analyses)} frames in precision window")

                if not window_analyses:
                    logger.debug(f"  No frames analyzed - using window center as fallback")
                    results.append((window.center_time, 0.3, {
                        'source': 'llm_precision_fallback',
                        'window_source': window.source,
                        'fallback': True,
                    }))
                    continue

                # Pattern mode: extract detections and match against pattern
                if use_pattern_mode:
                    # Build detection sequence: (timestamp, type) sorted by time
                    all_detections = []
                    for ts, analysis in window_analyses:
                        if analysis.is_credits:
                            all_detections.append((ts, 'c'))
                        if analysis.is_logo:
                            all_detections.append((ts, 'l'))

                    # Sort by timestamp (should already be sorted, but ensure it)
                    all_detections.sort(key=lambda x: x[0])

                    logger.debug(
                        f"  Pattern mode: {len(all_detections)} detections in window: "
                        f"{[(f'{t/60:.1f}m', d) for t, d in all_detections]}"
                    )

                    # Try to match pattern
                    split_ts = self._match_pattern(all_detections, pattern_tokens, pattern_split_index)

                    if split_ts is not None:
                        results.append((split_ts, 0.90, {
                            'source': 'llm_precision_pattern',
                            'window_source': window.source,
                            'pattern': precision_pattern,
                            'detection_count': len(all_detections),
                        }))
                        continue

                    # Pattern didn't match in primary window - try expansion
                    logger.debug(
                        f"  Pattern did not match in primary window - expanding search"
                    )

                    # Expansion 1: BACKWARD
                    backward_start = max(0, window.start_time - EXPANSION_DURATION)
                    backward_end = window.start_time - PRECISION_INTERVAL

                    if backward_start < backward_end:
                        logger.debug(
                            f"  Pattern expansion BACKWARD: {backward_start/60:.1f}-{backward_end/60:.1f}m"
                        )

                        exp_analyses, _, _, _ = self._scan_precision_range(
                            file_path, backward_start, backward_end,
                            temp_dir, PRECISION_INTERVAL, "[PATTERN←] ",
                            progress_callback=progress_callback
                        )

                        # Combine with original window analyses
                        combined_analyses = exp_analyses + list(window_analyses)
                        combined_detections = []
                        for ts, analysis in combined_analyses:
                            if analysis.is_credits:
                                combined_detections.append((ts, 'c'))
                            if analysis.is_logo:
                                combined_detections.append((ts, 'l'))
                        combined_detections.sort(key=lambda x: x[0])

                        logger.debug(
                            f"  Combined detections after backward expansion: "
                            f"{[(f'{t/60:.1f}m', d) for t, d in combined_detections]}"
                        )

                        split_ts = self._match_pattern(combined_detections, pattern_tokens, pattern_split_index)

                        if split_ts is not None:
                            results.append((split_ts, 0.85, {
                                'source': 'llm_precision_pattern_expanded',
                                'window_source': window.source,
                                'pattern': precision_pattern,
                                'detection_count': len(combined_detections),
                                'from_expansion': True,
                            }))
                            continue

                    # Expansion 2: FORWARD
                    forward_start = window.end_time + PRECISION_INTERVAL
                    forward_end = window.end_time + EXPANSION_DURATION

                    logger.debug(
                        f"  Pattern expansion FORWARD: {forward_start/60:.1f}-{forward_end/60:.1f}m"
                    )

                    exp_analyses, _, _, _ = self._scan_precision_range(
                        file_path, forward_start, forward_end,
                        temp_dir, PRECISION_INTERVAL, "[PATTERN→] ",
                        progress_callback=progress_callback
                    )

                    # Combine all analyses
                    all_analyses = list(window_analyses) + exp_analyses
                    if backward_start < backward_end:
                        # Include backward expansion too
                        back_analyses, _, _, _ = self._scan_precision_range(
                            file_path, backward_start, backward_end,
                            temp_dir, PRECISION_INTERVAL, "",
                            progress_callback=progress_callback
                        )
                        all_analyses = back_analyses + all_analyses

                    combined_detections = []
                    for ts, analysis in all_analyses:
                        if analysis.is_credits:
                            combined_detections.append((ts, 'c'))
                        if analysis.is_logo:
                            combined_detections.append((ts, 'l'))
                    combined_detections.sort(key=lambda x: x[0])

                    logger.debug(
                        f"  Combined detections after all expansions: "
                        f"{[(f'{t/60:.1f}m', d) for t, d in combined_detections]}"
                    )

                    split_ts = self._match_pattern(combined_detections, pattern_tokens, pattern_split_index)

                    if split_ts is not None:
                        results.append((split_ts, 0.80, {
                            'source': 'llm_precision_pattern_expanded',
                            'window_source': window.source,
                            'pattern': precision_pattern,
                            'detection_count': len(combined_detections),
                            'from_expansion': True,
                        }))
                        continue

                    # Pattern mode failed - no normal mode fallback
                    logger.warning(
                        f"  PATTERN MATCH FAILED: Could not match pattern '{precision_pattern}' "
                        f"in window {window.center_time/60:.1f}m (even after expansion). "
                        f"Detections found: {[(f'{t/60:.1f}m', d) for t, d in combined_detections]}"
                    )
                    results.append((window.center_time, 0.0, {
                        'source': 'llm_precision_pattern_failed',
                        'window_source': window.source,
                        'failed': True,
                        'pattern': precision_pattern,
                        'error': f"Pattern '{precision_pattern}' did not match detections",
                        'detections_found': [(f'{t/60:.1f}m', d) for t, d in combined_detections],
                    }))
                    continue

                # Non-pattern mode: use buffer-based logic
                # Try to find boundary in primary window
                result = self._process_precision_detections(
                    window_analyses, logo_timestamps, credits_timestamps,
                    credits_transitions, window.source, "",
                    post_credits_buffer
                )

                if result:
                    results.append(result)
                    continue

                # No detections in primary window - try expansion
                logger.debug(
                    f"  NO DETECTIONS in primary window - expanding search "
                    f"(±{EXPANSION_DURATION}s)"
                )

                # Expansion 1: Search BACKWARD (cumulative errors make boundaries earlier)
                backward_start = max(0, window.start_time - EXPANSION_DURATION)
                backward_end = window.start_time - PRECISION_INTERVAL  # Don't re-scan

                if backward_start < backward_end:
                    logger.debug(
                        f"  Expanding BACKWARD: {backward_start/60:.1f}-{backward_end/60:.1f}m"
                    )

                    _, logo_ts, credits_ts, credits_trans = self._scan_precision_range(
                        file_path, backward_start, backward_end,
                        temp_dir, PRECISION_INTERVAL, "[EXPAND←] ",
                        progress_callback=progress_callback
                    )

                    result = self._process_precision_detections(
                        [], logo_ts, credits_ts, credits_trans,
                        window.source, "backward",
                        post_credits_buffer
                    )

                    if result:
                        logger.debug(f"  Found boundary in backward expansion!")
                        results.append(result)
                        continue

                # Expansion 2: Search FORWARD
                forward_start = window.end_time + PRECISION_INTERVAL  # Don't re-scan
                forward_end = window.end_time + EXPANSION_DURATION

                logger.debug(
                    f"  Expanding FORWARD: {forward_start/60:.1f}-{forward_end/60:.1f}m"
                )

                _, logo_ts, credits_ts, credits_trans = self._scan_precision_range(
                    file_path, forward_start, forward_end,
                    temp_dir, PRECISION_INTERVAL, "[EXPAND→] ",
                    progress_callback=progress_callback
                )

                result = self._process_precision_detections(
                    [], logo_ts, credits_ts, credits_trans,
                    window.source, "forward",
                    post_credits_buffer
                )

                if result:
                    logger.debug(f"  Found boundary in forward expansion!")
                    results.append(result)
                    continue

                # Still nothing after precision expansion - fall back to normal mode
                # Use 10-minute window (±5m from center) with 10-second intervals
                # Only scan the portions not already covered by precision mode
                NORMAL_INTERVAL = 10  # 10-second sampling
                NORMAL_HALF_WINDOW = 300  # 5 minutes each side

                # Calculate what we've already scanned:
                # - Primary: window.start_time to window.end_time
                # - Backward expansion: backward_start to window.start_time
                # - Forward expansion: window.end_time to forward_end
                # Already covered: backward_start to forward_end

                # For normal mode, scan the far regions not yet covered
                far_backward_start = max(0, window.center_time - NORMAL_HALF_WINDOW)
                far_backward_end = backward_start - NORMAL_INTERVAL  # Don't overlap

                far_forward_start = forward_end + NORMAL_INTERVAL  # Don't overlap
                far_forward_end = window.center_time + NORMAL_HALF_WINDOW

                logger.debug(
                    f"  Falling back to NORMAL MODE (10s intervals) for uncovered regions"
                )

                # Scan far backward region
                if far_backward_start < far_backward_end:
                    logger.debug(
                        f"  Normal mode FAR BACKWARD: {far_backward_start/60:.1f}-{far_backward_end/60:.1f}m"
                    )

                    _, logo_ts, credits_ts, credits_trans = self._scan_precision_range(
                        file_path, far_backward_start, far_backward_end,
                        temp_dir, NORMAL_INTERVAL, "[NORMAL←] ",
                        progress_callback=progress_callback
                    )

                    result = self._process_precision_detections(
                        [], logo_ts, credits_ts, credits_trans,
                        window.source, "normal_backward",
                        post_credits_buffer
                    )

                    if result:
                        logger.debug(f"  Found boundary in normal mode far backward!")
                        results.append(result)
                        continue

                # Scan far forward region
                if far_forward_start < far_forward_end:
                    logger.debug(
                        f"  Normal mode FAR FORWARD: {far_forward_start/60:.1f}-{far_forward_end/60:.1f}m"
                    )

                    _, logo_ts, credits_ts, credits_trans = self._scan_precision_range(
                        file_path, far_forward_start, far_forward_end,
                        temp_dir, NORMAL_INTERVAL, "[NORMAL→] ",
                        progress_callback=progress_callback
                    )

                    result = self._process_precision_detections(
                        [], logo_ts, credits_ts, credits_trans,
                        window.source, "normal_forward",
                        post_credits_buffer
                    )

                    if result:
                        logger.debug(f"  Found boundary in normal mode far forward!")
                        results.append(result)
                        continue

                # All detection attempts failed - return failure
                logger.warning(
                    f"  DETECTION FAILED: No transitions or logos found in window "
                    f"{window.center_time/60:.1f}m (searched ±5 minutes). "
                    f"Cannot determine reliable split point."
                )
                results.append((window.center_time, 0.0, {
                    'source': 'llm_precision_failed',
                    'window_source': window.source,
                    'failed': True,
                    'error': 'No transitions or logos found - cannot determine reliable split point',
                }))

        return results
