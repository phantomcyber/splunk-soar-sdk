import os
import sys
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator


@contextmanager
def add_to_path(path: Path) -> Iterator[None]:
    """
    Add the path to sys.path temporarily
    """
    original_sys_path = sys.path[:]
    sys.path.insert(0, path.as_posix())  # Insert at the start for priority
    try:
        yield
    finally:
        # Restore the original sys.path after the context
        sys.path = original_sys_path


@contextmanager
def context_directory(path: Path) -> Iterator[None]:
    """
    Temporarily change the current working directory and add it to path
    as if the code inside was running directly from the given path.
    """
    original_dir = Path.cwd().as_posix()
    try:
        os.chdir(path.as_posix())
        with add_to_path(Path.cwd().parent):
            yield
    finally:
        os.chdir(original_dir)
