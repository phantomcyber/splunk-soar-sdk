import os
import sys
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator


@contextmanager
def add_to_path(path: Path) -> Iterator[None]:
    """Temporarily add the given path to the head of sys.path.

    .. note:
        Any changes made to sys.path outside of this function will be reverted when this
        context manager exits.
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
    """Temporarily change the current directory and add it to path.

    This context manager effectively makes it as if the code inside was running directly
    from the given path.
    """
    original_dir = Path.cwd().as_posix()
    try:
        os.chdir(path.as_posix())
        with add_to_path(Path.cwd().parent):
            yield
    finally:
        os.chdir(original_dir)


def relative_to_cwd(path: Path) -> str:
    """Reinterpret the given path as relative to the current working directory."""
    return path.relative_to(Path.cwd()).as_posix()
