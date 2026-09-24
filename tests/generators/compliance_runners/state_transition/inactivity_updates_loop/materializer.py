"""Materialize singleton-eligible vectors for the inactivity-update loop."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class InactivityUpdatesLoopMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "inactivity_updates"

    def materialize_solution(self, solution: Any) -> tuple[dict, list["TestCasePart"]]:
        spec = self.spec
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        epoch = int(spec.GENESIS_EPOCH) + int(spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY) + 2
        pre.slot = spec.Slot((epoch + 1) * int(spec.SLOTS_PER_EPOCH) - 1)
        leaking = bool(getattr(solution, "leaking", False))
        previous_epoch = max(int(spec.GENESIS_EPOCH), epoch - 1)
        finalized_epoch = max(
            int(spec.GENESIS_EPOCH),
            previous_epoch - int(spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY) - 1,
        ) if leaking else previous_epoch
        pre.finalized_checkpoint = type(pre.finalized_checkpoint)(
            epoch=finalized_epoch, root=pre.finalized_checkpoint.root
        )
        for index, validator in enumerate(pre.validators):
            if index:
                validator.activation_epoch = spec.FAR_FUTURE_EPOCH
        validator = pre.validators[0]
        requested_delta = getattr(solution, "score_delta", None)
        active = bool(getattr(solution, "is_active_in_previous", True))
        flagged = bool(
            getattr(solution, "has_target_flag", requested_delta != "INCREASED")
        )
        slashed = bool(getattr(solution, "is_slashed", False))
        participating = bool(
            getattr(
                solution,
                "is_participating",
                active
                and flagged
                and not slashed
                and requested_delta != "INCREASED"
                and not (requested_delta == "UNCHANGED" and not leaking),
            )
        )
        if participating:
            active, flagged, slashed = True, True, False
        elif active and flagged:
            if "is_slashed" in vars(solution) and not slashed:
                flagged = False
            else:
                slashed = True
        if not active:
            slashed = True
        validator.slashed = slashed
        validator.activation_epoch = (
            spec.GENESIS_EPOCH if active else spec.FAR_FUTURE_EPOCH
        )
        validator.exit_epoch = spec.FAR_FUTURE_EPOCH
        validator.withdrawable_epoch = spec.FAR_FUTURE_EPOCH
        score_gt_zero = bool(getattr(solution, "score_gt_zero", False))
        recovery_comparison = bool(getattr(solution, "score_vs_recovery_rate", False))
        recovery = int(spec.config.INACTIVITY_SCORE_RECOVERY_RATE)
        if requested_delta == "INCREASED" and "leaking" not in vars(solution):
            leaking = True
            pre.finalized_checkpoint = type(pre.finalized_checkpoint)(
                epoch=max(
                    int(spec.GENESIS_EPOCH),
                    int(spec.get_previous_epoch(pre))
                    - int(spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY)
                    - 1,
                ),
                root=pre.finalized_checkpoint.root,
            )
        if requested_delta == "UNCHANGED":
            score = 1 if score_gt_zero else 0
        elif recovery_comparison:
            score = max(
                0,
                recovery + 2
                if participating
                else recovery + 1 - int(spec.config.INACTIVITY_SCORE_BIAS),
            )
        elif score_gt_zero or requested_delta in ("DECREASED", "INCREASED"):
            score = 1
        else:
            score = 0
        if not score_gt_zero and "score_gt_zero" in vars(solution):
            score = 0
        pre.inactivity_scores[0] = score
        if flagged:
            pre.previous_epoch_participation[0] = spec.ParticipationFlags(
                1 << int(spec.TIMELY_TARGET_FLAG_INDEX)
            )
        if participating:
            pre.previous_epoch_participation[0] = spec.ParticipationFlags(
                1 << int(spec.TIMELY_TARGET_FLAG_INDEX)
            )
        post = pre.copy()
        spec.process_inactivity_updates(post)
        claimed = {str(k): v for k, v in vars(solution).items() if not str(k).startswith("_")}
        return {"description": "process_inactivity_updates loop body", "claimed": claimed}, [
            ("pre", "ssz", pre.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]


MATERIALIZER = InactivityUpdatesLoopMaterializer
