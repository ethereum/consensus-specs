"""Materialize aspect-model solutions into process_builder_deposit_request cases.

Realizes each applicable coverage dimension into a concrete pre /
BuilderDepositRequest / post vector (real BLS deposit signatures) and serializes
the solution. The operation never raises, so `post` is always present.

Spec: specs/gloas/beacon-chain.md process_builder_deposit_request.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import builder_pubkey_to_privkey
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.materializer import (
    ConcretizingMaterializer,
)

from .concretization import STRATEGY, VALIDATOR_COUNT
from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class BuilderDepositRequestMaterializer(ConcretizingMaterializer):
    runner_name = "operations"
    handler_name = "builder_deposit_request"
    strategy = STRATEGY

    def _sign(self, request: Any, privkey: int) -> Any:
        spec = self.spec
        message = spec.DepositMessage(
            pubkey=request.pubkey,
            withdrawal_credentials=request.withdrawal_credentials,
            amount=request.amount,
        )
        root = spec.compute_signing_root(message, spec.compute_domain(spec.DOMAIN_BUILDER_DEPOSIT))
        return bls.Sign(privkey, root)

    def _base_state(self, slot: int) -> Any:
        spec = self.spec
        state = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * VALIDATOR_COUNT,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        state.builders = type(state.builders)()
        state.slot = spec.Slot(slot)
        return state

    def materialize_concrete_attributes(
        self, sol: Any, attributes: dict[str, Any]
    ) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        found = attributes["builder_found"]
        pre = self._base_state(attributes["slot"])
        current_epoch = int(spec.get_current_epoch(pre))
        if current_epoch != attributes["current_epoch"]:
            raise ValueError("builder-deposit concretization epoch does not match the base state")
        request_pubkey = attributes["request_pubkey"]
        wrong_pubkey = attributes["wrong_pubkey"]

        if found:
            pre.builders.append(
                spec.Builder(
                    pubkey=spec.BLSPubkey(request_pubkey),
                    version=spec.PAYLOAD_BUILDER_VERSION,
                    execution_address=spec.ExecutionAddress(attributes["execution_address"]),
                    balance=spec.Gwei(attributes["balance"]),
                    deposit_epoch=spec.Epoch(attributes["deposit_epoch"]),
                    withdrawable_epoch=spec.Epoch(attributes["withdrawable_epoch"]),
                )
            )
        elif attributes["reuses_swept_slot"]:
            # A distinct drained builder is reusable: the handler must replace
            # this registry entry instead of appending the request builder.
            pre.builders.append(
                spec.Builder(
                    pubkey=spec.BLSPubkey(wrong_pubkey),
                    version=spec.PAYLOAD_BUILDER_VERSION,
                    execution_address=spec.ExecutionAddress(attributes["execution_address"]),
                    balance=spec.Gwei(0),
                    deposit_epoch=spec.Epoch(0),
                    withdrawable_epoch=spec.Epoch(current_epoch),
                )
            )

        request = spec.BuilderDepositRequest(
            pubkey=spec.BLSPubkey(request_pubkey),
            withdrawal_credentials=spec.Bytes32(attributes["withdrawal_credentials"]),
            amount=spec.Gwei(attributes["amount"]),
        )
        signer = attributes["signer_pubkey"]
        request.signature = self._sign(request, builder_pubkey_to_privkey[signer])

        post = pre.copy()
        spec.process_builder_deposit_request(post, request)  # never raises

        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("builder_deposit_request", "ssz", request.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]
        claimed = self.claimed_record(TARGET, sol)
        meta = {
            "description": f"process_builder_deposit_request: {claimed['outcome']}",
            "bls_setting": 1,
            "claimed": claimed,
        }
        return meta, parts


MATERIALIZER = BuilderDepositRequestMaterializer
