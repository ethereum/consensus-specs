from eth2spec.test.helpers.custody import (
    get_valid_bit_challenge,
    get_valid_chunk_challenge,
    get_valid_custody_bit_response,
    get_valid_custody_chunk_response,
    get_valid_custody_key_reveal,
    get_custody_test_vector,
    get_custody_merkle_root,
)
from eth2spec.test.helpers.attestations import (
    get_valid_attestation,
)
from eth2spec.test.helpers.state import next_epoch
from eth2spec.test.helpers.block import apply_empty_block
from eth2spec.test.context import (
    with_all_phases_except,
    spec_state_test,
)
from eth2spec.test.phase_0.block_processing.test_process_attestation import run_attestation_processing
from eth2spec.test.phase_0.epoch_processing.run_epoch_process_base import run_epoch_processing_with

from eth2spec.test.phase_1.block_processing.test_process_bit_challenge import (
    run_bit_challenge_processing,
    run_custody_bit_response_processing,
)
from eth2spec.test.phase_1.block_processing.test_process_chunk_challenge import (
    run_chunk_challenge_processing,
    run_custody_chunk_response_processing,
)
from eth2spec.test.phase_1.block_processing.test_process_custody_key_reveal import run_custody_key_reveal_processing


def run_process_final_custody_updates(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_final_custody_updates')


@with_all_phases_except(['phase0'])
@spec_state_test
def test_validator_withdrawal_delay(spec, state):
    spec.initiate_validator_exit(state, 0)
    assert state.validators[0].withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    yield from run_process_final_custody_updates(spec, state)

    assert state.validators[0].withdrawable_epoch == spec.FAR_FUTURE_EPOCH


@with_all_phases_except(['phase0'])
@spec_state_test
def test_validator_withdrawal_reenable_after_custody_reveal(spec, state):
    spec.initiate_validator_exit(state, 0)
    assert state.validators[0].withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    next_epoch(spec, state)
    apply_empty_block(spec, state)

    assert state.validators[0].withdrawable_epoch == spec.FAR_FUTURE_EPOCH

    while spec.get_current_epoch(state) < state.validators[0].exit_epoch:
        next_epoch(spec, state)
        apply_empty_block(spec, state)

    while (state.validators[0].next_custody_secret_to_reveal
           <= spec.get_custody_period_for_validator(state, 0, state.validators[0].exit_epoch - 1)):
        custody_key_reveal = get_valid_custody_key_reveal(spec, state, validator_index=0)
        _, _, _ = run_custody_key_reveal_processing(spec, state, custody_key_reveal)

    yield from run_process_final_custody_updates(spec, state)

    assert state.validators[0].withdrawable_epoch < spec.FAR_FUTURE_EPOCH


@with_all_phases_except(['phase0'])
@spec_state_test
def test_validator_withdrawal_suspend_after_bit_challenge(spec, state):
    state.slot = spec.SLOTS_PER_EPOCH

    attestation = get_valid_attestation(spec, state, signed=True)

    test_vector = get_custody_test_vector(
        spec.get_custody_chunk_count(attestation.data.crosslink) * spec.BYTES_PER_CUSTODY_CHUNK)
    shard_root = get_custody_merkle_root(test_vector)
    attestation.data.crosslink.data_root = shard_root
    attestation.custody_bits[0] = 0
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY
    next_epoch(spec, state)
    apply_empty_block(spec, state)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    validator_index = spec.get_crosslink_committee(
        state,
        attestation.data.target.epoch,
        attestation.data.crosslink.shard
    )[0]

    spec.initiate_validator_exit(state, validator_index)
    assert state.validators[validator_index].withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    next_epoch(spec, state)
    apply_empty_block(spec, state)

    assert state.validators[validator_index].withdrawable_epoch == spec.FAR_FUTURE_EPOCH

    while spec.get_current_epoch(state) < state.validators[validator_index].exit_epoch:
        next_epoch(spec, state)
        apply_empty_block(spec, state)

    while (state.validators[validator_index].next_custody_secret_to_reveal
           <= spec.get_custody_period_for_validator(
               state,
               validator_index,
               state.validators[validator_index].exit_epoch - 1)):
        custody_key_reveal = get_valid_custody_key_reveal(spec, state, validator_index=validator_index)
        _, _, _ = run_custody_key_reveal_processing(spec, state, custody_key_reveal)

    next_epoch(spec, state)
    apply_empty_block(spec, state)

    challenge = get_valid_bit_challenge(spec, state, attestation)

    _, _, _ = run_bit_challenge_processing(spec, state, challenge)

    yield from run_process_final_custody_updates(spec, state)

    assert state.validators[validator_index].withdrawable_epoch == spec.FAR_FUTURE_EPOCH


@with_all_phases_except(['phase0'])
@spec_state_test
def test_validator_withdrawal_suspend_after_chunk_challenge(spec, state):
    state.slot = spec.SLOTS_PER_EPOCH

    attestation = get_valid_attestation(spec, state, signed=True)

    test_vector = get_custody_test_vector(
        spec.get_custody_chunk_count(attestation.data.crosslink) * spec.BYTES_PER_CUSTODY_CHUNK)
    shard_root = get_custody_merkle_root(test_vector)
    attestation.data.crosslink.data_root = shard_root
    attestation.custody_bits[0] = 0
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY
    next_epoch(spec, state)
    apply_empty_block(spec, state)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    validator_index = spec.get_crosslink_committee(
        state,
        attestation.data.target.epoch,
        attestation.data.crosslink.shard
    )[0]

    spec.initiate_validator_exit(state, validator_index)
    assert state.validators[validator_index].withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    next_epoch(spec, state)
    apply_empty_block(spec, state)

    assert state.validators[validator_index].withdrawable_epoch == spec.FAR_FUTURE_EPOCH

    while spec.get_current_epoch(state) < state.validators[validator_index].exit_epoch:
        next_epoch(spec, state)
        apply_empty_block(spec, state)

    while (state.validators[validator_index].next_custody_secret_to_reveal
           <= spec.get_custody_period_for_validator(
               state,
               validator_index,
               state.validators[validator_index].exit_epoch - 1)):
        custody_key_reveal = get_valid_custody_key_reveal(spec, state, validator_index=validator_index)
        _, _, _ = run_custody_key_reveal_processing(spec, state, custody_key_reveal)

    next_epoch(spec, state)
    apply_empty_block(spec, state)

    challenge = get_valid_chunk_challenge(spec, state, attestation)

    _, _, _ = run_chunk_challenge_processing(spec, state, challenge)

    yield from run_process_final_custody_updates(spec, state)

    assert state.validators[validator_index].withdrawable_epoch == spec.FAR_FUTURE_EPOCH


@with_all_phases_except(['phase0'])
@spec_state_test
def test_validator_withdrawal_resume_after_bit_challenge_response(spec, state):
    state.slot = spec.SLOTS_PER_EPOCH

    attestation = get_valid_attestation(spec, state, signed=True)

    test_vector = get_custody_test_vector(
        spec.get_custody_chunk_count(attestation.data.crosslink) * spec.BYTES_PER_CUSTODY_CHUNK)
    shard_root = get_custody_merkle_root(test_vector)
    attestation.data.crosslink.data_root = shard_root
    attestation.custody_bits[0] = 0
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY
    next_epoch(spec, state)
    apply_empty_block(spec, state)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    validator_index = spec.get_crosslink_committee(
        state,
        attestation.data.target.epoch,
        attestation.data.crosslink.shard
    )[0]

    spec.initiate_validator_exit(state, validator_index)
    assert state.validators[validator_index].withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    next_epoch(spec, state)
    apply_empty_block(spec, state)

    assert state.validators[validator_index].withdrawable_epoch == spec.FAR_FUTURE_EPOCH

    while spec.get_current_epoch(state) < state.validators[validator_index].exit_epoch:
        next_epoch(spec, state)
        apply_empty_block(spec, state)

    while (state.validators[validator_index].next_custody_secret_to_reveal
           <= spec.get_custody_period_for_validator(
               state,
               validator_index,
               state.validators[validator_index].exit_epoch - 1)):
        custody_key_reveal = get_valid_custody_key_reveal(spec, state, validator_index=validator_index)
        _, _, _ = run_custody_key_reveal_processing(spec, state, custody_key_reveal)

    next_epoch(spec, state)
    apply_empty_block(spec, state)

    challenge = get_valid_bit_challenge(spec, state, attestation)

    _, _, _ = run_bit_challenge_processing(spec, state, challenge)

    next_epoch(spec, state)
    apply_empty_block(spec, state)

    assert state.validators[validator_index].withdrawable_epoch == spec.FAR_FUTURE_EPOCH

    bit_challenge_index = state.custody_bit_challenge_index - 1
    response = get_valid_custody_bit_response(
        spec,
        state,
        challenge,
        test_vector,
        bit_challenge_index,
        invalid_chunk_bit=False)

    _, _, _ = run_custody_bit_response_processing(spec, state, response)

    yield from run_process_final_custody_updates(spec, state)

    assert state.validators[validator_index].withdrawable_epoch < spec.FAR_FUTURE_EPOCH


@with_all_phases_except(['phase0'])
@spec_state_test
def test_validator_withdrawal_resume_after_chunk_challenge_response(spec, state):
    state.slot = spec.SLOTS_PER_EPOCH

    attestation = get_valid_attestation(spec, state, signed=True)

    test_vector = get_custody_test_vector(
        spec.get_custody_chunk_count(attestation.data.crosslink) * spec.BYTES_PER_CUSTODY_CHUNK)
    shard_root = get_custody_merkle_root(test_vector)
    attestation.data.crosslink.data_root = shard_root
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY
    next_epoch(spec, state)
    apply_empty_block(spec, state)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    validator_index = spec.get_crosslink_committee(
        state,
        attestation.data.target.epoch,
        attestation.data.crosslink.shard
    )[0]

    spec.initiate_validator_exit(state, validator_index)
    assert state.validators[validator_index].withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    next_epoch(spec, state)
    apply_empty_block(spec, state)

    assert state.validators[validator_index].withdrawable_epoch == spec.FAR_FUTURE_EPOCH

    while spec.get_current_epoch(state) < state.validators[validator_index].exit_epoch:
        next_epoch(spec, state)
        apply_empty_block(spec, state)

    while (state.validators[validator_index].next_custody_secret_to_reveal
           <= spec.get_custody_period_for_validator(
               state,
               validator_index,
               state.validators[validator_index].exit_epoch - 1)):
        custody_key_reveal = get_valid_custody_key_reveal(spec, state, validator_index=validator_index)
        _, _, _ = run_custody_key_reveal_processing(spec, state, custody_key_reveal)

    next_epoch(spec, state)
    apply_empty_block(spec, state)

    challenge = get_valid_chunk_challenge(spec, state, attestation)

    _, _, _ = run_chunk_challenge_processing(spec, state, challenge)

    next_epoch(spec, state)
    apply_empty_block(spec, state)

    assert state.validators[validator_index].withdrawable_epoch == spec.FAR_FUTURE_EPOCH

    chunk_challenge_index = state.custody_chunk_challenge_index - 1
    response = get_valid_custody_chunk_response(spec, state, challenge, test_vector, chunk_challenge_index)

    _, _, _ = run_custody_chunk_response_processing(spec, state, response)

    yield from run_process_final_custody_updates(spec, state)

    assert state.validators[validator_index].withdrawable_epoch < spec.FAR_FUTURE_EPOCH
