#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Progress tracking utility for multi-method detection pipeline.

Provides progress tracking across multiple detection methods,
with support for both worker_log output and GUI gauge via PluginChildProcess.
"""

import json
import logging
import os
import tempfile
from typing import Callable, List, Optional, Dict, Any

logger = logging.getLogger("Unmanic.Plugin.split_multi_episode.progress")


class ProgressTracker:
    """
    Tracks progress across multiple detection methods.

    Can output status updates to worker_log and/or push progress
    to a queue for GUI gauge display via PluginChildProcess.
    """

    def __init__(
        self,
        worker_log: Optional[List[str]] = None,
        progress_queue: Optional[object] = None,
        log_queue: Optional[object] = None
    ):
        """
        Initialize progress tracker.

        Args:
            worker_log: List to append status messages to (direct mode)
            progress_queue: Queue to push progress updates to (child process mode)
            log_queue: Queue to push log messages to (child process mode)
        """
        self.worker_log = worker_log
        self.progress_queue = progress_queue
        self.log_queue = log_queue
        self.methods: List[str] = []
        self.completed_methods: int = 0
        self.current_method: Optional[str] = None
        self._total_windows: int = 1
        self._completed_windows: int = 0
        self._sub_progress: float = 0.0  # Progress within current window (0.0 to 1.0)

    def set_methods(self, method_names: List[str]):
        """Set the list of enabled detection methods."""
        self.methods = method_names
        self.completed_methods = 0
        self.log(f"Detection: {len(method_names)} methods enabled: {', '.join(method_names)}")

    def start_method(self, name: str, total_windows: int = 1):
        """Mark a method as starting."""
        self.current_method = name
        self._total_windows = total_windows
        self._completed_windows = 0
        method_idx = self.methods.index(name) + 1 if name in self.methods else 0
        self.log(f"[{method_idx}/{len(self.methods)}] Running {name}...")
        self._emit_progress()

    def update_window_progress(self, completed_windows: int):
        """Update progress within current method based on windows completed."""
        logger.debug(f"update_window_progress: {completed_windows}/{self._total_windows}")
        self._completed_windows = completed_windows
        self._sub_progress = 0.0  # Reset sub-progress when window completes
        # Always log window progress for precision mode visibility
        if self.current_method:
            percent = int((completed_windows / self._total_windows) * 100) if self._total_windows > 0 else 0
            self.log(f"  {self.current_method}: window {completed_windows}/{self._total_windows} ({percent}%)")
        self._emit_progress()

    def update_sub_progress(self, fraction: float):
        """Update progress within current window (0.0 to 1.0)."""
        self._sub_progress = max(0.0, min(1.0, fraction))
        self._emit_progress()

    def complete_method(self):
        """Mark current method as complete."""
        self.completed_methods += 1
        method_name = self.current_method
        self.current_method = None
        if method_name:
            pct = int((self.completed_methods / len(self.methods)) * 100) if self.methods else 0
            self.log(f"  {method_name} complete ({pct}% of detection done)")
        self._emit_progress()

    def log(self, message: str):
        """Add a message to the worker log."""
        if self.worker_log is not None:
            self.worker_log.append(message)
        if self.log_queue is not None:
            try:
                self.log_queue.put(message)
            except Exception:
                pass

    def _emit_progress(self):
        """Calculate and emit overall progress."""
        import sys

        if not self.methods:
            logger.debug("_emit_progress: no methods set, skipping")
            return

        # Calculate: (completed_methods + current_method_progress) / total_methods
        # Include sub-progress within current window
        current_progress = 0.0
        if self.current_method and self._total_windows > 0:
            current_progress = (self._completed_windows + self._sub_progress) / self._total_windows

        overall = (self.completed_methods + current_progress) / len(self.methods)
        percent = int(overall * 100)

        # Debug to stderr (visible in unmanic logs)
        print(
            f"[PROGRESS DEBUG] {percent}% "
            f"(windows={self._completed_windows}/{self._total_windows}, "
            f"sub={self._sub_progress:.2f}, "
            f"queue={self.progress_queue is not None})",
            file=sys.stderr, flush=True
        )

        if self.progress_queue is not None:
            try:
                self.progress_queue.put(percent)
            except Exception as e:
                print(f"[PROGRESS ERROR] Failed to put on queue: {e}", file=sys.stderr, flush=True)

    def get_overall_progress(self) -> int:
        """Get current overall progress (0-100)."""
        if not self.methods:
            return 0
        current_progress = 0.0
        if self.current_method and self._total_windows > 0:
            current_progress = self._completed_windows / self._total_windows
        overall = (self.completed_methods + current_progress) / len(self.methods)
        return int(overall * 100)


def run_detection_in_child_process(
    data: Dict[str, Any],
    detection_func: Callable,
    detection_args: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Run the detection function in a child process with GUI progress reporting.

    Uses Unmanic's PluginChildProcess to show progress in the GUI gauge.
    Results are passed back via a temp JSON file.

    Args:
        data: The data dict from on_worker_process (needed for PluginChildProcess)
        detection_func: Function that performs detection.
                       Signature: (args_dict, progress_tracker) -> dict
                       Should return a dict of results
        detection_args: Dict of arguments to pass to detection_func

    Returns:
        Dict of detection results, or None if failed
    """
    try:
        from unmanic.libs.unplugins.child_process import PluginChildProcess
        HAS_CHILD_PROCESS = True
    except ImportError:
        HAS_CHILD_PROCESS = False
        logger.warning("PluginChildProcess not available")

    if not HAS_CHILD_PROCESS:
        # Fall back to running in main process (no GUI gauge)
        logger.info("Running detection in main process (no GUI gauge)")
        tracker = ProgressTracker(worker_log=data.get('worker_log', []))
        return detection_func(detection_args, tracker)

    # Create temp file for results
    result_fd, result_path = tempfile.mkstemp(suffix='.json', prefix='split_detection_')
    os.close(result_fd)

    # Serialize detection_args to JSON for child process
    args_fd, args_path = tempfile.mkstemp(suffix='.json', prefix='split_args_')
    os.close(args_fd)
    with open(args_path, 'w') as f:
        json.dump(detection_args, f)

    # Note: We do NOT set our own command_progress_parser here.
    # Unmanic's worker provides a default parser that's bound to the subprocess monitor.
    # When PluginChildProcess drains prog_queue and calls parser(str(pct)),
    # the default parser updates monitor.subprocess_percent which the GUI reads.
    # If we overwrite the parser with our own function, it won't have access to the monitor.

    # Create child process
    proc = PluginChildProcess(plugin_id="split_multi_episode", data=data)

    def child_work(log_queue, prog_queue):
        """Work function that runs in child process."""
        try:
            # Read args from temp file
            with open(args_path, 'r') as f:
                args = json.load(f)

            # Create progress tracker with queues
            tracker = ProgressTracker(
                progress_queue=prog_queue,
                log_queue=log_queue
            )

            # Run detection
            result = detection_func(args, tracker)

            # Write results to temp file
            if result:
                with open(result_path, 'w') as f:
                    json.dump(result, f)
            else:
                with open(result_path, 'w') as f:
                    json.dump({'_empty': True}, f)

        except Exception as e:
            import traceback
            error_msg = f"Detection error: {e}\n{traceback.format_exc()}"
            log_queue.put(f"ERROR: {error_msg}")
            with open(result_path, 'w') as f:
                json.dump({'_error': str(e)}, f)

    # Run detection in child process
    logger.info("Starting detection in child process...")
    success = proc.run(child_work)
    logger.info(f"Child process completed, success={success}")

    # Read results from temp file
    result = None
    try:
        if os.path.exists(result_path):
            with open(result_path, 'r') as f:
                result = json.load(f)

            if '_error' in result:
                logger.error(f"Detection failed in child process: {result['_error']}")
                result = None
            elif '_empty' in result:
                result = {}
    except Exception as e:
        logger.error(f"Failed to read detection results: {e}")
    finally:
        # Clean up temp files
        for path in [result_path, args_path]:
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except Exception:
                pass

    return result
