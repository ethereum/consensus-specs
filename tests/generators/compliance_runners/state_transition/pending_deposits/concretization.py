"""Concrete queue plans for pending-deposits coverage cases."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.keys import pubkeys
from tests.generators.compliance_runners.state_transition.aspects_helpers.entity_reference import (
    distinct_indices,
)
from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
)

if TYPE_CHECKING:
    from random import Random


# Minimal Gloas reaches the activation cap at 64 validators. Twice this count
# makes exit churn larger, separating it from activation-only deposit churn.
NUM_VALIDATORS = 128


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Random) -> dict[str, Any]:
        primary_index, secondary_index = distinct_indices(rng, NUM_VALIDATORS, 2)
        new_validator_index = (
            NUM_VALIDATORS + distinct_indices(rng, len(pubkeys) - NUM_VALIDATORS, 1)[0]
        )
        unfinalized_slot = rng.randrange(1, int(spec.SLOTS_PER_EPOCH) + 1)

        layout = abstract_case.queue_layout
        role = abstract_case.primary_role
        entries: list[dict[str, Any]] = []
        fill_withdrawn_limit = 0
        initially_withdrawn = False

        if layout == "FIRST_UNFINALIZED":
            entries.append(
                {"source": "primary", "role": role, "amount": "primary", "slot": "unfinalized"}
            )
        elif layout == "SINGLE":
            entries.append({"source": "primary", "role": role, "amount": "primary"})
        elif layout == "POSTPONE_THEN_ACTIVE":
            entries.extend(
                (
                    {"source": "primary", "role": "EXITING", "amount": "primary"},
                    {"source": "secondary", "amount": "increment"},
                )
            )
        elif layout == "ACTIVE_THEN_UNFINALIZED":
            entries.extend(
                (
                    {"source": "primary", "role": role, "amount": "primary"},
                    {"source": "secondary", "amount": "increment", "slot": "unfinalized"},
                )
            )
        elif layout in {"TWO_PROCESSABLE", "INVALID_THEN_PROCESSABLE"}:
            primary_role = "NEW_INVALID" if layout == "INVALID_THEN_PROCESSABLE" else role
            entries.extend(
                (
                    {"source": "primary", "role": primary_role, "amount": "primary"},
                    {"source": "secondary", "amount": "second"},
                )
            )
        elif layout == "LIMIT_AFTER_WITHDRAWN":
            initially_withdrawn = True
            fill_withdrawn_limit = int(spec.MAX_PENDING_DEPOSITS_PER_EPOCH)
            entries.append({"source": "primary", "role": role, "amount": "primary"})
        elif layout != "EMPTY":
            raise ValueError(f"unknown queue layout: {layout}")

        return {
            "primary_index": primary_index,
            "secondary_index": secondary_index,
            "new_validator_index": new_validator_index,
            "unfinalized_slot": unfinalized_slot,
            "initial_churn": abstract_case.initial_churn,
            "primary_amount_to_available": abstract_case.primary_amount_to_available,
            "second_amount_to_remaining": abstract_case.second_amount_to_remaining,
            "withdrawable_epoch_to_next_epoch": abstract_case.withdrawable_epoch_to_next_epoch,
            "entries": entries,
            "initially_withdrawn": initially_withdrawn,
            "fill_withdrawn_limit": fill_withdrawn_limit,
        }


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
