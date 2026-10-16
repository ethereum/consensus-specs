"""Concrete witnesses for BLS-to-execution-change coverage cases."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
)

if TYPE_CHECKING:
    from random import Random


VALIDATOR_COUNT = 64


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Random) -> dict[str, Any]:
        if not abstract_case.validator_index_in_range:
            scenario = "OUT_OF_RANGE"
        elif not abstract_case.has_bls_withdrawal_credential:
            scenario = "NON_BLS_CREDENTIAL"
        elif not abstract_case.from_pubkey_matches:
            scenario = "PUBKEY_MISMATCH"
        elif not abstract_case.signature_valid:
            scenario = "INVALID_SIGNATURE"
        else:
            scenario = "VALID"

        index = (
            VALIDATOR_COUNT + rng.randrange(1, VALIDATOR_COUNT + 1)
            if scenario == "OUT_OF_RANGE"
            else rng.randrange(VALIDATOR_COUNT)
        )
        return {"scenario": scenario, "validator_index": index}


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
