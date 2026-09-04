"""Generate and validate withdrawal-processing compliance vectors."""

from __future__ import annotations

from tests.generators.compliance_runners.state_transition.withdrawal_processing.coverage import (
    materialize_profile,
)
from tests.generators.compliance_runners.state_transition.withdrawal_processing.validation import (
    main as validate,
)


def main() -> int:
    materialize_profile("exhaustive")
    print()
    return validate()


if __name__ == "__main__":
    raise SystemExit(main())
