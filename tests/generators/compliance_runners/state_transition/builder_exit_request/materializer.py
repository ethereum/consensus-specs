"""Materialize aspect-model solutions into process_builder_exit_request cases.

Consumes declaration witnesses, realizes each applicable
coverage dimension into a concrete pre / BuilderExitRequest / post vector, and
serializes the solution to dimensions.yaml. This operation never raises, so
`post` is always present (a no-op leaves it unchanged).

Spec: specs/gloas/beacon-chain.md process_builder_exit_request.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import (
    ConcretizingMaterializer,
)

from .concretization import STATE_EPOCH, STRATEGY
from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class BuilderExitRequestMaterializer(ConcretizingMaterializer):
    runner_name = "operations"
    handler_name = "builder_exit_request"
    strategy = STRATEGY

    def _base_state(self) -> Any:
        spec = self.spec
        state = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        state.builders = type(state.builders)()
        state.slot = spec.Slot(STATE_EPOCH * spec.SLOTS_PER_EPOCH)
        return state

    def materialize_concrete_attributes(
        self, sol: Any, attributes: dict[str, Any]
    ) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        found = sol.builder_pubkey_found
        pre = self._base_state()
        current_epoch = attributes["current_epoch"]
        if current_epoch != int(spec.get_current_epoch(pre)):
            raise ValueError("builder-exit concretization epoch does not match the base state")
        finalized_epoch = attributes["finalized_epoch"]
        pre.finalized_checkpoint = spec.Checkpoint(
            epoch=spec.Epoch(finalized_epoch), root=spec.Root(attributes["finalized_root"])
        )
        builder_pubkey = attributes["builder_pubkey"]
        builder_address = attributes["builder_address"]

        if found:
            deposit_epoch = attributes["deposit_epoch"]
            wset = sol.builder_withdrawable_epoch_set
            pre.builders.append(
                spec.Builder(
                    pubkey=spec.BLSPubkey(builder_pubkey),
                    version=spec.PAYLOAD_BUILDER_VERSION,
                    execution_address=spec.ExecutionAddress(builder_address),
                    balance=spec.Gwei(attributes["balance"]),
                    deposit_epoch=spec.Epoch(deposit_epoch),
                    withdrawable_epoch=spec.Epoch(current_epoch) if wset else spec.FAR_FUTURE_EPOCH,
                )
            )
            if sol.builder_has_pending_withdrawal:
                pre.builder_pending_withdrawals.append(
                    spec.BuilderPendingWithdrawal(
                        fee_recipient=spec.ExecutionAddress(builder_address),
                        amount=spec.Gwei(attributes["pending_withdrawal_amount"]),
                        builder_index=spec.BuilderIndex(0),
                    )
                )
            if sol.builder_has_pending_payment:
                payment_index = self.rng.randrange(len(pre.builder_pending_payments))
                pre.builder_pending_payments[payment_index] = spec.BuilderPendingPayment(
                    weight=spec.Gwei(self.rng.randrange(1, 1001)),
                    withdrawal=spec.BuilderPendingWithdrawal(
                        fee_recipient=spec.ExecutionAddress(builder_address),
                        amount=spec.Gwei(self.rng.randrange(1, 1001)),
                        builder_index=spec.BuilderIndex(0),
                    ),
                    proposer_index=spec.ValidatorIndex(self.rng.randrange(len(pre.validators))),
                )
        source_address = attributes["source_address"]

        request = spec.BuilderExitRequest(
            source_address=spec.ExecutionAddress(source_address),
            pubkey=spec.BLSPubkey(builder_pubkey),
        )
        post = pre.copy()
        spec.process_builder_exit_request(post, request)  # never raises

        claimed = self.claimed_record(TARGET, sol)
        meta = {
            "description": f"process_builder_exit_request: {claimed['outcome']}",
            "claimed": claimed,
        }
        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("builder_exit_request", "ssz", request.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]
        return meta, parts


MATERIALIZER = BuilderExitRequestMaterializer
