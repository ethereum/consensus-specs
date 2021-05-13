from random import Random

from eth2spec.test.helpers.attestations import cached_prepare_state_with_attestations
from eth2spec.test.context import is_post_altair
from eth2spec.test.helpers.deposits import mock_deposit
from eth2spec.test.helpers.state import next_epoch


def set_some_new_deposits(spec, state, rng):
    num_validators = len(state.validators)
    # Set ~1/10 to just recently deposited
    for index in range(num_validators):
        # If not already active, skip
        if not spec.is_active_validator(state.validators[index], spec.get_current_epoch(state)):
            continue
        if rng.randrange(num_validators) < num_validators // 10:
            mock_deposit(spec, state, index)
            # Set ~half of selected to eligible for activation
            if rng.choice([True, False]):
                state.validators[index].activation_eligibility_epoch = spec.get_current_epoch(state)


def exit_random_validators(spec, state, rng):
    if spec.get_current_epoch(state) < 5:
        # Move epochs forward to allow for some validators already exited/withdrawable
        for _ in range(5):
            next_epoch(spec, state)

    current_epoch = spec.get_current_epoch(state)
    # Exit ~1/2 of validators
    for index in spec.get_active_validator_indices(state, current_epoch):
        if rng.choice([True, False]):
            continue

        validator = state.validators[index]
        validator.exit_epoch = rng.choice([current_epoch - 1, current_epoch - 2, current_epoch - 3])
        # ~1/2 are withdrawable
        if rng.choice([True, False]):
            validator.withdrawable_epoch = current_epoch
        else:
            validator.withdrawable_epoch = current_epoch + 1


def slash_random_validators(spec, state, rng):
    # Slash ~1/2 of validators
    for index in range(len(state.validators)):
        # slash at least one validator
        if index == 0 or rng.choice([True, False]):
            spec.slash_validator(state, index)


def randomize_epoch_participation(spec, state, epoch, rng):
    assert epoch in (spec.get_current_epoch(state), spec.get_previous_epoch(state))
    if not is_post_altair(spec):
        if epoch == spec.get_current_epoch(state):
            pending_attestations = state.current_epoch_attestations
        else:
            pending_attestations = state.previous_epoch_attestations
        for pending_attestation in pending_attestations:
            # ~1/3 have bad target
            if rng.randint(0, 2) == 0:
                pending_attestation.data.target.root = b'\x55' * 32
            # ~1/3 have bad head
            if rng.randint(0, 2) == 0:
                pending_attestation.data.beacon_block_root = b'\x66' * 32
            # ~50% participation
            pending_attestation.aggregation_bits = [rng.choice([True, False])
                                                    for _ in pending_attestation.aggregation_bits]
            # Random inclusion delay
            pending_attestation.inclusion_delay = rng.randint(1, spec.SLOTS_PER_EPOCH)
    else:
        if epoch == spec.get_current_epoch(state):
            epoch_participation = state.current_epoch_participation
        else:
            epoch_participation = state.previous_epoch_participation
        for index in range(len(state.validators)):
            # ~1/3 have bad head or bad target or not timely enough
            is_timely_correct_head = rng.randint(0, 2) != 0
            flags = epoch_participation[index]

            def set_flag(index, value):
                nonlocal flags
                flag = spec.ParticipationFlags(2**index)
                if value:
                    flags |= flag
                else:
                    flags &= 0xff ^ flag

            set_flag(spec.TIMELY_HEAD_FLAG_INDEX, is_timely_correct_head)
            if is_timely_correct_head:
                # If timely head, then must be timely target
                set_flag(spec.TIMELY_TARGET_FLAG_INDEX, True)
                # If timely head, then must be timely source
                set_flag(spec.TIMELY_SOURCE_FLAG_INDEX, True)
            else:
                # ~50% of remaining have bad target or not timely enough
                set_flag(spec.TIMELY_TARGET_FLAG_INDEX, rng.choice([True, False]))
                # ~50% of remaining have bad source or not timely enough
                set_flag(spec.TIMELY_SOURCE_FLAG_INDEX, rng.choice([True, False]))
            epoch_participation[index] = flags


def randomize_attestation_participation(spec, state, rng=Random(8020)):
    cached_prepare_state_with_attestations(spec, state)
    randomize_epoch_participation(spec, state, spec.get_previous_epoch(state), rng)
    randomize_epoch_participation(spec, state, spec.get_current_epoch(state), rng)


def randomize_state(spec, state, rng=Random(8020)):
    set_some_new_deposits(spec, state, rng)
    exit_random_validators(spec, state, rng)
    slash_random_validators(spec, state, rng)
    randomize_attestation_participation(spec, state, rng)
