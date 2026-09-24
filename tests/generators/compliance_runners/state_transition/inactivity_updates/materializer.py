"""Materialize outer ``process_inactivity_updates`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class InactivityUpdatesMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "inactivity_updates"

    def materialize_solution(self, solution: Any) -> tuple[dict, list["TestCasePart"]]:
        spec = self.spec
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        after_genesis = bool(getattr(solution, "current_after_genesis", True))
        epoch = int(spec.GENESIS_EPOCH) + (
            int(spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY) + 2 if after_genesis else 0
        )
        pre.slot = spec.Slot((epoch + 1) * int(spec.SLOTS_PER_EPOCH) - 1)
        requested = str(getattr(solution, "eligible_validators", "ONE"))
        count = {"ZERO": 0, "ONE": 1, "MANY": 2}.get(requested, 1) if after_genesis else 0
        if bool(after_genesis) and not bool(getattr(solution, "has_ineligible_validators", True)):
            count = len(pre.validators)
        active_eligible = bool(getattr(solution, "has_active_eligible", count > 0))
        slashed = bool(getattr(solution, "has_slashed_validators", False))
        slash_eligible = count > 0 and not active_eligible
        if slash_eligible:
            count = max(count, 1)
        for _index, validator in enumerate(pre.validators):
            validator.slashed = False
            validator.activation_epoch = spec.FAR_FUTURE_EPOCH
            validator.exit_epoch = spec.FAR_FUTURE_EPOCH
            validator.withdrawable_epoch = spec.GENESIS_EPOCH
        if active_eligible:
            for index in range(count):
                validator = pre.validators[index]
                validator.activation_epoch = spec.GENESIS_EPOCH
                validator.withdrawable_epoch = spec.FAR_FUTURE_EPOCH
        if slash_eligible:
            for index in range(count):
                validator = pre.validators[index]
                validator.slashed = True
                validator.withdrawable_epoch = (
                    int(spec.get_previous_epoch(pre)) + 2
                    if bool(getattr(solution, "slashed_withdrawable_vs_previous", True))
                    else int(spec.get_previous_epoch(pre)) + 1
                )
        elif slashed:
            # A slashed validator beyond the withdrawable boundary is
            # eligible too. Reuse an existing eligible index where possible
            # so the requested ONE/MANY shape does not gain an extra member.
            slashed_index = (
                count - 1
                if count > 0 and bool(getattr(solution, "slashed_withdrawable_vs_previous", False))
                else len(pre.validators) - 1
            )
            pre.validators[slashed_index].slashed = True
            pre.validators[slashed_index].withdrawable_epoch = (
                int(spec.get_previous_epoch(pre)) + 2
                if bool(getattr(solution, "slashed_withdrawable_vs_previous", False))
                else int(spec.get_previous_epoch(pre)) + 1
            )
        leaking = bool(getattr(solution, "leaking", False))
        previous_epoch = max(int(spec.GENESIS_EPOCH), epoch - 1)
        finalized_epoch = (
            max(
                int(spec.GENESIS_EPOCH),
                previous_epoch - int(spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY) - 1,
            )
            if leaking
            else previous_epoch
        )
        pre.finalized_checkpoint = type(pre.finalized_checkpoint)(
            epoch=finalized_epoch, root=pre.finalized_checkpoint.root
        )
        branch_mix = str(getattr(solution, "branch_mix", "ALL_INCREMENT"))
        participating_count = 0 if branch_mix == "ALL_INCREMENT" else count
        if branch_mix == "MIXED":
            participating_count = 1
        target_flag = spec.ParticipationFlags(1 << int(spec.TIMELY_TARGET_FLAG_INDEX))
        has_zero_score = bool(getattr(solution, "has_zero_score_eligible", False))
        scores_changed = bool(getattr(solution, "scores_changed", True))
        for index in range(count):
            score = 0 if has_zero_score and index == 0 else 1
            if has_zero_score and scores_changed and not leaking and index == 1:
                score = 1
            if not scores_changed:
                score = 0
            pre.inactivity_scores[index] = score
            if index < participating_count and not pre.validators[index].slashed:
                pre.previous_epoch_participation[index] = target_flag
        # A leak-free zero score is a stable fixed point; a positive score
        # makes the changed-score obligation true.
        post = pre.copy()
        spec.process_inactivity_updates(post)
        claimed = {str(k): v for k, v in vars(solution).items() if not str(k).startswith("_")}
        return {"description": "process_inactivity_updates", "claimed": claimed}, [
            ("pre", "ssz", pre.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]


MATERIALIZER = InactivityUpdatesMaterializer
