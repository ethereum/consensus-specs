from unittest.mock import MagicMock, patch

import pytest

from tests.infra.helpers.withdrawals import verify_withdrawals_post_state


class TestVerifyWithdrawalsPostState:
    """Test suite for verify_withdrawals_post_state function"""

    def test_basic_withdrawal_verification_success(self):
        """Test successful withdrawal verification with basic parameters"""
        # Mock spec
        spec = MagicMock()
        spec.MAX_WITHDRAWALS_PER_PAYLOAD = 16
        spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP = 16384

        # Mock states
        pre_state = MagicMock()
        pre_state.next_withdrawal_index = 100
        pre_state.next_withdrawal_validator_index = 50
        pre_state.validators = [MagicMock() for _ in range(1000)]

        post_state = MagicMock()
        post_state.next_withdrawal_index = 102
        # Calculate expected next_withdrawal_validator_index: (50 + 16384) % 1000 = 434
        post_state.next_withdrawal_validator_index = (50 + 16384) % 1000  # 434
        post_state.validators = pre_state.validators
        post_state.balances = [32 * 10**9] * 1000  # 32 ETH per validator

        # Mock execution payload
        execution_payload = MagicMock()
        withdrawal1 = MagicMock()
        withdrawal1.index = 100
        withdrawal1.validator_index = 50
        withdrawal1.amount = 1000000000
        withdrawal2 = MagicMock()
        withdrawal2.index = 101
        withdrawal2.validator_index = 51
        withdrawal2.amount = 2000000000
        execution_payload.withdrawals = [withdrawal1, withdrawal2]

        # Expected withdrawals
        expected_withdrawals = [withdrawal1, withdrawal2]

        # Mock the is_post_gloas to return False for simpler test
        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=False):
            with patch("tests.infra.helpers.withdrawals.get_expected_withdrawals", return_value=[]):
                # This should not raise any exceptions
                verify_withdrawals_post_state(
                    spec=spec,
                    pre_state=pre_state,
                    post_state=post_state,
                    execution_payload=execution_payload,
                    expected_withdrawals=expected_withdrawals,
                    fully_withdrawable_indices=None,
                    partial_withdrawals_indices=None,
                    pending_withdrawal_requests=None,
                )

    def test_post_gloas_parent_block_not_full(self):
        """Test post-gloas behavior when parent block is not full"""
        # Mock spec
        spec = MagicMock()
        spec.is_parent_block_full.return_value = False

        # Mock states with same withdrawal indices
        pre_state = MagicMock()
        pre_state.next_withdrawal_index = 100
        pre_state.next_withdrawal_validator_index = 50

        post_state = MagicMock()
        post_state.next_withdrawal_index = 100  # Should remain unchanged
        post_state.next_withdrawal_validator_index = 50  # Should remain unchanged

        # Mock execution payload and expected withdrawals
        execution_payload = MagicMock()
        expected_withdrawals = []

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            # This should not raise any exceptions
            verify_withdrawals_post_state(
                spec=spec,
                pre_state=pre_state,
                post_state=post_state,
                execution_payload=execution_payload,
                expected_withdrawals=expected_withdrawals,
                fully_withdrawable_indices=None,
                partial_withdrawals_indices=None,
                pending_withdrawal_requests=None,
            )

    def test_withdrawal_index_mismatch_raises_assertion(self):
        """Test that incorrect withdrawal indices cause assertion failure"""
        # Mock spec
        spec = MagicMock()
        spec.MAX_WITHDRAWALS_PER_PAYLOAD = 16
        spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP = 16384

        # Mock states
        pre_state = MagicMock()
        pre_state.next_withdrawal_index = 100
        pre_state.next_withdrawal_validator_index = 50
        pre_state.validators = [MagicMock() for _ in range(1000)]

        post_state = MagicMock()
        post_state.next_withdrawal_index = 105  # Wrong index - should be 102
        post_state.next_withdrawal_validator_index = 52
        post_state.validators = pre_state.validators

        # Mock execution payload
        execution_payload = MagicMock()
        withdrawal1 = MagicMock()
        withdrawal1.index = 100
        withdrawal1.validator_index = 50
        withdrawal2 = MagicMock()
        withdrawal2.index = 101
        withdrawal2.validator_index = 51
        execution_payload.withdrawals = [withdrawal1, withdrawal2]

        expected_withdrawals = [withdrawal1, withdrawal2]

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=False):
            with patch("tests.infra.helpers.withdrawals.get_expected_withdrawals", return_value=[]):
                with pytest.raises(AssertionError):
                    verify_withdrawals_post_state(
                        spec=spec,
                        pre_state=pre_state,
                        post_state=post_state,
                        execution_payload=execution_payload,
                        expected_withdrawals=expected_withdrawals,
                        fully_withdrawable_indices=None,
                        partial_withdrawals_indices=None,
                        pending_withdrawal_requests=None,
                    )

    def test_withdrawal_with_balance_verification(self):
        """Test withdrawal verification with balance checks for fully and partially withdrawable validators"""
        # Mock spec
        spec = MagicMock()
        spec.MAX_WITHDRAWALS_PER_PAYLOAD = 16
        spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP = 16384
        spec.MAX_EFFECTIVE_BALANCE = 32 * 10**9  # 32 ETH

        # Mock states
        pre_state = MagicMock()
        pre_state.next_withdrawal_index = 100
        pre_state.next_withdrawal_validator_index = 50
        pre_state.validators = [MagicMock() for _ in range(1000)]

        post_state = MagicMock()
        post_state.next_withdrawal_index = 102
        # Calculate expected next_withdrawal_validator_index: (50 + 16384) % 1000 = 434
        post_state.next_withdrawal_validator_index = (50 + 16384) % 1000  # 434
        post_state.validators = pre_state.validators
        # Set up balances: validator 50 fully withdrawn (0), validator 60 partially withdrawn (32 ETH)
        post_state.balances = [32 * 10**9] * 1000
        post_state.balances[50] = 0  # Fully withdrawn
        post_state.balances[60] = (
            32 * 10**9
        )  # Partial withdrawal brought down to max effective balance

        # Mock execution payload
        execution_payload = MagicMock()
        withdrawal1 = MagicMock()
        withdrawal1.index = 100
        withdrawal1.validator_index = 50  # This validator should have 0 balance
        withdrawal2 = MagicMock()
        withdrawal2.index = 101
        withdrawal2.validator_index = 60  # This validator should have max effective balance
        execution_payload.withdrawals = [withdrawal1, withdrawal2]

        expected_withdrawals = [withdrawal1, withdrawal2]
        fully_withdrawable_indices = [50]
        partial_withdrawals_indices = [60]

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=False):
            with patch("tests.infra.helpers.withdrawals.get_expected_withdrawals", return_value=[]):
                with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=False):
                    # This should not raise any exceptions
                    verify_withdrawals_post_state(
                        spec=spec,
                        pre_state=pre_state,
                        post_state=post_state,
                        execution_payload=execution_payload,
                        expected_withdrawals=expected_withdrawals,
                        fully_withdrawable_indices=fully_withdrawable_indices,
                        partial_withdrawals_indices=partial_withdrawals_indices,
                        pending_withdrawal_requests=None,
                    )
