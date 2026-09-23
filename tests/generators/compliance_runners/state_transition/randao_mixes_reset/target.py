"""Coverage target for ``process_randao_mixes_reset``.

The handler copies the current epoch's RANDAO mix into the next epoch's
circular slot.  The target records the destination wraparound and the source
and destination mix relationship.
"""

# ruff: noqa: F841 - factor declarations are assignments the body never reads
from __future__ import annotations

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    CAttribute,
    CConstant,
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
    source_mix: CAttribute[bytes],
    destination_mix: CAttribute[bytes],
    *,
    zero_mix: CConstant[bytes],
):
    destination_is_first_slot: CPred = destination_index == 0
    source_nonzero: CPred = source_mix != zero_mix
    source_matches_destination: CPred = source_mix == destination_mix


RESET = capture_reset
ASPECTS = (RESET,)


def _observe(ctx: Context) -> None:
    capture_reset(**observe_attributes(ctx))


PROFILES = {
    "smoke": each(RESET.factors),
    "normal": RESET.exhaustive(),
    "standard": RESET.exhaustive(),
}


TARGET = Target(
    "randao_mixes_reset",
    ASPECTS,
    _observe,
    PROFILES,
    constants={"zero_mix": lambda spec: bytes(spec.Root()) if hasattr(spec, "Root") else bytes(32)},
)
