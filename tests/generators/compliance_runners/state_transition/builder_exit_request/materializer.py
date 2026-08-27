"""Materialize aspect-model solutions into process_builder_exit_request cases.

Consumes solution-like objects (from `coverage.py`), realizes each applicable
coverage dimension into a concrete pre / BuilderExitRequest / post vector, and
serializes the solution to dimensions.yaml. This operation never raises, so
`post` is always present (a no-op leaves it unchanged).

Spec: specs/gloas/beacon-chain.md process_builder_exit_request.
"""
from __future__ import annotations

from typing import Any

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import builder_pubkeys
from tests.generators.compliance_runners.state_transition.materializer import Materializer

from ...gen_base.gen_typing import TestCasePart

REQUEST_PUBKEY = builder_pubkeys[0]
BUILDER_ADDRESS = b"\x22" * 20
OTHER_ADDRESS = b"\x33" * 20
FINALIZED_EPOCH = 5
EPOCHS_PAST_GENESIS = 10

_DIMS = [
    "builder_pubkey_found",
    "builder_deposit_to_finalized_epoch", "builder_withdrawable_epoch_set",
    "builder_has_pending_withdrawal", "builder_has_pending_payment",
    "source_address_matches",
    "builder_active", "builder_has_pending_balance", "exit_initiated", "outcome",
]


def _s(sol: Any, n: str) -> str:
    return str(getattr(sol, n))


def _b(sol: Any, n: str) -> bool:
    return bool(getattr(sol, n))


class BuilderExitRequestMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "builder_exit_request"

    def _base_state(self) -> Any:
        spec = self.spec
        state = create_genesis_state(
            spec, validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        state.builders = type(state.builders)()
        state.slot = spec.Slot(EPOCHS_PAST_GENESIS * spec.SLOTS_PER_EPOCH)
        state.finalized_checkpoint = spec.Checkpoint(
            epoch=spec.Epoch(FINALIZED_EPOCH), root=spec.Root(b"\x01" * 32)
        )
        return state

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        found = _b(sol, "builder_pubkey_found")
        pre = self._base_state()
        current_epoch = int(spec.get_current_epoch(pre))

        if found:
            dep = _s(sol, "builder_deposit_to_finalized_epoch")
            deposit_epoch = {"LT": FINALIZED_EPOCH - 1, "EQ": FINALIZED_EPOCH, "GT": FINALIZED_EPOCH + 1}[dep]
            wset = _s(sol, "builder_withdrawable_epoch_set") == "T"
            pre.builders.append(
                spec.Builder(
                    pubkey=spec.BLSPubkey(REQUEST_PUBKEY),
                    version=spec.PAYLOAD_BUILDER_VERSION,
                    execution_address=spec.ExecutionAddress(BUILDER_ADDRESS),
                    balance=spec.Gwei(spec.MIN_ACTIVATION_BALANCE),
                    deposit_epoch=spec.Epoch(deposit_epoch),
                    withdrawable_epoch=spec.Epoch(current_epoch) if wset else spec.FAR_FUTURE_EPOCH,
                )
            )
            if _s(sol, "builder_has_pending_withdrawal") == "T":
                pre.builder_pending_withdrawals.append(
                    spec.BuilderPendingWithdrawal(
                        fee_recipient=spec.ExecutionAddress(BUILDER_ADDRESS),
                        amount=spec.Gwei(1), builder_index=spec.BuilderIndex(0),
                    )
                )
            if _s(sol, "builder_has_pending_payment") == "T":
                pre.builder_pending_payments[0] = spec.BuilderPendingPayment(
                    weight=spec.Gwei(1),
                    withdrawal=spec.BuilderPendingWithdrawal(
                        fee_recipient=spec.ExecutionAddress(BUILDER_ADDRESS),
                        amount=spec.Gwei(1), builder_index=spec.BuilderIndex(0),
                    ),
                    proposer_index=spec.ValidatorIndex(0),
                )
            matches = _s(sol, "source_address_matches") == "T"
            source_address = BUILDER_ADDRESS if matches else OTHER_ADDRESS
        else:
            source_address = BUILDER_ADDRESS  # arbitrary; pubkey absent from registry

        request = spec.BuilderExitRequest(
            source_address=spec.ExecutionAddress(source_address),
            pubkey=spec.BLSPubkey(REQUEST_PUBKEY),
        )
        post = pre.copy()
        spec.process_builder_exit_request(post, request)  # never raises

        claimed = {n: (_b(sol, n) if isinstance(getattr(sol, n), bool) else _s(sol, n)) for n in _DIMS}
        meta = {"description": f"process_builder_exit_request: {claimed['outcome']}", "claimed": claimed}
        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("builder_exit_request", "ssz", request.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]
        return meta, parts
