from unittest.mock import MagicMock, patch

import pytest

from tests.infra.helpers.withdrawals import prepare_withdrawals, verify_withdrawals_post_state


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


class TestPrepareWithdrawals:
    """Test suite for prepare_withdrawals function"""

    def test_prepare_builder_withdrawals(self):
        """Test setting up builder pending withdrawals"""
        # Mock spec
        spec = MagicMock()
        spec.MIN_ACTIVATION_BALANCE = 32_000_000_000
        spec.Gwei = int
        spec.get_current_epoch.return_value = 100
        spec.fork = "gloas"
        spec.has_builder_withdrawal_credential.return_value = True
        spec.BuilderPendingWithdrawal = MagicMock(side_effect=lambda **kwargs: kwargs)

        # Mock state
        state = MagicMock()
        state.builder_pending_withdrawals = []
        state.validators = [MagicMock() for _ in range(10)]
        state.validators[0].withdrawal_credentials = b"\x03" + b"\x00" * 11 + b"\x42" * 20
        state.validators[1].withdrawal_credentials = b"\x03" + b"\x00" * 11 + b"\x43" * 20
        state.balances = [100_000_000_000] * 10  # Plenty of balance

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                prepare_withdrawals(
                    spec,
                    state,
                    builder_indices=[0, 1],
                    builder_withdrawal_amounts=[1_000_000_000, 2_000_000_000],
                )

        # Verify two builder pending withdrawals were added
        assert len(state.builder_pending_withdrawals) == 2
        assert state.builder_pending_withdrawals[0]["amount"] == 1_000_000_000
        assert state.builder_pending_withdrawals[0]["builder_index"] == 0
        assert state.builder_pending_withdrawals[1]["amount"] == 2_000_000_000
        assert state.builder_pending_withdrawals[1]["builder_index"] == 1

    def test_prepare_pending_partial_withdrawals(self):
        """Test setting up pending partial withdrawals"""
        # Mock spec
        spec = MagicMock()
        spec.Gwei = int
        spec.fork = "electra"
        spec.get_current_epoch.return_value = 100
        spec.COMPOUNDING_WITHDRAWAL_PREFIX = b"\x02"
        spec.MAX_EFFECTIVE_BALANCE_ELECTRA = 2048_000_000_000
        spec.EFFECTIVE_BALANCE_INCREMENT = 1_000_000_000
        spec.has_compounding_withdrawal_credential.return_value = True
        spec.PendingPartialWithdrawal = MagicMock(side_effect=lambda **kwargs: kwargs)

        # Mock state
        state = MagicMock()
        state.pending_partial_withdrawals = []
        state.validators = [MagicMock() for _ in range(10)]
        state.balances = [0] * 10

        # Mock validators with compounding credentials
        for v in state.validators:
            v.withdrawal_credentials = b"\x02" + b"\x00" * 31
            v.effective_balance = 0

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=False):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                prepare_withdrawals(
                    spec,
                    state,
                    pending_partial_indices=[2, 3],
                    pending_partial_amounts=[500_000_000, 600_000_000],
                )

        # Verify two pending partial withdrawals were added to state
        assert len(state.pending_partial_withdrawals) == 2

        # Verify withdrawal details
        assert state.pending_partial_withdrawals[0]["validator_index"] == 2
        assert state.pending_partial_withdrawals[0]["amount"] == 500_000_000
        assert state.pending_partial_withdrawals[0]["withdrawable_epoch"] == 100

        assert state.pending_partial_withdrawals[1]["validator_index"] == 3
        assert state.pending_partial_withdrawals[1]["amount"] == 600_000_000
        assert state.pending_partial_withdrawals[1]["withdrawable_epoch"] == 100

        # Verify validator balances were set correctly
        assert state.balances[2] == 32_000_000_000 + 500_000_000  # effective_balance + amount
        assert state.balances[3] == 32_000_000_000 + 600_000_000

    def test_prepare_full_and_partial_withdrawals(self):
        """Test setting up full and partial withdrawals"""
        # Mock spec
        spec = MagicMock()
        spec.Gwei = int
        spec.fork = "capella"
        spec.get_current_epoch.return_value = 100
        spec.BLS_WITHDRAWAL_PREFIX = b"\x00"
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX = b"\x01"
        spec.MAX_EFFECTIVE_BALANCE = 32_000_000_000
        spec.EFFECTIVE_BALANCE_INCREMENT = 1_000_000_000
        spec.FAR_FUTURE_EPOCH = 2**64 - 1
        spec.is_fully_withdrawable_validator.return_value = True
        spec.is_partially_withdrawable_validator.return_value = True
        spec.has_compounding_withdrawal_credential.return_value = False

        # Mock state
        state = MagicMock()
        state.validators = [MagicMock() for _ in range(10)]
        state.balances = [0] * 10

        # Set up validators with BLS credentials (will be converted to ETH1)
        for v in state.validators:
            v.withdrawal_credentials = b"\x00" + b"\x00" * 31
            v.effective_balance = 0
            v.exit_epoch = spec.FAR_FUTURE_EPOCH
            v.withdrawable_epoch = spec.FAR_FUTURE_EPOCH

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=False):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=False):
                prepare_withdrawals(
                    spec,
                    state,
                    full_withdrawal_indices=[4, 5],
                    partial_withdrawal_indices=[6, 7],
                    partial_excess_balances=[1_000_000_000, 2_000_000_000],
                )

        # Verify full withdrawals: validators should be withdrawable
        assert state.validators[4].withdrawable_epoch == 100
        assert state.validators[4].exit_epoch <= 100
        assert state.validators[4].withdrawal_credentials[0:1] == b"\x01"  # ETH1 prefix
        assert state.balances[4] == 10_000_000_000  # Default balance set

        assert state.validators[5].withdrawable_epoch == 100
        assert state.validators[5].exit_epoch <= 100
        assert state.validators[5].withdrawal_credentials[0:1] == b"\x01"
        assert state.balances[5] == 10_000_000_000

        # Verify partial withdrawals: validators should have excess balance
        assert state.validators[6].withdrawal_credentials[0:1] == b"\x01"  # ETH1 prefix
        assert state.balances[6] == spec.MAX_EFFECTIVE_BALANCE + 1_000_000_000
        assert state.validators[6].effective_balance == spec.MAX_EFFECTIVE_BALANCE

        assert state.validators[7].withdrawal_credentials[0:1] == b"\x01"
        assert state.balances[7] == spec.MAX_EFFECTIVE_BALANCE + 2_000_000_000
        assert state.validators[7].effective_balance == spec.MAX_EFFECTIVE_BALANCE

    def test_prepare_withdrawals_builder_insufficient_balance(self):
        """Test that insufficient balance for builder raises assertion"""
        # Mock spec
        spec = MagicMock()
        spec.MIN_ACTIVATION_BALANCE = 32_000_000_000
        spec.Gwei = int
        spec.get_current_epoch.return_value = 100
        spec.has_builder_withdrawal_credential.return_value = True

        # Mock state with insufficient balance
        state = MagicMock()
        state.builder_pending_withdrawals = []
        state.validators = [MagicMock() for _ in range(10)]
        state.validators[0].withdrawal_credentials = b"\x03" + b"\x00" * 11 + b"\x42" * 20
        state.balances = [1_000_000_000] * 10  # Insufficient balance

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            with pytest.raises(AssertionError, match="needs balance"):
                prepare_withdrawals(
                    spec,
                    state,
                    builder_indices=[0],
                    builder_withdrawal_amounts=[10_000_000_000],
                )

    def test_prepare_withdrawals_with_future_epochs(self):
        """Test setting up withdrawals with future withdrawable epochs"""
        # Mock spec
        spec = MagicMock()
        spec.MIN_ACTIVATION_BALANCE = 32_000_000_000
        spec.Gwei = int
        spec.get_current_epoch.return_value = 100
        spec.has_builder_withdrawal_credential.return_value = True
        spec.BuilderPendingWithdrawal = MagicMock(side_effect=lambda **kwargs: kwargs)
        spec.BLS_WITHDRAWAL_PREFIX = b"\x00"
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX = b"\x01"
        spec.MAX_EFFECTIVE_BALANCE = 32_000_000_000
        spec.EFFECTIVE_BALANCE_INCREMENT = 1_000_000_000
        spec.FAR_FUTURE_EPOCH = 2**64 - 1
        spec.COMPOUNDING_WITHDRAWAL_PREFIX = b"\x02"
        spec.MAX_EFFECTIVE_BALANCE_ELECTRA = 2048_000_000_000
        spec.has_compounding_withdrawal_credential.return_value = True
        spec.PendingPartialWithdrawal = MagicMock(side_effect=lambda **kwargs: kwargs)
        spec.is_fully_withdrawable_validator.return_value = True
        spec.fork = "gloas"  # Set the fork to gloas

        # Mock state
        state = MagicMock()
        state.builder_pending_withdrawals = []
        state.pending_partial_withdrawals = []
        state.validators = [MagicMock() for _ in range(10)]
        state.balances = [100_000_000_000] * 10  # Plenty of balance

        # Set up validators with appropriate credentials
        for i, v in enumerate(state.validators):
            if i < 3:  # First 3 for builder withdrawals
                v.withdrawal_credentials = b"\x03" + b"\x00" * 11 + bytes([0x42 + i]) + b"\x00" * 19
            else:  # Others for partial withdrawals
                v.withdrawal_credentials = b"\x02" + b"\x00" * 31
                v.effective_balance = 0
            v.exit_epoch = spec.FAR_FUTURE_EPOCH
            v.withdrawable_epoch = spec.FAR_FUTURE_EPOCH

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                prepare_withdrawals(
                    spec,
                    state,
                    builder_indices=[0, 1, 2],
                    builder_withdrawal_amounts=[1_000_000_000, 2_000_000_000, 3_000_000_000],
                    builder_withdrawable_offsets=[0, 5, 10],  # Current, +5 epochs, +10 epochs
                    pending_partial_indices=[3, 4],
                    pending_partial_amounts=[500_000_000, 600_000_000],
                    pending_partial_withdrawable_offsets=[2, 7],  # +2 epochs, +7 epochs
                    full_withdrawal_indices=[5, 6],
                    full_withdrawable_offsets=[3, 15],  # +3 epochs, +15 epochs
                )

        # Verify builder pending withdrawals with future epochs
        assert len(state.builder_pending_withdrawals) == 3
        assert state.builder_pending_withdrawals[0]["withdrawable_epoch"] == 100  # Current epoch
        assert state.builder_pending_withdrawals[1]["withdrawable_epoch"] == 105  # +5 epochs
        assert state.builder_pending_withdrawals[2]["withdrawable_epoch"] == 110  # +10 epochs

        # Verify pending partial withdrawals with future epochs
        assert len(state.pending_partial_withdrawals) == 2
        assert state.pending_partial_withdrawals[0]["withdrawable_epoch"] == 102  # +2 epochs
        assert state.pending_partial_withdrawals[1]["withdrawable_epoch"] == 107  # +7 epochs

        # Verify full withdrawals with future epochs
        assert state.validators[5].withdrawable_epoch == 103  # +3 epochs
        assert state.validators[6].withdrawable_epoch == 115  # +15 epochs
