"""Generate process_consolidation_request cases (standard profile) and validate.

Usage:
    uv run python -m ...consolidation_request.run
"""
from __future__ import annotations

from .coverage import materialize_profile
from .validation import main as validate


def main() -> int:
    materialize_profile("standard")
    print()
    return validate()


if __name__ == "__main__":
    raise SystemExit(main())
