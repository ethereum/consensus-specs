"""Concrete witnesses for builder-deposit-request coverage cases."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.keys import builder_pubkeys
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


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Random) -> dict[str, Any]:
        rec = vars(abstract_case)
        # Keys zero and one identify the genesis builder and the synthetic zero-balance builder.
        request_index, wrong_index = distinct_indices(rng, len(builder_pubkeys) - 2, 2)
        found = rec["builder_pubkey_found"]
        exited = rec["builder_withdrawable_epoch_set"] is True
        zero_balance = rec["builder_balance_zero"] is True
        request_index = request_index + 2
        if found:
            request_index = 1 if zero_balance and not exited else 0
        request_pubkey = builder_pubkeys[request_index]
        wrong_pubkey = builder_pubkeys[wrong_index + 2]
        address_tail = spec.sha256(request_pubkey)[12:]
        attributes: dict[str, Any] = {
            "request_pubkey": request_pubkey,
            "builder_exited": exited,
            "builder_balance_zero": zero_balance,
            "reuses_swept_slot": rec["reuses_swept_slot"] is True,
        }
        attributes["withdrawal_credentials"] = withdrawal_credentials_from_profile(
            spec, rec["withdrawal_credentials_profile"], address_tail, rng
        )
        attributes["amount"] = deposit_amount_from_profile(spec, rec["amount_profile"], rng)
        attributes["signer_pubkey"] = (
            request_pubkey if rec["builder_signature_valid"] else wrong_pubkey
        )
        return attributes


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
