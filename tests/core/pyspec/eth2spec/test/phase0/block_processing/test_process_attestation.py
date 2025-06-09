from eth2spec.test.context import (
    always_bls,
    low_balances,
    never_bls,
    single_phase,
    spec_state_test,
    spec_test,
    with_all_phases,
    with_custom_state,
)
from eth2spec.test.helpers.attestations import (
    compute_max_inclusion_slot,
    get_valid_attestation,
    run_attestation_processing,
    sign_aggregate_attestation,
    sign_attestation,
)
from eth2spec.test.helpers.state import (
    next_epoch_via_block,
    next_slots,
    transition_to_slot_via_block,
)
from eth2spec.utils.ssz.ssz_typing import Bitlist


@with_all_phases
@spec_state_test
def test_one_basic_attestation(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_test
@with_custom_state(balances_fn=low_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@single_phase
def test_multi_proposer_index_iterations(spec, state):
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 2)
    attestation = get_valid_attestation(spec, state, signed=True)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_previous_epoch(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)
    next_epoch_via_block(spec, state)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_attestation_signature(spec, state):
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_empty_participants_zeroes_sig(spec, state):
    attestation = get_valid_attestation(
        spec, state, filter_participant_set=lambda comm: []
    )  # 0 participants
    attestation.signature = spec.BLSSignature(b"\x00" * 96)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_empty_participants_seemingly_valid_sig(spec, state):
    attestation = get_valid_attestation(
        spec, state, filter_participant_set=lambda comm: []
    )  # 0 participants
    # Special BLS value, valid for zero pubkeys on some (but not all) BLS implementations.
    attestation.signature = spec.BLSSignature(b"\xc0" + b"\x00" * 95)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_before_inclusion_delay(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)
    # do not increment slot to allow for inclusion delay

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
def test_at_max_inclusion_slot(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)

    # increment past latest inclusion slot
    transition_to_slot_via_block(spec, state, compute_max_inclusion_slot(spec, attestation))

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_invalid_after_max_inclusion_slot(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)

    # increment past latest inclusion slot
    transition_to_slot_via_block(spec, state, compute_max_inclusion_slot(spec, attestation) + 1)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_old_source_epoch(spec, state):
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 5)
    state.finalized_checkpoint.epoch = 2
    state.previous_justified_checkpoint.epoch = 3
    state.current_justified_checkpoint.epoch = 4
    attestation = get_valid_attestation(spec, state, slot=(spec.SLOTS_PER_EPOCH * 3) + 1)

    # test logic sanity check: make sure the attestation is pointing to oldest known source epoch
    assert attestation.data.source.epoch == state.previous_justified_checkpoint.epoch

    # Now go beyond that, it will be invalid
    attestation.data.source.epoch -= 1

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_wrong_index_for_committee_signature(spec, state):
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.data.index += 1

    yield from run_attestation_processing(spec, state, attestation, valid=False)


def reduce_state_committee_count_from_max(spec, state):
    """
    Modified ``state`` to ensure that it has fewer committees at each slot than ``MAX_COMMITTEES_PER_SLOT``
    """
    while (
        spec.get_committee_count_per_slot(state, spec.get_current_epoch(state))
        >= spec.MAX_COMMITTEES_PER_SLOT
    ):
        state.validators = state.validators[: len(state.validators) // 2]
        state.balances = state.balances[: len(state.balances) // 2]


@with_all_phases
@spec_state_test
@never_bls
def test_invalid_wrong_index_for_slot_0(spec, state):
    reduce_state_committee_count_from_max(spec, state)

    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # Invalid index: current committees per slot is less than the max
    attestation.data.index = spec.MAX_COMMITTEES_PER_SLOT - 1

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
@never_bls
def test_invalid_wrong_index_for_slot_1(spec, state):
    reduce_state_committee_count_from_max(spec, state)

    current_epoch = spec.get_current_epoch(state)
    committee_count = spec.get_committee_count_per_slot(state, current_epoch)

    attestation = get_valid_attestation(spec, state, index=0)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # Invalid index: off by one
    attestation.data.index = committee_count

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
@never_bls
def test_invalid_index(spec, state):
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # Invalid index: off by one (with respect to valid range) on purpose
    attestation.data.index = spec.MAX_COMMITTEES_PER_SLOT

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_mismatched_target_and_slot(spec, state):
    next_epoch_via_block(spec, state)
    next_epoch_via_block(spec, state)

    attestation = get_valid_attestation(spec, state)
    attestation.data.slot = attestation.data.slot - spec.SLOTS_PER_EPOCH

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_old_target_epoch(spec, state):
    assert spec.MIN_ATTESTATION_INCLUSION_DELAY < spec.SLOTS_PER_EPOCH * 2

    attestation = get_valid_attestation(spec, state, signed=True)

    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 2)  # target epoch will be too old to handle

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_future_target_epoch(spec, state):
    assert spec.MIN_ATTESTATION_INCLUSION_DELAY < spec.SLOTS_PER_EPOCH * 2

    attestation = get_valid_attestation(spec, state)

    participants = spec.get_attesting_indices(state, attestation)
    attestation.data.target.epoch = (
        spec.get_current_epoch(state) + 1
    )  # target epoch will be too new to handle

    # manually add signature for correct participants
    attestation.signature = sign_aggregate_attestation(spec, state, attestation.data, participants)

    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_new_source_epoch(spec, state):
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.data.source.epoch += 1

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_source_root_is_target_root(spec, state):
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.data.source.root = attestation.data.target.root

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_current_source_root(spec, state):
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 5)

    state.finalized_checkpoint.epoch = 2

    state.previous_justified_checkpoint = spec.Checkpoint(epoch=3, root=b"\x01" * 32)
    state.current_justified_checkpoint = spec.Checkpoint(epoch=4, root=b"\x32" * 32)

    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation = get_valid_attestation(spec, state, slot=spec.SLOTS_PER_EPOCH * 5)

    # Test logic sanity checks:
    assert attestation.data.target.epoch == spec.get_current_epoch(state)
    assert state.current_justified_checkpoint.root != state.previous_justified_checkpoint.root
    assert attestation.data.source.root == state.current_justified_checkpoint.root

    # Make attestation source root invalid: should be current justified, not previous one
    attestation.data.source.root = state.previous_justified_checkpoint.root

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_previous_source_root(spec, state):
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 5)

    state.finalized_checkpoint.epoch = 2

    state.previous_justified_checkpoint = spec.Checkpoint(epoch=3, root=b"\x01" * 32)
    state.current_justified_checkpoint = spec.Checkpoint(epoch=4, root=b"\x32" * 32)

    attestation = get_valid_attestation(spec, state, slot=(spec.SLOTS_PER_EPOCH * 4) + 1)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # Test logic sanity checks:
    assert attestation.data.target.epoch == spec.get_previous_epoch(state)
    assert state.current_justified_checkpoint.root != state.previous_justified_checkpoint.root
    assert attestation.data.source.root == state.previous_justified_checkpoint.root

    # Make attestation source root invalid: should be previous justified, not current one
    attestation.data.source.root = state.current_justified_checkpoint.root

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_bad_source_root(spec, state):
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.data.source.root = b"\x42" * 32

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_too_many_aggregation_bits(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # one too many bits
    attestation.aggregation_bits.append(0b0)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_too_few_aggregation_bits(spec, state):
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.aggregation_bits = Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](
        *([0b1] + [0b0] * (len(attestation.aggregation_bits) - 1))
    )

    sign_attestation(spec, state, attestation)

    # one too few bits
    attestation.aggregation_bits = attestation.aggregation_bits[:-1]

    yield from run_attestation_processing(spec, state, attestation, valid=False)


#
# Full correct attestation contents at different slot inclusions
#


@with_all_phases
@spec_state_test
def test_correct_attestation_included_at_min_inclusion_delay(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_correct_attestation_included_at_sqrt_epoch_delay(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)
    next_slots(spec, state, spec.integer_squareroot(spec.SLOTS_PER_EPOCH))

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_correct_attestation_included_at_one_epoch_delay(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)
    next_slots(spec, state, spec.SLOTS_PER_EPOCH)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_correct_attestation_included_at_max_inclusion_slot(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)
    next_slots(spec, state, compute_max_inclusion_slot(spec, attestation))

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_invalid_correct_attestation_included_after_max_inclusion_slot(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)

    # increment past latest inclusion slot
    next_slots(spec, state, compute_max_inclusion_slot(spec, attestation) + 1)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


#
# Incorrect head but correct source/target at different slot inclusions
#


@with_all_phases
@spec_state_test
def test_incorrect_head_included_at_min_inclusion_delay(spec, state):
    attestation = get_valid_attestation(spec, state, signed=False)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.data.beacon_block_root = b"\x42" * 32
    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_incorrect_head_included_at_sqrt_epoch_delay(spec, state):
    attestation = get_valid_attestation(spec, state, signed=False)
    next_slots(spec, state, spec.integer_squareroot(spec.SLOTS_PER_EPOCH))

    attestation.data.beacon_block_root = b"\x42" * 32
    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_incorrect_head_included_at_max_inclusion_slot(spec, state):
    attestation = get_valid_attestation(spec, state, signed=False)
    next_slots(spec, state, compute_max_inclusion_slot(spec, attestation))

    attestation.data.beacon_block_root = b"\x42" * 32
    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_invalid_incorrect_head_included_after_max_inclusion_slot(spec, state):
    attestation = get_valid_attestation(spec, state, signed=False)

    # increment past latest inclusion slot
    next_slots(spec, state, compute_max_inclusion_slot(spec, attestation) + 1)

    attestation.data.beacon_block_root = b"\x42" * 32
    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


#
# Incorrect head and target but correct source at different slot inclusions
#


@with_all_phases
@spec_state_test
def test_incorrect_head_and_target_min_inclusion_delay(spec, state):
    attestation = get_valid_attestation(spec, state, signed=False)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.data.beacon_block_root = b"\x42" * 32
    attestation.data.target.root = b"\x42" * 32
    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_incorrect_head_and_target_included_at_sqrt_epoch_delay(spec, state):
    attestation = get_valid_attestation(spec, state, signed=False)
    next_slots(spec, state, spec.integer_squareroot(spec.SLOTS_PER_EPOCH))

    attestation.data.beacon_block_root = b"\x42" * 32
    attestation.data.target.root = b"\x42" * 32
    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_incorrect_head_and_target_included_at_epoch_delay(spec, state):
    attestation = get_valid_attestation(spec, state, signed=False)
    next_slots(spec, state, spec.SLOTS_PER_EPOCH)

    attestation.data.beacon_block_root = b"\x42" * 32
    attestation.data.target.root = b"\x42" * 32
    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_invalid_incorrect_head_and_target_included_after_max_inclusion_slot(spec, state):
    attestation = get_valid_attestation(spec, state, signed=False)
    # increment past latest inclusion slot
    next_slots(spec, state, compute_max_inclusion_slot(spec, attestation) + 1)

    attestation.data.beacon_block_root = b"\x42" * 32
    attestation.data.target.root = b"\x42" * 32
    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


#
# Correct head and source but incorrect target at different slot inclusions
#


@with_all_phases
@spec_state_test
def test_incorrect_target_included_at_min_inclusion_delay(spec, state):
    attestation = get_valid_attestation(spec, state, signed=False)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.data.target.root = b"\x42" * 32
    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_incorrect_target_included_at_sqrt_epoch_delay(spec, state):
    attestation = get_valid_attestation(spec, state, signed=False)
    next_slots(spec, state, spec.integer_squareroot(spec.SLOTS_PER_EPOCH))

    attestation.data.target.root = b"\x42" * 32
    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_incorrect_target_included_at_epoch_delay(spec, state):
    attestation = get_valid_attestation(spec, state, signed=False)
    next_slots(spec, state, spec.SLOTS_PER_EPOCH)

    attestation.data.target.root = b"\x42" * 32
    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_invalid_incorrect_target_included_after_max_inclusion_slot(spec, state):
    attestation = get_valid_attestation(spec, state, signed=False)
    # increment past latest inclusion slot
    next_slots(spec, state, compute_max_inclusion_slot(spec, attestation) + 1)

    attestation.data.target.root = b"\x42" * 32
    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=False)
