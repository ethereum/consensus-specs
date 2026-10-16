"""Concrete validator plans for registry-updates coverage cases."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
)

if TYPE_CHECKING:
    from random import Random


VALIDATOR_COUNT = 64
REQUESTED_BRANCHES = (
    "queues_validator",
    "ejects_validator",
    "activates_validator",
    "leaves_validator_unchanged",
)


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Random) -> dict[str, Any]:
        requested = {name: getattr(abstract_case, name) for name in REQUESTED_BRANCHES}
        has_validators = abstract_case.has_validators

        active_branch = None
        if has_validators and not requested["leaves_validator_unchanged"]:
            active_branch = next(name for name, value in requested.items() if value)

        validator_count = VALIDATOR_COUNT if has_validators else 0
        enabled_branches = [name for name, enabled in requested.items() if enabled]
        validator_indices = rng.sample(range(validator_count), len(enabled_branches))

        return {
            "requested": requested,
            "has_validators": has_validators,
            "active_branch": active_branch,
            "enabled_branches": enabled_branches,
            "validator_indices": validator_indices,
        }


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
