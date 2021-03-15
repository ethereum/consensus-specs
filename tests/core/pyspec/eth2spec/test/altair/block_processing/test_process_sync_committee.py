from collections import Counter
import random
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.block_processing import run_block_processing_to
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    transition_to,
)
from eth2spec.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
)
from eth2spec.test.context import (
    PHASE0, PHASE1,
    MAINNET, MINIMAL,
    expect_assertion_error,
    with_all_phases_except,
    with_configs,
    spec_state_test,
    always_bls,
)
from eth2spec.utils.hash_function import hash


def run_sync_committee_processing(spec, state, block, expect_exception=False):
    """
    Processes everything up to the sync committee work, then runs the sync committee work in isolation, and
    produces a pre-state and post-state (None if exception) specifically for sync-committee processing changes.
    """
    # process up to the sync committee work
    call = run_block_processing_to(spec, state, block, 'process_sync_committee')
    yield 'pre', state
    yield 'sync_aggregate', block.body.sync_aggregate
    if expect_exception:
        expect_assertion_error(lambda: call(state, block))
        yield 'post', None
    else:
        call(state, block)
        yield 'post', state


def get_committee_indices(spec, state, duplicates=False):
    """
    This utility function allows the caller to ensure there are or are not
    duplicate validator indices in the returned committee based on
    the boolean ``duplicates``.
    """
    state = state.copy()
    current_epoch = spec.get_current_epoch(state)
    randao_index = current_epoch % spec.EPOCHS_PER_HISTORICAL_VECTOR
    while True:
        committee = spec.get_sync_committee_indices(state, spec.get_current_epoch(state))
        if duplicates:
            if len(committee) != len(set(committee)):
                return committee
        else:
            if len(committee) == len(set(committee)):
                return committee
        state.randao_mixes[randao_index] = hash(state.randao_mixes[randao_index])


@with_all_phases_except([PHASE0, PHASE1])
@spec_state_test
@always_bls
def test_invalid_signature_missing_participant(spec, state):
    committee = spec.get_sync_committee_indices(state, spec.get_current_epoch(state))
    random_participant = random.choice(committee)

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    # Exclude one participant whose signature was included.
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[index != random_participant for index in committee],
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            committee,  # full committee signs
        )
    )
    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


@with_all_phases_except([PHASE0, PHASE1])
@spec_state_test
@always_bls
def test_invalid_signature_extra_participant(spec, state):
    committee = spec.get_sync_committee_indices(state, spec.get_current_epoch(state))
    random_participant = random.choice(committee)

    block = build_empty_block_for_next_slot(spec, state)
    # Exclude one signature even though the block claims the entire committee participated.
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] * len(committee),
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            [index for index in committee if index != random_participant],
        )
    )

    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


def compute_sync_committee_participant_reward(spec, state, participant_index, active_validator_count, committee_size):
    base_reward = spec.get_base_reward(state, participant_index)
    proposer_reward = spec.get_proposer_reward(state, participant_index)
    max_participant_reward = base_reward - proposer_reward
    return max_participant_reward * active_validator_count // committee_size // spec.SLOTS_PER_EPOCH


@with_all_phases_except([PHASE0, PHASE1])
@with_configs([MINIMAL], reason="to create nonduplicate committee")
@spec_state_test
def test_sync_committee_rewards_nonduplicate_committee(spec, state):
    committee = get_committee_indices(spec, state, duplicates=False)
    committee_size = len(committee)
    active_validator_count = len(spec.get_active_validator_indices(state, spec.get_current_epoch(state)))

    # Preconditions of this test case
    assert active_validator_count >= spec.SYNC_COMMITTEE_SIZE
    assert committee_size == len(set(committee))

    yield 'pre', state

    pre_balances = state.balances.copy()

    block = build_empty_block_for_next_slot(spec, state)
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] * committee_size,
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            committee,
        )
    )

    yield from run_sync_committee_processing(spec, state, block)

    for index in range(len(state.validators)):
        expected_reward = 0

        if index == block.proposer_index:
            expected_reward += sum([spec.get_proposer_reward(state, index) for index in committee])

        if index in committee:
            expected_reward += compute_sync_committee_participant_reward(
                spec,
                state,
                index,
                active_validator_count,
                committee_size
            )

        assert state.balances[index] == pre_balances[index] + expected_reward


@with_all_phases_except([PHASE0, PHASE1])
@with_configs([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_sync_committee_rewards_duplicate_committee(spec, state):
    committee = get_committee_indices(spec, state, duplicates=True)
    committee_size = len(committee)
    active_validator_count = len(spec.get_active_validator_indices(state, spec.get_current_epoch(state)))

    # Preconditions of this test case
    assert active_validator_count < spec.SYNC_COMMITTEE_SIZE
    assert committee_size > len(set(committee))

    pre_balances = state.balances.copy()
    block = build_empty_block_for_next_slot(spec, state)
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] * committee_size,
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            committee,
        )
    )
    yield from run_sync_committee_processing(spec, state, block)

    multiplicities = Counter(committee)

    for index in range(len(state.validators)):
        expected_reward = 0

        if index == block.proposer_index:
            expected_reward += sum([spec.get_proposer_reward(state, index) for index in committee])

        if index in committee:
            reward = compute_sync_committee_participant_reward(
                spec,
                state,
                index,
                active_validator_count,
                committee_size,
            )
            expected_reward += reward * multiplicities[index]

        assert state.balances[index] == pre_balances[index] + expected_reward


@with_all_phases_except([PHASE0, PHASE1])
@spec_state_test
@always_bls
def test_invalid_signature_past_block(spec, state):
    committee = spec.get_sync_committee_indices(state, spec.get_current_epoch(state))

    blocks = []
    for _ in range(2):
        # NOTE: need to transition twice to move beyond the degenerate case at genesis
        block = build_empty_block_for_next_slot(spec, state)
        # Valid sync committee signature here...
        block.body.sync_aggregate = spec.SyncAggregate(
            sync_committee_bits=[True] * len(committee),
            sync_committee_signature=compute_aggregate_sync_committee_signature(
                spec,
                state,
                block.slot - 1,
                committee,
            )
        )

        signed_block = state_transition_and_sign_block(spec, state, block)
        blocks.append(signed_block)

    invalid_block = build_empty_block_for_next_slot(spec, state)
    # Invalid signature from a slot other than the previous
    invalid_block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] * len(committee),
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            invalid_block.slot - 2,
            committee,
        )
    )

    yield from run_sync_committee_processing(spec, state, invalid_block, expect_exception=True)


@with_all_phases_except([PHASE0, PHASE1])
@with_configs([MINIMAL], reason="to produce different committee sets")
@spec_state_test
@always_bls
def test_invalid_signature_previous_committee(spec, state):
    # NOTE: the `state` provided is at genesis and the process to select
    # sync committees currently returns the same committee for the first and second
    # periods at genesis.
    # To get a distinct committee so we can generate an "old" signature, we need to advance
    # 2 EPOCHS_PER_SYNC_COMMITTEE_PERIOD periods.
    current_epoch = spec.get_current_epoch(state)
    old_sync_committee = state.next_sync_committee

    epoch_in_future_sync_commitee_period = current_epoch + 2 * spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    slot_in_future_sync_committee_period = epoch_in_future_sync_commitee_period * spec.SLOTS_PER_EPOCH
    transition_to(spec, state, slot_in_future_sync_committee_period)

    # Use the previous sync committee to produce the signature.
    pubkeys = [validator.pubkey for validator in state.validators]
    # Ensure that the pubkey sets are different.
    assert set(old_sync_committee.pubkeys) != set(state.current_sync_committee.pubkeys)
    committee = [pubkeys.index(pubkey) for pubkey in old_sync_committee.pubkeys]

    block = build_empty_block_for_next_slot(spec, state)
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] * len(committee),
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            committee,
        )
    )

    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


@with_all_phases_except([PHASE0, PHASE1])
@spec_state_test
@always_bls
def test_valid_signature_future_committee(spec, state):
    # NOTE: the `state` provided is at genesis and the process to select
    # sync committees currently returns the same committee for the first and second
    # periods at genesis.
    # To get a distinct committee so we can generate an "old" signature, we need to advance
    # 2 EPOCHS_PER_SYNC_COMMITTEE_PERIOD periods.
    current_epoch = spec.get_current_epoch(state)
    old_current_sync_committee = state.current_sync_committee
    old_next_sync_committee = state.next_sync_committee

    epoch_in_future_sync_committee_period = current_epoch + 2 * spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    slot_in_future_sync_committee_period = epoch_in_future_sync_committee_period * spec.SLOTS_PER_EPOCH
    transition_to(spec, state, slot_in_future_sync_committee_period)

    sync_committee = state.current_sync_committee

    expected_sync_committee = spec.get_sync_committee(state, epoch_in_future_sync_committee_period)

    assert sync_committee == expected_sync_committee
    assert sync_committee != old_current_sync_committee
    assert sync_committee != old_next_sync_committee

    pubkeys = [validator.pubkey for validator in state.validators]
    committee_indices = [pubkeys.index(pubkey) for pubkey in sync_committee.pubkeys]

    block = build_empty_block_for_next_slot(spec, state)
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] * len(committee_indices),
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            committee_indices,
        )
    )

    yield from run_sync_committee_processing(spec, state, block)
