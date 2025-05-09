import functools
import os
import signal
import time

from rich.console import Console


def install_sigint_handler(console: Console) -> None:
    """On Ctrl-C, show the cursor and exit immediately."""

    def _handle_sigint(signum, frame):
        console.show_cursor()
        os._exit(0)

    signal.signal(signal.SIGINT, _handle_sigint)


@functools.lru_cache(maxsize=None)
def format_seconds(seconds: int) -> str:
    """Convert seconds to a more readable time."""
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def time_since(start_time: int) -> str:
    """Get the duration since some start time."""
    return format_seconds(int(time.time() - start_time))
