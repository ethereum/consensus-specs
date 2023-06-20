from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    next_epoch_via_block,
    transition_to,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.context import (
    DENEB,
    spec_state_test,
    spec_configured_state_test,
    with_deneb_and_later,
    with_phases,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)
from eth2spec.test.helpers.attestations import (
    get_valid_attestation,
)
from eth2spec.test.helpers.sharding import (
    get_sample_opaque_tx,
)


def run_block_with_blobs(spec, state, blob_count, data_gas_used=1, excess_data_gas=1, valid=True):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, _, blob_kzg_commitments, _ = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.data_gas_used = data_gas_used
    block.body.execution_payload.excess_data_gas = excess_data_gas
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)

    if valid:
        signed_block = state_transition_and_sign_block(spec, state, block)
    else:
        signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', state if valid else None


@with_deneb_and_later
@spec_state_test
def test_zero_blob(spec, state):
    yield from run_block_with_blobs(spec, state, blob_count=0)


@with_deneb_and_later
@spec_state_test
def test_one_blob(spec, state):
    yield from run_block_with_blobs(spec, state, blob_count=1)


@with_deneb_and_later
@spec_state_test
def test_max_blobs_per_block(spec, state):
    yield from run_block_with_blobs(spec, state, blob_count=spec.MAX_BLOBS_PER_BLOCK)


@with_deneb_and_later
@spec_state_test
def test_invalid_exceed_max_blobs_per_block(spec, state):
    yield from run_block_with_blobs(spec, state, blob_count=spec.MAX_BLOBS_PER_BLOCK + 1, valid=False)


@with_phases([DENEB])
@spec_configured_state_test({
    'DENEB_FORK_EPOCH': 2,
})
def test_include_attestation_from_previous_fork_with_new_range(spec, state):
    # Transition to the epoch prior to the fork epoch
    next_epoch_via_block(spec, state)

    # Generate an attestation for slot 0 of this epoch
    attestation = get_valid_attestation(spec, state, signed=True)

    # Transition to second to last slot in `DENEB_FORK_EPOCH`
    next_epoch_via_block(spec, state)
    current_epoch = spec.get_current_epoch(state)
    assert current_epoch == spec.config.DENEB_FORK_EPOCH
    penultimate_slot = spec.compute_start_slot_at_epoch(current_epoch + 1) - 2
    transition_to(spec, state, penultimate_slot)

    # Ensure the new state is in the increased EIP-7045 slot inclusion range
    assert penultimate_slot - attestation.data.slot > spec.SLOTS_PER_EPOCH

    block = build_empty_block_for_next_slot(spec, state)
    block.body.attestations.append(attestation)

    yield 'pre', state

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state
