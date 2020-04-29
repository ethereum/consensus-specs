from eth2spec.test.helpers.attestations import prepare_state_with_full_attestations


def run_attestation_component_deltas(spec, state, component_delta_fn, matching_att_fn):
    """
    Run ``component_delta_fn``, yielding:
      - pre-state ('pre')
      - rewards ('rewards')
      - penalties ('penalties')
    """
    yield 'pre', state

    rewards, penalties = component_delta_fn(state)

    yield 'rewards', rewards
    yield 'penalties', penalties

    matching_attestations = matching_att_fn(state, spec.get_previous_epoch(state))
    matching_indices = spec.get_unslashed_attesting_indices(state, matching_attestations)
    for index in spec.get_eligible_validator_indices(state):
        validator = state.validators[index]
        enough_for_reward = (
            validator.effective_balance * spec.BASE_REWARD_FACTOR
            > spec.integer_squareroot(spec.get_total_active_balance(state)) // spec.BASE_REWARDS_PER_EPOCH
        )

        if index in matching_indices and not validator.slashed:
            if enough_for_reward:
                assert rewards[index] > 0
            else:
                assert rewards[index] == 0
            assert penalties[index] == 0
        else:
            assert rewards[index] == 0
            if enough_for_reward:
                assert penalties[index] > 0
            else:
                assert penalties[index] == 0


def test_empty(spec, state, runner):
    # Do not add any attestations to state

    yield from runner(spec, state)


def test_full_all_correct(spec, state, runner):
    prepare_state_with_full_attestations(spec, state)

    yield from runner(spec, state)


def test_half_full(spec, state, runner):
    prepare_state_with_full_attestations(spec, state)

    # Remove half of attestations
    state.previous_epoch_attestations = state.previous_epoch_attestations[:len(state.previous_epoch_attestations) // 2]

    yield from runner(spec, state)


def test_one_attestation_one_correct(spec, state, runner):
    prepare_state_with_full_attestations(spec, state)

    # Remove half of attestations
    state.previous_epoch_attestations = state.previous_epoch_attestations[:1]

    yield from runner(spec, state)


def test_with_slashed_validators(spec, state, runner):
    prepare_state_with_full_attestations(spec, state)

    # Slash half of validators
    for validator in state.validators[:len(state.validators) // 2]:
        validator.slashed = True

    yield from runner(spec, state)


def test_some_zero_effective_balances_that_attested(spec, state, runner):
    prepare_state_with_full_attestations(spec, state)

    # Set some balances to zero
    state.validators[0].effective_balance = 0
    state.validators[1].effective_balance = 0

    yield from runner(spec, state)


def test_some_zero_effective_balances_that_did_not_attest(spec, state, runner):
    prepare_state_with_full_attestations(spec, state)

    # Set some balances to zero
    attestation = state.previous_epoch_attestations[0]
    # Remove attestation
    state.previous_epoch_attestations = state.previous_epoch_attestations[1:]
    # Set removed indices effective balance to zero
    indices = spec.get_unslashed_attesting_indices(state, [attestation])
    for index in indices:
        state.validators[index].effective_balance = 0

    yield from runner(spec, state)


def test_full_fraction_incorrect(spec, state, correct_target, correct_head, fraction_incorrect, runner):
    prepare_state_with_full_attestations(spec, state)

    # Make fraction_incorrect of pending attestations have bad target/head as specified
    num_incorrect = int(fraction_incorrect * len(state.previous_epoch_attestations))
    for pending_attestation in state.previous_epoch_attestations[:num_incorrect]:
        if not correct_target:
            pending_attestation.data.target.root = b'\x55' * 32
        if not correct_head:
            pending_attestation.data.beacon_block_root = b'\x66' * 32

    yield from runner(spec, state)
