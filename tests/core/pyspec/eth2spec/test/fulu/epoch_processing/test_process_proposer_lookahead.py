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
        state.proposer_lookahead[: spec.SLOTS_PER_EPOCH * spec.MIN_SEED_LOOKAHEAD]
        == initial_lookahead[spec.SLOTS_PER_EPOCH :]
    )

    # run_epoch_processing_with does not increment the slot
    state.slot += 1

    # Verify lookahead in state matches the computed lookahead
    computed_lookahead = spec.initialize_proposer_lookahead(state)
    assert state.proposer_lookahead == computed_lookahead


@with_fulu_and_later
@spec_state_test
def test_proposer_lookahead_does_not_contain_exited_validators(spec, state):
    """
    Test proposer lookahead does not contain exited validators.
    """
    # Transition few epochs to past the MIN_SEED_LOOKAHEAD
    for _ in range(spec.MIN_SEED_LOOKAHEAD + 1):
        next_epoch(spec, state)

    # Exit first half of active validators
    active_validators = spec.get_active_validator_indices(state, spec.get_current_epoch(state))
    validators_to_exit = active_validators[: len(active_validators) // 2]

    # Initiate validator exits
    for validator_index in validators_to_exit:
        spec.initiate_validator_exit(state, validator_index)

    # Check when these validators are scheduled to exit
    exit_epochs = [state.validators[i].exit_epoch for i in validators_to_exit]
    min_exit_epoch = min(exit_epochs)

    # Progress epoch until we reach the epoch with the first validator exit
    while spec.get_current_epoch(state) < min_exit_epoch - 1:
        next_epoch(spec, state)

    # Run epoch processing, many validators will exit in this epoch
    yield from run_epoch_processing_with(spec, state, "process_proposer_lookahead")

    # run_epoch_processing_with does not increment the slot
    state.slot += 1

    # Check that the proposer lookahead does not contain exited validators
    for validator_index in state.proposer_lookahead:
        assert spec.is_active_validator(
            state.validators[validator_index], spec.get_current_epoch(state)
        ), f"Validator {validator_index} in lookahead should be active"
