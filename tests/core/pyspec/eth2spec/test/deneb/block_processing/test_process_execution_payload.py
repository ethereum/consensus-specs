from random import Random

from eth2spec.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_deneb_and_later,
)
from eth2spec.test.helpers.blob import (
    get_max_blob_count,
    get_sample_blob_tx,
)
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
    compute_el_block_hash,
    get_execution_payload_header,
)
from eth2spec.test.helpers.forks import is_post_eip7732
from eth2spec.test.helpers.keys import privkeys


def run_execution_payload_processing(
    spec, state, execution_payload, blob_kzg_commitments, valid=True, execution_valid=True
):
    """
    Run ``process_execution_payload``, yielding:
      - pre-state ('pre')
      - execution payload ('execution_payload')
      - execution details, to mock EVM execution ('execution.yml', a dict with 'execution_valid' key and boolean value)
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """

    # after EIP-7732 the execution payload is no longer in the body
    if is_post_eip7732(spec):
        envelope = spec.ExecutionPayloadEnvelope(
            payload=execution_payload,
            payload_withheld=False,
            blob_kzg_commitments=blob_kzg_commitments,
        )
        kzg_list = spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
            blob_kzg_commitments
        )
        state.latest_execution_payload_header.blob_kzg_commitments_root = kzg_list.hash_tree_root()
        post_state = state.copy()
        previous_state_root = state.hash_tree_root()
        if post_state.latest_block_header.state_root == spec.Root():
            post_state.latest_block_header.state_root = previous_state_root
        envelope.beacon_block_root = post_state.latest_block_header.hash_tree_root()

        post_state.latest_block_hash = execution_payload.block_hash
        post_state.latest_full_slot = state.slot
        envelope.state_root = post_state.hash_tree_root()
        privkey = privkeys[envelope.builder_index]
        signature = spec.get_execution_payload_envelope_signature(
            state,
            envelope,
            privkey,
        )
        signed_envelope = spec.SignedExecutionPayloadEnvelope(
            message=envelope,
            signature=signature,
        )
        body = spec.BeaconBlockBody()
    else:
        body = spec.BeaconBlockBody(
            blob_kzg_commitments=blob_kzg_commitments,
            execution_payload=execution_payload,
        )

    yield "pre", state
    yield "execution", {"execution_valid": execution_valid}
    yield "body", body

    called_new_block = False

    class TestEngine(spec.NoopExecutionEngine):
        def verify_and_notify_new_payload(self, new_payload_request) -> bool:
            nonlocal called_new_block
            called_new_block = True
            assert new_payload_request.execution_payload == execution_payload
            return execution_valid

    if not valid:
        if is_post_eip7732(spec):
            expect_assertion_error(
                lambda: spec.process_execution_payload(state, signed_envelope, TestEngine())
            )
        else:
            expect_assertion_error(
                lambda: spec.process_execution_payload(state, body, TestEngine())
            )
        yield "post", None
        return

    if is_post_eip7732(spec):
        spec.process_execution_payload(state, signed_envelope, TestEngine())
    else:
        spec.process_execution_payload(state, body, TestEngine())

    # Make sure we called the engine
    assert called_new_block

    yield "post", state

    if is_post_eip7732(spec):
        assert state.latest_block_hash == execution_payload.block_hash
        assert state.latest_full_slot == state.slot
    else:
        assert state.latest_execution_payload_header == get_execution_payload_header(
            spec, state, execution_payload
        )


"""
Tests with incorrect blob transactions in the execution payload, but the execution client returns
VALID, and the purpose of these tests is that the beacon client must not reject the block by
attempting to do a validation of its own.
"""


@with_deneb_and_later
@spec_state_test
def test_incorrect_blob_tx_type(spec, state):
    """
    The versioned hashes are wrong, but the testing ExecutionEngine returns VALID by default.
    """
    execution_payload = build_empty_execution_payload(spec, state)

    opaque_tx, _, blob_kzg_commitments, _ = get_sample_blob_tx(spec)
    opaque_tx = b"\x04" + opaque_tx[1:]  # incorrect tx type

    execution_payload.transactions = [opaque_tx]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    # Make the first block full in EIP-7732
    if is_post_eip7732(spec):
        state.latest_execution_payload_header.block_hash = execution_payload.block_hash

    yield from run_execution_payload_processing(
        spec, state, execution_payload, blob_kzg_commitments
    )


@with_deneb_and_later
@spec_state_test
def test_incorrect_transaction_length_1_extra_byte(spec, state):
    """
    The versioned hashes are wrong, but the testing ExecutionEngine returns VALID by default.
    """
    execution_payload = build_empty_execution_payload(spec, state)

    opaque_tx, _, blob_kzg_commitments, _ = get_sample_blob_tx(spec)
    opaque_tx = opaque_tx + b"\x12"  # incorrect tx length, longer

    execution_payload.transactions = [opaque_tx]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    # Make the first block full in EIP-7732
    if is_post_eip7732(spec):
        state.latest_execution_payload_header.block_hash = execution_payload.block_hash
    yield from run_execution_payload_processing(
        spec, state, execution_payload, blob_kzg_commitments
    )


@with_deneb_and_later
@spec_state_test
def test_incorrect_transaction_length_1_byte_short(spec, state):
    """
    The versioned hashes are wrong, but the testing ExecutionEngine returns VALID by default.
    """
    execution_payload = build_empty_execution_payload(spec, state)

    opaque_tx, _, blob_kzg_commitments, _ = get_sample_blob_tx(spec)
    opaque_tx = opaque_tx[:-1]  # incorrect tx length, shorter

    execution_payload.transactions = [opaque_tx]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    # Make the first block full in EIP-7732
    if is_post_eip7732(spec):
        state.latest_execution_payload_header.block_hash = execution_payload.block_hash
    yield from run_execution_payload_processing(
        spec, state, execution_payload, blob_kzg_commitments
    )


@with_deneb_and_later
@spec_state_test
def test_incorrect_transaction_length_empty(spec, state):
    """
    The versioned hashes are wrong, but the testing ExecutionEngine returns VALID by default.
    """
    execution_payload = build_empty_execution_payload(spec, state)

    opaque_tx, _, blob_kzg_commitments, _ = get_sample_blob_tx(spec)
    opaque_tx = opaque_tx[0:0]  # incorrect tx length, empty

    execution_payload.transactions = [opaque_tx]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    # Make the first block full in EIP-7732
    if is_post_eip7732(spec):
        state.latest_execution_payload_header.block_hash = execution_payload.block_hash
    yield from run_execution_payload_processing(
        spec, state, execution_payload, blob_kzg_commitments
    )


@with_deneb_and_later
@spec_state_test
def test_incorrect_transaction_length_32_extra_bytes(spec, state):
    """
    The versioned hashes are wrong, but the testing ExecutionEngine returns VALID by default.
    """
    execution_payload = build_empty_execution_payload(spec, state)

    opaque_tx, _, blob_kzg_commitments, _ = get_sample_blob_tx(spec)
    opaque_tx = opaque_tx + b"\x12" * 32  # incorrect tx length

    execution_payload.transactions = [opaque_tx]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    # Make the first block full in EIP-7732
    if is_post_eip7732(spec):
        state.latest_execution_payload_header.block_hash = execution_payload.block_hash
    yield from run_execution_payload_processing(
        spec, state, execution_payload, blob_kzg_commitments
    )


@with_deneb_and_later
@spec_state_test
def test_no_transactions_with_commitments(spec, state):
    """
    The versioned hashes are wrong, but the testing ExecutionEngine returns VALID by default.
    """
    execution_payload = build_empty_execution_payload(spec, state)

    _, _, blob_kzg_commitments, _ = get_sample_blob_tx(spec)

    execution_payload.transactions = []
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    # Make the first block full in EIP-7732
    if is_post_eip7732(spec):
        state.latest_execution_payload_header.block_hash = execution_payload.block_hash
    yield from run_execution_payload_processing(
        spec, state, execution_payload, blob_kzg_commitments
    )


@with_deneb_and_later
@spec_state_test
def test_incorrect_commitment(spec, state):
    """
    The versioned hashes are wrong, but the testing ExecutionEngine returns VALID by default.
    """
    execution_payload = build_empty_execution_payload(spec, state)

    opaque_tx, _, blob_kzg_commitments, _ = get_sample_blob_tx(spec)
    blob_kzg_commitments[0] = b"\x12" * 48  # incorrect commitment

    execution_payload.transactions = [opaque_tx]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    # Make the first block full in EIP-7732
    if is_post_eip7732(spec):
        state.latest_execution_payload_header.block_hash = execution_payload.block_hash
    yield from run_execution_payload_processing(
        spec, state, execution_payload, blob_kzg_commitments
    )


@with_deneb_and_later
@spec_state_test
def test_no_commitments_for_transactions(spec, state):
    """
    The versioned hashes are wrong, but the testing ExecutionEngine returns VALID by default.
    """
    execution_payload = build_empty_execution_payload(spec, state)

    opaque_tx, _, blob_kzg_commitments, _ = get_sample_blob_tx(spec, blob_count=2, rng=Random(1111))
    blob_kzg_commitments = []  # incorrect count

    execution_payload.transactions = [opaque_tx]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    if is_post_eip7732(spec):
        state.latest_execution_payload_header.block_hash = execution_payload.block_hash

    yield from run_execution_payload_processing(
        spec, state, execution_payload, blob_kzg_commitments
    )


@with_deneb_and_later
@spec_state_test
def test_incorrect_commitments_order(spec, state):
    """
    The versioned hashes are wrong, but the testing ExecutionEngine returns VALID by default.
    """
    execution_payload = build_empty_execution_payload(spec, state)

    opaque_tx, _, blob_kzg_commitments, _ = get_sample_blob_tx(spec, blob_count=2, rng=Random(1111))
    blob_kzg_commitments = [blob_kzg_commitments[1], blob_kzg_commitments[0]]  # incorrect order

    execution_payload.transactions = [opaque_tx]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    # Make the first block full in EIP-7732
    if is_post_eip7732(spec):
        state.latest_execution_payload_header.block_hash = execution_payload.block_hash
    yield from run_execution_payload_processing(
        spec, state, execution_payload, blob_kzg_commitments
    )


@with_deneb_and_later
@spec_state_test
def test_incorrect_transaction_no_blobs_but_with_commitments(spec, state):
    """
    The versioned hashes are wrong, but the testing ExecutionEngine returns VALID by default.
    """
    execution_payload = build_empty_execution_payload(spec, state)

    # the blob transaction is invalid, because the EL verifies that the tx contains at least one blob
    # therefore the EL should reject it, but the CL should not reject the block regardless
    opaque_tx, _, _, _ = get_sample_blob_tx(spec, blob_count=0, rng=Random(1111))
    _, _, blob_kzg_commitments, _ = get_sample_blob_tx(spec, blob_count=2, rng=Random(1112))

    execution_payload.transactions = [opaque_tx]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    if is_post_eip7732(spec):
        state.latest_execution_payload_header.block_hash = execution_payload.block_hash

    # the transaction doesn't contain any blob, but commitments are provided
    yield from run_execution_payload_processing(
        spec, state, execution_payload, blob_kzg_commitments
    )


@with_deneb_and_later
@spec_state_test
def test_incorrect_block_hash(spec, state):
    execution_payload = build_empty_execution_payload(spec, state)

    opaque_tx, _, blob_kzg_commitments, _ = get_sample_blob_tx(spec)

    execution_payload.transactions = [opaque_tx]
    execution_payload.block_hash = b"\x12" * 32  # incorrect block hash

    # CL itself doesn't verify EL block hash
    # Make the first block full in EIP-7732
    if is_post_eip7732(spec):
        state.latest_execution_payload_header.block_hash = execution_payload.block_hash
    yield from run_execution_payload_processing(
        spec, state, execution_payload, blob_kzg_commitments
    )


@with_deneb_and_later
@spec_state_test
def test_zeroed_commitment(spec, state):
    """
    The blob is invalid, but the commitment is in correct form.
    """
    execution_payload = build_empty_execution_payload(spec, state)

    opaque_tx, _, blob_kzg_commitments, _ = get_sample_blob_tx(
        spec, blob_count=1, is_valid_blob=False
    )
    assert all(commitment == b"\x00" * 48 for commitment in blob_kzg_commitments)

    execution_payload.transactions = [opaque_tx]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    # Make the first block full in EIP-7732
    if is_post_eip7732(spec):
        state.latest_execution_payload_header.block_hash = execution_payload.block_hash
    yield from run_execution_payload_processing(
        spec, state, execution_payload, blob_kzg_commitments
    )


@with_deneb_and_later
@spec_state_test
def test_invalid_correct_input__execution_invalid(spec, state):
    """
    The versioned hashes are wrong, but the testing ExecutionEngine returns VALID by default.
    """
    execution_payload = build_empty_execution_payload(spec, state)

    opaque_tx, _, blob_kzg_commitments, _ = get_sample_blob_tx(spec)

    execution_payload.transactions = [opaque_tx]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    # Make the first block full in EIP-7732
    if is_post_eip7732(spec):
        state.latest_execution_payload_header.block_hash = execution_payload.block_hash
    yield from run_execution_payload_processing(
        spec, state, execution_payload, blob_kzg_commitments, valid=False, execution_valid=False
    )


@with_deneb_and_later
@spec_state_test
def test_invalid_exceed_max_blobs_per_block(spec, state):
    execution_payload = build_empty_execution_payload(spec, state)

    opaque_tx, _, blob_kzg_commitments, _ = get_sample_blob_tx(
        spec, blob_count=get_max_blob_count(spec, state) + 1
    )

    execution_payload.transactions = [opaque_tx]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    # Make the first block full in EIP-7732
    if is_post_eip7732(spec):
        state.latest_execution_payload_header.block_hash = execution_payload.block_hash
    yield from run_execution_payload_processing(
        spec, state, execution_payload, blob_kzg_commitments, valid=False
    )
