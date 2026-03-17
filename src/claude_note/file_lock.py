"""Cross-platform file locking.

For Windows: Uses simple mutex-like approach with directory creation.
For Unix: Uses fcntl.flock
"""

import os
import sys
import time
import tempfile
from contextlib import contextmanager
from pathlib import Path

if sys.platform != "win32":
    import fcntl


@contextmanager
def file_lock(lock_file: Path, timeout: float = 30.0, exclusive: bool = True):
    """
    Cross-platform file locking context manager.

    Args:
        lock_file: Path to lock file
        timeout: Seconds to wait for lock
        exclusive: True for exclusive lock (ignored on Windows)

    Yields:
        True if lock acquired

    Raises:
        TimeoutError: If lock cannot be acquired within timeout
    """
    if sys.platform == "win32":
        # Windows: Use directory-based locking (atomic mkdir)
        lock_dir = lock_file.parent / f"{lock_file.name}.lockdir"
        acquired = False
        start_time = time.time()

        try:
            while time.time() - start_time < timeout:
                try:
                    lock_dir.mkdir(exist_ok=False)
                    acquired = True
                    break
                except FileExistsError:
                    # Check if lock is stale (older than timeout)
                    if lock_dir.exists():
                        stat = lock_dir.stat()
                        if time.time() - stat.st_mtime > timeout:
                            try:
                                lock_dir.rmdir()
                            except OSError:
                                pass
                            continue
                    time.sleep(0.1)

            if not acquired:
                raise TimeoutError(f"Could not acquire lock for {lock_file}")

            yield

        finally:
            if acquired:
                try:
                    lock_dir.rmdir()
                except OSError:
                    pass
    else:
        # Unix: Use fcntl.flock
        lock_file.parent.mkdir(parents=True, exist_ok=True)

        fd = None
        acquired = False
        start_time = time.time()

        try:
            fd = os.open(str(lock_file), os.O_WRONLY | os.O_CREAT, 0o644)

            while time.time() - start_time < timeout:
                try:
                    lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
                    fcntl.flock(fd, lock_type | fcntl.LOCK_NB)
                    acquired = True
                    break
                except BlockingIOError:
                    time.sleep(0.1)

            if not acquired:
                raise TimeoutError(f"Could not acquire lock for {lock_file}")

            yield

        finally:
            if fd is not None:
                if acquired:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
