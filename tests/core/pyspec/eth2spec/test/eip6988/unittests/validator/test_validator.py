from eth2spec.test.context import (
    spec_state_test,
    with_eip6988_and_later,
)
from eth2spec.test.helpers.state import next_slot


@with_eip6988_and_later
@spec_state_test
def test_slashed_validator_not_elected_for_proposal(spec, state):
    next_slot(spec, state)
    proposer_index = spec.get_beacon_proposer_index(state)
    state.validators[proposer_index].slashed = True

    assert spec.get_beacon_proposer_index(state) != proposer_index
