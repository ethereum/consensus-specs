from eth_consensus_specs.test.context import (
    always_bls,
    expect_assertion_error,
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.execution_payload import (
    build_empty_execution_payload,
    prepare_execution_payload_envelope,
    setup_state_with_payload_bid,
)


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

    called_new_payload = False

    class TestEngine(spec.NoopExecutionEngine):
        def verify_and_notify_new_payload(self, new_payload_request) -> bool:
            nonlocal called_new_payload
            called_new_payload = True
            assert new_payload_request.execution_payload == signed_envelope.message.payload
            return execution_valid

    if not valid:
        expect_assertion_error(
            lambda: spec.process_execution_payload(
                state, signed_envelope, TestEngine(), verify=True
            )
        )
        yield "post", None
        return

    # Use full verification including state root
    spec.process_execution_payload(state, signed_envelope, TestEngine(), verify=True)

    # Make sure we called the engine
    assert called_new_payload

    yield "post", state


#
# Valid cases
#


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_valid(spec, state):
    """
    Test valid execution payload processing with separate builder and non-zero payment
    """
    builder_index = 0

    setup_state_with_payload_bid(spec, state, builder_index, spec.Gwei(50000000))

    # Create execution payload that matches the committed bid
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
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

    # Verify pending withdrawal was added
    assert len(state.builder_pending_withdrawals) == pre_pending_withdrawals_len + 1
    new_withdrawal = state.builder_pending_withdrawals[len(state.builder_pending_withdrawals) - 1]
    assert new_withdrawal.amount == pre_payment.withdrawal.amount
    assert new_withdrawal.builder_index == builder_index
    assert new_withdrawal.fee_recipient == pre_payment.withdrawal.fee_recipient

    # Verify pending payment was cleared
    cleared_payment = state.builder_pending_payments[
        spec.SLOTS_PER_EPOCH + state.slot % spec.SLOTS_PER_EPOCH
    ]
    # Check if it's been cleared by checking that it equals an empty BuilderPendingPayment
    empty_payment = spec.BuilderPendingPayment()
    assert cleared_payment.weight == empty_payment.weight
    assert cleared_payment.withdrawal.amount == empty_payment.withdrawal.amount
    assert cleared_payment.withdrawal.builder_index == empty_payment.withdrawal.builder_index


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_self_build_zero_value(spec, state):
    """
    Test valid self-building scenario (zero value)
    """
    # Setup state with committed bid (self-build, zero value)
    setup_state_with_payload_bid(spec, state, spec.BUILDER_INDEX_SELF_BUILD, spec.Gwei(0))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec,
        state,
        builder_index=spec.BUILDER_INDEX_SELF_BUILD,
        execution_payload=execution_payload,
    )

    # Capture pre-state for verification
    pre_pending_withdrawals_len = len(state.builder_pending_withdrawals)

    yield from run_execution_payload_processing(spec, state, signed_envelope)

    # Verify state updates
    assert state.execution_payload_availability[state.slot % spec.SLOTS_PER_HISTORICAL_ROOT] == 0b1
    assert state.latest_block_hash == execution_payload.block_hash

    # In self-build with zero value, no withdrawal is added since amount is zero
    assert len(state.builder_pending_withdrawals) == pre_pending_withdrawals_len

    # Verify pending payment remains cleared (it was already empty)
    cleared_payment = state.builder_pending_payments[
        spec.SLOTS_PER_EPOCH + state.slot % spec.SLOTS_PER_EPOCH
    ]
    empty_payment = spec.BuilderPendingPayment()
    assert cleared_payment.weight == empty_payment.weight
    assert cleared_payment.withdrawal.amount == empty_payment.withdrawal.amount
    assert cleared_payment.withdrawal.builder_index == empty_payment.withdrawal.builder_index


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_large_payment_churn_impact(spec, state):
    """
    Test execution payload processing with large payment that impacts exit churn state
    """
    builder_index = 0

    # Use a very large payment (500 ETH) to ensure it impacts churn tracking
    large_payment_amount = spec.Gwei(500000000000)
    setup_state_with_payload_bid(spec, state, builder_index, large_payment_amount)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec,
        state,
        builder_index=builder_index,
        execution_payload=execution_payload,
    )

    # Capture pre-state for churn verification
    pre_payment = state.builder_pending_payments[
        spec.SLOTS_PER_EPOCH + state.slot % spec.SLOTS_PER_EPOCH
    ]
    pre_pending_withdrawals_len = len(state.builder_pending_withdrawals)

    yield from run_execution_payload_processing(spec, state, signed_envelope)

    # Verify builder payment was processed correctly
    assert len(state.builder_pending_withdrawals) == pre_pending_withdrawals_len + 1
    new_withdrawal = state.builder_pending_withdrawals[pre_pending_withdrawals_len]
    assert new_withdrawal.amount == pre_payment.withdrawal.amount
    assert new_withdrawal.builder_index == builder_index
    assert new_withdrawal.fee_recipient == pre_payment.withdrawal.fee_recipient

    # Verify pending payment was cleared
    cleared_payment = state.builder_pending_payments[
        spec.SLOTS_PER_EPOCH + state.slot % spec.SLOTS_PER_EPOCH
    ]
    empty_payment = spec.BuilderPendingPayment()
    assert cleared_payment.weight == empty_payment.weight
    assert cleared_payment.withdrawal.amount == empty_payment.withdrawal.amount
    assert cleared_payment.withdrawal.builder_index == empty_payment.withdrawal.builder_index


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_with_blob_commitments(spec, state):
    """
    Test execution payload processing with blob KZG commitments and separate builder
    """
    builder_index = 0

    # Create bid with blob commitments
    setup_state_with_payload_bid(
        spec,
        state,
        builder_index,
        spec.Gwei(3000000),
        blob_kzg_commitments=[spec.KZGCommitment(b"\x42" * 48), spec.KZGCommitment(b"\x43" * 48)],
    )

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec,
        state,
        builder_index=builder_index,
        execution_payload=execution_payload,
    )

    # Capture pre-state for payment verification
    pre_payment = state.builder_pending_payments[
        spec.SLOTS_PER_EPOCH + state.slot % spec.SLOTS_PER_EPOCH
    ]
    pre_pending_withdrawals_len = len(state.builder_pending_withdrawals)

    yield from run_execution_payload_processing(spec, state, signed_envelope)

    # Verify builder payment was processed correctly
    # 1. Verify pending withdrawal was added with correct amount and withdrawable epoch
    assert len(state.builder_pending_withdrawals) == pre_pending_withdrawals_len + 1
    new_withdrawal = state.builder_pending_withdrawals[pre_pending_withdrawals_len]
    assert new_withdrawal.amount == pre_payment.withdrawal.amount
    assert new_withdrawal.builder_index == builder_index
    assert new_withdrawal.fee_recipient == pre_payment.withdrawal.fee_recipient

    # Verify pending payment was cleared
    cleared_payment = state.builder_pending_payments[
        spec.SLOTS_PER_EPOCH + state.slot % spec.SLOTS_PER_EPOCH
    ]
    empty_payment = spec.BuilderPendingPayment()
    assert cleared_payment.weight == empty_payment.weight
    assert cleared_payment.withdrawal.amount == empty_payment.withdrawal.amount
    assert cleared_payment.withdrawal.builder_index == empty_payment.withdrawal.builder_index


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_with_execution_requests(spec, state):
    """
    Test execution payload processing with execution requests and separate builder
    """
    builder_index = 0

    setup_state_with_payload_bid(spec, state, builder_index, spec.Gwei(4000000))

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
        withdrawals=spec.List[spec.WithdrawalRequest, spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD](
            [
                spec.WithdrawalRequest(
                    source_address=spec.ExecutionAddress(b"\x04" * 20),
                    validator_pubkey=spec.BLSPubkey(b"\x05" * 48),
                    amount=spec.Gwei(16000000000),  # 16 ETH
                )
            ]
        ),
        consolidations=spec.List[
            spec.ConsolidationRequest, spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
        ](
            [
                spec.ConsolidationRequest(
                    source_address=spec.ExecutionAddress(b"\x06" * 20),
                    source_pubkey=spec.BLSPubkey(b"\x07" * 48),
                    target_pubkey=spec.BLSPubkey(b"\x08" * 48),
                )
            ]
        ),
    )

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec,
        state,
        builder_index=builder_index,
        execution_payload=execution_payload,
        execution_requests=execution_requests,
    )

    # Capture pre-state for verification
    pre_pending_deposits_len = len(state.pending_deposits)
    pre_payment = state.builder_pending_payments[
        spec.SLOTS_PER_EPOCH + state.slot % spec.SLOTS_PER_EPOCH
    ]
    pre_pending_withdrawals_len = len(state.builder_pending_withdrawals)

    yield from run_execution_payload_processing(spec, state, signed_envelope)

    # Verify deposit request was processed - deposits are always added to pending queue
    deposit_request = execution_requests.deposits[0]
    assert len(state.pending_deposits) == pre_pending_deposits_len + 1
    new_pending_deposit = state.pending_deposits[pre_pending_deposits_len]
    assert new_pending_deposit.pubkey == deposit_request.pubkey
    assert new_pending_deposit.withdrawal_credentials == deposit_request.withdrawal_credentials
    assert new_pending_deposit.amount == deposit_request.amount

    # Verify builder payment was processed correctly
    assert len(state.builder_pending_withdrawals) == pre_pending_withdrawals_len + 1
    new_withdrawal = state.builder_pending_withdrawals[pre_pending_withdrawals_len]
    assert new_withdrawal.amount == pre_payment.withdrawal.amount
    assert new_withdrawal.builder_index == builder_index
    assert new_withdrawal.fee_recipient == pre_payment.withdrawal.fee_recipient

    # Verify pending payment was cleared
    cleared_payment = state.builder_pending_payments[
        spec.SLOTS_PER_EPOCH + state.slot % spec.SLOTS_PER_EPOCH
    ]
    empty_payment = spec.BuilderPendingPayment()
    assert cleared_payment.weight == empty_payment.weight
    assert cleared_payment.withdrawal.amount == empty_payment.withdrawal.amount
    assert cleared_payment.withdrawal.builder_index == empty_payment.withdrawal.builder_index


#
# Invalid signature tests
#


@with_gloas_and_later
@spec_state_test
def test_process_execution_payload_invalid_signature(spec, state):
    """
    Test invalid signature fails with separate builder and non-zero payment
    """
    builder_index = 0

    setup_state_with_payload_bid(spec, state, builder_index, spec.Gwei(2000000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec,
        state,
        builder_index=builder_index,
        execution_payload=execution_payload,
        valid_signature=False,
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_wrong_beacon_block_root(spec, state):
    """
    Test wrong beacon block root fails with separate builder
    """
    builder_index = 0

    setup_state_with_payload_bid(spec, state, builder_index, spec.Gwei(1500000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
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
    Test wrong slot fails with separate builder
    """
    builder_index = 0

    setup_state_with_payload_bid(spec, state, builder_index, spec.Gwei(2500000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
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
    Test wrong builder index fails with separate builders
    """
    builder_index = 0

    setup_state_with_payload_bid(spec, state, builder_index, spec.Gwei(3500000))

    # Use different builder index in envelope
    other_builder_index = 1

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
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
def test_process_execution_payload_missing_expected_withdrawal(spec, state):
    """
    Verify payload rejected when it omits a withdrawal expected by the state.
    """
    builder_index = 0

    setup_state_with_payload_bid(spec, state, builder_index, spec.Gwei(2600000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    withdrawal = spec.Withdrawal(
        index=0,
        validator_index=0,
        address=b"\x22" * 20,
        amount=spec.Gwei(1),
    )
    state.payload_expected_withdrawals = spec.List[
        spec.Withdrawal, spec.MAX_WITHDRAWALS_PER_PAYLOAD
    ]([withdrawal])
    execution_payload.withdrawals = spec.List[spec.Withdrawal, spec.MAX_WITHDRAWALS_PER_PAYLOAD]()

    signed_envelope = prepare_execution_payload_envelope(
        spec, state, builder_index=builder_index, execution_payload=execution_payload
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_wrong_gas_limit(spec, state):
    """
    Test wrong gas limit fails with separate builder
    """
    builder_index = 0

    setup_state_with_payload_bid(spec, state, builder_index, spec.Gwei(1800000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = (
        state.latest_execution_payload_bid.gas_limit + 1
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
    Test wrong block hash fails with separate builder
    """
    builder_index = 0

    setup_state_with_payload_bid(spec, state, builder_index, spec.Gwei(2200000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = spec.Hash32(b"\x42" * 32)  # Wrong block hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
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
    Test wrong parent hash fails with separate builder
    """
    builder_index = 0

    setup_state_with_payload_bid(spec, state, builder_index, spec.Gwei(1600000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
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
    Test wrong prev_randao fails with separate builder
    """
    builder_index = 0

    setup_state_with_payload_bid(spec, state, builder_index, spec.Gwei(2100000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
    execution_payload.parent_hash = state.latest_block_hash
    execution_payload.prev_randao = spec.Bytes32(b"\x42" * 32)  # Wrong prev_randao

    signed_envelope = prepare_execution_payload_envelope(
        spec, state, builder_index=builder_index, execution_payload=execution_payload
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_bid_prev_randao_mismatch(spec, state):
    """
    Test that committed_bid.prev_randao must equal payload.prev_randao
    """
    builder_index = 0

    # Setup bid with one prev_randao value
    bid_prev_randao = spec.Bytes32(b"\x11" * 32)
    setup_state_with_payload_bid(
        spec, state, builder_index, spec.Gwei(2300000), prev_randao=bid_prev_randao
    )

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
    execution_payload.parent_hash = state.latest_block_hash
    # Set payload with a different prev_randao value
    execution_payload.prev_randao = spec.Bytes32(b"\x22" * 32)

    signed_envelope = prepare_execution_payload_envelope(
        spec, state, builder_index=builder_index, execution_payload=execution_payload
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_wrong_timestamp(spec, state):
    """
    Test wrong timestamp fails with separate builder
    """
    builder_index = 0

    setup_state_with_payload_bid(spec, state, builder_index, spec.Gwei(1900000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
    execution_payload.parent_hash = state.latest_block_hash
    execution_payload.timestamp = execution_payload.timestamp + 1  # Wrong timestamp

    signed_envelope = prepare_execution_payload_envelope(
        spec, state, builder_index=builder_index, execution_payload=execution_payload
    )

    yield from run_execution_payload_processing(spec, state, signed_envelope, valid=False)


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_execution_engine_invalid(spec, state):
    """
    Test execution engine returns invalid with separate builder
    """
    builder_index = 0

    setup_state_with_payload_bid(spec, state, builder_index, spec.Gwei(3200000))

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.block_hash = state.latest_execution_payload_bid.block_hash
    execution_payload.gas_limit = state.latest_execution_payload_bid.gas_limit
    execution_payload.parent_hash = state.latest_block_hash

    signed_envelope = prepare_execution_payload_envelope(
        spec, state, builder_index=builder_index, execution_payload=execution_payload
    )

    yield from run_execution_payload_processing(
        spec, state, signed_envelope, valid=False, execution_valid=False
    )
