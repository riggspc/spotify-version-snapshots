import os
import sys
import fcntl
from pathlib import Path
from contextlib import contextmanager
from spotify_snapshot.logging import get_colorized_logger

logger = get_colorized_logger()


class ProcessLockError(Exception):
    """Raised when unable to acquire process lock"""

    pass


class LockFile:
    """Handles process lock file operations"""

    def __init__(self, lock_dir: Path = Path("/tmp")):
        self.lock_dir = lock_dir

    def get_lock_path(self, name: str) -> Path:
        """Get the full path for a lock file"""
        return self.lock_dir / f".{name}.lock"

    @contextmanager
    def acquire(self, name: str = "spotify-snapshot"):
        """
        Acquire a process lock.

        Args:
            name: Name of the lock file (will be prefixed with '.')

        Raises:
            ProcessLockError: If another instance is already running
        """
        lock_path = self.get_lock_path(name)
        lock_file = None

        try:
            lock_file = open(lock_path, "w")
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                lock_file.close()
                logger.error(
                    f"Another instance is already running. Remove {lock_path} to override."
                )
                exit(1)

            yield

        except IOError as e:
            logger.error(f"Error acquiring lock file: {e}")
            exit(1)

        finally:
            if lock_file is not None and not lock_file.closed:
                try:
                    fcntl.flock(lock_file, fcntl.LOCK_UN)
                    lock_file.close()
                    lock_path.unlink(missing_ok=True)
                except Exception as e:
                    # Log error but don't raise
                    logger.error(f"Error cleaning up lock file: {e}")
                    exit(1)

    def remove(self, name: str) -> bool:
        """
        Remove a process lock file if it exists.

        Args:
            name: Name of the lock file (will be prefixed with '.')

        Returns:
            bool: True if the lock file was removed, False if it didn't exist
        """
        return self.get_lock_path(name).unlink(missing_ok=True)


# Create default instance
process_lock = LockFile()
