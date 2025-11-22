"""
Decorator for automatic spec trace generation.

This module provides the @spec_trace decorator for zero-boilerplate
test trace generation.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from pathlib import Path

__all__ = ["spec_trace", "create_spec_proxy"]


def spec_trace(
    fork_name: str | None = None, output_dir: Path | None = None, test_name: str | None = None
):
    """
    Decorator to automatically trace spec method calls.

    Usage:
        @spec_trace()
        def test_example(spec, state):
            spec.process_slots(state, 10)
            # All calls are automatically recorded

    Args:
        fork_name: Override fork name (default: auto-detect from spec)
        output_dir: Where to store trace files (default: ./traces)
        test_name: Custom test name (default: function name)

    Returns:
        Decorated function that generates traces automatically
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Import here to avoid module-level import conflicts
            from .proxy_core import SpecProxy  # noqa: PLC0415

            # Extract spec from kwargs
            spec = kwargs.get("spec")

            # Determine fork name
            _fork_name = fork_name or getattr(spec, "fork", "unknown")

            # Determine output directory
            _output_dir = output_dir or Path("./traces") / fn.__name__
            _output_dir.mkdir(parents=True, exist_ok=True)

            # Create proxy
            proxy = SpecProxy(
                spec_module=spec, fork_name=_fork_name, output_dir=_output_dir / "ssz_objects"
            )

            # Replace spec with proxy
            kwargs["spec"] = proxy

            # Run the test
            result = fn(*args, **kwargs)

            # Save trace
            trace_file = _output_dir / "trace.yaml"
            proxy.save_trace(trace_file)

            return result

        return wrapper

    return decorator


def create_spec_proxy(spec, fork_name: str | None = None, output_dir: Path | None = None):
    """
    Create a spec proxy manually (for use without decorator).

    This provides more control over the tracing process compared to the decorator.

    Usage:
        spec_proxy = create_spec_proxy(spec)
        spec_proxy.process_slots(state, 10)
        spec_proxy.save_trace(Path('trace.yaml'))

    Args:
        spec: The spec module to wrap
        fork_name: Fork name (default: auto-detect from spec.fork)
        output_dir: Directory for trace output (default: ./traces/manual)

    Returns:
        SpecProxy instance ready for use
    """
    # Import here to avoid module-level import conflicts
    from .proxy_core import SpecProxy  # noqa: PLC0415

    _fork_name = fork_name or getattr(spec, "fork", "unknown")
    _output_dir = output_dir or Path("./traces/manual")

    return SpecProxy(spec, _fork_name, _output_dir)
