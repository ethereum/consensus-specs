"""Generate and validate standard ``process_pending_deposits`` cases."""

from __future__ import annotations

from .coverage import materialize_profile
from .validation import main as validate


def main() -> int:
    materialize_profile("standard")
    print()
    return validate()


if __name__ == "__main__":
    raise SystemExit(main())
