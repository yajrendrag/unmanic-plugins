#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Boundary merger for combining detection results from multiple sources.

Merges, weighs, and validates episode boundaries detected by
different methods to produce a final set of high-confidence boundaries.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.boundary_merger")


@dataclass
class EpisodeBoundary:
    """Represents a detected episode boundary."""
    start_time: float  # seconds
    end_time: float    # seconds
    confidence: float  # 0.0 to 1.0
    source: str        # detection method name
    metadata: dict     # additional info


@dataclass
class MergedBoundary:
    """Represents a merged boundary from multiple sources."""
    start_time: float
    end_time: float
    confidence: float
    sources: List[str]
    source_boundaries: List[EpisodeBoundary]
    metadata: dict


class BoundaryMerger:
    """
    Merges episode boundaries from multiple detection methods.

    Combines boundaries that overlap or are close together,
    weights confidence based on detector reliability, and
    filters results based on configurable thresholds.

    Standalone capability is automatic based on detection type:
    - 'chapter' (true episode chapters): standalone - always reliable
    - 'silence_guided' (episode count from filename): standalone - uses known count
    - 'chapter_commercial': NOT standalone - commercial markers need confirmation
    - 'silence' (estimation-based): NOT standalone - guessing episode count
    - 'black_frame': NOT standalone - needs confirmation
    - Other methods: NOT standalone
    """

    # Default confidence weights for different detection methods
    DEFAULT_WEIGHTS = {
        'chapter': 1.0,          # Chapters are highly reliable
        'chapter_commercial': 0.7,  # Commercial markers less reliable
        'silence': 0.7,          # Silence is moderately reliable
        'silence_guided': 0.9,   # Guided silence is highly reliable
        'black_frame': 0.6,      # Black frames are less reliable alone
        'black_frame+silence': 0.85,  # Combined is more reliable
        'image_hash': 0.8,       # Image patterns are fairly reliable
        'audio_fingerprint': 0.8,
        'llm_vision': 0.9,       # LLM analysis is highly reliable
    }

    # Standalone sources - can establish boundaries without confirmation
    # These are inherent properties of the detection type, not configurable
    STANDALONE_SOURCES = {
        'chapter',         # True episode chapters are always reliable
        'silence_guided',  # Uses episode count from filename - reliable
    }

    def __init__(
        self,
        merge_threshold: float = 30.0,
        confidence_threshold: float = 0.7,
        require_multiple_detectors: bool = True,
        min_episode_length: float = 900,
        max_episode_length: float = 5400,
        weights: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize the boundary merger.

        Args:
            merge_threshold: Maximum time difference (seconds) to merge boundaries
            confidence_threshold: Minimum confidence to keep a boundary
            require_multiple_detectors: Require 2+ methods to agree (unless standalone)
            min_episode_length: Minimum episode duration in seconds
            max_episode_length: Maximum episode duration in seconds
            weights: Optional custom confidence weights by source
        """
        self.merge_threshold = merge_threshold
        self.confidence_threshold = confidence_threshold
        self.require_multiple_detectors = require_multiple_detectors
        self.min_episode_length = min_episode_length
        self.max_episode_length = max_episode_length
        self.weights = weights or self.DEFAULT_WEIGHTS

    def merge(
        self,
        all_boundaries: List[List[EpisodeBoundary]],
        total_duration: float
    ) -> List[MergedBoundary]:
        """
        Merge boundaries from multiple detection methods.

        When high-confidence sources (like chapters) disagree with lower-confidence
        sources (like silence), prioritizes the high-confidence source.

        Args:
            all_boundaries: List of boundary lists from each detector
            total_duration: Total file duration

        Returns:
            List of merged and validated boundaries
        """
        # Flatten and collect all boundaries
        flat_boundaries = []
        for boundaries in all_boundaries:
            flat_boundaries.extend(boundaries)

        if not flat_boundaries:
            logger.debug("No boundaries to merge")
            return []

        logger.info(f"Merging {len(flat_boundaries)} boundaries from {len(all_boundaries)} sources")

        # Check if we have a high-confidence primary source (chapters)
        primary_boundaries = self._get_primary_source_boundaries(all_boundaries)

        if primary_boundaries:
            # Use primary source as the base and only validate with others
            logger.debug(f"Using {len(primary_boundaries)} primary (chapter) boundaries as base")
            merged = self._merge_with_primary(primary_boundaries, all_boundaries, total_duration)
        else:
            # Standard merge: group boundaries by approximate end time
            groups = self._group_by_endpoint(flat_boundaries)

            # Merge each group
            merged = []
            for group in groups:
                merged_boundary = self._merge_group(group)
                if merged_boundary:
                    merged.append(merged_boundary)

        # Sort by start time
        merged.sort(key=lambda b: b.start_time)

        # Validate and filter
        validated = self._validate_boundaries(merged, total_duration)

        logger.info(f"Merged to {len(validated)} final boundaries")
        return validated

    def _get_primary_source_boundaries(
        self,
        all_boundaries: List[List[EpisodeBoundary]]
    ) -> Optional[List[EpisodeBoundary]]:
        """
        Check if there's a standalone source that can establish boundaries alone.

        Standalone methods are checked in order of their weight (highest first).

        Args:
            all_boundaries: List of boundary lists from each detector

        Returns:
            Primary source boundaries if found, else None
        """
        # Find all standalone sources and sort by weight
        standalone_candidates = []

        for boundaries in all_boundaries:
            if not boundaries:
                continue

            source = boundaries[0].source
            # Check if this source (or its base name) is in standalone methods
            is_standalone = self._is_standalone_source(source)

            if is_standalone:
                avg_confidence = sum(b.confidence for b in boundaries) / len(boundaries)
                weight = self.weights.get(source, 0.5)
                standalone_candidates.append((boundaries, weight * avg_confidence, source))

        if standalone_candidates:
            # Sort by weighted confidence (highest first)
            standalone_candidates.sort(key=lambda x: x[1], reverse=True)
            best = standalone_candidates[0]
            logger.debug(f"Using '{best[2]}' as primary source (standalone, score: {best[1]:.2f})")
            return best[0]

        return None

    def _is_standalone_source(self, source: str) -> bool:
        """
        Check if a source is standalone (can establish boundaries alone).

        Standalone capability is inherent to the detection type:
        - 'chapter': True episode chapters are always reliable
        - 'silence_guided': Uses known episode count from filename

        Args:
            source: The source name to check

        Returns:
            True if the source can work standalone
        """
        source_lower = source.lower()

        # Check exact match against standalone sources
        if source_lower in self.STANDALONE_SOURCES:
            return True

        # Check if source starts with any standalone source name
        for standalone in self.STANDALONE_SOURCES:
            if source_lower.startswith(standalone):
                return True

        return False

    def _merge_with_primary(
        self,
        primary_boundaries: List[EpisodeBoundary],
        all_boundaries: List[List[EpisodeBoundary]],
        total_duration: float
    ) -> List[MergedBoundary]:
        """
        Merge using a primary source as the base.

        Other sources are used to validate/boost confidence but don't create
        new boundaries that conflict with the primary source.

        Args:
            primary_boundaries: Boundaries from the primary source
            all_boundaries: All boundary lists
            total_duration: Total file duration

        Returns:
            List of merged boundaries
        """
        # Collect all non-primary boundaries
        other_boundaries = []
        for boundaries in all_boundaries:
            if boundaries != primary_boundaries:
                other_boundaries.extend(boundaries)

        merged = []

        for primary in primary_boundaries:
            # Find other boundaries that align with this primary boundary
            aligned = []
            for other in other_boundaries:
                # Check if the end times are close
                if abs(other.end_time - primary.end_time) <= self.merge_threshold:
                    aligned.append(other)

            # Create merged boundary
            sources = [primary.source]
            total_confidence = primary.confidence * self.weights.get(primary.source, 1.0)
            total_weight = self.weights.get(primary.source, 1.0)

            for other in aligned:
                weight = self.weights.get(other.source, 0.5)
                total_confidence += other.confidence * weight
                total_weight += weight
                if other.source not in sources:
                    sources.append(other.source)

            final_confidence = total_confidence / total_weight if total_weight > 0 else primary.confidence

            # Boost for multiple agreeing sources
            if len(sources) >= 2:
                final_confidence = min(final_confidence * 1.05, 0.95)

            merged.append(MergedBoundary(
                start_time=primary.start_time,
                end_time=primary.end_time,
                confidence=final_confidence,
                sources=sources,
                source_boundaries=[primary] + aligned,
                metadata={primary.source: primary.metadata}
            ))

        return merged

    def _group_by_endpoint(
        self,
        boundaries: List[EpisodeBoundary]
    ) -> List[List[EpisodeBoundary]]:
        """
        Group boundaries that have similar end times.

        Args:
            boundaries: List of all boundaries

        Returns:
            List of boundary groups
        """
        if not boundaries:
            return []

        # Sort by end time
        sorted_boundaries = sorted(boundaries, key=lambda b: b.end_time)

        groups = []
        current_group = [sorted_boundaries[0]]

        for boundary in sorted_boundaries[1:]:
            # Check if this boundary is close to the current group
            group_end = sum(b.end_time for b in current_group) / len(current_group)

            if abs(boundary.end_time - group_end) <= self.merge_threshold:
                current_group.append(boundary)
            else:
                # Start a new group
                groups.append(current_group)
                current_group = [boundary]

        # Add the last group
        groups.append(current_group)

        return groups

    def _merge_group(self, group: List[EpisodeBoundary]) -> Optional[MergedBoundary]:
        """
        Merge a group of overlapping boundaries.

        Args:
            group: List of boundaries in the group

        Returns:
            Merged boundary or None if invalid
        """
        if not group:
            return None

        # Collect unique sources
        sources = list(set(b.source for b in group))

        # Check multi-detector requirement
        if self.require_multiple_detectors and len(sources) < 2:
            # Exception: standalone methods are reliable enough alone
            has_standalone = any(self._is_standalone_source(s) for s in sources)
            if not has_standalone:
                logger.debug(f"Skipping boundary at {group[0].end_time:.1f}s: only one detector")
                return None

        # Calculate weighted average times
        total_weight = 0
        weighted_start = 0
        weighted_end = 0
        weighted_confidence = 0

        for boundary in group:
            weight = self.weights.get(boundary.source, 0.5) * boundary.confidence
            total_weight += weight
            weighted_start += boundary.start_time * weight
            weighted_end += boundary.end_time * weight
            weighted_confidence += boundary.confidence * weight

        if total_weight == 0:
            return None

        start_time = weighted_start / total_weight
        end_time = weighted_end / total_weight
        confidence = weighted_confidence / total_weight

        # Boost confidence for multiple agreeing detectors
        if len(sources) >= 2:
            confidence = min(confidence * 1.1, 0.95)
        if len(sources) >= 3:
            confidence = min(confidence * 1.1, 0.98)

        # Collect metadata
        combined_metadata = {}
        for boundary in group:
            combined_metadata[boundary.source] = boundary.metadata

        return MergedBoundary(
            start_time=start_time,
            end_time=end_time,
            confidence=confidence,
            sources=sources,
            source_boundaries=group,
            metadata=combined_metadata
        )

    def _validate_boundaries(
        self,
        merged: List[MergedBoundary],
        total_duration: float
    ) -> List[MergedBoundary]:
        """
        Validate merged boundaries for duration constraints.

        Args:
            merged: List of merged boundaries
            total_duration: Total file duration

        Returns:
            Validated list of boundaries
        """
        if not merged:
            return []

        validated = []
        prev_end = 0.0

        for boundary in merged:
            # Check confidence threshold
            if boundary.confidence < self.confidence_threshold:
                logger.debug(
                    f"Skipping boundary at {boundary.end_time:.1f}s: "
                    f"confidence {boundary.confidence:.2f} below threshold"
                )
                continue

            # Calculate episode duration
            episode_duration = boundary.end_time - boundary.start_time

            # Check duration constraints
            if episode_duration < self.min_episode_length:
                logger.debug(
                    f"Skipping boundary at {boundary.end_time:.1f}s: "
                    f"episode too short ({episode_duration:.1f}s)"
                )
                continue

            if episode_duration > self.max_episode_length:
                logger.warning(
                    f"Episode at {boundary.start_time:.1f}s is longer than max "
                    f"({episode_duration:.1f}s > {self.max_episode_length}s)"
                )
                # Still include but note the warning

            # Adjust start time to match previous end
            adjusted_boundary = MergedBoundary(
                start_time=prev_end,
                end_time=boundary.end_time,
                confidence=boundary.confidence,
                sources=boundary.sources,
                source_boundaries=boundary.source_boundaries,
                metadata=boundary.metadata
            )

            validated.append(adjusted_boundary)
            prev_end = boundary.end_time

        # Add final episode if there's remaining duration
        if validated and total_duration - prev_end >= self.min_episode_length:
            final_boundary = MergedBoundary(
                start_time=prev_end,
                end_time=total_duration,
                confidence=validated[-1].confidence * 0.9,  # Slightly lower confidence
                sources=['inferred'],
                source_boundaries=[],
                metadata={'final_episode': True, 'inferred': True}
            )
            validated.append(final_boundary)

        return validated

    def to_episode_list(
        self,
        merged_boundaries: List[MergedBoundary]
    ) -> List[Dict]:
        """
        Convert merged boundaries to a simple episode list.

        Args:
            merged_boundaries: List of merged boundaries

        Returns:
            List of episode dictionaries with start, end, confidence
        """
        episodes = []

        for i, boundary in enumerate(merged_boundaries):
            episodes.append({
                'episode_number': i + 1,
                'start_time': boundary.start_time,
                'end_time': boundary.end_time,
                'duration': boundary.end_time - boundary.start_time,
                'confidence': boundary.confidence,
                'sources': boundary.sources,
            })

        return episodes

    def get_split_points(
        self,
        merged_boundaries: List[MergedBoundary]
    ) -> List[Tuple[float, float]]:
        """
        Get split points for FFmpeg extraction.

        Args:
            merged_boundaries: List of merged boundaries

        Returns:
            List of (start_time, duration) tuples for each episode
        """
        split_points = []

        for boundary in merged_boundaries:
            duration = boundary.end_time - boundary.start_time
            split_points.append((boundary.start_time, duration))

        return split_points
