from eth2spec.test.context import spec_state_test, with_fulu_and_later
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with
from eth2spec.test.helpers.state import next_epoch


@with_fulu_and_later
@spec_state_test
def test_proposer_lookahead_in_state_matches_computed_lookahead(spec, state):
    """Test that the proposer lookahead in the state matches the computed lookahead."""
    # Transition few epochs to past the MIN_SEED_LOOKAHEAD
    for _ in range(spec.MIN_SEED_LOOKAHEAD + 1):
        next_epoch(spec, state)

    # Get initial lookahead
    initial_lookahead = state.proposer_lookahead.copy()

    # Run epoch processing
    yield from run_epoch_processing_with(spec, state, "process_proposer_lookahead")

    # Verify lookahead was shifted correctly
    assert (
        state.proposer_lookahead[: spec.SLOTS_PER_EPOCH]
        == initial_lookahead[spec.SLOTS_PER_EPOCH :]
    )

    # run_epoch_processing_with does not increment the slot
    state.slot += 1

    # Verify lookahead in state matches the computed lookahead
    computed_lookahead = spec.initialize_proposer_lookahead(state)
    assert state.proposer_lookahead == computed_lookahead
