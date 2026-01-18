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

Respond in this exact format:
CREDITS: YES/NO
TITLE_CARD: YES/NO
PREVIOUSLY_ON: YES/NO
INTRO: YES/NO
OUTRO: YES/NO
CONFIDENCE: HIGH/MEDIUM/LOW"""

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        model: str = "llava:7b-v1.6-mistral-q4_K_M",
        frames_per_boundary: int = 5,
        min_episode_length: float = 900,
        max_episode_length: float = 5400,
    ):
        """
        Initialize the LLM detector.

        Args:
            ollama_host: Ollama API endpoint
            model: Vision model to use
            frames_per_boundary: Number of frames to analyze per potential boundary
            min_episode_length: Minimum episode duration in seconds
            max_episode_length: Maximum episode duration in seconds
        """
        self.ollama_host = ollama_host
        self.model = model
        self.frames_per_boundary = frames_per_boundary
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

        if not frames:
            return None

        # Analyze the middle frame (or first available)
        frame_to_analyze = frames[len(frames) // 2] if len(frames) > 1 else frames[0]

        try:
            response = self._query_llm(frame_to_analyze)
            if response:
                return self._parse_response(timestamp, response)
        except Exception as e:
            logger.debug(f"LLM analysis failed for timestamp {timestamp}: {e}")

        return None

    def _query_llm(self, frame_path: str) -> Optional[str]:
        """
        Query the LLM with a frame image.

        Args:
            frame_path: Path to the frame image

        Returns:
            LLM response text or None on error
        """
        # Read and encode the image
        with open(frame_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        # Try using ollama library first
        if OLLAMA_AVAILABLE:
            try:
                client = ollama.Client(host=self.ollama_host)
                response = client.generate(
                    model=self.model,
                    prompt=self.DEFAULT_PROMPT,
                    images=[image_data],
                )
                return response.get('response', '')
            except Exception as e:
                logger.debug(f"Ollama library failed: {e}")

        # Fall back to REST API
        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": self.DEFAULT_PROMPT,
                    "images": [image_data],
                    "stream": False,
                },
                timeout=60
            )

            if response.status_code == 200:
                return response.json().get('response', '')

        except Exception as e:
            logger.debug(f"Ollama REST API failed: {e}")

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
                analysis.is_outro
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
