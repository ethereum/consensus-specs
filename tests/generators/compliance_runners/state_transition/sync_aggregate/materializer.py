"""Materialize Gloas ``process_sync_aggregate`` operation vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
    compute_committee_indices,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


_DIMS = ["participation_level", "signature_valid", "outcome"]
_VALIDATOR_COUNT = 64


class SyncAggregateMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "sync_aggregate"

    def _base_state(self) -> Any:
        spec = self.spec
        state = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * _VALIDATOR_COUNT,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        # The aggregate signs the previous-slot block root. Advancing to slot 1
        # creates the slot-0 root while keeping the current sync committee intact.
        spec.process_slots(state, spec.Slot(1))
        return state

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        level = str(solution.participation_level)
        committee_indices = compute_committee_indices(pre, pre.current_sync_committee)
        committee_size = len(committee_indices)
        participant_count = {
            "FULL": committee_size,
            "MAJORITY": committee_size // 2 + 1,
            "EMPTY": 0,
        }[level]
        bits = [position < participant_count for position in range(committee_size)]
        participants = committee_indices[:participant_count]
        signature = compute_aggregate_sync_committee_signature(
            spec, pre, int(pre.slot) - 1, participants
        )
        if not bool(solution.signature_valid):
            signature = spec.BLSSignature()
        aggregate = spec.SyncAggregate(
            sync_committee_bits=spec.SyncCommitteeBits(data=bits),
            sync_committee_signature=signature,
        )

        post = pre.copy()
        try:
            spec.process_sync_aggregate(post, aggregate)
        except (AssertionError, IndexError):
            post = None

        claimed = {
            name: bool(value) if isinstance(value := getattr(solution, name), bool) else str(value)
            for name in _DIMS
        }
        meta = {
            "description": f"process_sync_aggregate: {claimed['outcome']}",
            "bls_setting": 1,
            "claimed": claimed,
        }
        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("sync_aggregate", "ssz", aggregate.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        return meta, parts
