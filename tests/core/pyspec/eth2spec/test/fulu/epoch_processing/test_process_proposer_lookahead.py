from eth2spec.test.context import spec_state_test, with_fulu_and_later
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with
from eth2spec.test.helpers.state import next_epoch


@with_fulu_and_later
@spec_state_test
def test_next_epoch_proposer_lookahead_shifted_to_front(spec, state):
    """Test that the next epoch proposer lookahead is shifted to the front at epoch transition."""
    # Transition few epochs to pass the MIN_SEED_LOOKAHEAD
    next_epoch(spec, state)
    next_epoch(spec, state)
    # Get initial lookahead
    initial_lookahead = state.proposer_lookahead.copy()

    # Run epoch processing
    yield from run_epoch_processing_with(spec, state, 'process_proposer_lookahead')

    # Verify lookahead was shifted correctly
    assert state.proposer_lookahead[:spec.SLOTS_PER_EPOCH] == initial_lookahead[spec.SLOTS_PER_EPOCH:]


@with_fulu_and_later
@spec_state_test
def test_proposer_lookahead_in_state_matches_computed_lookahead(spec, state):
    """Test that the proposer lookahead in the state matches the lookahead computed on the fly."""
    # Transition few epochs to pass the MIN_SEED_LOOKAHEAD
    next_epoch(spec, state)
    next_epoch(spec, state)

    # Run epoch processing
    next_epoch(spec, state)

    # Verify lookahead in state matches the lookahead computed on the fly
    computed_lookahead = spec.initialize_proposer_lookahead(state)
    assert state.proposer_lookahead == computed_lookahead
