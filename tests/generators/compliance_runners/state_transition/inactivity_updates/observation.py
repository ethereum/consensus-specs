"""Shared recovery of the ``process_inactivity_updates`` slice from one vector.

Two targets abstract this handler: this package covers the genesis guard and
the shape of ``get_eligible_validator_indices``, and
``inactivity_updates_loop`` covers the loop body on vectors with exactly one
eligible index.  Both read the same things out of a decoded vector, so the
recovery lives here and neither target can drift in how it reads
``get_eligible_validator_indices`` or ``get_unslashed_participating_indices``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    NA,
)


@dataclass(frozen=True)
class Slice:
    """The handler's inputs, recovered from one decoded vector."""

    spec: Any
    pre: Any
    post: Any
    current_epoch: int
    genesis_epoch: int
    previous_epoch: int
    loop_reached: bool
    eligible: tuple[int, ...]
    ineligible_count: int
    active_eligible_count: int
    slashed_count: int
    max_slashed_withdrawable: Any  # NA when no validator is slashed
    participating: frozenset[int]
    finality_delay: int
    min_epochs_to_inactivity_penalty: int
    leak_free: bool
    bias: int
    recovery_rate: int

    # --- per-validator views --------------------------------------------------

    def score(self, index: int) -> int:
        return int(self.pre.inactivity_scores[index])

    def post_score(self, index: int) -> Any:
        return NA if self.post is None else int(self.post.inactivity_scores[index])

    def participates(self, index: int) -> bool:
        return index in self.participating

    def validator(self, index: int):
        return self.pre.validators[index]

    def has_timely_target_flag(self, index: int) -> bool:
        return bool(
            self.spec.has_flag(
                self.pre.previous_epoch_participation[index],
                self.spec.TIMELY_TARGET_FLAG_INDEX,
            )
        )

    def is_active_in_previous(self, index: int) -> bool:
        return bool(
            self.spec.is_active_validator(
                self.validator(index), self.spec.Epoch(self.previous_epoch)
            )
        )

    # --- loop-wide views ------------------------------------------------------

    @property
    def single_eligible(self) -> bool:
        return len(self.eligible) == 1

    @property
    def focus(self) -> Any:
        """The only eligible index, or ``NA`` when the loop is not a singleton."""
        return self.eligible[0] if self.single_eligible else NA

    @property
    def participating_count(self) -> int:
        return sum(self.participates(index) for index in self.eligible)

    @property
    def zero_score_count(self) -> int:
        return sum(self.score(index) == 0 for index in self.eligible)

    @property
    def changed_score_count(self) -> Any:
        if self.post is None:
            return NA
        return sum(
            self.score(index) != self.post_score(index) for index in range(len(self.pre.validators))
        )


def recover(ctx: Context) -> Slice:
    """Recover the handler slice from a decoded vector."""
    spec, pre = ctx.spec, ctx.pre
    current_epoch = int(spec.get_current_epoch(pre))
    previous_epoch = int(spec.get_previous_epoch(pre))
    loop_reached = current_epoch != int(spec.GENESIS_EPOCH)

    eligible = tuple(int(index) for index in spec.get_eligible_validator_indices(pre))
    eligible_set = set(eligible)
    active_eligible_count = sum(
        bool(spec.is_active_validator(pre.validators[index], spec.Epoch(previous_epoch)))
        for index in eligible
    )
    slashed_withdrawable = [
        int(validator.withdrawable_epoch) for validator in pre.validators if validator.slashed
    ]

    participating: frozenset[int] = frozenset()
    if loop_reached:
        participating = frozenset(
            int(index)
            for index in spec.get_unslashed_participating_indices(
                pre, spec.TIMELY_TARGET_FLAG_INDEX, spec.Epoch(previous_epoch)
            )
        )

    return Slice(
        spec=spec,
        pre=pre,
        post=ctx.post,
        current_epoch=current_epoch,
        genesis_epoch=int(spec.GENESIS_EPOCH),
        previous_epoch=previous_epoch,
        loop_reached=loop_reached,
        eligible=eligible,
        ineligible_count=len(pre.validators) - len(eligible_set),
        active_eligible_count=active_eligible_count,
        slashed_count=len(slashed_withdrawable),
        max_slashed_withdrawable=max(slashed_withdrawable) if slashed_withdrawable else NA,
        participating=participating,
        finality_delay=int(spec.get_finality_delay(pre)),
        min_epochs_to_inactivity_penalty=int(spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY),
        leak_free=not bool(spec.is_in_inactivity_leak(pre)),
        bias=int(spec.config.INACTIVITY_SCORE_BIAS),
        recovery_rate=int(spec.config.INACTIVITY_SCORE_RECOVERY_RATE),
    )


def observe_attributes(ctx: Context) -> dict[str, Any]:
    sl = recover(ctx)
    return {
        "current_epoch": sl.current_epoch,
        "loop_reached": sl.loop_reached,
        "any_slashed": sl.slashed_count > 0,
        "eligible_count": len(sl.eligible),
        "ineligible_count": sl.ineligible_count,
        "active_eligible_count": sl.active_eligible_count,
        "slashed_count": sl.slashed_count,
        "max_slashed_withdrawable": sl.max_slashed_withdrawable,
        "previous_epoch_plus_one": sl.previous_epoch + 1,
        "loop_nonempty": sl.loop_reached and len(sl.eligible) > 0,
        "post_present": sl.post is not None,
        "participating_count": sl.participating_count,
        "zero_score_count": sl.zero_score_count,
        "finality_delay": sl.finality_delay,
        "changed_score_count": sl.changed_score_count,
    }
