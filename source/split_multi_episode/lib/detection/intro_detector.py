#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Intro/outro sequence detection for episode boundary identification.

Uses GPU-accelerated frame extraction and perceptual hashing to find
recurring intro sequences (title cards, theme music visuals, credits)
that indicate episode boundaries.

Also uses Chromaprint audio fingerprinting to detect recurring theme
music patterns.
"""

import logging
import os
import subprocess
import tempfile
import json
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Set
from collections import defaultdict

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.intro_detector")

# Optional imports
try:
    from PIL import Image
    import imagehash
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False
    logger.warning("imagehash/Pillow not available - visual intro detection disabled")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# Check for Chromaprint (fpcalc command)
def _check_chromaprint_available() -> bool:
    """Check if fpcalc (Chromaprint) is available."""
    try:
        result = subprocess.run(
            ['fpcalc', '-version'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

CHROMAPRINT_AVAILABLE = _check_chromaprint_available()
if not CHROMAPRINT_AVAILABLE:
    logger.warning("Chromaprint (fpcalc) not available - audio fingerprinting disabled")


@dataclass
class FrameSignature:
    """Multi-hash signature for a video frame."""
    timestamp: float
    phash: str          # Perceptual hash
    dhash: str          # Difference hash
    colorhash: str      # Color histogram hash
    frame_path: str     # Path to extracted frame


@dataclass
class AudioSignature:
    """Chromaprint audio fingerprint for an audio segment."""
    timestamp: float
    duration: float
    fingerprint: List[int]  # Raw fingerprint as list of integers
    fingerprint_raw: str    # Base64 encoded raw fingerprint


@dataclass
class RegionSignature:
    """Combined video and audio signatures for a region."""
    region_start: float
    frames: List[FrameSignature]
    audio: Optional[AudioSignature] = None


@dataclass
class IntroSequence:
    """A detected intro/outro sequence."""
    start_offset: float      # Offset from episode start
    duration: float          # Sequence duration
    signature_frames: List[FrameSignature]
    occurrences: List[float]  # Timestamps where this sequence appears
    confidence: float
    audio_match: bool = False  # Whether audio fingerprints also matched
    video_match: bool = False  # Whether video hashes matched


@dataclass
class EpisodeBoundary:
    """Represents a detected episode boundary."""
    start_time: float
    end_time: float
    confidence: float
    source: str
    metadata: dict = field(default_factory=dict)


class IntroDetector:
    """
    Detects episode boundaries by finding recurring intro/outro sequences.

    Strategy:
    1. Extract frames from potential episode start regions (using GPU if available)
    2. Compute multi-hash signatures for each frame
    3. Extract audio fingerprints using Chromaprint for each region
    4. Find sequences of frames/audio that repeat at regular intervals
    5. Use these sequences to identify episode boundaries
    """

    CONFIDENCE = 0.85

    def __init__(
        self,
        intro_search_duration: float = 180.0,  # Search first 3 minutes
        outro_search_duration: float = 120.0,   # Search last 2 minutes
        frame_interval: float = 2.0,            # Extract frames every 2 seconds
        hash_threshold: int = 12,               # Max hamming distance for match
        min_sequence_matches: int = 3,          # Minimum matching frames for sequence
        min_episode_length: float = 900,        # 15 minutes
        max_episode_length: float = 5400,       # 90 minutes
        use_gpu: bool = True,
        enable_audio: bool = True,              # Enable audio fingerprinting
        audio_segment_duration: float = 60.0,   # Audio segment length for fingerprinting
        audio_similarity_threshold: float = 0.4,  # Min Chromaprint similarity (0-1)
    ):
        """
        Initialize the intro detector.

        Args:
            intro_search_duration: Duration at start to search for intros
            outro_search_duration: Duration at end to search for outros
            frame_interval: Interval between frame extractions
            hash_threshold: Maximum hamming distance for hash match
            min_sequence_matches: Minimum matching frames to consider a sequence
            min_episode_length: Minimum episode duration
            max_episode_length: Maximum episode duration
            use_gpu: Whether to use GPU for frame extraction
            enable_audio: Whether to use audio fingerprinting
            audio_segment_duration: Duration of audio to fingerprint at each region
            audio_similarity_threshold: Minimum similarity for audio match (0-1)
        """
        self.intro_search_duration = intro_search_duration
        self.outro_search_duration = outro_search_duration
        self.frame_interval = frame_interval
        self.hash_threshold = hash_threshold
        self.min_sequence_matches = min_sequence_matches
        self.min_episode_length = min_episode_length
        self.max_episode_length = max_episode_length
        self.use_gpu = use_gpu
        self.enable_audio = enable_audio
        self.audio_segment_duration = audio_segment_duration
        self.audio_similarity_threshold = audio_similarity_threshold
        self._gpu_available = None

    def is_available(self) -> bool:
        """Check if at least one detection method is available."""
        return IMAGEHASH_AVAILABLE or CHROMAPRINT_AVAILABLE

    def video_available(self) -> bool:
        """Check if video/image hashing is available."""
        return IMAGEHASH_AVAILABLE

    def audio_available(self) -> bool:
        """Check if audio fingerprinting is available."""
        return CHROMAPRINT_AVAILABLE and self.enable_audio

    def _check_gpu_available(self) -> bool:
        """Check if NVIDIA GPU decoding is available in FFmpeg."""
        if self._gpu_available is not None:
            return self._gpu_available

        try:
            result = subprocess.run(
                ['ffmpeg', '-hwaccels'],
                capture_output=True,
                text=True,
                timeout=10
            )
            self._gpu_available = 'cuda' in result.stdout.lower() or 'nvdec' in result.stdout.lower()
        except Exception:
            self._gpu_available = False

        logger.debug(f"GPU decoding available: {self._gpu_available}")
        return self._gpu_available

    def detect(
        self,
        file_path: str,
        total_duration: float,
        candidate_boundaries: Optional[List[float]] = None,
        expected_episode_count: Optional[int] = None
    ) -> List[EpisodeBoundary]:
        """
        Detect episode boundaries from recurring intro/outro patterns.

        Uses both video (perceptual hashing) and audio (Chromaprint fingerprinting)
        to find recurring intro sequences.

        Args:
            file_path: Path to the video file
            total_duration: Total duration in seconds
            candidate_boundaries: Optional pre-detected boundary timestamps
            expected_episode_count: Optional expected number of episodes

        Returns:
            List of EpisodeBoundary objects
        """
        if not self.is_available():
            logger.warning("Intro detection not available (missing dependencies)")
            return []

        # Log available detection methods
        methods = []
        if self.video_available():
            methods.append("video")
        if self.audio_available():
            methods.append("audio")
        logger.info(f"Starting intro sequence detection (methods: {', '.join(methods)})")

        with tempfile.TemporaryDirectory(prefix='split_intro_') as temp_dir:
            # Determine search regions
            if candidate_boundaries:
                search_regions = self._get_search_regions_from_candidates(
                    candidate_boundaries, total_duration
                )
            else:
                search_regions = self._estimate_search_regions(
                    total_duration, expected_episode_count
                )

            logger.info(f"Searching {len(search_regions)} potential episode start regions")

            # Extract video and audio signatures from each region
            region_signatures: Dict[float, RegionSignature] = {}
            for i, (region_start, region_end) in enumerate(search_regions):
                logger.debug(f"Processing region {i+1}: {region_start:.1f}s - {region_end:.1f}s")

                # Extract video frame signatures
                frame_signatures = []
                if self.video_available():
                    frame_signatures = self._extract_region_signatures(
                        file_path, region_start, region_end, temp_dir, i
                    )

                # Extract audio fingerprint
                audio_signature = None
                if self.audio_available():
                    audio_signature = self._extract_audio_signature(
                        file_path, region_start,
                        min(self.audio_segment_duration, region_end - region_start),
                        temp_dir, i
                    )

                if frame_signatures or audio_signature:
                    region_signatures[region_start] = RegionSignature(
                        region_start=region_start,
                        frames=frame_signatures,
                        audio=audio_signature
                    )

            if len(region_signatures) < 2:
                logger.debug("Not enough regions with signatures for comparison")
                return []

            # Find recurring sequences across regions (combining video and audio)
            intro_sequences = self._find_recurring_sequences_combined(region_signatures)

            if not intro_sequences:
                logger.debug("No recurring intro sequences found")
                return []

            logger.info(f"Found {len(intro_sequences)} recurring intro sequence(s)")

            # Convert sequences to boundaries
            boundaries = self._sequences_to_boundaries(
                intro_sequences, total_duration
            )

            return boundaries

    def _get_search_regions_from_candidates(
        self,
        candidate_boundaries: List[float],
        total_duration: float
    ) -> List[Tuple[float, float]]:
        """
        Create search regions around candidate boundary timestamps.
        """
        regions = []

        # Add region at file start
        regions.append((0, min(self.intro_search_duration, total_duration)))

        # Add regions after each candidate boundary
        for boundary in sorted(candidate_boundaries):
            if boundary > 0:
                region_start = boundary
                region_end = min(boundary + self.intro_search_duration, total_duration)
                if region_end - region_start >= 30:  # At least 30 seconds
                    regions.append((region_start, region_end))

        return regions

    def _estimate_search_regions(
        self,
        total_duration: float,
        expected_episode_count: Optional[int] = None
    ) -> List[Tuple[float, float]]:
        """
        Estimate search regions when no candidate boundaries are provided.
        """
        # Estimate episode count if not provided
        if expected_episode_count is None:
            avg_length = (self.min_episode_length + self.max_episode_length) / 2
            expected_episode_count = max(2, round(total_duration / avg_length))

        episode_length = total_duration / expected_episode_count
        regions = []

        for i in range(expected_episode_count):
            region_start = i * episode_length
            region_end = min(region_start + self.intro_search_duration, total_duration)
            regions.append((region_start, region_end))

        return regions

    def _extract_region_signatures(
        self,
        file_path: str,
        start_time: float,
        end_time: float,
        temp_dir: str,
        region_id: int
    ) -> List[FrameSignature]:
        """
        Extract frames from a region and compute multi-hash signatures.
        """
        signatures = []
        duration = end_time - start_time

        # Calculate frame timestamps
        timestamps = []
        current = 0.0
        while current < duration:
            timestamps.append(start_time + current)
            current += self.frame_interval

        # Build FFmpeg command for batch extraction
        use_gpu = self.use_gpu and self._check_gpu_available()

        for i, ts in enumerate(timestamps):
            frame_path = os.path.join(temp_dir, f'region{region_id}_frame{i:04d}.jpg')

            # Build FFmpeg command
            cmd = ['ffmpeg', '-y']

            # Add GPU decoding if available
            if use_gpu:
                cmd.extend(['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda'])

            cmd.extend([
                '-ss', str(ts),
                '-i', file_path,
                '-vframes', '1',
                '-q:v', '2',
            ])

            # Add scale filter to speed up hashing
            if use_gpu:
                cmd.extend(['-vf', 'scale_cuda=320:180,hwdownload,format=nv12'])
            else:
                cmd.extend(['-vf', 'scale=320:180'])

            cmd.append(frame_path)

            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=30
                )

                if os.path.exists(frame_path):
                    sig = self._compute_frame_signature(frame_path, ts)
                    if sig:
                        signatures.append(sig)
            except subprocess.TimeoutExpired:
                logger.debug(f"Frame extraction timed out at {ts}s")
            except Exception as e:
                logger.debug(f"Frame extraction failed at {ts}s: {e}")

        return signatures

    def _compute_frame_signature(
        self,
        frame_path: str,
        timestamp: float
    ) -> Optional[FrameSignature]:
        """
        Compute multi-hash signature for a frame.
        """
        try:
            img = Image.open(frame_path)

            # Compute multiple hash types for robust matching
            phash = str(imagehash.phash(img))
            dhash = str(imagehash.dhash(img))

            # Color hash - good for detecting title cards with specific colors
            try:
                colorhash = str(imagehash.colorhash(img))
            except Exception:
                colorhash = ""

            return FrameSignature(
                timestamp=timestamp,
                phash=phash,
                dhash=dhash,
                colorhash=colorhash,
                frame_path=frame_path
            )
        except Exception as e:
            logger.debug(f"Failed to compute signature for {frame_path}: {e}")
            return None

    def _extract_audio_signature(
        self,
        file_path: str,
        start_time: float,
        duration: float,
        temp_dir: str,
        region_id: int
    ) -> Optional[AudioSignature]:
        """
        Extract audio and compute Chromaprint fingerprint for a region.

        Args:
            file_path: Path to the video file
            start_time: Start time in seconds
            duration: Duration of audio to extract
            temp_dir: Temporary directory for audio files
            region_id: Region identifier

        Returns:
            AudioSignature with Chromaprint fingerprint, or None on error
        """
        if not CHROMAPRINT_AVAILABLE:
            return None

        audio_path = os.path.join(temp_dir, f'audio_region{region_id}.wav')

        try:
            # Extract audio segment using FFmpeg
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(start_time),
                '-i', file_path,
                '-t', str(duration),
                '-vn',              # No video
                '-ac', '1',         # Mono
                '-ar', '22050',     # Sample rate (Chromaprint default)
                '-acodec', 'pcm_s16le',
                audio_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=60
            )

            if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                logger.debug(f"Failed to extract audio for region {region_id}")
                return None

            # Generate Chromaprint fingerprint using fpcalc
            fp_cmd = [
                'fpcalc',
                '-raw',          # Output raw fingerprint integers
                '-json',         # JSON output
                '-length', str(int(duration)),
                audio_path
            ]

            fp_result = subprocess.run(
                fp_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if fp_result.returncode != 0:
                logger.debug(f"fpcalc failed for region {region_id}: {fp_result.stderr}")
                return None

            # Parse JSON output
            fp_data = json.loads(fp_result.stdout)
            fingerprint = fp_data.get('fingerprint', [])
            fingerprint_raw = fp_data.get('fingerprint', '')

            if not fingerprint:
                logger.debug(f"Empty fingerprint for region {region_id}")
                return None

            # Handle different output formats from fpcalc
            if isinstance(fingerprint, str):
                # fpcalc with -raw returns a comma-separated string
                fingerprint_raw = fingerprint
                fingerprint = [int(x) for x in fingerprint.split(',') if x.strip()]
            elif isinstance(fingerprint, list):
                fingerprint_raw = ','.join(str(x) for x in fingerprint)

            logger.debug(f"Got fingerprint for region {region_id}: {len(fingerprint)} samples")

            return AudioSignature(
                timestamp=start_time,
                duration=duration,
                fingerprint=fingerprint,
                fingerprint_raw=fingerprint_raw
            )

        except subprocess.TimeoutExpired:
            logger.debug(f"Audio extraction timed out for region {region_id}")
            return None
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse fpcalc output for region {region_id}: {e}")
            return None
        except Exception as e:
            logger.debug(f"Audio fingerprinting failed for region {region_id}: {e}")
            return None
        finally:
            # Clean up audio file
            if os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception:
                    pass

    def _compare_audio_signatures(
        self,
        sig1: AudioSignature,
        sig2: AudioSignature
    ) -> float:
        """
        Compare two Chromaprint audio fingerprints.

        Uses bit-level comparison of the fingerprint integers to compute
        similarity score.

        Args:
            sig1: First audio signature
            sig2: Second audio signature

        Returns:
            Similarity score from 0.0 to 1.0
        """
        if not sig1.fingerprint or not sig2.fingerprint:
            return 0.0

        fp1 = sig1.fingerprint
        fp2 = sig2.fingerprint

        # Compare overlapping portions
        min_len = min(len(fp1), len(fp2))
        if min_len == 0:
            return 0.0

        # Count matching bits using popcount (Hamming distance)
        total_bits = 0
        matching_bits = 0

        for i in range(min_len):
            # XOR to find differing bits
            diff = fp1[i] ^ fp2[i]
            # Count set bits (differing bits)
            diff_count = bin(diff & 0xFFFFFFFF).count('1')
            matching_bits += 32 - diff_count
            total_bits += 32

        similarity = matching_bits / total_bits if total_bits > 0 else 0.0

        return similarity

    def _find_recurring_sequences_combined(
        self,
        region_signatures: Dict[float, RegionSignature]
    ) -> List[IntroSequence]:
        """
        Find recurring sequences using both video and audio signatures.

        Combines video frame matching with audio fingerprint matching
        for more robust intro detection.

        Args:
            region_signatures: Dict mapping region start times to RegionSignature

        Returns:
            List of IntroSequence objects
        """
        if len(region_signatures) < 2:
            return []

        regions = sorted(region_signatures.keys())

        # First, check for audio matches between regions
        audio_matches: Dict[Tuple[float, float], float] = {}
        for i, r1 in enumerate(regions):
            sig1 = region_signatures[r1]
            if not sig1.audio:
                continue

            for r2 in regions[i + 1:]:
                sig2 = region_signatures[r2]
                if not sig2.audio:
                    continue

                similarity = self._compare_audio_signatures(sig1.audio, sig2.audio)
                if similarity >= self.audio_similarity_threshold:
                    audio_matches[(r1, r2)] = similarity
                    logger.debug(
                        f"Audio match between regions {r1:.1f}s and {r2:.1f}s: "
                        f"{similarity:.2%} similarity"
                    )

        # If we have strong audio matches, use those to boost confidence
        audio_matched_regions = set()
        for (r1, r2), sim in audio_matches.items():
            audio_matched_regions.add(r1)
            audio_matched_regions.add(r2)

        if audio_matched_regions:
            logger.info(
                f"Audio fingerprints matched in {len(audio_matched_regions)} regions"
            )

        # Now find video matches (using existing frame-based logic)
        # but boost confidence for regions that also have audio matches
        video_sequences = self._find_recurring_sequences_video(region_signatures)

        # If we found both video and audio matches, combine them
        if video_sequences and audio_matched_regions:
            for seq in video_sequences:
                # Check if this sequence's occurrences overlap with audio matches
                audio_overlap = len(set(seq.occurrences) & audio_matched_regions)
                if audio_overlap >= 2:
                    # Boost confidence and mark as dual-matched
                    seq.confidence = min(0.98, seq.confidence + 0.15)
                    seq.audio_match = True
                    seq.video_match = True
                    logger.info(
                        f"Intro sequence confirmed by both video and audio "
                        f"(confidence: {seq.confidence:.2f})"
                    )

        # If no video matches but we have audio matches, create sequences from audio
        if not video_sequences and len(audio_matched_regions) >= 2:
            logger.info("Creating intro sequences from audio matches alone")
            audio_sequences = self._create_sequences_from_audio_matches(
                audio_matches, region_signatures
            )
            return audio_sequences

        return video_sequences

    def _find_recurring_sequences_video(
        self,
        region_signatures: Dict[float, RegionSignature]
    ) -> List[IntroSequence]:
        """
        Find recurring video frame sequences (original algorithm).

        Args:
            region_signatures: Dict mapping region start times to RegionSignature

        Returns:
            List of IntroSequence objects
        """
        # Convert to the format expected by the original algorithm
        frame_signatures: Dict[float, List[FrameSignature]] = {}
        for region_start, reg_sig in region_signatures.items():
            if reg_sig.frames:
                frame_signatures[region_start] = reg_sig.frames

        if len(frame_signatures) < 2:
            return []

        return self._find_recurring_sequences(frame_signatures)

    def _create_sequences_from_audio_matches(
        self,
        audio_matches: Dict[Tuple[float, float], float],
        region_signatures: Dict[float, RegionSignature]
    ) -> List[IntroSequence]:
        """
        Create IntroSequence objects from audio-only matches.

        Args:
            audio_matches: Dict of (region1, region2) -> similarity
            region_signatures: All region signatures

        Returns:
            List of IntroSequence objects
        """
        if not audio_matches:
            return []

        # Find the best set of matching regions
        # Group by similar intervals to find consistent episode lengths
        interval_groups: Dict[int, List[Tuple[float, float, float]]] = defaultdict(list)

        for (r1, r2), similarity in audio_matches.items():
            interval = int(r2 - r1)
            bucket = (interval // 60) * 60  # Round to nearest minute
            interval_groups[bucket].append((r1, r2, similarity))

        if not interval_groups:
            return []

        # Find the most common interval
        best_interval = max(interval_groups.keys(), key=lambda k: len(interval_groups[k]))
        best_matches = interval_groups[best_interval]

        # Collect all regions involved
        all_regions = set()
        total_similarity = 0.0
        for r1, r2, sim in best_matches:
            all_regions.add(r1)
            all_regions.add(r2)
            total_similarity += sim

        avg_similarity = total_similarity / len(best_matches) if best_matches else 0

        # Create a single IntroSequence representing the audio-matched intro
        occurrences = sorted(all_regions)

        # Use audio duration as sequence duration
        audio_duration = self.audio_segment_duration
        for region in occurrences:
            if region_signatures[region].audio:
                audio_duration = region_signatures[region].audio.duration
                break

        sequence = IntroSequence(
            start_offset=0,  # Intro at start of episode
            duration=audio_duration,
            signature_frames=[],  # No video frames
            occurrences=occurrences,
            confidence=min(0.90, 0.7 + avg_similarity * 0.2),
            audio_match=True,
            video_match=False
        )

        return [sequence]

    def _find_recurring_sequences(
        self,
        region_signatures: Dict[float, List[FrameSignature]]
    ) -> List[IntroSequence]:
        """
        Find frame sequences that appear in multiple regions.

        This is the core algorithm that identifies intro sequences by
        finding similar frame patterns across potential episode starts.
        """
        if len(region_signatures) < 2:
            return []

        regions = sorted(region_signatures.keys())
        first_region = regions[0]
        first_sigs = region_signatures[first_region]

        # For each frame in the first region, check if similar frames
        # exist at similar offsets in other regions
        matching_sequences = []

        for i, sig1 in enumerate(first_sigs):
            offset_from_start = sig1.timestamp - first_region

            # Track how many other regions have matching frames at this offset
            matches_by_region = {first_region: sig1}

            for other_region in regions[1:]:
                other_sigs = region_signatures[other_region]

                # Find best matching frame at similar offset
                best_match = None
                best_similarity = 0

                for sig2 in other_sigs:
                    other_offset = sig2.timestamp - other_region

                    # Check if offsets are similar (within 5 seconds)
                    if abs(other_offset - offset_from_start) > 5.0:
                        continue

                    # Compare hashes
                    similarity = self._compare_signatures(sig1, sig2)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = sig2

                if best_match and best_similarity >= 0.7:  # 70% similarity threshold
                    matches_by_region[other_region] = best_match

            # If this frame matches in at least half the regions, it's significant
            match_ratio = len(matches_by_region) / len(regions)
            if match_ratio >= 0.5 and len(matches_by_region) >= 2:
                matching_sequences.append({
                    'offset': offset_from_start,
                    'matches': matches_by_region,
                    'match_ratio': match_ratio,
                    'reference_sig': sig1
                })

        # Merge consecutive matching frames into sequences
        intro_sequences = self._merge_to_sequences(matching_sequences, regions)

        return intro_sequences

    def _compare_signatures(self, sig1: FrameSignature, sig2: FrameSignature) -> float:
        """
        Compare two frame signatures and return similarity score (0-1).
        """
        try:
            # Compare perceptual hashes
            phash1 = imagehash.hex_to_hash(sig1.phash)
            phash2 = imagehash.hex_to_hash(sig2.phash)
            phash_dist = phash1 - phash2
            phash_sim = 1.0 - (phash_dist / 64.0)

            # Compare difference hashes
            dhash1 = imagehash.hex_to_hash(sig1.dhash)
            dhash2 = imagehash.hex_to_hash(sig2.dhash)
            dhash_dist = dhash1 - dhash2
            dhash_sim = 1.0 - (dhash_dist / 64.0)

            # Weighted average (phash is generally more reliable)
            similarity = (phash_sim * 0.6) + (dhash_sim * 0.4)

            # Bonus for color hash match
            if sig1.colorhash and sig2.colorhash:
                try:
                    chash1 = imagehash.hex_to_hash(sig1.colorhash)
                    chash2 = imagehash.hex_to_hash(sig2.colorhash)
                    chash_dist = chash1 - chash2
                    if chash_dist <= 5:  # Close color match
                        similarity = min(1.0, similarity + 0.1)
                except Exception:
                    pass

            return max(0.0, similarity)
        except Exception as e:
            logger.debug(f"Signature comparison error: {e}")
            return 0.0

    def _merge_to_sequences(
        self,
        matching_sequences: List[dict],
        regions: List[float]
    ) -> List[IntroSequence]:
        """
        Merge individual matching frames into coherent sequences.
        """
        if not matching_sequences:
            return []

        # Sort by offset
        matching_sequences.sort(key=lambda x: x['offset'])

        # Group consecutive matches into sequences
        sequences = []
        current_sequence = [matching_sequences[0]]

        for match in matching_sequences[1:]:
            prev_offset = current_sequence[-1]['offset']
            curr_offset = match['offset']

            # If within frame_interval * 1.5, consider it part of same sequence
            if curr_offset - prev_offset <= self.frame_interval * 1.5:
                current_sequence.append(match)
            else:
                # Save current sequence if long enough
                if len(current_sequence) >= self.min_sequence_matches:
                    seq = self._create_intro_sequence(current_sequence, regions)
                    if seq:
                        sequences.append(seq)
                current_sequence = [match]

        # Don't forget the last sequence
        if len(current_sequence) >= self.min_sequence_matches:
            seq = self._create_intro_sequence(current_sequence, regions)
            if seq:
                sequences.append(seq)

        return sequences

    def _create_intro_sequence(
        self,
        matches: List[dict],
        regions: List[float]
    ) -> Optional[IntroSequence]:
        """
        Create an IntroSequence from a list of matching frames.
        """
        if not matches:
            return None

        start_offset = matches[0]['offset']
        end_offset = matches[-1]['offset'] + self.frame_interval
        duration = end_offset - start_offset

        # Get all region timestamps where this sequence appears
        occurrences = set()
        for match in matches:
            occurrences.update(match['matches'].keys())

        # Calculate average match ratio
        avg_ratio = sum(m['match_ratio'] for m in matches) / len(matches)

        # Confidence based on match ratio and number of matching frames
        confidence = min(0.95, avg_ratio * (1 + len(matches) / 20))

        return IntroSequence(
            start_offset=start_offset,
            duration=duration,
            signature_frames=[m['reference_sig'] for m in matches],
            occurrences=sorted(occurrences),
            confidence=confidence
        )

    def _sequences_to_boundaries(
        self,
        intro_sequences: List[IntroSequence],
        total_duration: float
    ) -> List[EpisodeBoundary]:
        """
        Convert detected intro sequences to episode boundaries.
        """
        if not intro_sequences:
            return []

        # Use the sequence with highest confidence
        best_sequence = max(intro_sequences, key=lambda s: s.confidence * len(s.occurrences))

        logger.info(
            f"Using intro sequence: offset={best_sequence.start_offset:.1f}s, "
            f"duration={best_sequence.duration:.1f}s, "
            f"found in {len(best_sequence.occurrences)} regions"
        )

        boundaries = []
        occurrences = sorted(best_sequence.occurrences)

        for i, occurrence in enumerate(occurrences):
            # Episode starts at the occurrence (start of intro)
            # Adjust by intro offset to get actual episode start
            episode_start = occurrence

            # Episode ends at the next occurrence or at file end
            if i + 1 < len(occurrences):
                episode_end = occurrences[i + 1]
            else:
                episode_end = total_duration

            episode_duration = episode_end - episode_start

            # Validate duration
            if episode_duration < self.min_episode_length * 0.8:
                logger.debug(f"Skipping short episode: {episode_duration:.1f}s")
                continue

            boundaries.append(EpisodeBoundary(
                start_time=episode_start,
                end_time=episode_end,
                confidence=best_sequence.confidence,
                source='intro_sequence',
                metadata={
                    'intro_offset': best_sequence.start_offset,
                    'intro_duration': best_sequence.duration,
                    'matching_frames': len(best_sequence.signature_frames),
                }
            ))

        logger.info(f"Detected {len(boundaries)} episode boundaries from intro sequences")
        return boundaries

    def validate_with_intro(
        self,
        file_path: str,
        boundaries: List[EpisodeBoundary]
    ) -> List[EpisodeBoundary]:
        """
        Validate boundaries by checking for intro sequences at each.

        Args:
            file_path: Path to the video file
            boundaries: Boundaries from other detectors

        Returns:
            Validated boundaries with confidence adjustments
        """
        if not self.is_available() or len(boundaries) < 2:
            return boundaries

        candidate_times = [b.start_time for b in boundaries]
        total_duration = boundaries[-1].end_time

        with tempfile.TemporaryDirectory(prefix='split_intro_val_') as temp_dir:
            # Extract signatures from each boundary start
            region_sigs = {}
            for i, boundary in enumerate(boundaries):
                sigs = self._extract_region_signatures(
                    file_path,
                    boundary.start_time,
                    min(boundary.start_time + 60, total_duration),  # First minute
                    temp_dir,
                    i
                )
                if sigs:
                    region_sigs[boundary.start_time] = sigs

            # Check for matching patterns
            if len(region_sigs) >= 2:
                intro_seqs = self._find_recurring_sequences(region_sigs)

                if intro_seqs:
                    best_seq = max(intro_seqs, key=lambda s: s.confidence)
                    confirmed_starts = set(best_seq.occurrences)

                    # Adjust confidence for boundaries
                    validated = []
                    for boundary in boundaries:
                        if boundary.start_time in confirmed_starts:
                            # Boost confidence for confirmed boundaries
                            new_conf = min(0.95, boundary.confidence + 0.1)
                            validated.append(EpisodeBoundary(
                                start_time=boundary.start_time,
                                end_time=boundary.end_time,
                                confidence=new_conf,
                                source=f"{boundary.source}+intro",
                                metadata={
                                    **boundary.metadata,
                                    'intro_validated': True,
                                }
                            ))
                        else:
                            validated.append(boundary)

                    return validated

        return boundaries
