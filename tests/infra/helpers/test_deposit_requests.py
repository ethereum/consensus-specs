from unittest.mock import MagicMock, patch

from eth_consensus_specs.test.context import (
    spec_state_test,
    with_all_phases_from_to,
    with_electra_and_later,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.constants import ELECTRA, GLOAS
from eth_consensus_specs.test.helpers.keys import builder_pubkeys, pubkeys
from eth_consensus_specs.utils import bls
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

    # Verify the signature is valid
    deposit_message = spec.DepositMessage(
        pubkey=deposit_request.pubkey,
        withdrawal_credentials=deposit_request.withdrawal_credentials,
        amount=deposit_request.amount,
    )
    domain = spec.compute_domain(spec.DOMAIN_DEPOSIT)
    signing_root = spec.compute_signing_root(deposit_message, domain)
    assert bls.Verify(deposit_request.pubkey, signing_root, deposit_request.signature)


@with_electra_and_later
@spec_state_test
def test_prepare_process_deposit_request_compounding_credentials(spec, state):
    """Test prepare_process_deposit_request with compounding withdrawal credentials."""
    compounding_credentials = spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x59" * 20
    deposit_request = prepare_process_deposit_request(
        spec, state, withdrawal_credentials=compounding_credentials
    )

    assert deposit_request.withdrawal_credentials == compounding_credentials


def test_assert_validator_deposit():
    """Test assert_process_deposit_request passes for a correct validator deposit."""
    UNSET_VALUE = 2**64 - 1

    spec = MagicMock()
    spec.UNSET_DEPOSIT_REQUESTS_START_INDEX = UNSET_VALUE

    deposit_request = MagicMock()
    deposit_request.pubkey = b"\x01" * 48
    deposit_request.withdrawal_credentials = b"\x00" + b"\x01" * 31
    deposit_request.amount = 32_000_000_000
    deposit_request.signature = b"\x02" * 96
    deposit_request.index = 0

    slot = 100

    pending_deposit = MagicMock()
    pending_deposit.pubkey = deposit_request.pubkey
    pending_deposit.withdrawal_credentials = deposit_request.withdrawal_credentials
    pending_deposit.amount = deposit_request.amount
    pending_deposit.signature = deposit_request.signature
    pending_deposit.slot = slot

    pre_state = MagicMock()
    pre_state.pending_deposits = []
    pre_state.validators = [MagicMock()]
    pre_state.balances = [32_000_000_000]
    pre_state.deposit_requests_start_index = UNSET_VALUE

    state = MagicMock()
    state.pending_deposits = [pending_deposit]
    state.validators = [MagicMock()]
    state.balances = [32_000_000_000]
    state.deposit_requests_start_index = deposit_request.index
    state.slot = slot

    with patch("tests.infra.helpers.deposit_requests.is_post_gloas", return_value=False):
        assert_process_deposit_request(
            spec,
            state,
            pre_state,
            deposit_request=deposit_request,
        )


def test_assert_process_deposit_request_start_index_set():
    """Test that deposit_requests_start_index is set when UNSET (Electra/Fulu only)."""
    UNSET_VALUE = 2**64 - 1

    spec = MagicMock()
    spec.UNSET_DEPOSIT_REQUESTS_START_INDEX = UNSET_VALUE

    deposit_request = MagicMock()
    deposit_request.pubkey = b"\x01" * 48
    deposit_request.withdrawal_credentials = b"\x00" + b"\x01" * 31
    deposit_request.amount = 32_000_000_000
    deposit_request.signature = b"\x02" * 96
    deposit_request.index = 0

    slot = 100

    pending_deposit = MagicMock()
    pending_deposit.pubkey = deposit_request.pubkey
    pending_deposit.withdrawal_credentials = deposit_request.withdrawal_credentials
    pending_deposit.amount = deposit_request.amount
    pending_deposit.signature = deposit_request.signature
    pending_deposit.slot = slot

    pre_state = MagicMock()
    pre_state.pending_deposits = []
    pre_state.validators = [MagicMock()]
    pre_state.balances = [32_000_000_000]
    pre_state.deposit_requests_start_index = UNSET_VALUE

    state = MagicMock()
    state.pending_deposits = [pending_deposit]
    state.validators = [MagicMock()]
    state.balances = [32_000_000_000]
    state.deposit_requests_start_index = 0
    state.slot = slot

    with patch("tests.infra.helpers.deposit_requests.is_post_gloas", return_value=False):
        assert_process_deposit_request(
            spec,
            state,
            pre_state,
            deposit_request=deposit_request,
            expected_deposit_requests_start_index=0,
        )


def test_assert_process_deposit_request_start_index_unchanged():
    """Test that deposit_requests_start_index is NOT changed when already set (Electra/Fulu only)."""
    UNSET_VALUE = 2**64 - 1
    initial_start_index = 100

    spec = MagicMock()
    spec.UNSET_DEPOSIT_REQUESTS_START_INDEX = UNSET_VALUE

    deposit_request = MagicMock()
    deposit_request.pubkey = b"\x01" * 48
    deposit_request.withdrawal_credentials = b"\x00" + b"\x01" * 31
    deposit_request.amount = 32_000_000_000
    deposit_request.signature = b"\x02" * 96
    deposit_request.index = 0

    slot = 100

    pending_deposit = MagicMock()
    pending_deposit.pubkey = deposit_request.pubkey
    pending_deposit.withdrawal_credentials = deposit_request.withdrawal_credentials
    pending_deposit.amount = deposit_request.amount
    pending_deposit.signature = deposit_request.signature
    pending_deposit.slot = slot

    pre_state = MagicMock()
    pre_state.pending_deposits = []
    pre_state.validators = [MagicMock()]
    pre_state.balances = [32_000_000_000]
    pre_state.deposit_requests_start_index = initial_start_index

    state = MagicMock()
    state.pending_deposits = [pending_deposit]
    state.validators = [MagicMock()]
    state.balances = [32_000_000_000]
    state.deposit_requests_start_index = initial_start_index
    state.slot = slot

    with patch("tests.infra.helpers.deposit_requests.is_post_gloas", return_value=False):
        assert_process_deposit_request(
            spec,
            state,
            pre_state,
            deposit_request=deposit_request,
            expected_deposit_requests_start_index=initial_start_index,
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


def test_assert_new_builder_deposit():
    """Test assert_process_deposit_request passes for a new builder deposit."""
    spec = MagicMock()

    builder_pubkey = b"\x03" * 48
    deposit_request = MagicMock()
    deposit_request.pubkey = builder_pubkey
    deposit_request.withdrawal_credentials = b"\x03" + b"\x00" * 11 + b"\x59" * 20
    deposit_request.amount = 32_000_000_000
    deposit_request.signature = b"\x02" * 96
    deposit_request.index = 0

    # Pre state: no builders
    pre_state = MagicMock()
    pre_state.pending_deposits = []
    pre_state.validators = [MagicMock()]
    pre_state.balances = [32_000_000_000]
    pre_state.builders = []

    # Post state: one new builder with matching pubkey
    new_builder = MagicMock()
    new_builder.pubkey = builder_pubkey
    new_builder.balance = deposit_request.amount

    state = MagicMock()
    state.pending_deposits = []
    state.validators = [MagicMock()]
    state.balances = [32_000_000_000]
    state.builders = [new_builder]

    with patch("tests.infra.helpers.deposit_requests.is_post_gloas", return_value=True):
        assert_process_deposit_request(
            spec,
            state,
            pre_state,
            deposit_request=deposit_request,
            is_builder_deposit=True,
        )


@with_all_phases_from_to(ELECTRA, GLOAS)
@spec_state_test
def test_prepare_process_deposit_request_builder_credentials_before_gloas(spec, state):
    """Test prepare_process_deposit_request with builder credentials (0x03) before Gloas."""
    amount = spec.MIN_ACTIVATION_BALANCE

    # Builder withdrawal credentials (0x03 prefix) - no special meaning before Gloas
    withdrawal_credentials = b"\x03" + b"\x00" * 11 + b"\x59" * 20

    deposit_request = prepare_process_deposit_request(
        spec,
        state,
        amount=amount,
        signed=True,
        withdrawal_credentials=withdrawal_credentials,
    )

    # Should create a valid deposit request with the builder credentials preserved
    assert deposit_request.withdrawal_credentials == withdrawal_credentials
    assert deposit_request.amount == amount

    # Should use validator keys (not builder keys) since for_builder is False
    validator_index = len(state.validators)
    assert deposit_request.pubkey == pubkeys[validator_index]
