from eth2spec.test.context import with_all_phases, spec_state_test
from eth2spec.test.helpers.attestations import prepare_state_with_full_attestations


def run_get_target_deltas(spec, state):
    """
    Run ``process_block_header``, yielding:
      - pre-state ('pre')
      - rewards ('rewards')
      - penalties ('penalties')
    """
    yield 'pre', state

    rewards, penalties = spec.get_target_deltas(state)

    yield 'rewards', rewards
    yield 'penalties', penalties

    matching_target_attestations = spec.get_matching_target_attestations(state, spec.get_previous_epoch(state))
    matching_target_indices = spec.get_unslashed_attesting_indices(state, matching_target_attestations)
    for index in spec.get_eligible_validator_indices(state):
        if index in matching_target_indices and not state.validators[index].slashed:
            assert rewards[index] > 0
            assert penalties[index] == 0
        else:
            assert rewards[index] == 0
            assert penalties[index] > 0


@with_all_phases
@spec_state_test
def test_empty(spec, state):
    # Do not add any attestations to state

    yield from run_get_target_deltas(spec, state)


@with_all_phases
@spec_state_test
def test_full_all_correct(spec, state):
    prepare_state_with_full_attestations(spec, state)

    yield from run_get_target_deltas(spec, state)


@with_all_phases
@spec_state_test
def test_full_half_correct(spec, state):
    prepare_state_with_full_attestations(spec, state)

    # Make half of pending attestations have bad target
    for pending_attestation in state.previous_epoch_attestations[:len(state.previous_epoch_attestations) // 2]:
        pending_attestation.data.target.root = b'\x66'*32

    yield from run_get_target_deltas(spec, state)


@with_all_phases
@spec_state_test
def test_half_full(spec, state):
    prepare_state_with_full_attestations(spec, state)

    # Remove half of attestations
    state.previous_epoch_attestations = state.previous_epoch_attestations[:len(state.previous_epoch_attestations) // 2]

    yield from run_get_target_deltas(spec, state)


@with_all_phases
@spec_state_test
def test_one_correct(spec, state):
    prepare_state_with_full_attestations(spec, state)

    # Remove half of attestations
    state.previous_epoch_attestations = state.previous_epoch_attestations[:1]

    yield from run_get_target_deltas(spec, state)


@with_all_phases
@spec_state_test
def test_with_slashed_validators(spec, state):
    prepare_state_with_full_attestations(spec, state)

    # Slash half of validators
    for validator in state.validators:
        validator.slashed = True

    yield from run_get_target_deltas(spec, state)

def test_some_zero_balances(spec, state):

