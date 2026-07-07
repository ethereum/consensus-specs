from eth_consensus_specs.test.context import always_bls, spec_state_test, with_gloas_and_later
from eth_consensus_specs.test.helpers.builder_deposit_requests import (
    assert_process_builder_deposit_request,
    prepare_process_builder_deposit_request,
    run_builder_deposit_request_processing,
)
from eth_consensus_specs.test.helpers.deposits import prepare_builder_deposit_request
from eth_consensus_specs.test.helpers.keys import builder_pubkey_to_privkey, privkeys, pubkeys
from eth_consensus_specs.utils import bls


def run_builder_deposit_processing(
    spec, state, builder_deposit_request, is_new_builder=True, valid=True
):
    """
    Run ``process_builder_deposit_request``, yielding:
      - pre-state ('pre')
      - builder_deposit_request ('builder_deposit_request')
      - post-state ('post').

    Args:
        is_new_builder: If True, expect a new builder to be created.
                        If False, expect a top-up of an existing builder.
        valid: If True, expect the deposit to be applied (new builder or top-up).
               If False, expect no changes (invalid signature, wrong credentials, etc).
    """
    pre_state = state.copy()
    pre_builder_count = len(state.builders)

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    if not valid:
        # Invalid deposit should not change state (builder not created)
        assert_process_builder_deposit_request(
            spec,
            state,
            pre_state,
            builder_deposit_request=builder_deposit_request,
            state_unchanged=True,
        )
    elif is_new_builder:
        # New builder should be added to registry
        assert_process_builder_deposit_request(
            spec,
            state,
            pre_state,
            builder_deposit_request=builder_deposit_request,
            expected_builder_balance=builder_deposit_request.amount,
            expected_execution_address=spec.ExecutionAddress(
                builder_deposit_request.withdrawal_credentials[12:]
            ),
            expected_builder_withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
        )
    else:
        # Top-up should increase balance
        assert_process_builder_deposit_request(
            spec,
            state,
            pre_state,
            builder_deposit_request=builder_deposit_request,
            expected_builder_count=pre_builder_count,
            expected_builder_balance_delta=builder_deposit_request.amount,
        )


#
# New builder deposits
#


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__new_builder(spec, state):
    """Test fresh builder deposit creates a new builder."""
    amount = spec.MIN_DEPOSIT_AMOUNT
    builder_deposit_request = prepare_builder_deposit_request(spec, state, amount, signed=True)

    yield from run_builder_deposit_processing(spec, state, builder_deposit_request)


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__new_builder_non_payload_version(spec, state):
    """
    Test fresh builder deposit with a non-payload builder version.

    Gloas registers new builders with PAYLOAD_BUILDER_VERSION.
    """
    amount = spec.MIN_DEPOSIT_AMOUNT
    withdrawal_credentials = (
        bytes([spec.PAYLOAD_BUILDER_VERSION + 1]) + b"\x00" * 11 + b"\x42" * 20
    )
    builder_deposit_request = prepare_builder_deposit_request(
        spec, state, amount, withdrawal_credentials=withdrawal_credentials, signed=True
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=builder_deposit_request,
        expected_builder_balance=amount,
        expected_execution_address=spec.ExecutionAddress(
            builder_deposit_request.withdrawal_credentials[12:]
        ),
        expected_builder_withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
    )

    builder_index = [b.pubkey for b in state.builders].index(builder_deposit_request.pubkey)
    assert state.builders[builder_index].version == spec.PAYLOAD_BUILDER_VERSION


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__new_builder_large_amount(spec, state):
    """Test fresh builder deposit with a large amount."""
    # 1000 ETH deposit
    amount = spec.Gwei(1_000 * spec.ETH_TO_GWEI)
    builder_deposit_request = prepare_builder_deposit_request(spec, state, amount, signed=True)

    yield from run_builder_deposit_processing(spec, state, builder_deposit_request)


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__new_builder_very_large_amount(spec, state):
    """Test fresh builder deposit with a very large amount."""
    # 10k ETH deposit
    amount = spec.Gwei(10_000 * spec.ETH_TO_GWEI)
    builder_deposit_request = prepare_builder_deposit_request(spec, state, amount, signed=True)

    yield from run_builder_deposit_processing(spec, state, builder_deposit_request)


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__new_builder_extra_gwei(spec, state):
    """
    Test builder deposit with non-round amount (extra gwei).

    Input State Configured:
        - Valid beacon state with existing builders
        - Builder deposit request with amount = MIN_DEPOSIT_AMOUNT + 1 (non-round)

    Output State Verified:
        - New builder created
        - Builder balance equals exact deposit amount (including extra gwei)
    """
    amount = spec.MIN_DEPOSIT_AMOUNT + spec.Gwei(1)
    builder_deposit_request = prepare_process_builder_deposit_request(
        spec, state, amount=amount, signed=True
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=builder_deposit_request,
        expected_builder_balance=amount,
    )


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__new_builder_max_minus_one(spec, state):
    """
    Test builder deposit with amount = MAX_EFFECTIVE_BALANCE - 1.

    Input State Configured:
        - Valid beacon state with existing builders
        - Builder deposit request with amount just below max effective balance

    Output State Verified:
        - New builder created
        - Builder balance equals MAX_EFFECTIVE_BALANCE - 1
    """
    amount = spec.MAX_EFFECTIVE_BALANCE - 1
    builder_deposit_request = prepare_process_builder_deposit_request(
        spec, state, amount=amount, signed=True
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=builder_deposit_request,
        expected_builder_balance=amount,
    )


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__new_builder_empty_registry(spec, state):
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
    builder_deposit_request = prepare_process_builder_deposit_request(
        spec, state, amount=amount, signed=True, builders=[]
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=builder_deposit_request,
        expected_builder_count=1,
        expected_builder_index=0,
        expected_builder_balance=amount,
        expected_builder_withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
    )


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__new_builder_pubkey_is_validator(spec, state):
    """
    Test that a builder deposit request registers a builder even when the
    pubkey already belongs to a validator. The validator and builder
    registries are keyed independently, so one pubkey may be both.
    """
    validator_pubkey = state.validators[0].pubkey
    assert validator_pubkey == pubkeys[0]
    amount = spec.MIN_DEPOSIT_AMOUNT
    pre_builder_count = len(state.builders)

    builder_deposit_request = prepare_builder_deposit_request(
        spec, state, amount, pubkey=validator_pubkey, privkey=privkeys[0], signed=True
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=builder_deposit_request,
        expected_builder_count=pre_builder_count + 1,
        expected_builder_balance=amount,
    )


#
# Top-up deposits for existing builders
#


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__top_up(spec, state):
    """
    Test builder top-up with builder credentials.

    Input State Configured:
        - Existing builder pubkey
        - Builder withdrawal credentials

    Output State Verified:
        - Builder balance increased (top-up)
        - No pending deposits added
    """
    builder_pubkey = state.builders[0].pubkey
    amount = spec.MIN_DEPOSIT_AMOUNT
    pre_balance = state.builders[0].balance
    pre_builder_count = len(state.builders)

    builder_deposit_request = prepare_builder_deposit_request(
        spec, state, amount, pubkey=builder_pubkey, signed=True
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=builder_deposit_request,
        expected_builder_count=pre_builder_count,
        expected_builder_balance=pre_balance + amount,
    )


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__top_up_large(spec, state):
    """Test large top-up deposit for an existing builder."""
    # Large top-up (500 ETH)
    amount = spec.Gwei(500 * spec.ETH_TO_GWEI)
    pubkey = state.builders[0].pubkey
    builder_deposit_request = prepare_builder_deposit_request(
        spec, state, amount, pubkey=pubkey, signed=True
    )

    yield from run_builder_deposit_processing(
        spec, state, builder_deposit_request, is_new_builder=False
    )


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__top_up_single_builder(spec, state):
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
    builder_deposit_request = prepare_process_builder_deposit_request(
        spec,
        state,
        builder_index=0,
        amount=amount,
        signed=True,
        builders=[first_builder],
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=builder_deposit_request,
        expected_builder_count=1,
        expected_builder_balance=pre_balance + amount,
    )


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__top_up_last_index(spec, state):
    """
    Test top-up targeting last builder in registry.

    Input State Configured:
        - Multiple builders in registry
        - Top-up targets last builder

    Output State Verified:
        - Last builder's balance increased
        - Other builders unchanged (verified by assert_process_builder_deposit_request invariant)
    """
    last_index = len(state.builders) - 1
    pubkey = state.builders[last_index].pubkey
    pre_balance = state.builders[last_index].balance
    pre_builder_count = len(state.builders)
    amount = spec.MIN_DEPOSIT_AMOUNT

    builder_deposit_request = prepare_builder_deposit_request(
        spec, state, amount, pubkey=pubkey, signed=True
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    # assert_process_builder_deposit_request verifies other builders unchanged for top-ups
    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=builder_deposit_request,
        expected_builder_count=pre_builder_count,
        expected_builder_index=last_index,
        expected_builder_balance=pre_balance + amount,
    )


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__top_up_ignores_request_fields(spec, state):
    """
    Test that a top-up for an existing builder ignores the supplied withdrawal
    credentials. The existing registration is unchanged.
    """
    builder_pubkey = state.builders[0].pubkey
    amount = spec.MIN_DEPOSIT_AMOUNT
    pre_balance = state.builders[0].balance
    pre_builder_count = len(state.builders)

    # Use withdrawal credentials that differ from the registration
    withdrawal_credentials = b"\x07" + b"\x00" * 11 + b"\x42" * 20
    assert state.builders[0].version != spec.uint8(withdrawal_credentials[0])
    assert state.builders[0].execution_address != spec.ExecutionAddress(withdrawal_credentials[12:])

    builder_deposit_request = prepare_builder_deposit_request(
        spec,
        state,
        amount,
        pubkey=builder_pubkey,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    # Should top up the existing builder (other request fields are ignored)
    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=builder_deposit_request,
        expected_builder_count=pre_builder_count,
        expected_builder_balance=pre_balance + amount,
    )
    assert state.builders[0].version == pre_state.builders[0].version
    assert state.builders[0].execution_address == pre_state.builders[0].execution_address


#
# Invalid deposits
#


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_builder_deposit_request__new_builder_invalid_sig(spec, state):
    """Test that new builder deposit with invalid signature is dropped."""
    amount = spec.MIN_DEPOSIT_AMOUNT
    # Don't sign the deposit
    builder_deposit_request = prepare_builder_deposit_request(spec, state, amount, signed=False)

    yield from run_builder_deposit_processing(
        spec, state, builder_deposit_request, is_new_builder=True, valid=False
    )


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_builder_deposit_request__new_builder_replayed_validator_sig(spec, state):
    """
    Test that a builder deposit signed under DOMAIN_DEPOSIT is dropped.

    A signature over the same DepositMessage under DOMAIN_DEPOSIT is a valid
    validator deposit signature. It must not be accepted here, otherwise any
    validator deposit could be replayed to the builder deposit contract to
    register its pubkey as a builder.
    """
    amount = spec.MIN_DEPOSIT_AMOUNT
    builder_deposit_request = prepare_builder_deposit_request(spec, state, amount, signed=False)

    # Sign over the validator deposit domain instead of DOMAIN_BUILDER_DEPOSIT
    deposit_message = spec.DepositMessage(
        pubkey=builder_deposit_request.pubkey,
        withdrawal_credentials=builder_deposit_request.withdrawal_credentials,
        amount=builder_deposit_request.amount,
    )
    domain = spec.compute_domain(spec.DOMAIN_DEPOSIT)
    signing_root = spec.compute_signing_root(deposit_message, domain)
    privkey = builder_pubkey_to_privkey[builder_deposit_request.pubkey]
    builder_deposit_request.signature = bls.Sign(privkey, signing_root)

    yield from run_builder_deposit_processing(
        spec, state, builder_deposit_request, is_new_builder=True, valid=False
    )


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_builder_deposit_request__top_up_invalid_sig(spec, state):
    """Test that top-up deposit with invalid signature still succeeds for existing builders."""
    amount = spec.MIN_DEPOSIT_AMOUNT
    pubkey = state.builders[0].pubkey
    # Don't sign the deposit
    builder_deposit_request = prepare_builder_deposit_request(
        spec, state, amount, pubkey=pubkey, signed=False
    )

    # Top-ups don't require signature verification for existing builders
    yield from run_builder_deposit_processing(
        spec, state, builder_deposit_request, is_new_builder=False
    )


#
# Builder slot reuse
#


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__reuses_exited_builder_slot(spec, state):
    """Test that new builder can reuse slot of fully exited builder with zero balance."""
    pre_builder_count = len(state.builders)

    # Advance epochs and make builder 0 exited with zero balance
    builder_deposit_request = prepare_process_builder_deposit_request(
        spec,
        state,
        amount=spec.MIN_DEPOSIT_AMOUNT,
        signed=True,
        advance_epochs=1,
        builder_modifications={0: {"withdrawable_epoch": "current_epoch-1", "balance": 0}},
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=builder_deposit_request,
        slot_reused=True,
        expected_builder_count=pre_builder_count,
        expected_builder_index=0,
    )


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__reuses_first_of_multiple_exited_slots(spec, state):
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
    builder_deposit_request = prepare_process_builder_deposit_request(
        spec,
        state,
        amount=spec.MIN_DEPOSIT_AMOUNT,
        signed=True,
        advance_epochs=1,
        builder_modifications={
            0: {"withdrawable_epoch": "current_epoch-1", "balance": 0},
            1: {"withdrawable_epoch": "current_epoch-1", "balance": 0},
        },
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=builder_deposit_request,
        slot_reused=True,
        expected_builder_count=pre_builder_count,
        expected_builder_index=0,
    )


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__reuses_slot_at_current_epoch(spec, state):
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
    builder_deposit_request = prepare_process_builder_deposit_request(
        spec,
        state,
        amount=spec.MIN_DEPOSIT_AMOUNT,
        signed=True,
        advance_epochs=1,
        builder_modifications={0: {"withdrawable_epoch": "current_epoch", "balance": 0}},
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=builder_deposit_request,
        slot_reused=True,
        expected_builder_count=pre_builder_count,
        expected_builder_index=0,
    )


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__no_reuse_future_epoch(spec, state):
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
    builder_deposit_request = prepare_process_builder_deposit_request(
        spec,
        state,
        amount=spec.MIN_DEPOSIT_AMOUNT,
        signed=True,
        advance_epochs=1,
        builder_modifications={0: {"withdrawable_epoch": "current_epoch+1", "balance": 0}},
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    # slot_reused=False also verifies original builders are unchanged
    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=builder_deposit_request,
        slot_reused=False,
        expected_builder_count=pre_builder_count + 1,
        expected_builder_index=pre_builder_count,
    )


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__no_reuse_nonzero_balance(spec, state):
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
    builder_deposit_request = prepare_process_builder_deposit_request(
        spec,
        state,
        amount=spec.MIN_DEPOSIT_AMOUNT,
        signed=True,
        advance_epochs=1,
        builder_modifications={0: {"withdrawable_epoch": "current_epoch-1", "balance": 1}},
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, builder_deposit_request)

    # slot_reused=False also verifies original builders are unchanged
    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=builder_deposit_request,
        slot_reused=False,
        expected_builder_count=pre_builder_count + 1,
        expected_builder_index=pre_builder_count,
    )


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__exited_builder_top_up_zero_balance(spec, state):
    """
    Test top-up to a fully-swept exited builder resets its withdrawable epoch.

    Input State Configured:
        - Existing builder at index 0 that has exited (withdrawable_epoch in the
          past) and has been fully swept (balance == 0)

    Output State Verified:
        - Builder balance increased (top-up)
        - withdrawable_epoch reset to current_epoch + MIN_BUILDER_WITHDRAWABILITY_DELAY
    """
    builder_pubkey = state.builders[0].pubkey
    amount = spec.MIN_DEPOSIT_AMOUNT
    pre_builder_count = len(state.builders)

    # Advance an epoch and mark builder 0 as exited (withdrawable_epoch in the
    # past) and fully swept (balance == 0)
    deposit_request = prepare_process_builder_deposit_request(
        spec,
        state,
        pubkey=builder_pubkey,
        amount=amount,
        signed=True,
        advance_epochs=1,
        builder_modifications={0: {"withdrawable_epoch": "current_epoch-1", "balance": 0}},
    )
    pre_state = state.copy()
    expected_withdrawable_epoch = (
        spec.get_current_epoch(state) + spec.config.MIN_BUILDER_WITHDRAWABILITY_DELAY
    )
    # Sanity check: the exited epoch differs from the expected reset value
    assert pre_state.builders[0].withdrawable_epoch != expected_withdrawable_epoch
    assert pre_state.builders[0].balance == 0

    yield from run_builder_deposit_request_processing(spec, state, deposit_request)

    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=deposit_request,
        expected_builder_count=pre_builder_count,
        expected_builder_index=0,
        expected_builder_balance_delta=amount,
        expected_builder_withdrawable_epoch=expected_withdrawable_epoch,
    )


@with_gloas_and_later
@spec_state_test
def test_process_builder_deposit_request__exited_builder_top_up_nonzero_balance(spec, state):
    """
    Test that a top-up to an exited builder that still holds a balance does NOT
    reset its withdrawable epoch.

    Input State Configured:
        - Existing builder at index 0 that has exited (withdrawable_epoch in the
          past) and still holds a large non-zero balance

    Output State Verified:
        - Builder balance increased by the top-up amount
        - withdrawable_epoch unchanged (no reset)
    """
    builder_pubkey = state.builders[0].pubkey
    balance = 1 * spec.ETH_TO_GWEI
    amount = spec.Gwei(1 * spec.ETH_TO_GWEI)
    pre_builder_count = len(state.builders)

    # Advance an epoch and mark builder 0 as exited (withdrawable_epoch in the
    # past) while keeping a non-zero balance (funds not yet swept)
    deposit_request = prepare_process_builder_deposit_request(
        spec,
        state,
        pubkey=builder_pubkey,
        amount=amount,
        signed=True,
        advance_epochs=1,
        builder_modifications={0: {"withdrawable_epoch": "current_epoch-1", "balance": balance}},
    )
    pre_state = state.copy()
    # Sanity check: the builder is exited but still holds a balance
    assert pre_state.builders[0].withdrawable_epoch != spec.FAR_FUTURE_EPOCH
    assert pre_state.builders[0].balance > 0

    yield from run_builder_deposit_request_processing(spec, state, deposit_request)

    assert_process_builder_deposit_request(
        spec,
        state,
        pre_state,
        builder_deposit_request=deposit_request,
        expected_builder_count=pre_builder_count,
        expected_builder_index=0,
        expected_builder_balance_delta=amount,
        expected_builder_withdrawable_epoch=pre_state.builders[0].withdrawable_epoch,
    )
