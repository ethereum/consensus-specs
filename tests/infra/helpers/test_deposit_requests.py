from eth2spec.test.context import (
    spec_state_test,
    with_all_phases_from_to,
    with_electra_and_later,
    with_gloas_and_later,
)
from eth2spec.test.helpers.constants import ELECTRA, FULU
from eth2spec.test.helpers.keys import builder_pubkeys, pubkeys
from tests.infra.helpers.deposit_requests import (
    assert_process_deposit_request,
    prepare_process_deposit_request,
)


@with_electra_and_later
@spec_state_test
def test_prepare_process_deposit_request_defaults(spec, state):
    """Test prepare_process_deposit_request with default parameters."""
    validator_index = len(state.validators)
    deposit_request = prepare_process_deposit_request(spec, state)

    # Default amount should be MIN_ACTIVATION_BALANCE
    assert deposit_request.amount == spec.MIN_ACTIVATION_BALANCE

    # Default request_index should be 0
    assert deposit_request.index == 0

    # Pubkey should be from the validator index
    assert deposit_request.pubkey == pubkeys[validator_index]

    # Withdrawal credentials should be BLS prefix + hash(pubkey)[1:]
    expected_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(pubkeys[validator_index])[1:]
    assert deposit_request.withdrawal_credentials == expected_credentials


@with_electra_and_later
@spec_state_test
def test_prepare_process_deposit_request_custom_amount(spec, state):
    """Test prepare_process_deposit_request with custom amount."""
    custom_amount = spec.Gwei(5_000_000_000)
    deposit_request = prepare_process_deposit_request(spec, state, amount=custom_amount)
    assert deposit_request.amount == custom_amount


@with_electra_and_later
@spec_state_test
def test_prepare_process_deposit_request_custom_index(spec, state):
    """Test prepare_process_deposit_request with custom request_index."""
    custom_index = 42
    deposit_request = prepare_process_deposit_request(spec, state, request_index=custom_index)
    assert deposit_request.index == custom_index


@with_electra_and_later
@spec_state_test
def test_prepare_process_deposit_request_existing_validator(spec, state):
    """Test prepare_process_deposit_request for top-up of existing validator."""
    validator_index = 0  # Use first existing validator
    deposit_request = prepare_process_deposit_request(spec, state, validator_index=validator_index)
    assert deposit_request.pubkey == state.validators[validator_index].pubkey


@with_electra_and_later
@spec_state_test
def test_prepare_process_deposit_request_signed(spec, state):
    """Test prepare_process_deposit_request with signed=True."""
    deposit_request = prepare_process_deposit_request(spec, state, signed=True)

    # Signature should not be empty when signed
    assert deposit_request.signature != spec.BLSSignature()


@with_electra_and_later
@spec_state_test
def test_prepare_process_deposit_request_state_override(spec, state):
    """Test prepare_process_deposit_request with state override."""
    custom_start_index = 123
    prepare_process_deposit_request(spec, state, deposit_requests_start_index=custom_start_index)

    # State should have the overridden value
    assert state.deposit_requests_start_index == custom_start_index


@with_electra_and_later
@spec_state_test
def test_prepare_process_deposit_request_compounding_credentials(spec, state):
    """Test prepare_process_deposit_request with compounding withdrawal credentials."""
    compounding_credentials = spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x59" * 20
    deposit_request = prepare_process_deposit_request(
        spec, state, withdrawal_credentials=compounding_credentials
    )

    assert deposit_request.withdrawal_credentials == compounding_credentials


@with_electra_and_later
@spec_state_test
def test_run_and_assert_deposit_request_processing(spec, state):
    """Test full flow: prepare, run, and assert."""
    # Prepare the deposit request
    deposit_request = prepare_process_deposit_request(spec, state, signed=True)

    # Save pre-state for assertions
    pre_state = state.copy()

    # Run processing (just process, don't yield for test vectors)
    spec.process_deposit_request(state, deposit_request)

    # Assert the outcomes
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
    )


@with_all_phases_from_to(ELECTRA, FULU)
@spec_state_test
def test_assert_process_deposit_request_start_index_set(spec, state):
    """Test that deposit_requests_start_index is set when UNSET (Electra/Fulu only)."""
    # Ensure start index is UNSET
    state.deposit_requests_start_index = spec.UNSET_DEPOSIT_REQUESTS_START_INDEX

    request_index = 42
    deposit_request = prepare_process_deposit_request(
        spec, state, request_index=request_index, signed=True
    )

    pre_state = state.copy()
    spec.process_deposit_request(state, deposit_request)

    # Should be set to the request index
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        expected_deposit_requests_start_index=request_index,
    )


@with_all_phases_from_to(ELECTRA, FULU)
@spec_state_test
def test_assert_process_deposit_request_start_index_unchanged(spec, state):
    """Test that deposit_requests_start_index is NOT changed when already set (Electra/Fulu only)."""
    # Set a custom start index
    initial_start_index = 100
    state.deposit_requests_start_index = initial_start_index

    request_index = 42  # Different from initial_start_index
    deposit_request = prepare_process_deposit_request(
        spec, state, request_index=request_index, signed=True
    )

    pre_state = state.copy()
    spec.process_deposit_request(state, deposit_request)

    # Should remain unchanged
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        expected_deposit_requests_start_index=initial_start_index,
        start_index_unchanged=True,
    )


# ============================================================================
# Builder deposit tests (Gloas+)
# ============================================================================


@with_gloas_and_later
@spec_state_test
def test_prepare_process_deposit_request_for_builder(spec, state):
    """Test prepare_process_deposit_request with for_builder=True."""
    builder_index = len(state.builders)
    deposit_request = prepare_process_deposit_request(spec, state, for_builder=True)

    # Should use builder pubkey
    assert deposit_request.pubkey == builder_pubkeys[builder_index]

    # Should use BUILDER_WITHDRAWAL_PREFIX (0x03)
    assert deposit_request.withdrawal_credentials[0:1] == spec.BUILDER_WITHDRAWAL_PREFIX

    # Default amount should be MIN_ACTIVATION_BALANCE
    assert deposit_request.amount == spec.MIN_ACTIVATION_BALANCE


@with_gloas_and_later
@spec_state_test
def test_prepare_process_deposit_request_builder_custom_amount(spec, state):
    """Test prepare_process_deposit_request for builder with custom amount."""
    custom_amount = spec.Gwei(100_000_000_000)  # 100 ETH
    deposit_request = prepare_process_deposit_request(
        spec, state, for_builder=True, amount=custom_amount
    )

    assert deposit_request.amount == custom_amount


@with_gloas_and_later
@spec_state_test
def test_run_and_assert_builder_deposit_processing(spec, state):
    """Test full flow for builder deposit: prepare, run, and assert."""
    # Prepare the builder deposit request
    deposit_request = prepare_process_deposit_request(spec, state, for_builder=True, signed=True)

    # Save pre-state for assertions
    pre_state = state.copy()
    pre_builder_count = len(state.builders)

    # Run processing
    spec.process_deposit_request(state, deposit_request)

    # Assert the outcomes (new builder created)
    assert_process_deposit_request(
        spec,
        state,
        pre_state,
        deposit_request=deposit_request,
        is_builder_deposit=True,
    )

    # Verify new builder was created
    assert len(state.builders) == pre_builder_count + 1
