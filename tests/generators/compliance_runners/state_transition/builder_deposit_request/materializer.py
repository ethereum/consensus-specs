"""Materialize aspect-model solutions into process_builder_deposit_request cases.

Realizes each applicable coverage dimension into a concrete pre /
BuilderDepositRequest / post vector (real BLS deposit signatures) and serializes
the solution. The operation never raises, so `post` is always present.

Spec: specs/gloas/beacon-chain.md process_builder_deposit_request.
"""

from __future__ import annotations

from functools import cached_property
from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.deposits import sign_builder_deposit_request
from eth_consensus_specs.test.helpers.genesis import build_mock_builder, create_genesis_state
from eth_consensus_specs.test.helpers.keys import builder_pubkey_to_privkey
from tests.generators.compliance_runners.state_transition.materializer import (
    ConcretizingMaterializer,
)
from tests.generators.compliance_runners.state_transition.materializer.common import (
    exit_builder_after_empty_parent,
    finalize_genesis_builders,
    process_execution_requests_after_empty_parent,
)
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from .concretization import STRATEGY, VALIDATOR_COUNT
from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class BuilderDepositRequestMaterializer(ConcretizingMaterializer):
    runner_name = "operations"
    handler_name = "builder_deposit_request"
    strategy = STRATEGY

    @cached_property
    def _genesis_state(self) -> Any:
        spec = self.spec
        balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
        return create_genesis_state(spec, [balance] * VALIDATOR_COUNT, balance, builder_count=1)

    @cached_property
    def _first_slot_state(self) -> Any:
        spec = self.spec
        state = self._genesis_state.copy()
        spec.process_slots(state, state.slot + 1)
        return state

    @cached_property
    def _synthetic_zero_balance_state(self) -> Any:
        spec = self.spec
        state = self._first_slot_state.copy()
        # EIP-8282 enforces a minimum deposit in the execution layer. Seed the
        # zero-balance unexited builder for isolated consensus-handler coverage.
        state.builders.append(build_mock_builder(spec, 1, spec.Gwei(0)))
        return state

    @cached_property
    def _exited_state(self) -> Any:
        spec = self.spec
        state = finalize_genesis_builders(spec, self._genesis_state.copy())
        exit_builder_after_empty_parent(spec, state, spec.BuilderIndex(0))
        spec.process_slots(state, state.slot + 1)
        return state

    @cached_property
    def _swept_state(self) -> Any:
        spec = self.spec
        state = self._exited_state.copy()
        spec.process_slots(
            state, spec.compute_start_slot_at_epoch(state.builders[0].withdrawable_epoch)
        )
        # Confirming a full payload lets the child run the builder sweep.
        process_execution_requests_after_empty_parent(spec, state, spec.ExecutionRequests())
        assert spec.get_index_for_new_builder(state) == spec.BuilderIndex(0)
        spec.process_slots(state, state.slot + 1)
        return state

    def materialize_concrete_attributes(
        self, sol: Any, attributes: dict[str, Any]
    ) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        exited = attributes["builder_exited"]
        zero_balance = attributes["builder_balance_zero"]
        if attributes["reuses_swept_slot"] or (exited and zero_balance):
            pre = self._swept_state
        elif exited:
            pre = self._exited_state
        elif zero_balance:
            pre = self._synthetic_zero_balance_state
        else:
            pre = self._first_slot_state

        request = spec.BuilderDepositRequest(
            pubkey=spec.BLSPubkey(attributes["request_pubkey"]),
            withdrawal_credentials=spec.Bytes32(attributes["withdrawal_credentials"]),
            amount=spec.Gwei(attributes["amount"]),
        )
        post = pre.copy()
        with bls_enabled():
            privkey = builder_pubkey_to_privkey[attributes["signer_pubkey"]]
            request.signature = sign_builder_deposit_request(spec, request, privkey)
            spec.process_builder_deposit_request(post, request)

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
