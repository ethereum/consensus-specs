from eth2spec.test.context import always_bls, spec_state_test, with_gloas_and_later
from eth2spec.test.helpers.deposits import (
    build_deposit_data,
    prepare_builder_deposit_request,
)
from eth2spec.test.helpers.keys import builder_pubkey_to_privkey
from eth2spec.test.helpers.state import next_epoch


def run_builder_deposit_request_processing(
    spec, state, deposit_request, is_new_builder=True, valid=True
):
    """
    Run ``process_deposit_request`` for a builder deposit, yielding:
      - pre-state ('pre')
      - deposit_request ('deposit_request')
      - post-state ('post').

    Args:
        is_new_builder: If True, expect a new builder to be created.
                        If False, expect a top-up of an existing builder.
        valid: If True, expect the deposit to be applied (new builder or top-up).
               If False, expect no changes (invalid signature, pubkey already validator, etc).
    """
    pre_builder_count = len(state.builders)
    pre_pending_deposits_count = len(state.pending_deposits)
    pre_balance = 0

    # For top-ups, get pre-balance
    if not is_new_builder:
        builder_index = spec.get_builder_index(state, deposit_request.pubkey)
        pre_balance = state.builders[builder_index].balance

    yield "pre", state
    yield "deposit_request", deposit_request

    spec.process_deposit_request(state, deposit_request)

    yield "post", state

    # Builder deposits are applied immediately (not queued like validators)
    # Verify no pending deposits were added for builder deposits
    assert len(state.pending_deposits) == pre_pending_deposits_count

    if not valid:
        # Invalid deposit should not change state
        assert len(state.builders) == pre_builder_count
        if not is_new_builder:
            assert state.builders[builder_index].balance == pre_balance
    elif is_new_builder:
        # New builder should be added to registry
        builder_index = spec.get_builder_index(state, deposit_request.pubkey)
        builder = state.builders[builder_index]
        assert builder.pubkey == deposit_request.pubkey
        assert builder.withdrawal_credentials == deposit_request.withdrawal_credentials
        assert builder.balance == deposit_request.amount
        assert builder.withdrawable_epoch == spec.FAR_FUTURE_EPOCH
    else:
        # Top-up should increase balance
        assert len(state.builders) == pre_builder_count
        assert state.builders[builder_index].balance == pre_balance + deposit_request.amount


#
# New builder deposits
#


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__new_builder(spec, state):
    """Test fresh builder deposit creates a new builder."""
    amount = spec.MIN_DEPOSIT_AMOUNT
    deposit_request = prepare_builder_deposit_request(spec, state, amount, signed=True)

    yield from run_builder_deposit_request_processing(spec, state, deposit_request)


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__new_builder_large_amount(spec, state):
    """Test fresh builder deposit with a large amount."""
    # 1000 ETH deposit
    amount = spec.Gwei(1_000 * spec.ETH_TO_GWEI)
    deposit_request = prepare_builder_deposit_request(spec, state, amount, signed=True)

    yield from run_builder_deposit_request_processing(spec, state, deposit_request)


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__new_builder_very_large_amount(spec, state):
    """Test fresh builder deposit with a very large amount."""
    # 10k ETH deposit
    amount = spec.Gwei(10_000 * spec.ETH_TO_GWEI)
    deposit_request = prepare_builder_deposit_request(spec, state, amount, signed=True)

    yield from run_builder_deposit_request_processing(spec, state, deposit_request)


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__new_builder_extra_gwei(spec, state):
    """Test builder deposit with non-round amount (extra gwei)."""
    # Amount with extra gwei
    amount = spec.MIN_DEPOSIT_AMOUNT + spec.Gwei(1)
    deposit_request = prepare_builder_deposit_request(spec, state, amount, signed=True)

    yield from run_builder_deposit_request_processing(spec, state, deposit_request)

    # Verify the exact amount was deposited
    builder_index = spec.get_builder_index(state, deposit_request.pubkey)
    assert state.builders[builder_index].balance == amount


#
# Top-up deposits for existing builders
#


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__builder_top_up(spec, state):
    """Test top-up deposit for an existing builder."""
    amount = spec.MIN_DEPOSIT_AMOUNT
    pubkey = state.builders[0].pubkey
    deposit_request = prepare_builder_deposit_request(
        spec, state, amount, pubkey=pubkey, signed=True
    )

    yield from run_builder_deposit_request_processing(
        spec, state, deposit_request, is_new_builder=False
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__builder_top_up_large(spec, state):
    """Test large top-up deposit for an existing builder."""
    # Large top-up (500 ETH)
    amount = spec.Gwei(500 * spec.ETH_TO_GWEI)
    pubkey = state.builders[0].pubkey
    deposit_request = prepare_builder_deposit_request(
        spec, state, amount, pubkey=pubkey, signed=True
    )

    yield from run_builder_deposit_request_processing(
        spec, state, deposit_request, is_new_builder=False
    )


#
# Invalid signature tests
#


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_deposit_request__new_builder_invalid_sig(spec, state):
    """Test that new builder deposit with invalid signature is rejected."""
    amount = spec.MIN_DEPOSIT_AMOUNT
    # Don't sign the deposit
    deposit_request = prepare_builder_deposit_request(spec, state, amount, signed=False)

    yield from run_builder_deposit_request_processing(
        spec, state, deposit_request, is_new_builder=True, valid=False
    )


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_deposit_request__builder_top_up_invalid_sig(spec, state):
    """Test that top-up deposit with invalid signature still succeeds for existing builders."""
    amount = spec.MIN_DEPOSIT_AMOUNT
    pubkey = state.builders[0].pubkey
    # Don't sign the deposit
    deposit_request = prepare_builder_deposit_request(
        spec, state, amount, pubkey=pubkey, signed=False
    )

    # Top-ups don't require signature verification for existing builders
    yield from run_builder_deposit_request_processing(
        spec, state, deposit_request, is_new_builder=False
    )


#
# deposit_requests_start_index tests
#


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__set_start_index(spec, state):
    """Test that deposit_requests_start_index is set on first deposit request."""
    assert state.deposit_requests_start_index == spec.UNSET_DEPOSIT_REQUESTS_START_INDEX

    amount = spec.MIN_DEPOSIT_AMOUNT
    deposit_request = prepare_builder_deposit_request(spec, state, amount, signed=True)

    yield from run_builder_deposit_request_processing(spec, state, deposit_request)

    assert state.deposit_requests_start_index == deposit_request.index


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__set_start_index_only_once(spec, state):
    """Test that deposit_requests_start_index is only set once."""
    initial_start_index = 1
    state.deposit_requests_start_index = initial_start_index

    amount = spec.MIN_DEPOSIT_AMOUNT
    deposit_request = prepare_builder_deposit_request(spec, state, amount, signed=True)

    # Make sure our deposit request has a different index
    assert initial_start_index != deposit_request.index

    yield from run_builder_deposit_request_processing(spec, state, deposit_request)

    # Start index should remain unchanged
    assert state.deposit_requests_start_index == initial_start_index


#
# Edge cases
#


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__builder_pubkey_already_validator(spec, state):
    """Test that deposit with builder credentials but validator pubkey returns early."""
    # Use a pubkey that belongs to an existing validator
    validator_pubkey = state.validators[0].pubkey
    # Get any builder's privkey for signing (signature doesn't matter since we return early)
    privkey = builder_pubkey_to_privkey[state.builders[0].pubkey]

    amount = spec.MIN_DEPOSIT_AMOUNT

    # Create builder withdrawal credentials
    withdrawal_credentials = spec.BUILDER_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x59" * 20

    deposit_data = build_deposit_data(
        spec,
        validator_pubkey,
        privkey,
        amount,
        withdrawal_credentials,
        signed=True,
    )
    deposit_request = spec.DepositRequest(
        pubkey=deposit_data.pubkey,
        withdrawal_credentials=deposit_data.withdrawal_credentials,
        amount=deposit_data.amount,
        signature=deposit_data.signature,
        index=spec.uint64(0),
    )

    yield from run_builder_deposit_request_processing(
        spec, state, deposit_request, is_new_builder=True, valid=False
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__reuses_exited_builder_slot(spec, state):
    """Test that new builder can reuse slot of fully exited builder with zero balance."""
    # Advance state so we can set exit_epoch to a past epoch
    next_epoch(spec, state)

    # Make builder 0 exited with zero balance
    state.builders[0].exit_epoch = spec.get_current_epoch(state) - 1
    state.builders[0].balance = spec.Gwei(0)

    pre_builder_count = len(state.builders)

    amount = spec.MIN_DEPOSIT_AMOUNT
    deposit_request = prepare_builder_deposit_request(spec, state, amount, signed=True)

    yield from run_builder_deposit_request_processing(spec, state, deposit_request)

    # Verify builder count stayed the same (slot was reused, not appended)
    assert len(state.builders) == pre_builder_count
    # Verify the new builder is at index 0 (reused slot)
    assert state.builders[0].pubkey == deposit_request.pubkey
