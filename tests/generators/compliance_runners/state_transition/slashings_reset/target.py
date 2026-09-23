"""Coverage target for ``process_slashings_reset``.

The handler selects the next epoch's circular slashings slot and resets it to
zero.  The target records the wraparound case and whether the selected slot
actually contains a value to clear.
"""

# ruff: noqa: F841 - factor declarations are assignments the body never reads
from __future__ import annotations

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    CAttribute,
    Context,
    coverage_aspect,
    CPred,
    each,
    Target,
)

from .observation import observe_attributes


@coverage_aspect("reset")
def capture_reset(
    destination_index: CAttribute[int],
    destination_value: CAttribute[int],
):
    destination_is_first_slot: CPred = destination_index == 0
    destination_nonzero: CPred = destination_value > 0


RESET = capture_reset
ASPECTS = (RESET,)


def _observe(ctx: Context) -> None:
    capture_reset(**observe_attributes(ctx))


PROFILES = {
    "smoke": each(RESET.factors),
    "normal": RESET.exhaustive(),
    "standard": RESET.exhaustive(),
}


TARGET = Target("slashings_reset", ASPECTS, _observe, PROFILES)
