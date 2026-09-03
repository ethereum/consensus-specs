"""Generate process_execution_payload_bid cases and validate them in one step.

Coordinator only; the materializer and validation stay independent of each other.

Usage:
    uv run python -m tests.generators.compliance_runners.state_transition.bid_processing.run
"""

from __future__ import annotations

from tests.generators.compliance_runners.state_transition.bid_processing.materializer import (
    main as generate,
)
from tests.generators.compliance_runners.state_transition.bid_processing.validation import (
    main as validate,
)


def main() -> int:
    generate()
    print()
    return validate()


if __name__ == "__main__":
    raise SystemExit(main())
