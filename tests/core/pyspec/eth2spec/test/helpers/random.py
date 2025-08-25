from random import Random

from eth2spec.test.helpers.attestations import cached_prepare_state_with_attestations
from eth2spec.test.helpers.deposits import mock_deposit
from eth2spec.test.helpers.forks import (
    is_post_altair,
    is_post_electra,
)
from eth2spec.test.helpers.state import next_epoch
from eth2spec.test.helpers.withdrawals import set_compounding_withdrawal_credential_with_balance


def set_some_activations(spec, state, rng, activation_epoch=None):
    if activation_epoch is None:
        activation_epoch = spec.get_current_epoch(state)
    num_validators = len(state.validators)
    selected_indices = []
    for index in range(num_validators):
        # If is slashed or exiting, skip
        if (
            state.validators[index].slashed
            or state.validators[index].exit_epoch != spec.FAR_FUTURE_EPOCH
        ):
            continue
        # Set ~1/10 validators' activation_eligibility_epoch and activation_epoch
        if rng.randrange(num_validators) < num_validators // 10:
            state.validators[index].activation_eligibility_epoch = max(
                int(activation_epoch) - int(spec.MAX_SEED_LOOKAHEAD) - 1,
                spec.GENESIS_EPOCH,
            )
            state.validators[index].activation_epoch = activation_epoch
            selected_indices.append(index)
    return selected_indices


def set_some_new_deposits(spec, state, rng):
    deposited_indices = []
    num_validators = len(state.validators)
    # Set ~1/10 to just recently deposited
    for index in range(num_validators):
        # If not already active, skip
        if not spec.is_active_validator(state.validators[index], spec.get_current_epoch(state)):
            continue
        if rng.randrange(num_validators) < num_validators // 10:
            mock_deposit(spec, state, index)
            if rng.choice([True, False]):
                # Set ~half of selected to eligible for activation
                state.validators[index].activation_eligibility_epoch = spec.get_current_epoch(state)
            else:
                # The validators that just made a deposit
                deposited_indices.append(index)
    return deposited_indices


def exit_random_validators(
    spec, state, rng, fraction=0.5, exit_epoch=None, withdrawable_epoch=None, from_epoch=None
):
    """
    Set some validators' exit_epoch and withdrawable_epoch.

    If exit_epoch is configured, use the given exit_epoch. Otherwise, randomly set exit_epoch and withdrawable_epoch.
    """
    if from_epoch is None:
        from_epoch = spec.MAX_SEED_LOOKAHEAD + 1
    epoch_diff = int(from_epoch) - int(spec.get_current_epoch(state))
    for _ in range(epoch_diff):
        # NOTE: if `epoch_diff` is negative, then this loop body does not execute.
        next_epoch(spec, state)

    current_epoch = spec.get_current_epoch(state)
    exited_indices = []
    for index in spec.get_active_validator_indices(state, current_epoch):
        sampled = rng.random() < fraction
        if not sampled:
            continue

        exited_indices.append(index)
        validator = state.validators[index]
        if exit_epoch is None:
            assert withdrawable_epoch is None
            validator.exit_epoch = rng.choice(
                [current_epoch, current_epoch - 1, current_epoch - 2, current_epoch - 3]
            )
            # ~1/2 are withdrawable (note, unnatural span between exit epoch and withdrawable epoch)
            if rng.choice([True, False]):
                validator.withdrawable_epoch = current_epoch
            else:
                validator.withdrawable_epoch = current_epoch + 1
        else:
            validator.exit_epoch = exit_epoch
            if withdrawable_epoch is None:
                validator.withdrawable_epoch = (
                    validator.exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
                )
            else:
                validator.withdrawable_epoch = withdrawable_epoch

    return exited_indices


def slash_random_validators(spec, state, rng, fraction=0.5):
    slashed_indices = []
    for index in range(len(state.validators)):
        # slash at least one validator
        sampled = rng.random() < fraction
        if index == 0 or sampled:
            spec.slash_validator(state, index)
            slashed_indices.append(index)
    return slashed_indices


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
                pending_attestation.data.target.root = b"\x55" * 32
            # ~1/3 have bad head
            if rng.randint(0, 2) == 0:
                pending_attestation.data.beacon_block_root = b"\x66" * 32
            # ~50% participation
            pending_attestation.aggregation_bits = [
                rng.choice([True, False]) for _ in pending_attestation.aggregation_bits
            ]
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
                    flags &= 0xFF ^ flag

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


def randomize_previous_epoch_participation(spec, state, rng=None):
    if rng is None:
        rng = Random(8020)
    cached_prepare_state_with_attestations(spec, state)
    randomize_epoch_participation(spec, state, spec.get_previous_epoch(state), rng)
    if not is_post_altair(spec):
        state.current_epoch_attestations = []
    else:
        state.current_epoch_participation = [
            spec.ParticipationFlags(0b0000_0000) for _ in range(len(state.validators))
        ]


def randomize_attestation_participation(spec, state, rng=None):
    if rng is None:
        rng = Random(8020)
    cached_prepare_state_with_attestations(spec, state)
    randomize_epoch_participation(spec, state, spec.get_previous_epoch(state), rng)
    randomize_epoch_participation(spec, state, spec.get_current_epoch(state), rng)


def set_some_pending_deposits(spec, state, rng):
    """Set ~1/10 validators to have pending deposits if post-Electra."""
    num_validators = len(state.validators)
    deposited_indices = []

    for index in range(num_validators):
        # Skip if not active
        if not spec.is_active_validator(state.validators[index], spec.get_current_epoch(state)):
            continue

        # Set ~1/10 validators to have pending deposits
        if rng.randrange(num_validators) < num_validators // 10:
            validator = state.validators[index]
            amount = spec.EFFECTIVE_BALANCE_INCREMENT * rng.randint(1, 4)

            pending_deposit = spec.PendingDeposit(
                pubkey=validator.pubkey,
                withdrawal_credentials=validator.withdrawal_credentials,
                amount=amount,
                signature=spec.bls.G2_POINT_AT_INFINITY,
                slot=spec.GENESIS_SLOT,
            )
            state.pending_deposits.append(pending_deposit)
            deposited_indices.append(index)

    return deposited_indices


def set_some_pending_partial_withdrawals(spec, state, rng):
    """Set ~1/10 validators to have pending partial withdrawals if post-Electra."""
    num_validators = len(state.validators)
    current_epoch = spec.get_current_epoch(state)
    withdrawal_indices = []

    for index in range(num_validators):
        # Skip if not active
        if not spec.is_active_validator(state.validators[index], current_epoch):
            continue

        # Set ~1/10 validators to have pending partial withdrawals
        if rng.randrange(num_validators) < num_validators // 10:
            # Set validator to compounding type with MAX_EFFECTIVE_BALANCE_ELECTRA
            set_compounding_withdrawal_credential_with_balance(
                spec,
                state,
                index,
                effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
                balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
            )

            # Create pending partial withdrawal
            amount = spec.EFFECTIVE_BALANCE_INCREMENT * rng.randint(1, 4)
            withdrawable_epoch = current_epoch + rng.randint(0, 3)

            pending_withdrawal = spec.PendingPartialWithdrawal(
                validator_index=index,
                amount=amount,
                withdrawable_epoch=withdrawable_epoch,
            )
            state.pending_partial_withdrawals.append(pending_withdrawal)
            withdrawal_indices.append(index)

    return withdrawal_indices


def set_some_pending_consolidations(spec, state, rng):
    """Set some pairs of validators to have pending consolidations if post-Electra."""
    current_epoch = spec.get_current_epoch(state)
    active_indices = spec.get_active_validator_indices(state, current_epoch)

    # Only proceed if we have enough active validators
    if len(active_indices) < 2:
        return []

    consolidation_pairs = []
    num_consolidations = min(
        len(active_indices) // 20, 5
    )  # ~5% of validators, max 5 consolidations

    # Shuffle indices to get random pairs
    shuffled_indices = list(active_indices)
    rng.shuffle(shuffled_indices)

    for i in range(num_consolidations):
        if i * 2 + 1 < len(shuffled_indices):
            source_index = shuffled_indices[i * 2]
            target_index = shuffled_indices[i * 2 + 1]

            # Set both source and target validators to compounding type
            set_compounding_withdrawal_credential_with_balance(
                spec,
                state,
                source_index,
                effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
                balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
            )
            set_compounding_withdrawal_credential_with_balance(
                spec,
                state,
                target_index,
                effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
                balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
            )

            pending_consolidation = spec.PendingConsolidation(
                source_index=source_index,
                target_index=target_index,
            )
            state.pending_consolidations.append(pending_consolidation)
            consolidation_pairs.append((source_index, target_index))

    return consolidation_pairs


def randomize_state(spec, state, rng=None, exit_fraction=0.5, slash_fraction=0.5):
    if rng is None:
        rng = Random(8020)
    set_some_new_deposits(spec, state, rng)
    exit_random_validators(spec, state, rng, fraction=exit_fraction)
    slash_random_validators(spec, state, rng, fraction=slash_fraction)
    randomize_attestation_participation(spec, state, rng)
    if is_post_electra(spec):
        set_some_pending_deposits(spec, state, rng)
        set_some_pending_partial_withdrawals(spec, state, rng)
        set_some_pending_consolidations(spec, state, rng)


def patch_state_to_non_leaking(spec, state):
    """
    This function performs an irregular state transition so that:
    1. the current justified checkpoint references the previous epoch
    2. the previous justified checkpoint references the epoch before previous
    3. the finalized checkpoint matches the previous justified checkpoint

    The effects of this function are intended to offset randomization side effects
    performed by other functionality in this module so that if the ``state`` was leaking,
    then the ``state`` is not leaking after.
    """
    state.justification_bits[0] = True
    state.justification_bits[1] = True
    previous_epoch = spec.get_previous_epoch(state)
    previous_root = spec.get_block_root(state, previous_epoch)
    previous_previous_epoch = max(spec.GENESIS_EPOCH, spec.Epoch(previous_epoch - 1))
    previous_previous_root = spec.get_block_root(state, previous_previous_epoch)
    state.previous_justified_checkpoint = spec.Checkpoint(
        epoch=previous_previous_epoch,
        root=previous_previous_root,
    )
    state.current_justified_checkpoint = spec.Checkpoint(
        epoch=previous_epoch,
        root=previous_root,
    )
    state.finalized_checkpoint = spec.Checkpoint(
        epoch=previous_previous_epoch,
        root=previous_previous_root,
    )
