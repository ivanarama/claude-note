"""Worker process management for claude-note.

Provides functions to start, stop, and check status of the worker process.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

from . import config


_PID_FILE = config.STATE_DIR / "worker.pid"


def _read_pid() -> Optional[int]:
    """Read worker PID from file."""
    if not _PID_FILE.exists():
        return None
    try:
        return int(_PID_FILE.read_text().strip())
    except (ValueError, IOError):
        return None


def _write_pid(pid: int) -> None:
    """Write worker PID to file."""
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(pid))


def _remove_pid() -> None:
    """Remove worker PID file."""
    try:
        _PID_FILE.unlink()
    except FileNotFoundError:
        pass


def _is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running."""
    if sys.platform == "win32":
        # Windows: use tasklist
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
        )
        return str(pid) in result.stdout
    else:
        # Unix: use kill with signal 0
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def is_worker_running() -> bool:
    """Check if worker process is currently running."""
    pid = _read_pid()
    if pid is None:
        return False
    return _is_process_running(pid)


def start_worker(foreground: bool = False, verbose: bool = False) -> bool:
    """
    Start the worker process.

    Args:
        foreground: If True, run in foreground (for testing)
        verbose: If True, enable verbose logging

    Returns:
        True if worker was started, False if already running
    """
    if is_worker_running():
        return False

    # Build command
    cmd = [sys.executable, "-m", "claude_note.worker"]
    if foreground or verbose:
        cmd.extend(["--foreground"])
        if verbose:
            cmd.extend(["--verbose"])

    if foreground:
        # Run in foreground (blocking)
        subprocess.run(cmd)
        return True
    else:
        # Run as background process
        if sys.platform == "win32":
            # Windows: use CREATE_NEW_PROCESS_GROUP
            process = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # Unix: double fork to daemonize
            process = subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        _write_pid(process.pid)
        return True


def stop_worker() -> bool:
    """
    Stop the worker process.

    Returns:
        True if worker was stopped, False if not running
    """
    pid = _read_pid()
    if pid is None:
        return False

    if not _is_process_running(pid):
        _remove_pid()
        return False

    try:
        if sys.platform == "win32":
            # Windows: use taskkill
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        else:
            # Unix: send SIGTERM
            os.kill(pid, signal.SIGTERM)

        _remove_pid()
        return True
    except (OSError, ProcessLookupError):
        _remove_pid()
        return False


def get_worker_status() -> dict:
    """
    Get detailed worker status.

    Returns:
        Dict with keys: running, pid, uptime_seconds
    """
    pid = _read_pid()
    running = pid is not None and _is_process_running(pid)

    return {
        "running": running,
        "pid": pid if running else None,
    }
