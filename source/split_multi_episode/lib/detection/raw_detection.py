#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Raw detection types and clustering logic for episode boundary detection.

This module implements the raw clustering architecture where:
1. Each detector returns ALL raw detections (not just "best" per window)
2. Detections are clustered by timestamp across all detectors
3. Clusters are scored by agreement, diversity, and proximity
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.raw_detection")


@dataclass
class RawDetection:
    """
    A single raw detection from any detector.

    Attributes:
        timestamp: Detection time in seconds
        score: Weight/importance of this detection (higher = more significant)
        source: Detector type (e.g., 'black_frame', 'llm_credits', 'llm_logo')
        metadata: Additional information about the detection
    """
    timestamp: float
    score: float
    source: str
    metadata: dict = field(default_factory=dict)

    def __repr__(self):
        return f"RawDetection({self.timestamp/60:.1f}m, score={self.score:.1f}, source={self.source})"


@dataclass
class DetectionCluster:
    """
    A cluster of nearby detections from potentially multiple detectors.

    Attributes:
        detections: List of RawDetection objects in this cluster
        center_time: Weighted center timestamp of the cluster
        total_score: Combined score of all detections
        sources: Set of unique detector sources in this cluster
    """
    detections: List[RawDetection]
    center_time: float = 0.0
    total_score: float = 0.0
    sources: set = field(default_factory=set)

    def __post_init__(self):
        if self.detections:
            self._calculate_metrics()

    def _calculate_metrics(self):
        """Calculate cluster metrics from detections."""
        if not self.detections:
            return

        # Weighted center (weighted by score)
        total_weight = sum(d.score for d in self.detections)
        if total_weight > 0:
            self.center_time = sum(d.timestamp * d.score for d in self.detections) / total_weight
        else:
            self.center_time = sum(d.timestamp for d in self.detections) / len(self.detections)

        # Total score
        self.total_score = sum(d.score for d in self.detections)

        # Unique sources
        self.sources = set(d.source for d in self.detections)

    def add_detection(self, detection: RawDetection):
        """Add a detection to the cluster and recalculate metrics."""
        self.detections.append(detection)
        self._calculate_metrics()

    @property
    def num_detectors(self) -> int:
        """Number of unique detector types in this cluster."""
        return len(self.sources)

    @property
    def spread(self) -> float:
        """Time spread of detections in seconds."""
        if len(self.detections) < 2:
            return 0.0
        timestamps = [d.timestamp for d in self.detections]
        return max(timestamps) - min(timestamps)

    def final_score(self, diversity_weight: float = 1.5, proximity_weight: float = 0.1) -> float:
        """
        Calculate final cluster score with bonuses.

        Args:
            diversity_weight: Multiplier bonus per unique detector type
            proximity_weight: Penalty factor for spread (tighter = better)

        Returns:
            Final weighted score
        """
        # Base score from detections
        score = self.total_score

        # Diversity bonus: more different detector types = higher confidence
        # Using exponential bonus for multiple sources
        if self.num_detectors > 1:
            diversity_bonus = diversity_weight ** (self.num_detectors - 1)
            score *= diversity_bonus

        # Proximity bonus: tighter clusters are more reliable
        # Small penalty for spread
        if self.spread > 0:
            proximity_penalty = 1.0 / (1.0 + proximity_weight * self.spread)
            score *= proximity_penalty

        return score

    def __repr__(self):
        return (f"DetectionCluster(center={self.center_time/60:.1f}m, "
                f"score={self.total_score:.1f}, sources={self.sources}, "
                f"final={self.final_score():.1f})")


class RawDetectionClusterer:
    """
    Clusters raw detections from multiple detectors.
    """

    def __init__(
        self,
        cluster_tolerance: float = 60.0,  # seconds
        diversity_weight: float = 1.5,
        proximity_weight: float = 0.1,
    ):
        """
        Initialize the clusterer.

        Args:
            cluster_tolerance: Maximum time difference to consider detections
                as belonging to the same cluster (seconds)
            diversity_weight: Bonus multiplier for each unique detector type
            proximity_weight: Penalty factor for cluster spread
        """
        self.cluster_tolerance = cluster_tolerance
        self.diversity_weight = diversity_weight
        self.proximity_weight = proximity_weight

    def cluster_detections(
        self,
        detections: List[RawDetection],
        window_start: float = None,
        window_end: float = None,
    ) -> List[DetectionCluster]:
        """
        Cluster detections by timestamp proximity.

        Args:
            detections: List of raw detections to cluster
            window_start: Optional start time to filter detections
            window_end: Optional end time to filter detections

        Returns:
            List of DetectionCluster objects, sorted by final score descending
        """
        if not detections:
            return []

        # Debug: show timestamp range of all detections
        all_timestamps = [d.timestamp for d in detections]
        logger.debug(
            f"Clustering: {len(detections)} total detections, "
            f"timestamp range: {min(all_timestamps)/60:.1f}-{max(all_timestamps)/60:.1f}m"
        )
        if window_start is not None and window_end is not None:
            logger.debug(
                f"Window filter: {window_start/60:.1f}-{window_end/60:.1f}m"
            )

        # Filter to window if specified
        filtered = detections
        if window_start is not None:
            filtered = [d for d in filtered if d.timestamp >= window_start]
        if window_end is not None:
            filtered = [d for d in filtered if d.timestamp <= window_end]

        logger.debug(f"After filtering: {len(filtered)} detections in window")

        if not filtered:
            # Debug: show some sample timestamps that didn't match
            sample = detections[:5]
            logger.debug(f"Sample timestamps: {[f'{d.timestamp/60:.1f}m' for d in sample]}")
            return []

        # Sort by timestamp
        sorted_detections = sorted(filtered, key=lambda d: d.timestamp)

        # Build clusters using greedy approach
        clusters = []
        used = set()

        for i, detection in enumerate(sorted_detections):
            if i in used:
                continue

            # Start a new cluster
            cluster = DetectionCluster(detections=[detection])
            used.add(i)

            # Add nearby detections to this cluster
            for j, other in enumerate(sorted_detections):
                if j in used:
                    continue

                # Check if within tolerance of cluster center
                if abs(other.timestamp - cluster.center_time) <= self.cluster_tolerance:
                    cluster.add_detection(other)
                    used.add(j)

            # Add completed cluster to list
            clusters.append(cluster)

        # Sort clusters by final score (descending)
        clusters.sort(key=lambda c: c.final_score(self.diversity_weight, self.proximity_weight), reverse=True)

        return clusters

    def get_best_boundary(
        self,
        detections: List[RawDetection],
        window_start: float = None,
        window_end: float = None,
    ) -> Optional[Tuple[float, float, Dict]]:
        """
        Get the best boundary from clustered detections.

        Args:
            detections: List of raw detections
            window_start: Optional window start time
            window_end: Optional window end time

        Returns:
            Tuple of (timestamp, confidence, metadata) or None
        """
        clusters = self.cluster_detections(detections, window_start, window_end)

        if not clusters:
            return None

        best = clusters[0]

        # Convert final score to confidence (0-1 range)
        # Using sigmoid-like mapping
        final_score = best.final_score(self.diversity_weight, self.proximity_weight)
        confidence = min(0.95, final_score / (final_score + 50))  # Normalize to 0-0.95

        metadata = {
            'cluster_score': final_score,
            'num_detections': len(best.detections),
            'num_detectors': best.num_detectors,
            'sources': list(best.sources),
            'spread': best.spread,
            'detections': [(d.timestamp, d.score, d.source) for d in best.detections],
        }

        logger.debug(
            f"Best cluster: {best.center_time/60:.1f}m, "
            f"score={final_score:.1f}, sources={best.sources}, "
            f"confidence={confidence:.2f}"
        )

        return (best.center_time, confidence, metadata)
