"""Materialize singleton-eligible vectors for the inactivity-update loop."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

from .cases import arithmetic_witnesses
from .target import BODY, TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class InactivityUpdatesLoopMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "inactivity_updates"

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        if not hasattr(self, "_target"):
            self._target = TARGET.for_spec(spec)
        target = self._target
        _, configurations = target._configurations(filtered=True)
        requested = frozenset(
            (str(k), v) for k, v in vars(solution).items() if not str(k).startswith("_")
        )
        completions = [c for c in configurations if requested <= c]
        if not completions:
            raise ValueError(f"no feasible inactivity-loop completion for {dict(requested)}")
        assignment = dict(min(completions, key=lambda c: repr(sorted(c))))
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
        epoch = int(spec.GENESIS_EPOCH) + delay + 1
        pre.slot = spec.Slot((epoch + 1) * int(spec.SLOTS_PER_EPOCH) - 1)
        pre.finalized_checkpoint = type(pre.finalized_checkpoint)(
            epoch=int(spec.get_previous_epoch(pre)) - delay,
            root=pre.finalized_checkpoint.root,
        )
        focus_index = self.rng.randrange(len(pre.validators))
        for index, validator in enumerate(pre.validators):
            if index != focus_index:
                validator.activation_epoch = spec.FAR_FUTURE_EPOCH
        validator = pre.validators[focus_index]
        active = assignment["is_active_in_previous"]
        flagged = assignment["has_target_flag"]
        slashed = assignment["is_slashed"]
        validator.slashed = slashed
        validator.activation_epoch = spec.GENESIS_EPOCH if active else spec.FAR_FUTURE_EPOCH
        validator.exit_epoch = spec.FAR_FUTURE_EPOCH
        validator.withdrawable_epoch = spec.FAR_FUTURE_EPOCH
        pre.inactivity_scores[focus_index] = score
        if flagged:
            pre.previous_epoch_participation[focus_index] = spec.ParticipationFlags(
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
