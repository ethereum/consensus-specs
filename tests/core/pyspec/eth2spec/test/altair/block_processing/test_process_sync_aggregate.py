import random
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.block_processing import run_block_processing_to
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    transition_to,
)
from eth2spec.test.helpers.constants import (
    MAINNET, MINIMAL,
)
from eth2spec.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
    compute_sync_committee_participant_reward_and_penalty,
    compute_sync_committee_proposer_reward,
    compute_committee_indices,
)
from eth2spec.test.context import (
    default_activation_threshold,
    expect_assertion_error,
    misc_balances,
    single_phase,
    with_altair_and_later,
    with_custom_state,
    with_presets,
    spec_state_test,
    always_bls,
    spec_test,
)
from eth2spec.utils.hash_function import hash


def run_sync_committee_processing(spec, state, block, expect_exception=False):
    """
    Processes everything up to the sync committee work, then runs the sync committee work in isolation, and
    produces a pre-state and post-state (None if exception) specifically for sync-committee processing changes.
    """
    # process up to the sync committee work
    call = run_block_processing_to(spec, state, block, 'process_sync_aggregate')
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
    randao_index = (current_epoch + 1) % spec.EPOCHS_PER_HISTORICAL_VECTOR
    while True:
        committee = spec.get_next_sync_committee_indices(state)
        if duplicates:
            if len(committee) != len(set(committee)):
                return committee
        else:
            if len(committee) == len(set(committee)):
                return committee
        state.randao_mixes[randao_index] = hash(state.randao_mixes[randao_index])


@with_altair_and_later
@spec_state_test
@always_bls
def test_invalid_signature_bad_domain(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)
    rng = random.Random(2020)
    random_participant = rng.choice(committee_indices)

    block = build_empty_block_for_next_slot(spec, state)
    # Exclude one participant whose signature was included.
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[index != random_participant for index in committee_indices],
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            committee_indices,  # full committee signs
            domain_type=spec.DOMAIN_BEACON_ATTESTER,  # Incorrect domain
        )
    )
    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


@with_altair_and_later
@spec_state_test
@always_bls
def test_invalid_signature_missing_participant(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)
    rng = random.Random(2020)
    random_participant = rng.choice(committee_indices)

    block = build_empty_block_for_next_slot(spec, state)
    # Exclude one participant whose signature was included.
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[index != random_participant for index in committee_indices],
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            committee_indices,  # full committee signs
        )
    )
    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


@with_altair_and_later
@spec_state_test
@always_bls
def test_invalid_signature_no_participants(spec, state):
    block = build_empty_block_for_next_slot(spec, state)
    # No participants is an allowed case, but needs a specific signature, not the full-zeroed signature.
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[False] * len(block.body.sync_aggregate.sync_committee_bits),
        sync_committee_signature=b'\x00' * 96
    )
    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)

# No-participants, with valid signature, is tested in test_sync_committee_rewards_empty_participants already.


@with_altair_and_later
@spec_state_test
@always_bls
def test_invalid_signature_infinite_signature_with_all_participants(spec, state):
    block = build_empty_block_for_next_slot(spec, state)
    # Include all participants, try the special-case signature for no-participants
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] * len(block.body.sync_aggregate.sync_committee_bits),
        sync_committee_signature=spec.G2_POINT_AT_INFINITY
    )
    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


@with_altair_and_later
@spec_state_test
@always_bls
def test_invalid_signature_infinite_signature_with_single_participant(spec, state):
    block = build_empty_block_for_next_slot(spec, state)
    # Try include a single participant with the special-case signature for no-participants.
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] + ([False] * (len(block.body.sync_aggregate.sync_committee_bits) - 1)),
        sync_committee_signature=spec.G2_POINT_AT_INFINITY
    )
    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


@with_altair_and_later
@spec_state_test
@always_bls
def test_invalid_signature_extra_participant(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)
    rng = random.Random(3030)
    random_participant = rng.choice(committee_indices)

    block = build_empty_block_for_next_slot(spec, state)
    # Exclude one signature even though the block claims the entire committee participated.
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] * len(committee_indices),
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            [index for index in committee_indices if index != random_participant],
        )
    )

    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


def validate_sync_committee_rewards(spec, pre_state, post_state, committee_indices, committee_bits, proposer_index):
    for index in range(len(post_state.validators)):
        reward = 0
        penalty = 0
        if index in committee_indices:
            _reward, _penalty = compute_sync_committee_participant_reward_and_penalty(
                spec,
                pre_state,
                index,
                committee_indices,
                committee_bits,
            )
            reward += _reward
            penalty += _penalty

        if proposer_index == index:
            reward += compute_sync_committee_proposer_reward(
                spec,
                pre_state,
                committee_indices,
                committee_bits,
            )

        assert post_state.balances[index] == pre_state.balances[index] + reward - penalty


def run_successful_sync_committee_test(spec, state, committee_indices, committee_bits):
    pre_state = state.copy()

    block = build_empty_block_for_next_slot(spec, state)
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=committee_bits,
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            [index for index, bit in zip(committee_indices, committee_bits) if bit],
        )
    )

    yield from run_sync_committee_processing(spec, state, block)

    validate_sync_committee_rewards(
        spec,
        pre_state,
        state,
        committee_indices,
        committee_bits,
        block.proposer_index,
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_state_test
def test_sync_committee_rewards_nonduplicate_committee(spec, state):
    committee_indices = get_committee_indices(spec, state, duplicates=False)
    committee_size = len(committee_indices)
    committee_bits = [True] * committee_size
    active_validator_count = len(spec.get_active_validator_indices(state, spec.get_current_epoch(state)))

    # Preconditions of this test case
    assert active_validator_count > spec.SYNC_COMMITTEE_SIZE
    assert committee_size == len(set(committee_indices))

    yield from run_successful_sync_committee_test(spec, state, committee_indices, committee_bits)


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_sync_committee_rewards_duplicate_committee_no_participation(spec, state):
    committee_indices = get_committee_indices(spec, state, duplicates=True)
    committee_size = len(committee_indices)
    committee_bits = [False] * committee_size
    active_validator_count = len(spec.get_active_validator_indices(state, spec.get_current_epoch(state)))

    # Preconditions of this test case
    assert active_validator_count < spec.SYNC_COMMITTEE_SIZE
    assert committee_size > len(set(committee_indices))

    yield from run_successful_sync_committee_test(spec, state, committee_indices, committee_bits)


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_sync_committee_rewards_duplicate_committee_half_participation(spec, state):
    committee_indices = get_committee_indices(spec, state, duplicates=True)
    committee_size = len(committee_indices)
    committee_bits = [True] * (committee_size // 2) + [False] * (committee_size // 2)
    assert len(committee_bits) == committee_size
    active_validator_count = len(spec.get_active_validator_indices(state, spec.get_current_epoch(state)))

    # Preconditions of this test case
    assert active_validator_count < spec.SYNC_COMMITTEE_SIZE
    assert committee_size > len(set(committee_indices))

    yield from run_successful_sync_committee_test(spec, state, committee_indices, committee_bits)


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_sync_committee_rewards_duplicate_committee_full_participation(spec, state):
    committee_indices = get_committee_indices(spec, state, duplicates=True)
    committee_size = len(committee_indices)
    committee_bits = [True] * committee_size
    active_validator_count = len(spec.get_active_validator_indices(state, spec.get_current_epoch(state)))

    # Preconditions of this test case
    assert active_validator_count < spec.SYNC_COMMITTEE_SIZE
    assert committee_size > len(set(committee_indices))

    yield from run_successful_sync_committee_test(spec, state, committee_indices, committee_bits)


@with_altair_and_later
@spec_state_test
@always_bls
def test_sync_committee_rewards_not_full_participants(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)
    rng = random.Random(1010)
    committee_bits = [rng.choice([True, False]) for _ in committee_indices]

    yield from run_successful_sync_committee_test(spec, state, committee_indices, committee_bits)


@with_altair_and_later
@spec_state_test
@always_bls
def test_sync_committee_rewards_empty_participants(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)
    committee_bits = [False for _ in committee_indices]

    yield from run_successful_sync_committee_test(spec, state, committee_indices, committee_bits)


@with_altair_and_later
@spec_state_test
@always_bls
def test_invalid_signature_past_block(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)

    for _ in range(2):
        # NOTE: need to transition twice to move beyond the degenerate case at genesis
        block = build_empty_block_for_next_slot(spec, state)
        # Valid sync committee signature here...
        block.body.sync_aggregate = spec.SyncAggregate(
            sync_committee_bits=[True] * len(committee_indices),
            sync_committee_signature=compute_aggregate_sync_committee_signature(
                spec,
                state,
                block.slot - 1,
                committee_indices,
            )
        )

        state_transition_and_sign_block(spec, state, block)

    invalid_block = build_empty_block_for_next_slot(spec, state)
    # Invalid signature from a slot other than the previous
    invalid_block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[True] * len(committee_indices),
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            invalid_block.slot - 2,
            committee_indices,
        )
    )

    yield from run_sync_committee_processing(spec, state, invalid_block, expect_exception=True)


@with_altair_and_later
@with_presets([MINIMAL], reason="to produce different committee sets")
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
    # Ensure that the pubkey sets are different.
    assert set(old_sync_committee.pubkeys) != set(state.current_sync_committee.pubkeys)
    committee_indices = compute_committee_indices(spec, state, old_sync_committee)

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

    yield from run_sync_committee_processing(spec, state, block, expect_exception=True)


@with_altair_and_later
@spec_state_test
@always_bls
@with_presets([MINIMAL], reason="too slow")
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
    next_sync_committee = state.next_sync_committee

    assert next_sync_committee != sync_committee
    assert sync_committee != old_current_sync_committee
    assert sync_committee != old_next_sync_committee

    committee_indices = compute_committee_indices(spec, state, sync_committee)

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


@with_altair_and_later
@spec_state_test
@always_bls
@with_presets([MINIMAL], reason="prefer short search to find matching proposer")
def test_proposer_in_committee_without_participation(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)

    # NOTE: seem to reliably be getting a matching proposer in the first epoch w/ ``MINIMAL`` preset.
    for _ in range(spec.SLOTS_PER_EPOCH):
        block = build_empty_block_for_next_slot(spec, state)
        proposer_index = block.proposer_index
        proposer_pubkey = state.validators[proposer_index].pubkey
        proposer_is_in_sync_committee = proposer_pubkey in state.current_sync_committee.pubkeys
        if proposer_is_in_sync_committee:
            participation = [index != proposer_index for index in committee_indices]
            participants = [index for index in committee_indices if index != proposer_index]
        else:
            participation = [True for _ in committee_indices]
            participants = committee_indices
        # Valid sync committee signature here...
        block.body.sync_aggregate = spec.SyncAggregate(
            sync_committee_bits=participation,
            sync_committee_signature=compute_aggregate_sync_committee_signature(
                spec,
                state,
                block.slot - 1,
                participants,
            )
        )

        if proposer_is_in_sync_committee:
            assert state.validators[block.proposer_index].pubkey in state.current_sync_committee.pubkeys
            yield from run_sync_committee_processing(spec, state, block)
            break
        else:
            state_transition_and_sign_block(spec, state, block)
    else:
        raise AssertionError("failed to find a proposer in the sync committee set; check test setup")


@with_altair_and_later
@spec_state_test
@always_bls
@with_presets([MINIMAL], reason="prefer short search to find matching proposer")
def test_proposer_in_committee_with_participation(spec, state):
    committee_indices = compute_committee_indices(spec, state, state.current_sync_committee)
    participation = [True for _ in committee_indices]

    # NOTE: seem to reliably be getting a matching proposer in the first epoch w/ ``MINIMAL`` preset.
    for _ in range(spec.SLOTS_PER_EPOCH):
        block = build_empty_block_for_next_slot(spec, state)
        proposer_index = block.proposer_index
        proposer_pubkey = state.validators[proposer_index].pubkey
        proposer_is_in_sync_committee = proposer_pubkey in state.current_sync_committee.pubkeys

        # Valid sync committee signature here...
        block.body.sync_aggregate = spec.SyncAggregate(
            sync_committee_bits=participation,
            sync_committee_signature=compute_aggregate_sync_committee_signature(
                spec,
                state,
                block.slot - 1,
                committee_indices,
            )
        )

        if proposer_is_in_sync_committee:
            assert state.validators[block.proposer_index].pubkey in state.current_sync_committee.pubkeys
            yield from run_sync_committee_processing(spec, state, block)
            return
        else:
            state_transition_and_sign_block(spec, state, block)
    raise AssertionError("failed to find a proposer in the sync committee set; check test setup")


def _test_harness_for_randomized_test_case(spec, state, duplicates=False, participation_fn=None):
    committee_indices = get_committee_indices(spec, state, duplicates=duplicates)

    if participation_fn:
        participating_indices = participation_fn(committee_indices)
    else:
        participating_indices = committee_indices

    committee_bits = [index in participating_indices for index in committee_indices]
    committee_size = len(committee_indices)
    if duplicates:
        assert committee_size > len(set(committee_indices))
    else:
        assert committee_size == len(set(committee_indices))

    yield from run_successful_sync_committee_test(spec, state, committee_indices, committee_bits)


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_random_only_one_participant_with_duplicates(spec, state):
    rng = random.Random(101)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        duplicates=True,
        participation_fn=lambda comm: [rng.choice(comm)],
    )


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_random_low_participation_with_duplicates(spec, state):
    rng = random.Random(201)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        duplicates=True,
        participation_fn=lambda comm: rng.sample(comm, int(len(comm) * 0.25)),
    )


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_random_high_participation_with_duplicates(spec, state):
    rng = random.Random(301)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        duplicates=True,
        participation_fn=lambda comm: rng.sample(comm, int(len(comm) * 0.75)),
    )


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_random_all_but_one_participating_with_duplicates(spec, state):
    rng = random.Random(401)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        duplicates=True,
        participation_fn=lambda comm: rng.sample(comm, len(comm) - 1),
    )


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_test
@with_custom_state(balances_fn=misc_balances, threshold_fn=default_activation_threshold)
@single_phase
def test_random_misc_balances_and_half_participation_with_duplicates(spec, state):
    rng = random.Random(1401)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        duplicates=True,
        participation_fn=lambda comm: rng.sample(comm, len(comm) // 2),
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_state_test
def test_random_only_one_participant_without_duplicates(spec, state):
    rng = random.Random(501)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: [rng.choice(comm)],
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_state_test
def test_random_low_participation_without_duplicates(spec, state):
    rng = random.Random(601)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: rng.sample(comm, int(len(comm) * 0.25)),
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_state_test
def test_random_high_participation_without_duplicates(spec, state):
    rng = random.Random(701)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: rng.sample(comm, int(len(comm) * 0.75)),
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_state_test
def test_random_all_but_one_participating_without_duplicates(spec, state):
    rng = random.Random(801)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: rng.sample(comm, len(comm) - 1),
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_test
@with_custom_state(balances_fn=misc_balances, threshold_fn=default_activation_threshold)
@single_phase
def test_random_misc_balances_and_half_participation_without_duplicates(spec, state):
    rng = random.Random(1501)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: rng.sample(comm, len(comm) // 2),
    )
