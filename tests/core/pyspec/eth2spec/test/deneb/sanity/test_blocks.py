import random

from eth2spec.test.helpers.state import (
    state_transition_and_sign_block
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot
)
from eth2spec.test.context import (
    spec_state_test,
    with_deneb_and_later,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)
from eth2spec.test.helpers.sharding import (
    get_sample_opaque_tx,
)


def run_block_with_blobs(spec, state, blob_count, excess_data_gas=1):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, _, blob_kzg_commitments, _ = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.excess_data_gas = excess_data_gas
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state


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
def test_max_blobs(spec, state):
    yield from run_block_with_blobs(spec, state, blob_count=spec.MAX_BLOBS_PER_BLOCK)


@with_deneb_and_later
@spec_state_test
def test_invalid_incorrect_blob_tx_type(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, _, blob_kzg_commitments, _ = get_sample_opaque_tx(spec)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    opaque_tx = b'\x04' + opaque_tx[1:]  # incorrect tx type
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', None


@with_deneb_and_later
@spec_state_test
def test_invalid_incorrect_transaction_length_1_byte(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, _, blob_kzg_commitments, _ = get_sample_opaque_tx(spec)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    opaque_tx = opaque_tx + b'\x12'  # incorrect tx length
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', None


@with_deneb_and_later
@spec_state_test
def test_invalid_incorrect_transaction_length_32_bytes(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, _, blob_kzg_commitments, _ = get_sample_opaque_tx(spec)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    opaque_tx = opaque_tx + b'\x12' * 32  # incorrect tx length
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', None


@with_deneb_and_later
@spec_state_test
def test_invalid_incorrect_commitment(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, _, blob_kzg_commitments, _ = get_sample_opaque_tx(spec)
    blob_kzg_commitments[0] = b'\x12' * 48  # incorrect commitment
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', None


@with_deneb_and_later
@spec_state_test
def test_invalid_incorrect_commitments_order(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, _, blob_kzg_commitments, _ = get_sample_opaque_tx(spec, blob_count=2, rng=random.Random(1111))
    block.body.blob_kzg_commitments = [blob_kzg_commitments[1], blob_kzg_commitments[0]]  # incorrect order
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', None


@with_deneb_and_later
@spec_state_test
def test_incorrect_block_hash(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, _, blob_kzg_commitments, _ = get_sample_opaque_tx(spec)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = b'\x12' * 32  # incorrect block hash
    # CL itself doesn't verify EL block hash
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state
