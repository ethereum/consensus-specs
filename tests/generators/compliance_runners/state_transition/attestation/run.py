"""Generate and validate standard Gloas attestation cases."""

from .coverage import materialize_profile
from .validation import main as validate


def main() -> int:
    materialize_profile("standard")
    return validate()


if __name__ == "__main__":
    raise SystemExit(main())
