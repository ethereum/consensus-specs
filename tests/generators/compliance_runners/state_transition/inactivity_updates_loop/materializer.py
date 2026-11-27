"""Materialize the first eligible validator's inactivity-update witnesses."""

from __future__ import annotations

from functools import cached_property
from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_to
from tests.generators.compliance_runners.state_transition.inactivity_updates.history import (
    FOCUS_INDEX,
    InactivityHistory,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer

from .cases import arithmetic_witnesses
from .target import BODY, TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class InactivityUpdatesLoopMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "inactivity_updates"

    @cached_property
    def _history(self):
        return InactivityHistory(self.spec)

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        assignment = vars(solution)
        witnesses = arithmetic_witnesses(
            int(spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY),
            int(spec.config.INACTIVITY_SCORE_BIAS),
            int(spec.config.INACTIVITY_SCORE_RECOVERY_RATE),
            (BODY["score_gt_zero"], BODY["leaking"], BODY["score_vs_recovery_rate"]),
        )
        matches = [
            (key, value)
            for key, value in witnesses.items()
            if frozenset(key) <= frozenset(assignment.items())
        ]
        _, (score, delay) = min(matches, key=lambda item: repr(item[0]))
        pre = self._history.loop(
            delay=delay,
            active=assignment["is_active_in_previous"],
            flagged=assignment["has_target_flag"],
            slashed=assignment["is_slashed"],
        ).copy()
        pre.inactivity_scores[FOCUS_INDEX] = spec.Uint64(score)
        run_epoch_processing_to(spec, pre, "process_inactivity_updates")
        assert spec.get_finality_delay(pre) == delay
        post = pre.copy()
        spec.process_inactivity_updates(post)
        claimed = self.claimed_record(TARGET, solution)
        return {"description": "process_inactivity_updates loop body", "claimed": claimed}, [
            ("pre", "ssz", pre.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]


MATERIALIZER = InactivityUpdatesLoopMaterializer
