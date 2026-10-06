"""Coverage specification for the ETH1 reset guard and vote-list occupancy."""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    comparison,
    constant,
    coverage_spec,
    Integer,
    modulo,
)

from .observation import observe_attributes

next_epoch = attribute("next_epoch", Integer(min=1))
vote_count = attribute("vote_count", Integer(min=0))
epochs_per_eth1_voting_period = constant("epochs_per_eth1_voting_period", Integer(min=1))

RESET = aspect(
    "reset",
    modulo(
        "reset_remainder",
        next_epoch,
        epochs_per_eth1_voting_period,
        description="Exercise the reset boundary, its neighbours, and the period interior.",
    ),
    comparison(
        "votes_nonempty",
        vote_count,
        0,
        granularity="cmp5",
        description="Resetting a populated list has an observable effect.",
    ),
)
ASPECTS = (RESET,)
PROFILES = {
    "smoke": RESET.each(),
    "normal": RESET.exhaustive(),
    "max": RESET.exhaustive(),
    "standard": RESET.exhaustive(),
}

COVERAGE = coverage_spec(
    "eth1_data_reset",
    focus="process_eth1_data_reset: reset guard and vote-list occupancy",
    record="one vector",
    attributes=(next_epoch, vote_count),
    constants=(epochs_per_eth1_voting_period,),
    aspects=ASPECTS,
    profiles=PROFILES,
)

TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "epochs_per_eth1_voting_period": lambda spec: int(spec.EPOCHS_PER_ETH1_VOTING_PERIOD),
    },
)
