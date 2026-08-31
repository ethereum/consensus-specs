"""Shared case runner for state-transition compliance validators."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, TYPE_CHECKING

import snappy

from .catalog import HANDLERS, RUNNERS
from .materializer import SUITE_NAME

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class Check:
    dimension: str
    claimed: Any
    actual: Any
    status: str


def check_dimensions(claimed: dict, actual: dict) -> list[Check]:
    return [
        Check(
            name,
            value,
            actual.get(name, "<none>"),
            "ok" if actual.get(name, "<none>") == value else "mismatch",
        )
        for name, value in claimed.items()
    ]


def decode(path: Path, sedes: Any) -> Any:
    return sedes.decode_bytes(snappy.decompress(path.read_bytes()))


RUNNER_BY_HANDLER = {
    handler: runner for runner, handlers in RUNNERS.items() for handler in handlers
}


def validate_cases(
    test_dir: Path,
    handler: str,
    validate_case: Callable[..., Any],
    selected_cases: set[str] | None = None,
) -> int:
    """Run a handler validator over its materialized reference-test cases."""
    phase = RUNNER_BY_HANDLER[handler]
    case_dirs = sorted(test_dir.glob(f"**/{phase}/{handler}/{SUITE_NAME}/case_*"))
    if selected_cases is not None:
        case_dirs = [case_dir for case_dir in case_dirs if case_dir.name in selected_cases]
    if not case_dirs:
        suffix = " matching the requested cases" if selected_cases is not None else ""
        print(f"No cases found under {test_dir}{suffix}")
        return 1

    total_mm = total_err = 0
    for case_dir in case_dirs:
        result = validate_case(case_dir)
        if isinstance(result, tuple):
            checks, errors = result
        else:
            checks, errors = result, []
        mismatches = [check for check in checks if check.status == "mismatch"]
        total_mm += len(mismatches)
        total_err += len(errors)
        status = "OK" if not mismatches and not errors else "FAIL"
        outcome = next((check.claimed for check in checks if check.dimension == "outcome"), "?")
        print(f"{case_dir.name}: {status}  [{outcome}]")
        for check in mismatches:
            print(f"    dim {check.dimension}: claimed={check.claimed!r} actual={check.actual!r}")
        for error in errors:
            print(f"    oracle: {error}")

    print()
    if total_mm or total_err:
        print(f"FAILED: {total_mm} dimension mismatch(es), {total_err} oracle error(s)")
        return 1
    print(f"PASSED: {len(case_dirs)} cases, all dimensions consistent")
    return 0


def discover_handlers(test_dir: Path) -> list[str]:
    candidates = []
    for phase in ("operations", "epoch_processing"):
        for handler in HANDLERS:
            if list(test_dir.glob(f"**/{phase}/{handler}/**/case_*")):
                candidates.append((phase, handler))
    if not candidates:
        raise ValueError(f"could not discover a state-transition handler under {test_dir}")
    return [handler for _, handler in candidates]


def main(
    test_dir: Path | None = None,
    selected_cases: set[str] | None = None,
    handlers: tuple[str, ...] | None = None,
) -> int:
    if test_dir is None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--test-dir", type=Path, required=True)
        parser.add_argument(
            "--cases",
            type=str,
            help="comma-separated case names to validate, e.g. case_0205,case_0206",
        )
        args = parser.parse_args()
        test_dir = args.test_dir
        if args.cases:
            selected_cases = {case.strip() for case in args.cases.split(",") if case.strip()}
        else:
            selected_cases = None

    handlers = handlers if handlers is not None else tuple(discover_handlers(test_dir))
    result = 0
    for handler in handlers:
        module = import_module(f".{handler}", __package__)
        result |= validate_cases(test_dir, handler, module.validate_case, selected_cases)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
