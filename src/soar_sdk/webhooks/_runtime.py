__lazy_modules__ = {
    "collections.abc",
    "contextlib",
    "ctypes",
    "os",
    "sys",
    "tempfile",
    "threading",
}

import ctypes
import os
import sys
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager

_STDOUT_LOCK = threading.RLock()


@contextmanager
def capture_native_stdout() -> Iterator[None]:
    """Keep native webhook output out of the platform's JSON response channel."""
    # AppInterface redirects Python streams, but native extensions write to FD 1.
    # Serialize SDK webhook calls because descriptor redirection is process-wide.
    with _STDOUT_LOCK, tempfile.TemporaryFile(mode="w+b") as captured:
        libc = ctypes.CDLL(None)
        sys.stdout.flush()
        libc.fflush(None)
        saved_fd = os.dup(1)
        try:
            os.dup2(captured.fileno(), 1)
            yield
        finally:
            try:
                sys.stdout.flush()
                libc.fflush(None)
            finally:
                os.dup2(saved_fd, 1)
                os.close(saved_fd)
            captured_bytes = captured.tell()
            if captured_bytes:
                # AppInterface records Python stderr in app_interface.log.
                # Never log native output, which may contain secrets.
                sys.stderr.write(
                    f"Captured {captured_bytes} bytes of native stdout during webhook execution.\n"
                )
