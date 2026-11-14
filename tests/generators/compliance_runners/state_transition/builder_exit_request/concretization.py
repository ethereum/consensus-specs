"""Concrete witnesses for builder-exit-request coverage cases."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.keys import builder_pubkeys
from tests.generators.compliance_runners.state_transition.aspects_helpers.byte_witness import (
    distinct_bytes,
)
from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
)

if TYPE_CHECKING:
    from random import Random


# The materializer's base state is placed at this epoch.
STATE_EPOCH = 10


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Random) -> dict[str, Any]:
        rec = vars(abstract_case)
        finalized_epoch = rng.randrange(2, STATE_EPOCH)
        finalized_root, _ = distinct_bytes(rng, 32)
        builder_pubkey = rng.choice(builder_pubkeys)
        builder_address, other_address = distinct_bytes(rng, 20)
        result: dict[str, Any] = {
            "current_epoch": STATE_EPOCH,
            "finalized_epoch": finalized_epoch,
            "finalized_root": finalized_root,
            "builder_pubkey": builder_pubkey,
            "builder_address": builder_address,
            "source_address": builder_address,
        }

        if rec["builder_pubkey_found"]:
            deposit_relation = rec["builder_deposit_to_finalized_epoch"]
            if deposit_relation == "LT":
                deposit_epoch = rng.randrange(finalized_epoch)
            elif deposit_relation == "EQ":
                deposit_epoch = finalized_epoch
            else:
                deposit_epoch = finalized_epoch + rng.randrange(1, 11)
            result["deposit_epoch"] = deposit_epoch
            result["balance"] = int(spec.MIN_ACTIVATION_BALANCE) + rng.randrange(1001)
            if rec["builder_has_pending_withdrawal"]:
                result["pending_withdrawal_amount"] = rng.randrange(1, 1001)
            if rec["source_address_matches"]:
                result["source_address"] = builder_address
            else:
                result["source_address"] = other_address

        return result


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
