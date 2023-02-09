from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
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


def _run_validate_blobs_sidecar_test(spec, state, blob_count):
    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, blobs, blob_kzg_commitments = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    state_transition_and_sign_block(spec, state, block)

    blobs_sidecar = spec.get_blobs_sidecar(block, blobs)
    expected_commitments = [spec.blob_to_kzg_commitment(blobs[i]) for i in range(blob_count)]
    spec.validate_blobs_sidecar(block.slot, block.hash_tree_root(), expected_commitments, blobs_sidecar)


@with_deneb_and_later
@spec_state_test
def test_validate_blobs_sidecar_zero_blobs(spec, state):
    _run_validate_blobs_sidecar_test(spec, state, blob_count=0)


@with_deneb_and_later
@spec_state_test
def test_validate_blobs_sidecar_one_blob(spec, state):
    _run_validate_blobs_sidecar_test(spec, state, blob_count=1)


@with_deneb_and_later
@spec_state_test
def test_validate_blobs_sidecar_two_blobs(spec, state):
    _run_validate_blobs_sidecar_test(spec, state, blob_count=2)


@with_deneb_and_later
@spec_state_test
def test_validate_blobs_sidecar_max_blobs(spec, state):
    _run_validate_blobs_sidecar_test(spec, state, blob_count=spec.MAX_BLOBS_PER_BLOCK)
