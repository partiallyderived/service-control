import os
import shutil

from collections.abc import Iterator
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from typing import Any


def _rm_prompts(force: bool, path: str) -> bool:
    return not force and os.path.exists(path) and not os.access(path, os.W_OK)


def ls_recursive(path: str) -> Iterator[str]:
    if os.path.isfile(path):
        yield path
    else:
        for pth in os.listdir(path):
            yield from ls_recursive(os.path.join(path, pth))
        yield path


def replace(src: str, dest: str) -> bool:
    existed = rm(dest, recursive=True, force=True)
    os.rename(src, dest)
    return existed


def rm(path: str, recursive: bool = False, force: bool = False) -> bool:
    if recursive:
        if force:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except FileNotFoundError:
                return False
        else:
            num_write_protected = 0
            num_not_write_protected = 0
            for pth in ls_recursive(path):
                if os.access(pth, os.W_OK):
                    num_not_write_protected += 1
                    if os.path.isdir(path):
                        os.rmdir(path)
                    else:
                        # If the file does not exist os.remove raise the
                        # FileNotFoundError instead of us.
                        os.remove(path)
                else:
                    num_write_protected += 1
            if num_write_protected:
                s_maybe1 = 's' if num_write_protected != 1 else ''
                s_maybe2 = 's' if num_not_write_protected != 1 else ''
                raise PermissionError(
                    f'Refusing to remove {num_write_protected} write-protected '
                    f'file{s_maybe1} (use force=True to delete anyway).\n'
                    f'Note: {num_not_write_protected} non-protected'
                    f'file{s_maybe2} were removed.'
                )
    elif not force and os.path.exists(path) and not os.access(path, os.W_OK):
        raise PermissionError(
            f'Refusing to remove write-protected file {path} (use force=True '
            f'to delete anyway).'
        )
    else:
        # If path is a directory or it does not exist, let os.remove raise the
        # IsADirectoryError or FileNotFoundError respectively.
        try:
            os.remove(path)
        except FileNotFoundError:
            if force:
                return False
            raise
    return True


def swap(path1: str, path2: str) -> None:
    with temp_file_path() as temp_path:
        os.remove(temp_path)
        # May result in FileNotFoundError, let it propagate if so.
        os.rename(path1, temp_path)
        try:
            os.rename(path2, path1)
        except FileNotFoundError:
            # Try to undo what we did.
            os.rename(temp_path, path1)
            raise
        os.rename(temp_path, path2)


@contextmanager
def temp_file_path(*args: Any, delete: bool = True, **kwargs: Any) -> str:
    """Creates a temporary file and returns an absolute path to it. This differs
    from ``tempfile.NamedTemporaryFile`` in that, when ``delete`` is ``True``
    (the default), the file is not deleted when it is closed, but instead after
    this context manager exits. Any ``FileNotFoundError`` raised when trying to
    remove the file when exiting is ignored.

    :param args: Positional arguments to pass to
        ``tempfile.NamedTemporaryFile``.
    :param delete: If ``True``, deletes the file after this context manager
        exits. Defaults to ``True``.
    :param kwargs: Keyword arguments to pass to ``tempfile.NamedTemporaryFile``.
    :return: Path to the created file. This file is not open for writing.
    """
    temp = NamedTemporaryFile(*args, **kwargs, delete=False)
    temp.close()
    try:
        yield temp.name
    finally:
        if delete:
            try:
                os.remove(temp.name)
            except FileNotFoundError:
                pass
