import functools
import inspect
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tests.infra.trace.models import CLASS_NAME_MAP, NON_SSZ_FIXTURES
from tests.infra.trace.traced_spec import RecordingSpec

DEFAULT_TRACE_DIR = Path("traces").resolve()

TRACE_PATH_EXCLUDED_FIXTURES = {
    "spec",
    "state",
    "phases",
    "post_spec",
    "pre_tag",
    "post_tag",
    "fork_epoch",
}


# these helpers are slightly verbose but it's just for filename generation
def _sanitize_value_for_path(value: Any) -> str:
    """Converts a parameter value into a filesystem-friendly string."""
    if isinstance(value, (int, bool)):
        s_val = str(value)
    elif isinstance(value, str):
        s_val = value
    elif isinstance(value, bytes):
        s_val = value.hex()
    elif hasattr(value, "__name__"):
        s_val = value.__name__
    else:
        s_val = str(value)

    # Replace invalid chars
    s_val = re.sub(r'[<>:"/\\|?*]', "_", s_val)
    s_val = re.sub(r"[^a-zA-Z0-9_-]", "-", s_val)
    return s_val[:50]


def _get_trace_output_dir(
    base_output_dir: str | None,
    fn: Callable,
    bound_args: inspect.BoundArguments,
    fork_name: str,
    preset_name: str,
) -> str:
    """Calculates the output directory path for the trace artifacts."""
    if base_output_dir:
        return base_output_dir

    test_module = fn.__module__.split(".")[-1]
    test_name = fn.__name__

    # Generate a suffix based on test parameters (e.g., param_a=True -> param_a_True)
    param_parts = []
    for name, value in bound_args.arguments.items():
        if name in TRACE_PATH_EXCLUDED_FIXTURES:
            continue
        sanitized_val = _sanitize_value_for_path(value)
        param_parts.append(f"{name}_{sanitized_val}")

    path = DEFAULT_TRACE_DIR / fork_name / preset_name / test_module / test_name

    if param_parts:
        path /= "__".join(param_parts)

    return path


def record_spec_trace(_fn: Callable | None = None, *, output_dir: str | None = None):
    """
    Decorator to wrap a pyspec test and record execution traces.
    Can be used with or without arguments:
        @record_spec_trace
        @record_spec_trace(output_dir="...")
    """

    def decorator(fn: Callable):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # 1. Bind arguments to find 'spec' and fixtures
            try:
                bound_args = inspect.signature(fn).bind(*args, **kwargs)
                bound_args.apply_defaults()
            except TypeError:
                # Fallback for non-test invocations
                return fn(*args, **kwargs)

            if "spec" not in bound_args.arguments:
                return fn(*args, **kwargs)

            real_spec = bound_args.arguments["spec"]

            # 2. Prepare context for recording
            initial_fixtures = {
                k: v
                for k, v in bound_args.arguments.items()
                if k != "spec" and (k in NON_SSZ_FIXTURES or CLASS_NAME_MAP.get(type(v).__name__))
            }

            metadata = {
                "fork": real_spec.fork,
                "preset": real_spec.config.PRESET_BASE,
            }

            parameters = {
                k: v
                for k, v in bound_args.arguments.items()
                if isinstance(v, (int, str, bool, type(None)))
            }

            # 3. Inject the recorder
            recorder = RecordingSpec(
                real_spec, initial_fixtures, metadata=metadata, parameters=parameters
            )
            bound_args.arguments["spec"] = recorder

            # 4. Run test & Save trace
            try:
                return fn(*bound_args.args, **bound_args.kwargs)
            finally:
                try:
                    # Use the *original* spec's fork name for the path
                    artifact_dir = _get_trace_output_dir(
                        output_dir, fn, bound_args, real_spec.fork, real_spec.config.PRESET_BASE
                    )
                    print(f"\n[Trace Recorder] Saving trace for {fn.__name__} to: {artifact_dir}")
                    recorder.save_trace(artifact_dir)
                except Exception as e:
                    print(f"ERROR: [Trace Recorder] FAILED to save trace for {fn.__name__}: {e}")

        return wrapper

    if _fn is None:
        return decorator
    elif callable(_fn):
        return decorator(_fn)
    else:
        raise TypeError("Invalid use of @record_spec_trace decorator.")
