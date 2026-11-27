"""Materialize outer ``process_inactivity_updates`` epoch vectors."""

from __future__ import annotations

from functools import cached_property
from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_to
from tests.generators.compliance_runners.state_transition.materializer import Materializer

from .history import InactivityHistory
from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class InactivityUpdatesMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "inactivity_updates"

    @cached_property
    def _history(self):
        return InactivityHistory(self.spec)

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        if solution.current_after_genesis:
            slashed = solution.has_slashed_validators
            pre = self._history.outer(
                after_genesis=True,
                leaking=solution.leaking,
                slashed=slashed,
                matured=slashed and not solution.slashed_withdrawable_vs_previous,
                ineligible=solution.has_ineligible_validators,
                branch=solution.branch_mix,
            ).copy()
            eligible = spec.get_eligible_validator_indices(pre)
            for index in eligible:
                pre.inactivity_scores[index] = spec.Uint64(int(solution.scores_changed))
            if solution.has_zero_score_eligible:
                pre.inactivity_scores[self.rng.choice(eligible)] = spec.Uint64(0)
        else:
            pre = self._history.outer(after_genesis=False).copy()
        run_epoch_processing_to(spec, pre, "process_inactivity_updates")
        post = pre.copy()
        spec.process_inactivity_updates(post)
        claimed = self.claimed_record(TARGET, solution)
        return {"description": "process_inactivity_updates", "claimed": claimed}, [
            ("pre", "ssz", pre.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]


MATERIALIZER = InactivityUpdatesMaterializer
