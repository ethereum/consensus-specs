"""Materialize Gloas ``process_sync_committee_updates`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class SyncCommitteeUpdatesMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "sync_committee_updates"

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        at_period_boundary = bool(getattr(solution, "at_period_boundary", True))
        committees_already_match = bool(getattr(solution, "committees_already_match", True))
        computed_next_is_unchanged = bool(
            getattr(solution, "computed_next_is_unchanged", True)
        )
        period = int(spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD)
        current_epoch = period - 1 if at_period_boundary else 0
        pre.slot = spec.Slot(current_epoch * int(spec.SLOTS_PER_EPOCH))

        computed_next = spec.get_next_sync_committee(pre)
        alternate = computed_next.copy()
        alternate.pubkeys[0] = spec.BLSPubkey(b"\x99" * 48)
        next_committee = computed_next if computed_next_is_unchanged else alternate
        current = (
            next_committee
            if committees_already_match
            else (alternate if computed_next_is_unchanged else computed_next)
        )
        pre.current_sync_committee = current
        pre.next_sync_committee = next_committee

        post = pre.copy()
        spec.process_sync_committee_updates(post)
        claimed = {
            name: bool(getattr(solution, name))
            for name in (
                "at_period_boundary",
                "committees_already_match",
                "computed_next_is_unchanged",
            )
            if hasattr(solution, name)
        }
        meta = {
            "description": "process_sync_committee_updates",
            "claimed": claimed,
        }
        return meta, [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]


MATERIALIZER = SyncCommitteeUpdatesMaterializer
