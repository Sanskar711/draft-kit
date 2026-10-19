"""One companion per data directory, using native Windows or POSIX locks."""
import errno
import os
from pathlib import Path


class AlreadyRunning(RuntimeError):
    pass


class ProcessLock:
    def __init__(self, path: Path):
        self.fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if os.name == "nt":
                import msvcrt

                # Lock byte zero even in an empty file. Never truncate, write
                # or delete the shared file while another process uses it.
                msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            os.close(self.fd)
            self.fd = None
            if error.errno in (errno.EACCES, errno.EAGAIN):
                raise AlreadyRunning("A companion already uses this data directory.") from None
            raise

    def close(self):
        if self.fd is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(self.fd, 0, os.SEEK_SET)
                msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
