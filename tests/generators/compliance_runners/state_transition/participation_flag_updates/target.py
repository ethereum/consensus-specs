"""Coverage target for ``process_participation_flag_updates``.

The handler rotates the previous/current participation arrays and replaces the
current array with zero flags.  The target records validator-set size and the
contents of both arrays before rotation.
"""

# ruff: noqa: F841 - factor declarations are assignments the body never reads
from __future__ import annotations

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    CAttribute,
    coverage_aspect,
    CPred,
    each,
    Target,
)


@coverage_aspect("participation")
def capture_participation(
    validator_count: CAttribute[int],
    minimum_validator_count: CAttribute[int],
    previous_nonzero_count: CAttribute[int],
    current_nonzero_count: CAttribute[int],
):
    validator_set_is_larger: CPred = validator_count > minimum_validator_count
    previous_has_flags: CPred = previous_nonzero_count > 0
    current_has_flags: CPred = current_nonzero_count > 0


PARTICIPATION = capture_participation
ASPECTS = (PARTICIPATION,)


def _observe(ctx) -> None:
    spec, state = ctx.spec, ctx.pre
    capture_participation(
        validator_count=len(state.validators),
        minimum_validator_count=int(spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT),
        previous_nonzero_count=sum(
            bool(flags) for flags in state.previous_epoch_participation
        ),
        current_nonzero_count=sum(bool(flags) for flags in state.current_epoch_participation),
    )


PROFILES = {
    "smoke": each(PARTICIPATION.factors),
    "normal": PARTICIPATION.exhaustive(),
    "standard": PARTICIPATION.exhaustive(),
}


TARGET = Target("participation_flag_updates", ASPECTS, _observe, PROFILES)
