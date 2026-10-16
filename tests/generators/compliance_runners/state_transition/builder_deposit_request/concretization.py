"""Concrete witnesses for builder-deposit-request coverage cases."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.keys import builder_pubkeys
from tests.generators.compliance_runners.state_transition.aspects_helpers.byte_witness import (
    distinct_bytes,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.deposit_amount import (
    deposit_amount_from_profile,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.entity_reference import (
    distinct_indices,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.withdrawal_credential import (
    withdrawal_credentials_from_profile,
)
from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
)

if TYPE_CHECKING:
    from random import Random


VALIDATOR_COUNT = 64
EPOCHS_PAST_GENESIS = 10


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Random) -> dict[str, Any]:
        rec = vars(abstract_case)
        slot_epoch = rng.randrange(1, EPOCHS_PAST_GENESIS + 1)
        request_index, wrong_index = distinct_indices(rng, len(builder_pubkeys), 2)
        request_pubkey = builder_pubkeys[request_index]
        wrong_pubkey = builder_pubkeys[wrong_index]
        address_tail = spec.sha256(request_pubkey)[12:]
        attributes: dict[str, Any] = {
            "slot": slot_epoch * int(spec.SLOTS_PER_EPOCH),
            "current_epoch": slot_epoch,
            "request_pubkey": request_pubkey,
            "wrong_pubkey": wrong_pubkey,
            "address_tail": address_tail,
            "builder_found": rec["builder_pubkey_found"],
            "reuses_swept_slot": rec["reuses_swept_slot"] is True,
        }

        if rec["builder_pubkey_found"]:
            execution_address, _ = distinct_bytes(rng, 20)
            attributes["execution_address"] = execution_address
            attributes["balance"] = (
                0
                if rec["builder_balance_zero"]
                else rng.randrange(1, int(spec.MIN_ACTIVATION_BALANCE) + 1)
            )
            attributes["deposit_epoch"] = rng.randrange(slot_epoch + 1)
            attributes["withdrawable_epoch"] = (
                slot_epoch if rec["builder_withdrawable_epoch_set"] else int(spec.FAR_FUTURE_EPOCH)
            )
        elif rec["reuses_swept_slot"] is True:
            attributes["execution_address"] = distinct_bytes(rng, 20)[0]

        attributes["withdrawal_credentials"] = withdrawal_credentials_from_profile(
            spec, rec["withdrawal_credentials_profile"], address_tail, rng
        )
        attributes["amount"] = deposit_amount_from_profile(spec, rec["amount_profile"], rng)
        attributes["signer_pubkey"] = (
            request_pubkey if rec["builder_signature_valid"] else wrong_pubkey
        )
        return attributes


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
