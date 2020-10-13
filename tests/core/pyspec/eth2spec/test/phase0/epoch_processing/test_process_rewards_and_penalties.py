from eth2spec.test.context import (
    spec_state_test, spec_test,
    with_all_phases, single_phase,
    with_phases, PHASE0,
    with_custom_state,
    zero_activation_threshold,
    misc_balances, low_single_balance,
)
from eth2spec.test.helpers.state import (
    next_epoch,
    next_slot,
)
from eth2spec.test.helpers.attestations import (
    add_attestations_to_state,
    get_valid_attestation,
    sign_attestation,
    prepare_state_with_attestations,
)
from eth2spec.test.helpers.rewards import leaking
from eth2spec.test.helpers.attester_slashings import get_indexed_attestation_participants
from eth2spec.test.phase0.epoch_processing.run_epoch_process_base import run_epoch_processing_with
from random import Random


def run_process_rewards_and_penalties(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_rewards_and_penalties')


@with_all_phases
@spec_state_test
def test_genesis_epoch_no_attestations_no_penalties(spec, state):
    pre_state = state.copy()

    assert spec.compute_epoch_at_slot(state.slot) == spec.GENESIS_EPOCH

    yield from run_process_rewards_and_penalties(spec, state)

    for index in range(len(pre_state.validators)):
        assert state.balances[index] == pre_state.balances[index]


@with_all_phases
@spec_state_test
def test_genesis_epoch_full_attestations_no_rewards(spec, state):
    attestations = []
    for slot in range(spec.SLOTS_PER_EPOCH - 1):
        # create an attestation for each slot
        if slot < spec.SLOTS_PER_EPOCH:
            attestation = get_valid_attestation(spec, state, signed=True)
            attestations.append(attestation)
        # fill each created slot in state after inclusion delay
        if slot >= spec.MIN_ATTESTATION_INCLUSION_DELAY:
            include_att = attestations[slot - spec.MIN_ATTESTATION_INCLUSION_DELAY]
            add_attestations_to_state(spec, state, [include_att], state.slot)
        next_slot(spec, state)

    # ensure has not cross the epoch boundary
    assert spec.compute_epoch_at_slot(state.slot) == spec.GENESIS_EPOCH

    pre_state = state.copy()

    yield from run_process_rewards_and_penalties(spec, state)

    for index in range(len(pre_state.validators)):
        assert state.balances[index] == pre_state.balances[index]


@with_all_phases
@spec_state_test
def test_full_attestations_random_incorrect_fields(spec, state):
    attestations = prepare_state_with_attestations(spec, state)
    for i, attestation in enumerate(state.previous_epoch_attestations):
        if i % 3 == 0:
            # Mess up some head votes
            attestation.data.beacon_block_root = b'\x56' * 32
        if i % 3 == 1:
            # Message up some target votes
            attestation.data.target.root = b'\x23' * 32
        if i % 3 == 2:
            # Keep some votes 100% correct
            pass

    yield from run_process_rewards_and_penalties(spec, state)

    attesting_indices = spec.get_unslashed_attesting_indices(state, attestations)
    assert len(attesting_indices) > 0
    # No balance checks, non-trivial base on group rewards
    # Mainly for consensus tests


@with_all_phases
@spec_test
@with_custom_state(balances_fn=misc_balances, threshold_fn=lambda spec: spec.MAX_EFFECTIVE_BALANCE // 2)
@single_phase
def test_full_attestations_misc_balances(spec, state):
    attestations = prepare_state_with_attestations(spec, state)

    pre_state = state.copy()

    yield from run_process_rewards_and_penalties(spec, state)

    attesting_indices = spec.get_unslashed_attesting_indices(state, attestations)
    assert len(attesting_indices) > 0
    assert len(attesting_indices) != len(pre_state.validators)
    assert any(v.effective_balance != spec.MAX_EFFECTIVE_BALANCE for v in state.validators)
    for index in range(len(pre_state.validators)):
        if index in attesting_indices:
            assert state.balances[index] > pre_state.balances[index]
        elif spec.is_active_validator(pre_state.validators[index], spec.compute_epoch_at_slot(state.slot)):
            assert state.balances[index] < pre_state.balances[index]
        else:
            assert state.balances[index] == pre_state.balances[index]
    # Check if base rewards are consistent with effective balance.
    brs = {}
    for index in attesting_indices:
        br = spec.get_base_reward(state, index)
        if br in brs:
            assert brs[br] == state.validators[index].effective_balance
        else:
            brs[br] = state.validators[index].effective_balance


@with_all_phases
@spec_test
@with_custom_state(balances_fn=low_single_balance, threshold_fn=zero_activation_threshold)
@single_phase
def test_full_attestations_one_validaor_one_gwei(spec, state):
    attestations = prepare_state_with_attestations(spec, state)

    yield from run_process_rewards_and_penalties(spec, state)

    # Few assertions. Mainly to check that this extreme case can run without exception
    attesting_indices = spec.get_unslashed_attesting_indices(state, attestations)
    assert len(attesting_indices) == 1


@with_all_phases
@spec_state_test
def test_no_attestations_all_penalties(spec, state):
    # Move to next epoch to ensure rewards/penalties are processed
    next_epoch(spec, state)
    pre_state = state.copy()

    assert spec.compute_epoch_at_slot(state.slot) == spec.GENESIS_EPOCH + 1

    yield from run_process_rewards_and_penalties(spec, state)

    for index in range(len(pre_state.validators)):
        assert state.balances[index] < pre_state.balances[index]


def run_with_participation(spec, state, participation_fn):
    participated = set()

    def participation_tracker(slot, comm_index, comm):
        att_participants = participation_fn(slot, comm_index, comm)
        participated.update(att_participants)
        return att_participants

    attestations = prepare_state_with_attestations(spec, state, participation_fn=participation_tracker)
    proposer_indices = [a.proposer_index for a in state.previous_epoch_attestations]

    pre_state = state.copy()

    yield from run_process_rewards_and_penalties(spec, state)

    attesting_indices = spec.get_unslashed_attesting_indices(state, attestations)
    assert len(attesting_indices) == len(participated)

    for index in range(len(pre_state.validators)):
        if spec.is_in_inactivity_leak(state):
            # Proposers can still make money during a leak
            if index in proposer_indices and index in participated:
                assert state.balances[index] > pre_state.balances[index]
            # If not proposer but participated optimally, should have exactly neutral balance
            elif index in attesting_indices:
                assert state.balances[index] == pre_state.balances[index]
            else:
                assert state.balances[index] < pre_state.balances[index]
        else:
            if index in participated:
                assert state.balances[index] > pre_state.balances[index]
            else:
                assert state.balances[index] < pre_state.balances[index]


@with_all_phases
@spec_state_test
def test_almost_empty_attestations(spec, state):
    rng = Random(1234)
    yield from run_with_participation(spec, state, lambda slot, comm_index, comm: rng.sample(comm, 1))


@with_all_phases
@spec_state_test
@leaking()
def test_almost_empty_attestations_with_leak(spec, state):
    rng = Random(1234)
    yield from run_with_participation(spec, state, lambda slot, comm_index, comm: rng.sample(comm, 1))


@with_all_phases
@spec_state_test
def test_random_fill_attestations(spec, state):
    rng = Random(4567)
    yield from run_with_participation(spec, state, lambda slot, comm_index, comm: rng.sample(comm, len(comm) // 3))


@with_all_phases
@spec_state_test
@leaking()
def test_random_fill_attestations_with_leak(spec, state):
    rng = Random(4567)
    yield from run_with_participation(spec, state, lambda slot, comm_index, comm: rng.sample(comm, len(comm) // 3))


@with_all_phases
@spec_state_test
def test_almost_full_attestations(spec, state):
    rng = Random(8901)
    yield from run_with_participation(spec, state, lambda slot, comm_index, comm: rng.sample(comm, len(comm) - 1))


@with_all_phases
@spec_state_test
@leaking()
def test_almost_full_attestations_with_leak(spec, state):
    rng = Random(8901)
    yield from run_with_participation(spec, state, lambda slot, comm_index, comm: rng.sample(comm, len(comm) - 1))


@with_all_phases
@spec_state_test
def test_full_attestation_participation(spec, state):
    yield from run_with_participation(spec, state, lambda slot, comm_index, comm: comm)


@with_all_phases
@spec_state_test
@leaking()
def test_full_attestation_participation_with_leak(spec, state):
    yield from run_with_participation(spec, state, lambda slot, comm_index, comm: comm)


@with_all_phases
@spec_state_test
def test_duplicate_attestation(spec, state):
    """
    Although duplicate attestations can be included on-chain, they should only
    be rewarded for once.
    This test addresses this issue found at Interop
    https://github.com/djrtwo/interop-test-cases/tree/master/tests/prysm_16_duplicate_attestation_rewards
    """
    attestation = get_valid_attestation(spec, state, signed=True)

    indexed_attestation = spec.get_indexed_attestation(state, attestation)
    participants = get_indexed_attestation_participants(spec, indexed_attestation)

    assert len(participants) > 0

    single_state = state.copy()
    dup_state = state.copy()

    inclusion_slot = state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY
    add_attestations_to_state(spec, single_state, [attestation], inclusion_slot)
    add_attestations_to_state(spec, dup_state, [attestation, attestation], inclusion_slot)

    next_epoch(spec, single_state)
    next_epoch(spec, dup_state)

    # Run non-duplicate inclusion rewards for comparison. Do not yield test vectors
    for _ in run_process_rewards_and_penalties(spec, single_state):
        pass

    # Output duplicate inclusion to test vectors
    yield from run_process_rewards_and_penalties(spec, dup_state)

    for index in participants:
        assert state.balances[index] < single_state.balances[index]
        assert single_state.balances[index] == dup_state.balances[index]


# TODO: update to all phases when https://github.com/ethereum/eth2.0-specs/pull/2024 is merged
# Currently disabled for Phase 1+ due to the mechanics of on-time-attestations complicating what should be a simple test
@with_phases([PHASE0])
@spec_state_test
def test_duplicate_participants_different_attestation_1(spec, state):
    """
    Same attesters get two different attestations on chain for the same inclusion delay
    Earlier attestation (by list order) is correct, later has incorrect head
    Note: although these are slashable, they can validly be included
    """
    correct_attestation = get_valid_attestation(spec, state, signed=True)
    incorrect_attestation = correct_attestation.copy()
    incorrect_attestation.data.beacon_block_root = b'\x42' * 32
    sign_attestation(spec, state, incorrect_attestation)

    indexed_attestation = spec.get_indexed_attestation(state, correct_attestation)
    participants = get_indexed_attestation_participants(spec, indexed_attestation)

    assert len(participants) > 0

    single_correct_state = state.copy()
    dup_state = state.copy()

    inclusion_slot = state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY
    add_attestations_to_state(spec, single_correct_state, [correct_attestation], inclusion_slot)
    add_attestations_to_state(spec, dup_state, [correct_attestation, incorrect_attestation], inclusion_slot)

    next_epoch(spec, single_correct_state)
    next_epoch(spec, dup_state)

    # Run non-duplicate inclusion rewards for comparison. Do not yield test vectors
    for _ in run_process_rewards_and_penalties(spec, single_correct_state):
        pass

    # Output duplicate inclusion to test vectors
    yield from run_process_rewards_and_penalties(spec, dup_state)

    for index in participants:
        assert state.balances[index] < single_correct_state.balances[index]
        assert single_correct_state.balances[index] == dup_state.balances[index]


# TODO: update to all phases when https://github.com/ethereum/eth2.0-specs/pull/2024 is merged
# Currently disabled for Phase 1+ due to the mechanics of on-time-attestations complicating what should be a simple test
@with_phases([PHASE0])
@spec_state_test
def test_duplicate_participants_different_attestation_2(spec, state):
    """
    Same attesters get two different attestations on chain for the same inclusion delay
    Earlier attestation (by list order) has incorrect head, later is correct
    Note: although these are slashable, they can validly be included
    """
    correct_attestation = get_valid_attestation(spec, state, signed=True)
    incorrect_attestation = correct_attestation.copy()
    incorrect_attestation.data.beacon_block_root = b'\x42' * 32
    sign_attestation(spec, state, incorrect_attestation)

    indexed_attestation = spec.get_indexed_attestation(state, correct_attestation)
    participants = get_indexed_attestation_participants(spec, indexed_attestation)

    assert len(participants) > 0

    single_correct_state = state.copy()
    dup_state = state.copy()

    inclusion_slot = state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY
    add_attestations_to_state(spec, single_correct_state, [correct_attestation], inclusion_slot)
    add_attestations_to_state(spec, dup_state, [incorrect_attestation, correct_attestation], inclusion_slot)

    next_epoch(spec, single_correct_state)
    next_epoch(spec, dup_state)

    # Run non-duplicate inclusion rewards for comparison. Do not yield test vectors
    for _ in run_process_rewards_and_penalties(spec, single_correct_state):
        pass

    # Output duplicate inclusion to test vectors
    yield from run_process_rewards_and_penalties(spec, dup_state)

    for index in participants:
        assert state.balances[index] < single_correct_state.balances[index]
        # Inclusion delay does not take into account correctness so equal reward
        assert single_correct_state.balances[index] == dup_state.balances[index]


# TODO: update to all phases when https://github.com/ethereum/eth2.0-specs/pull/2024 is merged
# Currently disabled for Phase 1+ due to the mechanics of on-time-attestations complicating what should be a simple test
@with_phases([PHASE0])
@spec_state_test
def test_duplicate_participants_different_attestation_3(spec, state):
    """
    Same attesters get two different attestations on chain for *different* inclusion delay
    Earlier attestation (by list order) has incorrect head, later is correct
    Note: although these are slashable, they can validly be included
    """
    correct_attestation = get_valid_attestation(spec, state, signed=True)
    incorrect_attestation = correct_attestation.copy()
    incorrect_attestation.data.beacon_block_root = b'\x42' * 32
    sign_attestation(spec, state, incorrect_attestation)

    indexed_attestation = spec.get_indexed_attestation(state, correct_attestation)
    participants = get_indexed_attestation_participants(spec, indexed_attestation)

    assert len(participants) > 0

    single_correct_state = state.copy()
    dup_state = state.copy()

    inclusion_slot = state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY
    add_attestations_to_state(spec, single_correct_state, [correct_attestation], inclusion_slot)
    add_attestations_to_state(spec, dup_state, [incorrect_attestation], inclusion_slot)
    add_attestations_to_state(spec, dup_state, [correct_attestation], inclusion_slot + 1)

    next_epoch(spec, single_correct_state)
    next_epoch(spec, dup_state)

    # Run non-duplicate inclusion rewards for comparison. Do not yield test vectors
    for _ in run_process_rewards_and_penalties(spec, single_correct_state):
        pass

    # Output duplicate inclusion to test vectors
    yield from run_process_rewards_and_penalties(spec, dup_state)

    for index in participants:
        assert state.balances[index] < single_correct_state.balances[index]
        # Inclusion delay does not take into account correctness so equal reward
        assert single_correct_state.balances[index] == dup_state.balances[index]


@with_all_phases
@spec_state_test
# Case when some eligible attestations are slashed. Modifies attesting_balance and consequently rewards/penalties.
def test_attestations_some_slashed(spec, state):
    attestations = prepare_state_with_attestations(spec, state)
    attesting_indices_before_slashings = list(spec.get_unslashed_attesting_indices(state, attestations))

    # Slash maximum amount of validators allowed per epoch.
    for i in range(spec.MIN_PER_EPOCH_CHURN_LIMIT):
        spec.slash_validator(state, attesting_indices_before_slashings[i])

    assert len(state.previous_epoch_attestations) == len(attestations)

    pre_state = state.copy()

    yield from run_process_rewards_and_penalties(spec, state)

    attesting_indices = spec.get_unslashed_attesting_indices(state, attestations)
    assert len(attesting_indices) > 0
    assert len(attesting_indices_before_slashings) - len(attesting_indices) == spec.MIN_PER_EPOCH_CHURN_LIMIT
    for index in range(len(pre_state.validators)):
        if index in attesting_indices:
            # non-slashed attester should gain reward
            assert state.balances[index] > pre_state.balances[index]
        else:
            # Slashed non-proposer attester should have penalty
            assert state.balances[index] < pre_state.balances[index]
