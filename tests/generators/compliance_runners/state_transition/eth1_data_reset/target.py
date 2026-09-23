"""Coverage target for ``process_eth1_data_reset``.

The handler has one control-flow condition: ETH1 data votes are reset when the
next epoch reaches the end of the ETH1 voting period.  Vote-list occupancy is
also recorded so a reset is measured with both an empty and a populated input.

The capture signature declares the input attributes, its body defines factors,
and profiles declare their interactions. ``observation.py`` supplies concrete
attributes from a vector; the binding below connects the two.
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
    next_epoch: CAttribute[int],
    vote_count: CAttribute[int],
    *,
    epochs_per_eth1_voting_period: CConstant[int],
):
    at_reset_boundary: CPred = next_epoch % epochs_per_eth1_voting_period == 0
    votes_nonempty: CPred = vote_count > 0


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
    "eth1_data_reset",
    ASPECTS,
    _observe,
    PROFILES,
    constants={
        "epochs_per_eth1_voting_period": lambda spec: int(spec.EPOCHS_PER_ETH1_VOTING_PERIOD),
    },
)
