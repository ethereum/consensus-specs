from eth2spec.test.context import always_bls, spec_state_test, with_gloas_and_later
from eth2spec.test.helpers.deposits import (
    make_withdrawal_credentials,
    prepare_builder_deposit_request,
    prepare_deposit_request,
    prepare_pending_deposit,
)
from eth2spec.test.helpers.keys import (
    builder_pubkey_to_privkey,
    pubkeys,
)
from tests.infra.helpers.deposit_requests import (
    assert_process_deposit_request,
    prepare_process_deposit_request,
    run_deposit_request_processing,
)


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
    pre_state = state.copy()
    pre_builder_count = len(state.builders)

    yield "pre", state
    yield "deposit_request", deposit_request

    spec.process_deposit_request(state, deposit_request)

    yield "post", state

    if not valid:
        # Invalid deposit should not change state (builder not created)
        assert_process_deposit_request(
            spec,
            state,
            pre_state,
            state_unchanged=True,
        )
    elif is_new_builder:
        # New builder should be added to registry
        assert_process_deposit_request(
            spec,
            state,
            pre_state,
            deposit_request=deposit_request,
            is_builder_deposit=True,
            expected_builder_balance=deposit_request.amount,
            expected_execution_address=spec.ExecutionAddress(
                deposit_request.withdrawal_credentials[12:]
            ),
            expected_builder_withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
        )
    else:
        # Top-up should increase balance
        assert_process_deposit_request(
            spec,
            state,
            pre_state,
            deposit_request=deposit_request,
            is_builder_deposit=True,
            expected_builder_count=pre_builder_count,
            expected_builder_balance_delta=deposit_request.amount,
        )


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
    """
    Test builder deposit with non-round amount (extra gwei).

    Input State Configured:
        - Valid beacon state with existing builders
        - Deposit request with amount = MIN_DEPOSIT_AMOUNT + 1 (non-round)

    Output State Verified:
        - New builder created
        - Builder balance equals exact deposit amount (including extra gwei)
    """
    amount = spec.MIN_DEPOSIT_AMOUNT + spec.Gwei(1)
    deposit_request = prepare_process_deposit_request(
        spec, state, for_builder=True, amount=amount, signed=True
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        expected_builder_balance=amount,
    )


#
# Top-up deposits for existing builders
#


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__builder_top_up(spec, state):
    """
    Test builder top-up with builder credentials.

    Input State Configured:
        - Existing builder pubkey
        - Builder withdrawal credentials (0x03 prefix)

    Output State Verified:
        - Builder balance increased (top-up)
        - No pending deposits added
        - Credentials field is ignored for existing builder lookup
    """
    builder_pubkey = state.builders[0].pubkey
    amount = spec.MIN_DEPOSIT_AMOUNT
    pre_balance = state.builders[0].balance
    pre_builder_count = len(state.builders)

    # Top-up existing builder using its pubkey with builder credentials (default for for_builder)
    deposit_request = prepare_process_deposit_request(
        spec, state, for_builder=True, pubkey=builder_pubkey, amount=amount, signed=True
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        expected_builder_count=pre_builder_count,
        expected_builder_balance=pre_balance + amount,
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
# Edge cases
#


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__new_builder_zero_amount(spec, state):
    """
    Test fresh builder deposit with zero amount creates a builder with zero balance.

    Input State Configured:
        - Valid beacon state with existing builders
        - Deposit request with amount = 0

    Output State Verified:
        - New builder created in registry
        - Builder balance is zero
        - Builder has correct pubkey and execution address
        - No pending deposits added (builder deposits are immediate)
    """
    deposit_request = prepare_process_deposit_request(
        spec, state, for_builder=True, amount=0, signed=True
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        expected_builder_balance=spec.Gwei(0),
        expected_execution_address=spec.ExecutionAddress(
            deposit_request.withdrawal_credentials[12:]
        ),
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__new_builder_below_minimum(spec, state):
    """
    Test builder deposit with amount below MIN_DEPOSIT_AMOUNT.

    Input State Configured:
        - Valid beacon state with existing builders
        - Deposit request with amount = MIN_DEPOSIT_AMOUNT - 1

    Output State Verified:
        - New builder created (below-minimum amounts are accepted for builders)
        - Builder balance equals deposit amount
    """
    amount = spec.MIN_DEPOSIT_AMOUNT - 1
    deposit_request = prepare_process_deposit_request(
        spec, state, for_builder=True, amount=amount, signed=True
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        expected_builder_balance=amount,
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__new_builder_max_minus_one(spec, state):
    """
    Test builder deposit with amount = MAX_EFFECTIVE_BALANCE - 1.

    Input State Configured:
        - Valid beacon state with existing builders
        - Deposit request with amount just below max effective balance

    Output State Verified:
        - New builder created
        - Builder balance equals MAX_EFFECTIVE_BALANCE - 1
    """
    amount = spec.MAX_EFFECTIVE_BALANCE - 1
    deposit_request = prepare_process_deposit_request(
        spec, state, for_builder=True, amount=amount, signed=True
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        expected_builder_balance=amount,
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__reuses_exited_builder_slot(spec, state):
    """Test that new builder can reuse slot of fully exited builder with zero balance."""
    pre_builder_count = len(state.builders)

    # Advance epochs and make builder 0 exited with zero balance
    deposit_request = prepare_process_deposit_request(
        spec,
        state,
        for_builder=True,
        amount=spec.MIN_DEPOSIT_AMOUNT,
        signed=True,
        advance_epochs=1,
        builder_modifications={0: {"withdrawable_epoch": "current_epoch-1", "balance": 0}},
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        slot_reused=True,
        expected_builder_count=pre_builder_count,
        expected_builder_index=0,
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__reuses_first_of_multiple_exited_slots(spec, state):
    """
    Test that first reusable slot is selected when multiple slots are available.

    Input State Configured:
        - Builder at index 0: exited with zero balance (reusable)
        - Builder at index 1: exited with zero balance (reusable)
        - Builder at index 2: active (not reusable)

    Output State Verified:
        - First reusable slot (index 0) is used
        - Builder count unchanged
    """
    pre_builder_count = len(state.builders)

    # Advance epochs and make builders 0 and 1 both reusable (exited with zero balance)
    # Builder 2 stays active (default FAR_FUTURE_EPOCH)
    deposit_request = prepare_process_deposit_request(
        spec,
        state,
        for_builder=True,
        amount=spec.MIN_DEPOSIT_AMOUNT,
        signed=True,
        advance_epochs=1,
        builder_modifications={
            0: {"withdrawable_epoch": "current_epoch-1", "balance": 0},
            1: {"withdrawable_epoch": "current_epoch-1", "balance": 0},
        },
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        slot_reused=True,
        expected_builder_count=pre_builder_count,
        expected_builder_index=0,
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__reuses_slot_at_current_epoch(spec, state):
    """
    Test slot reuse when withdrawable_epoch == current_epoch.

    Input State Configured:
        - Builder at index 0: withdrawable_epoch = current_epoch, balance = 0

    Output State Verified:
        - Slot IS reusable at exact epoch boundary
        - New builder placed at index 0
    """
    pre_builder_count = len(state.builders)

    # Advance epochs and make builder 0 reusable exactly at current epoch
    deposit_request = prepare_process_deposit_request(
        spec,
        state,
        for_builder=True,
        amount=spec.MIN_DEPOSIT_AMOUNT,
        signed=True,
        advance_epochs=1,
        builder_modifications={0: {"withdrawable_epoch": "current_epoch", "balance": 0}},
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        slot_reused=True,
        expected_builder_count=pre_builder_count,
        expected_builder_index=0,
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__no_reuse_future_epoch(spec, state):
    """
    Test slot NOT reusable when withdrawable_epoch == current_epoch + 1.

    Input State Configured:
        - Builder at index 0: withdrawable_epoch = current_epoch + 1, balance = 0

    Output State Verified:
        - Slot is NOT reusable (epoch in future)
        - New builder appended to registry
        - Original builders unchanged
    """
    pre_builder_count = len(state.builders)

    # Advance epochs and make builder 0 NOT yet reusable (one epoch in future)
    deposit_request = prepare_process_deposit_request(
        spec,
        state,
        for_builder=True,
        amount=spec.MIN_DEPOSIT_AMOUNT,
        signed=True,
        advance_epochs=1,
        builder_modifications={0: {"withdrawable_epoch": "current_epoch+1", "balance": 0}},
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    # slot_reused=False also verifies original builders are unchanged
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        slot_reused=False,
        expected_builder_count=pre_builder_count + 1,
        expected_builder_index=pre_builder_count,
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__no_reuse_nonzero_balance(spec, state):
    """
    Test slot NOT reusable when balance == 1.

    Input State Configured:
        - Builder at index 0: withdrawable_epoch in past, balance = 1 (minimum non-zero)

    Output State Verified:
        - Slot is NOT reusable (non-zero balance blocks reuse)
        - New builder appended to registry
        - Original builders unchanged
    """
    pre_builder_count = len(state.builders)

    # Advance epochs and make builder 0 exited but with minimum non-zero balance
    deposit_request = prepare_process_deposit_request(
        spec,
        state,
        for_builder=True,
        amount=spec.MIN_DEPOSIT_AMOUNT,
        signed=True,
        advance_epochs=1,
        builder_modifications={0: {"withdrawable_epoch": "current_epoch-1", "balance": 1}},
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    # slot_reused=False also verifies original builders are unchanged
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        slot_reused=False,
        expected_builder_count=pre_builder_count + 1,
        expected_builder_index=pre_builder_count,
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__new_builder_empty_registry(spec, state):
    """
    Test new builder deposit when state.builders is empty.

    Input State Configured:
        - Empty builders registry

    Output State Verified:
        - New builder appended as index 0
        - Builder has correct fields including withdrawable_epoch = FAR_FUTURE_EPOCH
    """
    amount = spec.MIN_DEPOSIT_AMOUNT
    # Clear builders registry via the helper
    deposit_request = prepare_process_deposit_request(
        spec, state, for_builder=True, amount=amount, signed=True, builders=[]
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        expected_builder_count=1,
        expected_builder_index=0,
        expected_builder_balance=amount,
        expected_builder_withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__builder_top_up_single_builder(spec, state):
    """
    Test top-up with single builder in registry.

    Input State Configured:
        - Exactly one builder in registry

    Output State Verified:
        - Builder balance increased
        - Builder count unchanged (still 1)
    """
    # Keep only one builder
    first_builder = state.builders[0]
    pre_balance = first_builder.balance
    amount = spec.MIN_DEPOSIT_AMOUNT

    # Top-up existing builder at index 0, keeping only one builder
    deposit_request = prepare_process_deposit_request(
        spec,
        state,
        builder_index=0,
        amount=amount,
        signed=True,
        builders=[first_builder],
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        expected_builder_count=1,
        expected_builder_balance=pre_balance + amount,
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__builder_top_up_last_index(spec, state):
    """
    Test top-up targeting last builder in registry.

    Input State Configured:
        - Multiple builders in registry
        - Top-up targets last builder

    Output State Verified:
        - Last builder's balance increased
        - Other builders unchanged (verified by assert_process_deposit_request invariant)
    """
    last_index = len(state.builders) - 1
    pubkey = state.builders[last_index].pubkey
    pre_balance = state.builders[last_index].balance
    pre_builder_count = len(state.builders)
    amount = spec.MIN_DEPOSIT_AMOUNT

    # Top-up existing builder at last index using its pubkey
    deposit_request = prepare_process_deposit_request(
        spec, state, for_builder=True, pubkey=pubkey, amount=amount, signed=True
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    # assert_process_deposit_request verifies other builders unchanged for top-ups
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        expected_builder_count=pre_builder_count,
        expected_builder_index=last_index,
        expected_builder_balance=pre_balance + amount,
    )


#
# Deposit routing tests
#
# These tests verify the routing logic in process_deposit_request:
# - Existing builder pubkey → builder (regardless of credentials)
# - Existing validator pubkey → validator queue (regardless of credentials)
# - New pubkey + builder credentials → new builder
# - New pubkey + validator credentials → validator queue
#


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__routing__builder_pubkey_validator_credentials(spec, state):
    """Test that existing builder pubkey with validator credentials still tops up builder."""
    builder_pubkey = state.builders[0].pubkey
    amount = spec.MIN_DEPOSIT_AMOUNT
    pre_balance = state.builders[0].balance
    pre_builder_count = len(state.builders)

    # Create validator-style withdrawal credentials (BLS prefix) - but use builder pubkey
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(builder_pubkey)[1:]

    # Use builder_index=0 to use existing builder's pubkey with validator credentials
    deposit_request = prepare_process_deposit_request(
        spec,
        state,
        builder_index=0,
        amount=amount,
        signed=True,
        withdrawal_credentials=withdrawal_credentials,
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    # Should top up existing builder (credentials are ignored for existing builders)
    # is_builder_deposit=True because the pubkey belongs to an existing builder
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        expected_builder_count=pre_builder_count,
        expected_builder_balance=pre_balance + amount,
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__routing__validator_pubkey_builder_credentials(spec, state):
    """Test that existing validator pubkey with builder credentials goes to validator queue."""
    validator_pubkey = state.validators[0].pubkey
    amount = spec.MIN_DEPOSIT_AMOUNT
    pre_builder_count = len(state.builders)

    # Create builder withdrawal credentials - but use existing validator pubkey
    withdrawal_credentials = spec.BUILDER_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x59" * 20

    # Use validator_index=0 to use existing validator's pubkey with builder credentials
    deposit_request = prepare_process_deposit_request(
        spec,
        state,
        validator_index=0,
        amount=amount,
        signed=True,
        withdrawal_credentials=withdrawal_credentials,
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    # Should route to validator queue (pubkey lookup finds validator first)
    # is_builder_deposit=False because it goes to validator queue
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=False,
        expected_pending_deposit_pubkey=validator_pubkey,
        expected_pending_deposit_amount=amount,
        expected_builder_count=pre_builder_count,
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__routing__validator_pubkey_validator_credentials(spec, state):
    """Test that existing validator pubkey with validator credentials goes to validator queue."""
    validator_pubkey = state.validators[0].pubkey
    amount = spec.MIN_DEPOSIT_AMOUNT
    pre_builder_count = len(state.builders)

    # Create deposit with validator (non-builder) credentials for existing validator
    deposit_request = prepare_process_deposit_request(
        spec,
        state,
        validator_index=0,
        amount=amount,
        signed=True,
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    # Should route to validator queue
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=False,
        expected_pending_deposit_pubkey=validator_pubkey,
        expected_pending_deposit_amount=amount,
        expected_builder_count=pre_builder_count,
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__routing__new_pubkey_validator_credentials(spec, state):
    """Test that new pubkey with validator credentials goes to validator queue."""
    # Use a pubkey that doesn't exist as validator or builder (new validator index)
    new_pubkey = pubkeys[len(state.validators)]
    amount = spec.MIN_DEPOSIT_AMOUNT
    pre_builder_count = len(state.builders)

    # Create deposit with validator (non-builder) credentials for new validator
    deposit_request = prepare_process_deposit_request(
        spec,
        state,
        amount=amount,
        signed=True,
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    # Should route to validator queue (for new validator creation)
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=False,
        expected_pending_deposit_pubkey=new_pubkey,
        expected_pending_deposit_amount=amount,
        expected_builder_count=pre_builder_count,
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__routing__new_pubkey_eth1_credentials(spec, state):
    """
    Test that new pubkey with ETH1 credentials (0x01) routes to validator queue.

    Input State Configured:
        - New pubkey (not existing validator or builder)
        - ETH1_WITHDRAWAL_PREFIX credentials

    Output State Verified:
        - No new builder created (builder count unchanged)
        - Pending deposit added to validator queue
    """
    new_pubkey = pubkeys[len(state.validators)]
    amount = spec.MIN_DEPOSIT_AMOUNT
    pre_builder_count = len(state.builders)

    # Create ETH1 withdrawal credentials (0x01 prefix)
    withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x59" * 20  # 20-byte eth1 address
    )

    deposit_request = prepare_process_deposit_request(
        spec,
        state,
        amount=amount,
        signed=True,
        withdrawal_credentials=withdrawal_credentials,
    )

    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    # is_builder_deposit=False triggers builder count unchanged check
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=False,
        expected_pending_deposit_pubkey=new_pubkey,
        expected_pending_deposit_credentials=withdrawal_credentials,
        expected_builder_count=pre_builder_count,
    )


#
# Pending validator deposit tests
#
# These tests verify that deposits with builder credentials for pubkeys
# that already have a pending deposit with a valid signature go to the
# validator queue instead of becoming builders.
#


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__routing__new_pubkey_compounding_credentials(spec, state):
    """
    Test new pubkey with compounding credentials (0x02) routes to validator queue.

    Input State Configured:
        - New pubkey (not existing validator or builder)
        - COMPOUNDING_WITHDRAWAL_PREFIX credentials

    Output State Verified:
        - No new builder created (builder count unchanged)
        - Pending deposit added to validator queue
    """
    new_pubkey = pubkeys[len(state.validators)]
    amount = spec.MIN_DEPOSIT_AMOUNT
    pre_builder_count = len(state.builders)

    # Create compounding withdrawal credentials (0x02 prefix)
    withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x59" * 20  # 20-byte eth1 address
    )

    deposit_request = prepare_process_deposit_request(
        spec,
        state,
        amount=amount,
        signed=True,
        withdrawal_credentials=withdrawal_credentials,
    )

    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    # is_builder_deposit=False triggers builder count unchanged check
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=False,
        expected_pending_deposit_pubkey=new_pubkey,
        expected_pending_deposit_credentials=withdrawal_credentials,
        expected_builder_count=pre_builder_count,
    )


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_deposit_request__routing__pending_deposit_valid_signature(spec, state):
    """Test that pubkey with pending deposit with valid signature goes to validator queue."""
    # Use a pubkey that doesn't exist as validator or builder yet
    new_validator_index = len(state.validators)
    amount = spec.MIN_DEPOSIT_AMOUNT

    # Add a pending deposit with a valid signature for this pubkey
    pending_withdrawal_credentials = make_withdrawal_credentials(
        spec, spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX, b"\xab"
    )
    pending_deposit = prepare_pending_deposit(
        spec,
        new_validator_index,
        amount,
        withdrawal_credentials=pending_withdrawal_credentials,
        signed=True,
    )
    state.pending_deposits.append(pending_deposit)

    # Now create a deposit request with builder credentials for the same pubkey
    deposit_request = prepare_deposit_request(
        spec,
        new_validator_index,
        amount,
        index=0,
        withdrawal_credentials=make_withdrawal_credentials(
            spec, spec.BUILDER_WITHDRAWAL_PREFIX, b"\x59"
        ),
        signed=True,
    )

    pre_builder_count = len(state.builders)
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    # Should NOT create a new builder (pubkey is a pending validator)
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=False,
        expected_builder_count=pre_builder_count,
    )


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_deposit_request__routing__pending_deposit_invalid_signature(spec, state):
    """Test that pubkey with pending deposit with invalid signature becomes builder."""
    # Use a pubkey from builder_pubkeys that doesn't exist as validator or builder yet
    existing_builder_pubkeys = {builder.pubkey for builder in state.builders}
    new_builder_pubkey = None
    for pk in builder_pubkey_to_privkey:
        if pk not in existing_builder_pubkeys:
            new_builder_pubkey = pk
            break
    assert new_builder_pubkey is not None
    privkey = builder_pubkey_to_privkey[new_builder_pubkey]
    amount = spec.MIN_DEPOSIT_AMOUNT

    # Add a pending deposit with an invalid signature (won't create a validator)
    invalid_pending_deposit = spec.PendingDeposit(
        pubkey=new_builder_pubkey,
        amount=amount,
        withdrawal_credentials=make_withdrawal_credentials(
            spec, spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX, b"\xab"
        ),
        signature=spec.BLSSignature(),  # Invalid empty signature
        slot=spec.GENESIS_SLOT,
    )
    state.pending_deposits.append(invalid_pending_deposit)

    # Now create a deposit request with builder credentials for the same pubkey
    deposit_request = prepare_deposit_request(
        spec,
        0,
        amount,
        index=0,
        pubkey=new_builder_pubkey,
        privkey=privkey,
        withdrawal_credentials=make_withdrawal_credentials(
            spec, spec.BUILDER_WITHDRAWAL_PREFIX, b"\x59"
        ),
        signed=True,
    )

    pre_builder_count = len(state.builders)
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    # SHOULD create a new builder (pending deposit has invalid sig, so is_pending_validator is False)
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        expected_builder_count=pre_builder_count + 1,
        expected_builder_balance=amount,
        expected_execution_address=spec.ExecutionAddress(
            deposit_request.withdrawal_credentials[12:]
        ),
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__nonstandard_credential_padding(spec, state):
    """
    Test builder deposit with non-zero bytes in credentials[1:12].

    The Builder container extracts execution_address from credentials[12:].
    This test verifies that non-standard padding (non-zero bytes in [1:12])
    still results in correct address extraction.

    Input State Configured:
        - New builder pubkey
        - Builder credentials with non-zero padding in bytes 1-11

    Output State Verified:
        - New builder created
        - execution_address extracted from credentials[12:]
        - Non-zero padding bytes in [1:12] are ignored
    """
    amount = spec.MIN_DEPOSIT_AMOUNT
    pre_builder_count = len(state.builders)

    # Create credentials with non-zero padding bytes in [1:12]
    execution_address = b"\xab" * 20  # 20-byte execution address
    nonstandard_padding = b"\xff" * 11  # Non-zero bytes instead of standard 0x00

    withdrawal_credentials = (
        spec.BUILDER_WITHDRAWAL_PREFIX
        + nonstandard_padding  # Non-standard: typically b"\x00" * 11
        + execution_address
    )

    deposit_request = prepare_process_deposit_request(
        spec,
        state,
        for_builder=True,
        amount=amount,
        signed=True,
        withdrawal_credentials=withdrawal_credentials,
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
        expected_builder_count=pre_builder_count + 1,
        expected_builder_balance=amount,
        expected_execution_address=spec.ExecutionAddress(execution_address),
    )


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_deposit_request__routing__pending_deposits_invalid_then_valid(spec, state):
    """Test that pubkey with invalid pending deposits followed by valid one goes to validator queue."""
    # Use a pubkey that doesn't exist as validator or builder yet
    new_validator_index = len(state.validators)
    new_pubkey = pubkeys[new_validator_index]
    amount = spec.MIN_DEPOSIT_AMOUNT

    # Add multiple pending deposits with invalid signatures first
    for _ in range(3):
        invalid_pending_deposit = spec.PendingDeposit(
            pubkey=new_pubkey,
            amount=amount,
            withdrawal_credentials=make_withdrawal_credentials(
                spec, spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX, b"\xab"
            ),
            signature=spec.BLSSignature(),  # Invalid empty signature
            slot=spec.GENESIS_SLOT,
        )
        state.pending_deposits.append(invalid_pending_deposit)

    # Add a valid pending deposit after the invalid ones
    valid_withdrawal_credentials = make_withdrawal_credentials(
        spec, spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX, b"\xcd"
    )
    valid_pending_deposit = prepare_pending_deposit(
        spec,
        new_validator_index,
        amount,
        withdrawal_credentials=valid_withdrawal_credentials,
        signed=True,
    )
    state.pending_deposits.append(valid_pending_deposit)

    # Now create a deposit request with builder credentials for the same pubkey
    deposit_request = prepare_deposit_request(
        spec,
        new_validator_index,
        amount,
        index=0,
        withdrawal_credentials=make_withdrawal_credentials(
            spec, spec.BUILDER_WITHDRAWAL_PREFIX, b"\x59"
        ),
        signed=True,
    )

    pre_builder_count = len(state.builders)
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    # Should NOT create a new builder (there's a valid pending deposit in the queue)
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=False,
        expected_builder_count=pre_builder_count,
    )


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_deposit_request__routing__pending_deposit_builder_credentials(spec, state):
    """Test that pubkey with pending deposit with builder credentials goes to validator queue."""
    # Use a pubkey that doesn't exist as validator or builder yet
    new_validator_index = len(state.validators)
    amount = spec.MIN_DEPOSIT_AMOUNT

    # Add a pending deposit with builder credentials and a valid signature
    pending_withdrawal_credentials = make_withdrawal_credentials(
        spec, spec.BUILDER_WITHDRAWAL_PREFIX, b"\xab"
    )
    pending_deposit = prepare_pending_deposit(
        spec,
        new_validator_index,
        amount,
        withdrawal_credentials=pending_withdrawal_credentials,
        signed=True,
    )
    state.pending_deposits.append(pending_deposit)

    # Now create another deposit request with builder credentials for the same pubkey
    deposit_request = prepare_deposit_request(
        spec,
        new_validator_index,
        amount,
        index=0,
        withdrawal_credentials=make_withdrawal_credentials(
            spec, spec.BUILDER_WITHDRAWAL_PREFIX, b"\x59"
        ),
        signed=True,
    )

    pre_builder_count = len(state.builders)
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    # Should NOT create a new builder (pubkey has valid pending deposit)
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=False,
        expected_builder_count=pre_builder_count,
    )
