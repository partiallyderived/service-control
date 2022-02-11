import traceback
from collections.abc import Callable
from types import ModuleType

import enough
from enough import T


# noinspection PyUnresolvedReferences
class ServiceControlError(Exception):
    """Base class of all exceptions in the service-control package."""
    @property
    def _br(self) -> ModuleType:
        # Gives the bobbeyreese module so that it may be used in f-strings.
        return enough

    @property
    def _error_tb(self) -> str:
        # Gives the traceback-formatted exception string.
        return ''.join(traceback.format_exception(self.error))

    def _fmt_error_map(self, key_fn: Callable[[T], object] = enough.identity) -> str:
        # Gives a string representation of a mapping from objects to their associated exceptions.
        return '\n\n'.join(f'{key_fn(k)}: {"".join(traceback.format_exception(e))}' for k, e in self.errors.items())
