"""Materialize aspect-model solutions into process_builder_exit_request cases.

Consumes declaration witnesses, realizes each applicable
coverage dimension into a concrete pre / BuilderExitRequest / post vector, and
serializes the solution to dimensions.yaml. This operation never raises, so
`post` is always present (a no-op leaves it unchanged).

Spec: specs/gloas/beacon-chain.md process_builder_exit_request.
"""

from __future__ import annotations

from functools import cached_property
from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.deposits import prepare_builder_deposit_request
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import builder_pubkeys
from tests.generators.compliance_runners.state_transition.materializer import Materializer
from tests.generators.compliance_runners.state_transition.materializer.common import (
    exit_builder_after_empty_parent,
    finalize_genesis_builders,
    process_execution_requests_after_empty_parent,
    process_payload_block_after_empty_parent,
)
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class BuilderExitRequestMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "builder_exit_request"

    @cached_property
    def _genesis_state(self) -> Any:
        spec = self.spec
        balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
        return create_genesis_state(spec, [balance] * 64, balance, builder_count=1)

    @cached_property
    def _unfinalized_state(self) -> Any:
        spec = self.spec
        state = self._genesis_state.copy()
        spec.process_slots(state, spec.compute_start_slot_at_epoch(spec.GENESIS_EPOCH + 1))
        return state

    @cached_property
    def _recent_deposit_state(self) -> Any:
        spec = self.spec
        state = self._unfinalized_state.copy()
        with bls_enabled():
            deposit = prepare_builder_deposit_request(
                spec, state, amount=spec.MIN_DEPOSIT_AMOUNT, pubkey=builder_pubkeys[1], signed=True
            )
        requests = spec.ExecutionRequests(builder_deposits=spec.BuilderDepositRequests.of(deposit))
        process_execution_requests_after_empty_parent(spec, state, requests)
        spec.process_slots(state, state.slot + 1)
        return state

    @cached_property
    def _active_state(self) -> Any:
        return finalize_genesis_builders(self.spec, self._genesis_state.copy())

    @cached_property
    def _exited_state(self) -> Any:
        spec = self.spec
        state = self._active_state.copy()
        exit_builder_after_empty_parent(spec, state, spec.BuilderIndex(0))
        spec.process_slots(state, state.slot + 1)
        return state

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        builder_index = spec.BuilderIndex(0)
        if not sol.builder_pubkey_found or sol.builder_deposit_to_finalized_epoch == "EQ":
            pre = self._unfinalized_state.copy()
        elif sol.builder_deposit_to_finalized_epoch == "GT":
            pre = self._recent_deposit_state.copy()
            builder_index = spec.BuilderIndex(1)
        elif sol.builder_withdrawable_epoch_set:
            pre = self._exited_state.copy()
        else:
            pre = self._active_state.copy()

        builder = pre.builders[builder_index]
        pubkey = builder.pubkey
        source_address = builder.execution_address
        if not sol.builder_pubkey_found:
            pubkey = spec.BLSPubkey(self.rng.choice(builder_pubkeys[2:]))
        elif not sol.source_address_matches:
            source_address = spec.ExecutionAddress(
                bytes([source_address[0] ^ 1]) + bytes(source_address[1:])
            )
        request = spec.BuilderExitRequest(source_address=source_address, pubkey=pubkey)

        if sol.builder_has_pending_payment is True:
            # A missed payload leaves the earlier bid's payment pending.
            process_payload_block_after_empty_parent(
                spec,
                pre,
                spec.ExecutionRequests(),
                builder_index=builder_index,
                value=self.rng.randrange(1, 1001),
            )
            spec.process_slots(pre, pre.slot + 1)

        requests = spec.ExecutionRequests(builder_exits=spec.BuilderExitRequests.of(request))
        paid_parent = sol.builder_has_pending_withdrawal is True
        process_payload_block_after_empty_parent(
            spec,
            pre,
            requests,
            builder_index=builder_index if paid_parent else None,
            value=self.rng.randrange(1, 1001) if paid_parent else 0,
        )
        payment_index = spec.SLOTS_PER_EPOCH + pre.slot % spec.SLOTS_PER_EPOCH
        spec.process_slots(pre, pre.slot + 1)
        # Parent payment settlement precedes exit requests in apply_parent_execution_payload.
        spec.settle_builder_payment(pre, payment_index)
        post = pre.copy()
        spec.process_builder_exit_request(post, request)

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
