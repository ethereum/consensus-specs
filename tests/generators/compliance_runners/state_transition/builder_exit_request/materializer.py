"""Materialize aspect-model solutions into process_builder_exit_request cases.

Consumes solution-like objects (from `coverage.py`), realizes each applicable
coverage dimension into a concrete pre / BuilderExitRequest / post vector, and
serializes the solution to dimensions.yaml. This operation never raises, so
`post` is always present (a no-op leaves it unchanged).

Spec: specs/gloas/beacon-chain.md process_builder_exit_request.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import builder_pubkeys
from tests.generators.compliance_runners.state_transition.aspects_helpers.byte_witness import (
    distinct_bytes,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart

EPOCHS_PAST_GENESIS = 10

_DIMS = [
    "builder_pubkey_found",
    "builder_deposit_to_finalized_epoch",
    "builder_withdrawable_epoch_set",
    "builder_has_pending_withdrawal",
    "builder_has_pending_payment",
    "source_address_matches",
    "builder_active",
    "builder_has_pending_balance",
    "exit_initiated",
    "outcome",
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
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
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
        finalized_epoch = self.rng.randrange(2, current_epoch)
        finalized_root, _ = distinct_bytes(self.rng, 32)
        pre.finalized_checkpoint = spec.Checkpoint(
            epoch=spec.Epoch(finalized_epoch), root=spec.Root(finalized_root)
        )
        builder_pubkey = self.rng.choice(builder_pubkeys)
        builder_address, other_address = distinct_bytes(self.rng, 20)

        if found:
            dep = _s(sol, "builder_deposit_to_finalized_epoch")
            deposit_epoch = {
                "LT": self.rng.randrange(finalized_epoch),
                "EQ": finalized_epoch,
                "GT": finalized_epoch + self.rng.randrange(1, 11),
            }[dep]
            wset = _s(sol, "builder_withdrawable_epoch_set") == "T"
            pre.builders.append(
                spec.Builder(
                    pubkey=spec.BLSPubkey(builder_pubkey),
                    version=spec.PAYLOAD_BUILDER_VERSION,
                    execution_address=spec.ExecutionAddress(builder_address),
                    balance=spec.Gwei(int(spec.MIN_ACTIVATION_BALANCE) + self.rng.randrange(1001)),
                    deposit_epoch=spec.Epoch(deposit_epoch),
                    withdrawable_epoch=spec.Epoch(current_epoch) if wset else spec.FAR_FUTURE_EPOCH,
                )
            )
            if _s(sol, "builder_has_pending_withdrawal") == "T":
                pre.builder_pending_withdrawals.append(
                    spec.BuilderPendingWithdrawal(
                        fee_recipient=spec.ExecutionAddress(builder_address),
                        amount=spec.Gwei(self.rng.randrange(1, 1001)),
                        builder_index=spec.BuilderIndex(0),
                    )
                )
            if _s(sol, "builder_has_pending_payment") == "T":
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
            matches = _s(sol, "source_address_matches") == "T"
            source_address = builder_address if matches else other_address
        else:
            source_address = builder_address  # arbitrary; pubkey absent from registry

        request = spec.BuilderExitRequest(
            source_address=spec.ExecutionAddress(source_address),
            pubkey=spec.BLSPubkey(builder_pubkey),
        )
        post = pre.copy()
        spec.process_builder_exit_request(post, request)  # never raises

        claimed = {
            n: (_b(sol, n) if isinstance(getattr(sol, n), bool) else _s(sol, n)) for n in _DIMS
        }
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
