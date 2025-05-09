import functools
import os
import signal

from rich.console import Console


def install_sigint_handler(console: Console) -> None:
    """On Ctrl-C, show the cursor and exit immediately."""

    def _handle_sigint(signum, frame):
        console.show_cursor()
        os._exit(0)

    signal.signal(signal.SIGINT, _handle_sigint)


@functools.lru_cache(maxsize=None)
def format_duration(seconds):
    """Convert seconds to a more readable time."""
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)
