"""Materialize aspect-model solutions into process_builder_deposit_request cases.

Realizes each applicable coverage dimension into a concrete pre /
BuilderDepositRequest / post vector (real BLS deposit signatures) and serializes
the solution. The operation never raises, so `post` is always present.

Spec: specs/gloas/beacon-chain.md process_builder_deposit_request.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import builder_pubkey_to_privkey, builder_pubkeys
from eth_consensus_specs.utils import bls
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
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart

EPOCHS_PAST_GENESIS = 10

_DIMS = [
    "withdrawal_credentials_profile",
    "wc_is_builder_prefix",
    "builder_pubkey_found",
    "builder_signature_valid",
    "amount_profile",
    "builder_withdrawable_epoch_set",
    "builder_balance_zero",
    "reset_applies",
    "builder_credited",
    "outcome",
]


def _s(sol: Any, n: str) -> str:
    return str(getattr(sol, n))


def _b(sol: Any, n: str) -> bool:
    return bool(getattr(sol, n))


class BuilderDepositRequestMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "builder_deposit_request"

    def _sign(self, request: Any, privkey: int) -> Any:
        spec = self.spec
        message = spec.DepositMessage(
            pubkey=request.pubkey,
            withdrawal_credentials=request.withdrawal_credentials,
            amount=request.amount,
        )
        root = spec.compute_signing_root(message, spec.compute_domain(spec.DOMAIN_BUILDER_DEPOSIT))
        return bls.Sign(privkey, root)

    def _base_state(self) -> Any:
        spec = self.spec
        state = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        state.builders = type(state.builders)()
        state.slot = spec.Slot(
            self.rng.randrange(1, EPOCHS_PAST_GENESIS + 1) * spec.SLOTS_PER_EPOCH
        )
        return state

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        found = _b(sol, "builder_pubkey_found")
        pre = self._base_state()
        current_epoch = int(spec.get_current_epoch(pre))
        request_pubkey_index, wrong_pubkey_index = distinct_indices(
            self.rng, len(builder_pubkeys), 2
        )
        request_pubkey = builder_pubkeys[request_pubkey_index]
        wrong_pubkey = builder_pubkeys[wrong_pubkey_index]
        address_tail = spec.sha256(request_pubkey)[12:]

        if found:
            wset = _s(sol, "builder_withdrawable_epoch_set") == "T"
            bzero = _s(sol, "builder_balance_zero") == "T"
            execution_address, _ = distinct_bytes(self.rng, 20)
            pre.builders.append(
                spec.Builder(
                    pubkey=spec.BLSPubkey(request_pubkey),
                    version=spec.PAYLOAD_BUILDER_VERSION,
                    execution_address=spec.ExecutionAddress(execution_address),
                    balance=(
                        spec.Gwei(0)
                        if bzero
                        else spec.Gwei(self.rng.randrange(1, int(spec.MIN_ACTIVATION_BALANCE) + 1))
                    ),
                    deposit_epoch=spec.Epoch(self.rng.randrange(current_epoch + 1)),
                    withdrawable_epoch=spec.Epoch(current_epoch) if wset else spec.FAR_FUTURE_EPOCH,
                )
            )

        credentials_profile = _s(sol, "withdrawal_credentials_profile")
        wc = withdrawal_credentials_from_profile(spec, credentials_profile, address_tail, self.rng)
        amount = deposit_amount_from_profile(spec, _s(sol, "amount_profile"), self.rng)

        request = spec.BuilderDepositRequest(
            pubkey=spec.BLSPubkey(request_pubkey),
            withdrawal_credentials=spec.Bytes32(wc),
            amount=spec.Gwei(amount),
        )
        signer = request_pubkey if _s(sol, "builder_signature_valid") == "T" else wrong_pubkey
        request.signature = self._sign(request, builder_pubkey_to_privkey[signer])

        post = pre.copy()
        spec.process_builder_deposit_request(post, request)  # never raises

        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("builder_deposit_request", "ssz", request.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]
        claimed = {
            n: (_b(sol, n) if isinstance(getattr(sol, n), bool) else _s(sol, n)) for n in _DIMS
        }
        meta = {
            "description": f"process_builder_deposit_request: {claimed['outcome']}",
            "bls_setting": 1,
            "claimed": claimed,
        }
        return meta, parts
