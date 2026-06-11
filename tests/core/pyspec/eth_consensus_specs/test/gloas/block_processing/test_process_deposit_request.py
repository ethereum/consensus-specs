from eth_consensus_specs.test.context import spec_state_test, with_gloas_and_later
from tests.infra.helpers.deposit_requests import (
    assert_process_deposit_request,
    prepare_process_deposit_request,
    run_deposit_request_processing,
)

#
# In Gloas, deposit requests never create or top up builders. Builders are
# created and topped up only via builder deposit requests. These tests verify
# that deposits with builder withdrawal credentials, or for pubkeys that are
# already builders, are queued as ordinary pending deposits.
#


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__builder_credentials_queued(spec, state):
    """
    Test that a deposit with builder withdrawal credentials is queued.

    Input State Configured:
        - New pubkey (not an existing validator or builder)
        - Builder withdrawal credentials (0x03 prefix)

    Output State Verified:
        - Pending deposit added to the validator queue
        - No builder created (builder count unchanged)
    """
    amount = spec.MIN_DEPOSIT_AMOUNT
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
        expected_pending_deposit_pubkey=deposit_request.pubkey,
        expected_pending_deposit_amount=amount,
        expected_pending_deposit_credentials=deposit_request.withdrawal_credentials,
    )


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__builder_pubkey_queued(spec, state):
    """
    Test that a deposit for a pubkey that is already a builder is queued.

    Input State Configured:
        - Existing builder pubkey
        - Builder withdrawal credentials (0x03 prefix)

    Output State Verified:
        - Pending deposit added to the validator queue
        - Builder unchanged (no top-up)
    """
    amount = spec.MIN_DEPOSIT_AMOUNT
    deposit_request = prepare_process_deposit_request(
        spec, state, builder_index=0, amount=amount, signed=True
    )
    pre_state = state.copy()

    yield from run_deposit_request_processing(spec, state, deposit_request)

    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        expected_pending_deposit_pubkey=deposit_request.pubkey,
        expected_pending_deposit_amount=amount,
    )
    # The existing builder must be untouched
    assert state.builders[0] == pre_state.builders[0]


@with_gloas_and_later
@spec_state_test
def test_process_deposit_request__builder_pubkey_validator_credentials(spec, state):
    """
    Test that a deposit for a builder pubkey with validator credentials is queued.

    Input State Configured:
        - Existing builder pubkey
        - ETH1 withdrawal credentials (0x01 prefix)

    Output State Verified:
        - Pending deposit added to the validator queue
        - Builder unchanged (no top-up)
    """
    amount = spec.MIN_DEPOSIT_AMOUNT
    withdrawal_credentials = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x59" * 20
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

    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        expected_pending_deposit_pubkey=deposit_request.pubkey,
        expected_pending_deposit_credentials=withdrawal_credentials,
    )
    # The existing builder must be untouched
    assert state.builders[0] == pre_state.builders[0]
