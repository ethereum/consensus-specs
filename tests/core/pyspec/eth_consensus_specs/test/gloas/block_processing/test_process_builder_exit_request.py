from eth_consensus_specs.test.context import spec_state_test, with_gloas_and_later
from eth_consensus_specs.test.helpers.keys import builder_pubkeys
from eth_consensus_specs.test.helpers.state import next_slots


def advance_past_finalization(spec, state):
    """Advance slots and finalize so that genesis-epoch builders become active."""
    epoch = spec.get_current_epoch(state)
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 3)
    state.finalized_checkpoint.epoch = epoch + 1


def prepare_builder_exit_request(spec, state, builder_index, source_address=None):
    """
    Create a builder exit request for the builder at the given index,
    authorized by its execution address unless source_address is provided.
    """
    builder = state.builders[builder_index]
    if source_address is None:
        source_address = builder.execution_address
    return spec.BuilderExitRequest(
        source_address=source_address,
        pubkey=builder.pubkey,
    )


def run_builder_exit_request_processing(spec, state, builder_exit_request, valid=True):
    """
    Run ``process_builder_exit_request``, yielding:
      - pre-state ('pre')
      - builder_exit_request ('builder_exit_request')
      - post-state ('post').

    The function never raises. If valid is False, expect the request to be
    consumed without changing the state.
    """
    pre_state = state.copy()

    yield "pre", state
    yield "builder_exit_request", builder_exit_request

    spec.process_builder_exit_request(state, builder_exit_request)

    yield "post", state

    if not valid:
        assert state == pre_state


@with_gloas_and_later
@spec_state_test
def test_process_builder_exit_request__success(spec, state):
    """Test successful builder exit with no pending balance."""
    builder_index = 0

    advance_past_finalization(spec, state)
    assert spec.is_active_builder(state, builder_index)
    assert spec.get_pending_balance_to_withdraw_for_builder(state, builder_index) == 0

    current_epoch = spec.get_current_epoch(state)
    builder_exit_request = prepare_builder_exit_request(spec, state, builder_index)

    yield from run_builder_exit_request_processing(spec, state, builder_exit_request)

    assert not spec.is_active_builder(state, builder_index)
    expected_withdrawable = current_epoch + spec.config.MIN_BUILDER_WITHDRAWABILITY_DELAY
    assert state.builders[builder_index].withdrawable_epoch == expected_withdrawable


@with_gloas_and_later
@spec_state_test
def test_process_builder_exit_request__unknown_pubkey(spec, state):
    """Test that an exit request for an unknown pubkey is a no-op."""
    advance_past_finalization(spec, state)

    # Use a pubkey that is not in the builder registry
    existing_pubkeys = {builder.pubkey for builder in state.builders}
    unknown_pubkey = None
    for pk in builder_pubkeys:
        if pk not in existing_pubkeys:
            unknown_pubkey = pk
            break
    assert unknown_pubkey is not None

    builder_exit_request = spec.BuilderExitRequest(
        source_address=spec.ExecutionAddress(b"\x42" * 20),
        pubkey=unknown_pubkey,
    )

    yield from run_builder_exit_request_processing(spec, state, builder_exit_request, valid=False)


@with_gloas_and_later
@spec_state_test
def test_process_builder_exit_request__inactive_deposit_epoch(spec, state):
    """Test that an inactive builder (deposit epoch not finalized) cannot exit."""
    builder_index = 0

    # Set builder's deposit epoch to a non-finalized epoch
    state.builders[builder_index].deposit_epoch = spec.Epoch(1)

    advance_past_finalization(spec, state)
    assert state.finalized_checkpoint.epoch == state.builders[builder_index].deposit_epoch
    assert not spec.is_active_builder(state, builder_index)

    builder_exit_request = prepare_builder_exit_request(spec, state, builder_index)

    yield from run_builder_exit_request_processing(spec, state, builder_exit_request, valid=False)


@with_gloas_and_later
@spec_state_test
def test_process_builder_exit_request__already_exited(spec, state):
    """Test that an already-exited builder cannot exit again."""
    builder_index = 0

    # Set builder's withdrawable epoch which indicates it has initiated an exit
    state.builders[builder_index].withdrawable_epoch = spec.get_current_epoch(state) + 10

    advance_past_finalization(spec, state)
    assert not spec.is_active_builder(state, builder_index)

    builder_exit_request = prepare_builder_exit_request(spec, state, builder_index)

    yield from run_builder_exit_request_processing(spec, state, builder_exit_request, valid=False)


@with_gloas_and_later
@spec_state_test
def test_process_builder_exit_request__wrong_source_address(spec, state):
    """Test that an exit request from the wrong source address is a no-op."""
    builder_index = 0

    advance_past_finalization(spec, state)
    assert spec.is_active_builder(state, builder_index)

    # Use a source address that differs from the builder's execution address
    wrong_address = spec.ExecutionAddress(b"\x42" * 20)
    assert state.builders[builder_index].execution_address != wrong_address
    builder_exit_request = prepare_builder_exit_request(
        spec, state, builder_index, source_address=wrong_address
    )

    yield from run_builder_exit_request_processing(spec, state, builder_exit_request, valid=False)


@with_gloas_and_later
@spec_state_test
def test_process_builder_exit_request__pending_withdrawal(spec, state):
    """Test that a builder cannot exit while having a pending withdrawal."""
    builder_index = 0

    advance_past_finalization(spec, state)
    assert spec.is_active_builder(state, builder_index)

    # Add pending withdrawal for this builder
    withdrawal_amount = spec.MIN_ACTIVATION_BALANCE
    withdrawal = spec.BuilderPendingWithdrawal(
        fee_recipient=spec.ExecutionAddress(b"\x70" * 20),
        amount=withdrawal_amount,
        builder_index=builder_index,
    )
    state.builder_pending_withdrawals.append(withdrawal)
    pending_balance = spec.get_pending_balance_to_withdraw_for_builder(state, builder_index)
    assert pending_balance == withdrawal_amount

    builder_exit_request = prepare_builder_exit_request(spec, state, builder_index)

    yield from run_builder_exit_request_processing(spec, state, builder_exit_request, valid=False)


@with_gloas_and_later
@spec_state_test
def test_process_builder_exit_request__pending_payment(spec, state):
    """Test that a builder cannot exit while having a pending payment."""
    builder_index = 0

    advance_past_finalization(spec, state)
    assert spec.is_active_builder(state, builder_index)

    # Add pending payment for this builder
    payment_amount = spec.MIN_ACTIVATION_BALANCE
    payment = spec.BuilderPendingPayment(
        weight=spec.get_builder_payment_quorum_threshold(state) + 1,
        withdrawal=spec.BuilderPendingWithdrawal(
            fee_recipient=spec.ExecutionAddress(b"\x60" * 20),
            amount=payment_amount,
            builder_index=builder_index,
        ),
    )
    state.builder_pending_payments[0] = payment
    pending_balance = spec.get_pending_balance_to_withdraw_for_builder(state, builder_index)
    assert pending_balance == payment_amount

    builder_exit_request = prepare_builder_exit_request(spec, state, builder_index)

    yield from run_builder_exit_request_processing(spec, state, builder_exit_request, valid=False)
