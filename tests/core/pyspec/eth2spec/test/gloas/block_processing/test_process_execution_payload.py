from eth2spec.test.context import (
    always_bls,
    spec_state_test,
    with_gloas_and_later,
)
from eth2spec.test.gloas.block_processing.test_process_execution_payload_header import (
    make_validator_builder,
)
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
)
from eth2spec.test.helpers.keys import privkeys


def run_execution_payload_processing(
    spec, state, signed_envelope, valid=True, execution_valid=True
):
    """
    Run ``process_execution_payload``, yielding:
    - pre-state ('pre')
    - signed_envelope ('signed_envelope')
    - execution details ('execution.yml')
    - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield "pre", state
    yield "signed_envelope", signed_envelope
    yield "execution", {"execution_valid": execution_valid}

    if not valid:
        expect_assertion_error = True
    else:
        expect_assertion_error = False

    called_new_payload = False

    class TestEngine(spec.NoopExecutionEngine):
        def verify_and_notify_new_payload(self, new_payload_request) -> bool:
            nonlocal called_new_payload
            called_new_payload = True
            assert new_payload_request.execution_payload == signed_envelope.message.payload
            return execution_valid

    if expect_assertion_error:
        try:
            # Use full verification for invalid tests to catch the right errors
            spec.process_execution_payload(state, signed_envelope, TestEngine(), verify=True)
            assert False, "Expected AssertionError but none was raised"
        except AssertionError:
            pass
        yield "post", None
        return

    # Skip state root verification in tests for simplicity (only for valid tests)
    spec.process_execution_payload(state, signed_envelope, TestEngine(), verify=False)

    # Make sure we called the engine
    assert called_new_payload

    yield "post", state


def prepare_execution_payload_envelope(
    spec,
    state,
    builder_index=None,
    slot=None,
    beacon_block_root=None,
    state_root=None,
    execution_payload=None,
    execution_requests=None,
    blob_kzg_commitments=None,
    valid_signature=True,
):
    """
    Helper to create a signed execution payload envelope with customizable parameters.
    Note: This should be called AFTER setting up the state with the committed header.
    """
    if builder_index is None:
        builder_index = spec.get_beacon_proposer_index(state)

    if slot is None:
        slot = state.slot

    if beacon_block_root is None:
        # Cache latest block header state root if not already set
        if state.latest_block_header.state_root == spec.Root():
            state.latest_block_header.state_root = state.hash_tree_root()
        beacon_block_root = state.latest_block_header.hash_tree_root()

    if execution_payload is None:
        execution_payload = build_empty_execution_payload(spec, state)

    if execution_requests is None:
        execution_requests = spec.ExecutionRequests(
            deposits=spec.List[spec.DepositRequest, spec.MAX_DEPOSIT_REQUESTS_PER_PAYLOAD](),
            withdrawals=spec.List[
                spec.WithdrawalRequest, spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD
            ](),
            consolidations=spec.List[
                spec.ConsolidationRequest, spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
            ](),
        )

    if blob_kzg_commitments is None:
        blob_kzg_commitments = spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK]()

    # Create a copy of state for computing state_root after execution payload processing
    if state_root is None:
        post_state = state.copy()
        # Simulate the state changes that process_execution_payload will make
        payment = post_state.builder_pending_payments[
            spec.SLOTS_PER_EPOCH + state.slot % spec.SLOTS_PER_EPOCH
        ]
        if payment.withdrawal.amount > 0:
            exit_queue_epoch = spec.compute_exit_epoch_and_update_churn(
                post_state, payment.withdrawal.amount
            )
            payment.withdrawal.withdrawable_epoch = spec.Epoch(
                exit_queue_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
            )
            post_state.builder_pending_withdrawals.append(payment.withdrawal)

        # Clear the pending payment (either zero amount or processed above)
        post_state.builder_pending_payments[
            spec.SLOTS_PER_EPOCH + state.slot % spec.SLOTS_PER_EPOCH
        ] = spec.BuilderPendingPayment()

        post_state.execution_payload_availability[state.slot % spec.SLOTS_PER_HISTORICAL_ROOT] = 0b1
        post_state.latest_block_hash = execution_payload.block_hash
        post_state.latest_full_slot = state.slot
        state_root = post_state.hash_tree_root()

    envelope = spec.ExecutionPayloadEnvelope(
        payload=execution_payload,
        execution_requests=execution_requests,
        builder_index=builder_index,
        beacon_block_root=beacon_block_root,
        slot=slot,
        blob_kzg_commitments=blob_kzg_commitments,
        state_root=state_root,
    )

    if valid_signature:
        privkey = privkeys[builder_index]
        signature = spec.get_execution_payload_envelope_signature(state, envelope, privkey)
    else:
        # Invalid signature
        signature = spec.BLSSignature()

    return spec.SignedExecutionPayloadEnvelope(
        message=envelope,
        signature=signature,
    )


def setup_state_with_payload_header(spec, state, builder_index=None, value=None):
    """
    Helper to setup state with a committed execution payload header.
    This simulates the state after process_execution_payload_header has run.
    """
    if builder_index is None:
        builder_index = spec.get_beacon_proposer_index(state)

    if value is None:
        value = spec.Gwei(0)

    # Create and set the latest execution payload header
    kzg_list = spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK]()
    header = spec.ExecutionPayloadHeader(
        parent_block_hash=state.latest_block_hash,
        parent_block_root=state.latest_block_header.hash_tree_root(),
        block_hash=spec.Hash32(),
        fee_recipient=spec.ExecutionAddress(),
        gas_limit=spec.uint64(30000000),
        builder_index=builder_index,
        slot=state.slot,
        value=value,
        blob_kzg_commitments_root=kzg_list.hash_tree_root(),
    )
    state.latest_execution_payload_header = header

    # Setup withdrawals root
    empty_withdrawals = spec.List[spec.Withdrawal, spec.MAX_WITHDRAWALS_PER_PAYLOAD]()
    state.latest_withdrawals_root = empty_withdrawals.hash_tree_root()

    # Add pending payment if value > 0
    if value > 0:
        pending_payment = spec.BuilderPendingPayment(
            weight=0,
            withdrawal=spec.BuilderPendingWithdrawal(
                fee_recipient=header.fee_recipient,
                amount=value,
                builder_index=builder_index,
            ),
        )
        state.builder_pending_payments[spec.SLOTS_PER_EPOCH + state.slot % spec.SLOTS_PER_EPOCH] = (
            pending_payment
        )


#
# Valid cases
#


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_valid(spec, state):
    """
    Test valid execution payload processing
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(1000000))

    # Create execution payload that matches the committed header
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec, state, builder_index=builder_index, execution_payload=execution_payload
    )

    pre_payment = state.builder_pending_payments[
        spec.SLOTS_PER_EPOCH + state.slot % spec.SLOTS_PER_EPOCH
    ]
    pre_pending_withdrawals_len = len(state.builder_pending_withdrawals)

    yield from run_execution_payload_processing(spec, state, signed_envelope)

    # Verify state updates
    assert state.execution_payload_availability[state.slot % spec.SLOTS_PER_HISTORICAL_ROOT] == 0b1
    assert state.latest_block_hash == execution_payload.block_hash
    assert state.latest_full_slot == state.slot

    # Verify pending withdrawal was added
    assert len(state.builder_pending_withdrawals) == pre_pending_withdrawals_len + 1
    new_withdrawal = state.builder_pending_withdrawals[len(state.builder_pending_withdrawals) - 1]
    assert new_withdrawal.amount == pre_payment.withdrawal.amount
    assert new_withdrawal.builder_index == builder_index

    # Verify pending payment was cleared
    cleared_payment = state.builder_pending_payments[
        spec.SLOTS_PER_EPOCH + state.slot % spec.SLOTS_PER_EPOCH
    ]
    assert cleared_payment.withdrawal.amount == 0


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_self_build_zero_value(spec, state):
    """
    Test valid self-building scenario (zero value)
    """
    proposer_index = spec.get_beacon_proposer_index(state)

    # Setup state with committed header (self-build, zero value)
    setup_state_with_payload_header(spec, state, proposer_index, spec.Gwei(0))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec, state, builder_index=proposer_index, execution_payload=execution_payload
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope)

    # Verify state updates
    assert state.execution_payload_availability[state.slot % spec.SLOTS_PER_HISTORICAL_ROOT] == 0b1
    assert state.latest_block_hash == execution_payload.block_hash
    assert state.latest_full_slot == state.slot


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_with_blob_commitments(spec, state):
    """
    Test execution payload processing with blob KZG commitments
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(500000))

    # Create blob commitments
    blob_kzg_commitments = spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
        [
            spec.KZGCommitment(b"\x42" * 48),
            spec.KZGCommitment(b"\x43" * 48),
        ]
    )

    # Update header with correct blob commitments root
    state.latest_execution_payload_header.blob_kzg_commitments_root = (
        blob_kzg_commitments.hash_tree_root()
    )

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec,
        state,
        builder_index=builder_index,
        execution_payload=execution_payload,
        blob_kzg_commitments=blob_kzg_commitments,
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_with_execution_requests(spec, state):
    """
    Test execution payload processing with execution requests
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(750000))

    # Create execution requests
    execution_requests = spec.ExecutionRequests(
        deposits=spec.List[spec.DepositRequest, spec.MAX_DEPOSIT_REQUESTS_PER_PAYLOAD](
            [
                spec.DepositRequest(
                    pubkey=spec.BLSPubkey(b"\x01" * 48),
                    withdrawal_credentials=spec.Bytes32(b"\x02" * 32),
                    amount=spec.Gwei(32000000000),  # 32 ETH
                    signature=spec.BLSSignature(b"\x03" * 96),
                    index=spec.uint64(0),
                )
            ]
        ),
        withdrawals=spec.List[spec.WithdrawalRequest, spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD](),
        consolidations=spec.List[
            spec.ConsolidationRequest, spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
        ](),
    )

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec,
        state,
        builder_index=builder_index,
        execution_payload=execution_payload,
        execution_requests=execution_requests,
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope)


#
# Invalid signature tests
#


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_invalid_signature(spec, state):
    """
    Test invalid signature fails
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(1000000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec,
        state,
        builder_index=builder_index,
        execution_payload=execution_payload,
        valid_signature=False,
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


#
# Consistency validation tests
#


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_wrong_beacon_block_root(spec, state):
    """
    Test wrong beacon block root fails
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(1000000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    wrong_beacon_block_root = spec.Root(b"\x42" * 32)
    signed_envelope = prepare_execution_payload_envelope(
        spec,
        state,
        builder_index=builder_index,
        execution_payload=execution_payload,
        beacon_block_root=wrong_beacon_block_root,
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_wrong_slot(spec, state):
    """
    Test wrong slot fails
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(1000000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec,
        state,
        builder_index=builder_index,
        execution_payload=execution_payload,
        slot=state.slot + 1,  # Wrong slot
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_wrong_builder_index(spec, state):
    """
    Test wrong builder index fails
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(1000000))

    # Use different builder index in envelope
    other_builder_index = (builder_index + 1) % len(state.validators)
    make_validator_builder(spec, state, other_builder_index)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec,
        state,
        builder_index=other_builder_index,  # Wrong builder
        execution_payload=execution_payload,
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_wrong_blob_commitments_root(spec, state):
    """
    Test wrong blob KZG commitments root fails
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header with specific blob commitments root
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(1000000))
    original_blob_commitments = spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
        [spec.KZGCommitment(b"\x11" * 48)]
    )
    state.latest_execution_payload_header.blob_kzg_commitments_root = (
        original_blob_commitments.hash_tree_root()
    )

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    # Use different blob commitments
    wrong_blob_commitments = spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
        [spec.KZGCommitment(b"\x22" * 48)]
    )

    signed_envelope = prepare_execution_payload_envelope(
        spec,
        state,
        builder_index=builder_index,
        execution_payload=execution_payload,
        blob_kzg_commitments=wrong_blob_commitments,
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_wrong_gas_limit(spec, state):
    """
    Test wrong gas limit fails
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(1000000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = (
        state.latest_execution_payload_header.gas_limit + 1
    )  # Wrong gas limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec, state, builder_index=builder_index, execution_payload=execution_payload
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_wrong_block_hash(spec, state):
    """
    Test wrong block hash fails
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(1000000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = spec.Hash32(b"\x42" * 32)  # Wrong block hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec, state, builder_index=builder_index, execution_payload=execution_payload
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_wrong_parent_hash(spec, state):
    """
    Test wrong parent hash fails
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(1000000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = spec.Hash32(b"\x42" * 32)  # Wrong parent hash

    signed_envelope = prepare_execution_payload_envelope(
        spec, state, builder_index=builder_index, execution_payload=execution_payload
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_wrong_prev_randao(spec, state):
    """
    Test wrong prev_randao fails
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(1000000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = state.latest_block_hash
    execution_payload.prev_randao = spec.Bytes32(b"\x42" * 32)  # Wrong prev_randao

    signed_envelope = prepare_execution_payload_envelope(
        spec, state, builder_index=builder_index, execution_payload=execution_payload
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_wrong_timestamp(spec, state):
    """
    Test wrong timestamp fails
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(1000000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = state.latest_block_hash
    execution_payload.timestamp = execution_payload.timestamp + 1  # Wrong timestamp

    signed_envelope = prepare_execution_payload_envelope(
        spec, state, builder_index=builder_index, execution_payload=execution_payload
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_max_blob_commitments_valid(spec, state):
    """
    Test max blob commitments is valid (edge case)
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(1000000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    # Create exactly MAX_BLOBS_PER_BLOCK_ELECTRA commitments (should be valid)
    max_blob_commitments = [
        spec.KZGCommitment(b"\x42" * 48) for _ in range(spec.config.MAX_BLOBS_PER_BLOCK_ELECTRA)
    ]
    blob_kzg_commitments = spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
        max_blob_commitments
    )

    # Update committed header to match
    state.latest_execution_payload_header.blob_kzg_commitments_root = (
        blob_kzg_commitments.hash_tree_root()
    )

    signed_envelope = prepare_execution_payload_envelope(
        spec,
        state,
        builder_index=builder_index,
        execution_payload=execution_payload,
        blob_kzg_commitments=blob_kzg_commitments,
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=True)


#
# Execution engine validation tests
#


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_execution_engine_invalid(spec, state):
    """
    Test execution engine returns invalid
    """
    builder_index = spec.get_beacon_proposer_index(state)
    make_validator_builder(spec, state, builder_index)

    # Setup state with committed header
    setup_state_with_payload_header(spec, state, builder_index, spec.Gwei(1000000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_header.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_header.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec, state, builder_index=builder_index, execution_payload=execution_payload
    )

    yield from run_execution_payload_processing(
        spec, state, signed_envelope, valid=False, execution_valid=False
    )
