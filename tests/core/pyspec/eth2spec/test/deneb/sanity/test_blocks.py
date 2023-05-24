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


def run_block_with_blobs(spec, state, blob_count, excess_data_gas=1, valid=True):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, _, blob_kzg_commitments, _ = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.excess_data_gas = excess_data_gas
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)

    print(len(block.body.blob_kzg_commitments))

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
