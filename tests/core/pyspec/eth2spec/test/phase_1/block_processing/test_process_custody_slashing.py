from eth2spec.test.helpers.custody import (
    get_valid_custody_slashing,
    get_custody_test_vector,
    get_custody_merkle_root,
    get_shard_transition,
)
from eth2spec.test.helpers.attestations import (
    get_valid_on_time_attestation,
)
from eth2spec.utils.ssz.ssz_impl import hash_tree_root
from eth2spec.utils.ssz.ssz_typing import ByteList
from eth2spec.test.helpers.state import next_epoch, get_balance, transition_to
from eth2spec.test.helpers.block import apply_empty_block
from eth2spec.test.context import (
    with_all_phases_except,
    spec_state_test,
    expect_assertion_error,
)
from eth2spec.test.phase_0.block_processing.test_process_attestation import run_attestation_processing


def run_custody_slashing_processing(spec, state, custody_slashing, valid=True, correct=True):
    """
    Run ``process_bit_challenge``, yielding:
      - pre-state ('pre')
      - CustodySlashing ('custody_slashing')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield 'pre', state
    yield 'custody_slashing', custody_slashing

    if not valid:
        expect_assertion_error(lambda: spec.process_custody_slashing(state, custody_slashing))
        yield 'post', None
        return

    if correct:
        pre_slashed_balance = get_balance(state, custody_slashing.message.malefactor_index)
    else:
        pre_slashed_balance = get_balance(state, custody_slashing.message.whistleblower_index)

    spec.process_custody_slashing(state, custody_slashing)

    if correct:
        slashed_validator = state.validators[custody_slashing.message.malefactor_index]
        assert get_balance(state, custody_slashing.message.malefactor_index) < pre_slashed_balance
    else:
        slashed_validator = state.validators[custody_slashing.message.whistleblower_index]
        assert get_balance(state, custody_slashing.message.whistleblower_index) < pre_slashed_balance
    
    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    yield 'post', state


@with_all_phases_except(['phase0'])
@spec_state_test
def test_custody_slashing(spec, state):
    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    shard = 0
    offset_slots = spec.get_offset_slots(state, shard)
    shard_transition = get_shard_transition(spec, state.slot, [2**15 // 3] * len(offset_slots))
    data_index = 0
    attestation = get_valid_on_time_attestation(spec, state, index=shard, signed=True, shard_transition=shard_transition, valid_custody_bits=False)

    transition_to(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH * (spec.EPOCHS_PER_CUSTODY_PERIOD - 1))

    data_index = 0

    slashing = get_valid_custody_slashing(spec, state, attestation, shard_transition)

    yield from run_custody_slashing_processing(spec, state, slashing, correct=True)


@with_all_phases_except(['phase0'])
@spec_state_test
def test_incorrect_custody_slashing(spec, state):
    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    shard = 0
    offset_slots = spec.get_offset_slots(state, shard)
    shard_transition = get_shard_transition(spec, state.slot, [2**15 // 3] * len(offset_slots))
    data_index = 0
    attestation = get_valid_on_time_attestation(spec, state, index=shard, signed=True, shard_transition=shard_transition, valid_custody_bits=True)

    transition_to(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH * (spec.EPOCHS_PER_CUSTODY_PERIOD - 1))

    data_index = 0

    slashing = get_valid_custody_slashing(spec, state, attestation, shard_transition)

    yield from run_custody_slashing_processing(spec, state, slashing, correct=False)


@with_all_phases_except(['phase0'])
@spec_state_test
def test_multiple_epochs_custody(spec, state):
    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH * 3)
    shard = 0
    offset_slots = spec.get_offset_slots(state, shard)
    shard_transition = get_shard_transition(spec, state.slot, [2**15 // 3] * len(offset_slots))
    data_index = 0
    attestation = get_valid_on_time_attestation(spec, state, index=shard, signed=True, shard_transition=shard_transition, valid_custody_bits=False)

    transition_to(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH * (spec.EPOCHS_PER_CUSTODY_PERIOD - 1))

    data_index = 0

    slashing = get_valid_custody_slashing(spec, state, attestation, shard_transition)

    yield from run_custody_slashing_processing(spec, state, slashing, correct=True)


@with_all_phases_except(['phase0'])
@spec_state_test
def test_many_epochs_custody(spec, state):
    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH* 100)
    shard = 0
    offset_slots = spec.get_offset_slots(state, shard)
    shard_transition = get_shard_transition(spec, state.slot, [2**15 // 3] * len(offset_slots))
    data_index = 0
    attestation = get_valid_on_time_attestation(spec, state, index=shard, signed=True, shard_transition=shard_transition, valid_custody_bits=False)

    transition_to(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH * (spec.EPOCHS_PER_CUSTODY_PERIOD - 1))

    data_index = 0

    slashing = get_valid_custody_slashing(spec, state, attestation, shard_transition)

    yield from run_custody_slashing_processing(spec, state, slashing, correct=True)


@with_all_phases_except(['phase0'])
@spec_state_test
def test_off_chain_attestation(spec, state):
    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    shard = 0
    offset_slots = spec.get_offset_slots(state, shard)
    shard_transition = get_shard_transition(spec, state.slot, [2**15 // 3] * len(offset_slots))
    data_index = 0
    attestation = get_valid_on_time_attestation(spec, state, index=shard, signed=True, shard_transition=shard_transition, valid_custody_bits=False)

    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH * (spec.EPOCHS_PER_CUSTODY_PERIOD - 1))

    data_index = 0

    slashing = get_valid_custody_slashing(spec, state, attestation, shard_transition)

    yield from run_custody_slashing_processing(spec, state, slashing, correct=True)


@with_all_phases_except(['phase0'])
@spec_state_test
def test_invalid_custody_slashing(spec, state):
    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    shard = 0
    offset_slots = spec.get_offset_slots(state, shard)
    shard_transition = get_shard_transition(spec, state.slot, [2**15 // 3] * len(offset_slots))
    data_index = 0
    attestation = get_valid_on_time_attestation(spec, state, index=shard, signed=True, shard_transition=shard_transition, valid_custody_bits=False)

    transition_to(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH * (spec.EPOCHS_PER_CUSTODY_PERIOD - 1))

    data_index = 0

    slashing = get_valid_custody_slashing(spec, state, attestation, shard_transition)

    slashing.message.data = ByteList[spec.MAX_SHARD_BLOCK_SIZE]()

    yield from run_custody_slashing_processing(spec, state, slashing, valid=False)
