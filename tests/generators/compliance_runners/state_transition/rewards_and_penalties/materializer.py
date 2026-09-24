"""Materialize ``process_rewards_and_penalties`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class RewardsAndPenaltiesMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "rewards_and_penalties"

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        count = 64
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * count,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        after_genesis = bool(getattr(solution, "after_genesis", True))
        epoch = int(spec.GENESIS_EPOCH) + (
            int(spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY) + 2 if after_genesis else 0
        )
        pre.slot = spec.Slot((epoch + 1) * int(spec.SLOTS_PER_EPOCH) - 1)
        leaking = bool(getattr(solution, "in_inactivity_leak", False))
        reward = bool(getattr(solution, "has_flag_reward", False))
        penalty = bool(getattr(solution, "has_flag_penalty", False))
        inactivity_penalty = bool(getattr(solution, "has_inactivity_penalty", False))
        any_eligible = bool(getattr(solution, "has_eligible_validator", True))
        if (
            not reward
            and not penalty
            and not inactivity_penalty
            and "has_eligible_validator" not in vars(solution)
            and "in_inactivity_leak" in vars(solution)
            and not leaking
        ):
            any_eligible = False
        elif any_eligible and not reward and not penalty and not inactivity_penalty:
            if "in_inactivity_leak" not in vars(solution):
                leaking = True
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
        all_flags = spec.ParticipationFlags((1 << len(spec.PARTICIPATION_FLAG_WEIGHTS)) - 1)
        zero_flags = spec.ParticipationFlags(0)
        for i in range(count):
            if not any_eligible:
                pre.validators[i].activation_epoch = spec.FAR_FUTURE_EPOCH
            if reward and (penalty or inactivity_penalty) and any_eligible and not leaking:
                pre.previous_epoch_participation[i] = all_flags if i == 0 else zero_flags
            elif reward and any_eligible and not leaking:
                # A reward can coexist with no flag penalties when every
                # eligible validator has all flags; the reward still follows
                # from the non-empty participating set.
                pre.previous_epoch_participation[i] = all_flags
            elif penalty or inactivity_penalty:
                pre.previous_epoch_participation[i] = zero_flags
            elif any_eligible:
                pre.previous_epoch_participation[i] = all_flags
            else:
                pre.previous_epoch_participation[i] = zero_flags
            pre.inactivity_scores[i] = (
                int(spec.config.INACTIVITY_SCORE_BIAS) * 8 if inactivity_penalty else 0
            )
        post = pre.copy()
        spec.process_rewards_and_penalties(post)
        claimed = {str(k): v for k, v in vars(solution).items() if not str(k).startswith("_")}
        return {"description": "process_rewards_and_penalties", "claimed": claimed}, [
            ("pre", "ssz", pre.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]


MATERIALIZER = RewardsAndPenaltiesMaterializer
