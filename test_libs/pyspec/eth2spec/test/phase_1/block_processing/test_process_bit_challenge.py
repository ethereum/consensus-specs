from eth2spec.test.helpers.custody import (
    get_valid_bit_challenge,
    get_valid_custody_bit_response,
    get_custody_test_vector,
    get_custody_merkle_root,
)
from eth2spec.test.helpers.attestations import (
    get_valid_attestation,
)
from eth2spec.utils.ssz.ssz_impl import hash_tree_root
from eth2spec.test.helpers.state import next_epoch, get_balance
from eth2spec.test.helpers.block import apply_empty_block
from eth2spec.test.context import (
    with_all_phases_except,
    spec_state_test,
    expect_assertion_error,
)
from eth2spec.test.phase_0.block_processing.test_process_attestation import run_attestation_processing


def run_bit_challenge_processing(spec, state, custody_bit_challenge, valid=True):
    """
    Run ``process_bit_challenge``, yielding:
      - pre-state ('pre')
      - CustodyBitChallenge ('custody_bit_challenge')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield 'pre', state
    yield 'custody_bit_challenge', custody_bit_challenge

    if not valid:
        expect_assertion_error(lambda: spec.process_bit_challenge(state, custody_bit_challenge))
        yield 'post', None
        return

    spec.process_bit_challenge(state, custody_bit_challenge)

    assert state.custody_bit_challenge_records[state.custody_bit_challenge_index - 1].chunk_bits_merkle_root == \
        hash_tree_root(custody_bit_challenge.chunk_bits)
    assert state.custody_bit_challenge_records[state.custody_bit_challenge_index - 1].challenger_index == \
        custody_bit_challenge.challenger_index
    assert state.custody_bit_challenge_records[state.custody_bit_challenge_index - 1].responder_index == \
        custody_bit_challenge.responder_index

    yield 'post', state


def run_custody_bit_response_processing(spec, state, custody_response, valid=True):
    """
    Run ``process_bit_challenge_response``, yielding:
      - pre-state ('pre')
      - CustodyResponse ('custody_response')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield 'pre', state
    yield 'custody_response', custody_response

    if not valid:
        expect_assertion_error(lambda: spec.process_custody_response(state, custody_response))
        yield 'post', None
        return

    challenge = state.custody_bit_challenge_records[custody_response.challenge_index]
    pre_slashed_balance = get_balance(state, challenge.challenger_index)

    spec.process_custody_response(state, custody_response)

    slashed_validator = state.validators[challenge.challenger_index]

    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    assert get_balance(state, challenge.challenger_index) < pre_slashed_balance
    yield 'post', state


@with_all_phases_except(['phase0'])
@spec_state_test
def test_challenge_appended(spec, state):
    state.slot = spec.SLOTS_PER_EPOCH
    attestation = get_valid_attestation(spec, state, signed=True)

    test_vector = get_custody_test_vector(
        spec.get_custody_chunk_count(attestation.data.crosslink) * spec.BYTES_PER_CUSTODY_CHUNK)
    shard_root = get_custody_merkle_root(test_vector)
    attestation.data.crosslink.data_root = shard_root
    attestation.custody_bits[0] = 0

    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    _, _, _ = run_attestation_processing(spec, state, attestation)

    state.slot += spec.SLOTS_PER_EPOCH * spec.EPOCHS_PER_CUSTODY_PERIOD

    challenge = get_valid_bit_challenge(spec, state, attestation)

    yield from run_bit_challenge_processing(spec, state, challenge)


@with_all_phases_except(['phase0'])
@spec_state_test
def test_multiple_epochs_custody(spec, state):
    state.slot = spec.SLOTS_PER_EPOCH * 3
    attestation = get_valid_attestation(spec, state, signed=True)

    test_vector = get_custody_test_vector(
        spec.get_custody_chunk_count(attestation.data.crosslink) * spec.BYTES_PER_CUSTODY_CHUNK)
    shard_root = get_custody_merkle_root(test_vector)
    attestation.data.crosslink.data_root = shard_root
    attestation.custody_bits[0] = 0

    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    _, _, _ = run_attestation_processing(spec, state, attestation)

    state.slot += spec.SLOTS_PER_EPOCH * (spec.EPOCHS_PER_CUSTODY_PERIOD - 1)

    challenge = get_valid_bit_challenge(spec, state, attestation)

    yield from run_bit_challenge_processing(spec, state, challenge)


@with_all_phases_except(['phase0'])
@spec_state_test
def test_many_epochs_custody(spec, state):
    state.slot = spec.SLOTS_PER_EPOCH * 100
    attestation = get_valid_attestation(spec, state, signed=True)

    test_vector = get_custody_test_vector(
        spec.get_custody_chunk_count(attestation.data.crosslink) * spec.BYTES_PER_CUSTODY_CHUNK)
    shard_root = get_custody_merkle_root(test_vector)
    attestation.data.crosslink.data_root = shard_root
    attestation.custody_bits[0] = 0

    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    _, _, _ = run_attestation_processing(spec, state, attestation)

    state.slot += spec.SLOTS_PER_EPOCH * (spec.EPOCHS_PER_CUSTODY_PERIOD - 1)

    challenge = get_valid_bit_challenge(spec, state, attestation)

    yield from run_bit_challenge_processing(spec, state, challenge)


@with_all_phases_except(['phase0'])
@spec_state_test
def test_off_chain_attestation(spec, state):
    state.slot = spec.SLOTS_PER_EPOCH
    attestation = get_valid_attestation(spec, state, signed=True)

    test_vector = get_custody_test_vector(
        spec.get_custody_chunk_count(attestation.data.crosslink) * spec.BYTES_PER_CUSTODY_CHUNK)
    shard_root = get_custody_merkle_root(test_vector)
    attestation.data.crosslink.data_root = shard_root
    attestation.custody_bits[0] = 0

    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY
    state.slot += spec.SLOTS_PER_EPOCH * spec.EPOCHS_PER_CUSTODY_PERIOD

    challenge = get_valid_bit_challenge(spec, state, attestation)

    yield from run_bit_challenge_processing(spec, state, challenge)


@with_all_phases_except(['phase0'])
@spec_state_test
def test_invalid_custody_bit_challenge(spec, state):
    state.slot = spec.SLOTS_PER_EPOCH
    attestation = get_valid_attestation(spec, state, signed=True)

    test_vector = get_custody_test_vector(
        spec.get_custody_chunk_count(attestation.data.crosslink) * spec.BYTES_PER_CUSTODY_CHUNK)
    shard_root = get_custody_merkle_root(test_vector)
    attestation.data.crosslink.data_root = shard_root
    attestation.custody_bits[0] = 0

    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    _, _, _ = run_attestation_processing(spec, state, attestation)

    state.slot += spec.SLOTS_PER_EPOCH * spec.EPOCHS_PER_CUSTODY_PERIOD

    challenge = get_valid_bit_challenge(spec, state, attestation, invalid_custody_bit=True)

    yield from run_bit_challenge_processing(spec, state, challenge, valid=False)


@with_all_phases_except(['phase0'])
@spec_state_test
def test_max_reveal_lateness_1(spec, state):
    next_epoch(spec, state)
    apply_empty_block(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True)

    test_vector = get_custody_test_vector(
        spec.get_custody_chunk_count(attestation.data.crosslink) * spec.BYTES_PER_CUSTODY_CHUNK)
    shard_root = get_custody_merkle_root(test_vector)
    attestation.data.crosslink.data_root = shard_root
    attestation.custody_bits[0] = 0

    next_epoch(spec, state)
    apply_empty_block(spec, state)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    challenge = get_valid_bit_challenge(spec, state, attestation)

    responder_index = challenge.responder_index
    target_epoch = attestation.data.target.epoch

    state.validators[responder_index].max_reveal_lateness = 3

    latest_reveal_epoch = spec.get_randao_epoch_for_custody_period(
        spec.get_custody_period_for_validator(state, responder_index, target_epoch),
        responder_index
    ) + 2 * spec.EPOCHS_PER_CUSTODY_PERIOD + state.validators[responder_index].max_reveal_lateness

    while spec.get_current_epoch(state) < latest_reveal_epoch - 2:
        next_epoch(spec, state)
        apply_empty_block(spec, state)

    yield from run_bit_challenge_processing(spec, state, challenge)


@with_all_phases_except(['phase0'])
@spec_state_test
def test_max_reveal_lateness_2(spec, state):
    next_epoch(spec, state)
    apply_empty_block(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True)

    test_vector = get_custody_test_vector(
        spec.get_custody_chunk_count(attestation.data.crosslink) * spec.BYTES_PER_CUSTODY_CHUNK)
    shard_root = get_custody_merkle_root(test_vector)
    attestation.data.crosslink.data_root = shard_root
    attestation.custody_bits[0] = 0

    next_epoch(spec, state)
    apply_empty_block(spec, state)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    challenge = get_valid_bit_challenge(spec, state, attestation)

    responder_index = challenge.responder_index

    state.validators[responder_index].max_reveal_lateness = 3

    for i in range(spec.get_randao_epoch_for_custody_period(
        spec.get_custody_period_for_validator(state, responder_index),
        responder_index
    ) + 2 * spec.EPOCHS_PER_CUSTODY_PERIOD + state.validators[responder_index].max_reveal_lateness - 1):
        next_epoch(spec, state)
        apply_empty_block(spec, state)

    yield from run_bit_challenge_processing(spec, state, challenge, False)


@with_all_phases_except(['phase0'])
@spec_state_test
def test_custody_response(spec, state):
    state.slot = spec.SLOTS_PER_EPOCH
    attestation = get_valid_attestation(spec, state, signed=True)

    test_vector = get_custody_test_vector(
        spec.get_custody_chunk_count(attestation.data.crosslink) * spec.BYTES_PER_CUSTODY_CHUNK)
    shard_root = get_custody_merkle_root(test_vector)
    attestation.data.crosslink.data_root = shard_root
    attestation.custody_bits[0] = 0

    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    _, _, _ = run_attestation_processing(spec, state, attestation)

    state.slot += spec.SLOTS_PER_EPOCH * spec.EPOCHS_PER_CUSTODY_PERIOD

    challenge = get_valid_bit_challenge(spec, state, attestation)

    _, _, _ = run_bit_challenge_processing(spec, state, challenge)

    bit_challenge_index = state.custody_bit_challenge_index - 1

    custody_response = get_valid_custody_bit_response(spec, state, challenge, test_vector, bit_challenge_index)

    yield from run_custody_bit_response_processing(spec, state, custody_response)


@with_all_phases_except(['phase0'])
@spec_state_test
def test_custody_response_multiple_epochs(spec, state):
    state.slot = spec.SLOTS_PER_EPOCH * 3
    attestation = get_valid_attestation(spec, state, signed=True)

    test_vector = get_custody_test_vector(
        spec.get_custody_chunk_count(attestation.data.crosslink) * spec.BYTES_PER_CUSTODY_CHUNK)
    shard_root = get_custody_merkle_root(test_vector)
    attestation.data.crosslink.data_root = shard_root
    attestation.custody_bits[0] = 0

    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    _, _, _ = run_attestation_processing(spec, state, attestation)

    state.slot += spec.SLOTS_PER_EPOCH * spec.EPOCHS_PER_CUSTODY_PERIOD

    challenge = get_valid_bit_challenge(spec, state, attestation)

    _, _, _ = run_bit_challenge_processing(spec, state, challenge)

    bit_challenge_index = state.custody_bit_challenge_index - 1

    custody_response = get_valid_custody_bit_response(spec, state, challenge, test_vector, bit_challenge_index)

    yield from run_custody_bit_response_processing(spec, state, custody_response)


@with_all_phases_except(['phase0'])
@spec_state_test
def test_custody_response_many_epochs(spec, state):
    state.slot = spec.SLOTS_PER_EPOCH * 100
    attestation = get_valid_attestation(spec, state, signed=True)

    test_vector = get_custody_test_vector(
        spec.get_custody_chunk_count(attestation.data.crosslink) * spec.BYTES_PER_CUSTODY_CHUNK)
    shard_root = get_custody_merkle_root(test_vector)
    attestation.data.crosslink.data_root = shard_root
    attestation.custody_bits[0] = 0

    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    _, _, _ = run_attestation_processing(spec, state, attestation)

    state.slot += spec.SLOTS_PER_EPOCH * spec.EPOCHS_PER_CUSTODY_PERIOD

    challenge = get_valid_bit_challenge(spec, state, attestation)

    _, _, _ = run_bit_challenge_processing(spec, state, challenge)

    bit_challenge_index = state.custody_bit_challenge_index - 1

    custody_response = get_valid_custody_bit_response(spec, state, challenge, test_vector, bit_challenge_index)

    yield from run_custody_bit_response_processing(spec, state, custody_response)
