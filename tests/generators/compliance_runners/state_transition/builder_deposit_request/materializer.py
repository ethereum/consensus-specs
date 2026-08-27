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
from generators.compliance_runners.state_transition.aspects_helpers.deposit_amount import (
    deposit_amount_from_profile,
)
from generators.compliance_runners.state_transition.aspects_helpers.withdrawal_credential import (
    withdrawal_credentials_from_profile,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from generators.compliance_runners.gen_base.gen_typing import TestCasePart

REQUEST_PUBKEY = builder_pubkeys[0]
WRONG_PUBKEY = builder_pubkeys[1]
EPOCHS_PAST_GENESIS = 10

_DIMS = [
    "withdrawal_credentials_profile", "wc_is_builder_prefix", "builder_pubkey_found",
    "builder_signature_valid", "amount_profile", "amount_nonzero",
    "builder_withdrawable_epoch_set", "builder_balance_zero",
    "reset_applies", "builder_credited", "outcome",
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
            spec, validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        state.builders = type(state.builders)()
        state.slot = spec.Slot(EPOCHS_PAST_GENESIS * spec.SLOTS_PER_EPOCH)
        return state

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        found = _b(sol, "builder_pubkey_found")
        pre = self._base_state()
        current_epoch = int(spec.get_current_epoch(pre))
        address_tail = spec.sha256(REQUEST_PUBKEY)[12:]

        if found:
            wset = _s(sol, "builder_withdrawable_epoch_set") == "T"
            bzero = _s(sol, "builder_balance_zero") == "T"
            pre.builders.append(
                spec.Builder(
                    pubkey=spec.BLSPubkey(REQUEST_PUBKEY),
                    version=spec.PAYLOAD_BUILDER_VERSION,
                    execution_address=spec.ExecutionAddress(address_tail),
                    balance=spec.Gwei(0) if bzero else spec.Gwei(spec.MIN_ACTIVATION_BALANCE),
                    deposit_epoch=spec.Epoch(0),
                    withdrawable_epoch=spec.Epoch(current_epoch) if wset else spec.FAR_FUTURE_EPOCH,
                )
            )

        credentials_profile = _s(sol, "withdrawal_credentials_profile")
        wc = withdrawal_credentials_from_profile(spec, credentials_profile, address_tail)
        amount = deposit_amount_from_profile(spec, _s(sol, "amount_profile"))

        request = spec.BuilderDepositRequest(
            pubkey=spec.BLSPubkey(REQUEST_PUBKEY),
            withdrawal_credentials=spec.Bytes32(wc),
            amount=spec.Gwei(amount),
        )
        signer = REQUEST_PUBKEY if _s(sol, "builder_signature_valid") == "T" else WRONG_PUBKEY
        request.signature = self._sign(request, builder_pubkey_to_privkey[signer])

        post = pre.copy()
        spec.process_builder_deposit_request(post, request)  # never raises

        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("builder_deposit_request", "ssz", request.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]
        claimed = {n: (_b(sol, n) if isinstance(getattr(sol, n), bool) else _s(sol, n)) for n in _DIMS}
        meta = {"description": f"process_builder_deposit_request: {claimed['outcome']}", "bls_setting": 1, "claimed": claimed}
        return meta, parts
