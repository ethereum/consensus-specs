from unittest.mock import MagicMock, patch

import pytest

from tests.infra.helpers.withdrawals import (
    assert_process_withdrawals_pre_gloas,
    prepare_process_withdrawals,
)


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
                assert_process_withdrawals_pre_gloas(
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
            assert_process_withdrawals_pre_gloas(
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
                    assert_process_withdrawals_pre_gloas(
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
                    assert_process_withdrawals_pre_gloas(
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
        spec.BuilderPendingWithdrawal = MagicMock(side_effect=lambda **kwargs: kwargs)

        # Mock state with builders registry (new model)
        state = MagicMock()
        state.builder_pending_withdrawals = []
        state.validators = [MagicMock() for _ in range(10)]

        # Create mock builders in registry
        builder0 = MagicMock()
        builder0.execution_address = b"\x42" * 20
        builder0.balance = 100_000_000_000
        builder1 = MagicMock()
        builder1.execution_address = b"\x43" * 20
        builder1.balance = 100_000_000_000
        state.builders = [builder0, builder1]

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                prepare_process_withdrawals(
                    spec,
                    state,
                    builder_indices=[0, 1],
                    builder_withdrawal_amounts={0: 1_000_000_000, 1: 2_000_000_000},
                )

        # Verify two builder pending withdrawals were added
        assert len(state.builder_pending_withdrawals) == 2
        assert state.builder_pending_withdrawals[0]["amount"] == 1_000_000_000
        assert state.builder_pending_withdrawals[0]["builder_index"] == 0
        assert state.builder_pending_withdrawals[0]["fee_recipient"] == b"\x42" * 20
        assert state.builder_pending_withdrawals[1]["amount"] == 2_000_000_000
        assert state.builder_pending_withdrawals[1]["builder_index"] == 1
        assert state.builder_pending_withdrawals[1]["fee_recipient"] == b"\x43" * 20

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
                prepare_process_withdrawals(
                    spec,
                    state,
                    pending_partial_indices=[2, 3],
                    pending_partial_amounts={2: 500_000_000, 3: 600_000_000},
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
                prepare_process_withdrawals(
                    spec,
                    state,
                    full_withdrawal_indices=[4, 5],
                    partial_withdrawal_indices=[6, 7],
                    partial_excess_balances={7: 2_000_000_000},
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
        """Test that insufficient balance for builder is allowed (spec caps withdrawal)"""
        # Mock spec
        spec = MagicMock()
        spec.MIN_ACTIVATION_BALANCE = 32_000_000_000
        spec.Gwei = int
        spec.get_current_epoch.return_value = 100
        spec.BuilderPendingWithdrawal = MagicMock(side_effect=lambda **kwargs: kwargs)

        # Mock state with insufficient balance in builder registry
        state = MagicMock()
        state.builder_pending_withdrawals = []
        state.validators = [MagicMock() for _ in range(10)]

        # Create mock builder with insufficient balance
        builder0 = MagicMock()
        builder0.execution_address = b"\x42" * 20
        builder0.balance = 1_000_000_000  # Insufficient balance
        state.builders = [builder0]

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                # Should NOT raise - balance assertion was removed
                # Spec handles capping withdrawal to available balance
                prepare_process_withdrawals(
                    spec,
                    state,
                    builder_indices=[0],
                    builder_withdrawal_amounts={0: 10_000_000_000},
                )

        # Verify withdrawal was added (amount may exceed balance, spec handles capping)
        assert len(state.builder_pending_withdrawals) == 1
        assert state.builder_pending_withdrawals[0]["amount"] == 10_000_000_000

    def test_prepare_withdrawals_with_future_epochs(self):
        """Test setting up withdrawals with future withdrawable epochs"""
        # Mock spec
        spec = MagicMock()
        spec.Gwei = int
        spec.get_current_epoch.return_value = 100
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
        spec.fork = "electra"  # Use electra (no builder withdrawable offsets)

        # Mock state
        state = MagicMock()
        state.pending_partial_withdrawals = []
        state.validators = [MagicMock() for _ in range(10)]
        state.balances = [100_000_000_000] * 10  # Plenty of balance

        # Set up validators with compounding credentials
        for v in state.validators:
            v.withdrawal_credentials = b"\x02" + b"\x00" * 31
            v.effective_balance = 0
            v.exit_epoch = spec.FAR_FUTURE_EPOCH
            v.withdrawable_epoch = spec.FAR_FUTURE_EPOCH

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=False):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                prepare_process_withdrawals(
                    spec,
                    state,
                    pending_partial_indices=[3, 4],
                    pending_partial_amounts={3: 500_000_000, 4: 600_000_000},
                    pending_partial_withdrawable_offsets={3: 2, 4: 7},  # +2 epochs, +7 epochs
                    full_withdrawal_indices=[5, 6],
                    full_withdrawable_offsets={5: 3, 6: 15},  # +3 epochs, +15 epochs
                )

        # Verify pending partial withdrawals with future epochs
        assert len(state.pending_partial_withdrawals) == 2
        assert state.pending_partial_withdrawals[0]["withdrawable_epoch"] == 102  # +2 epochs
        assert state.pending_partial_withdrawals[1]["withdrawable_epoch"] == 107  # +7 epochs

        # Verify full withdrawals with future epochs
        assert state.validators[5].withdrawable_epoch == 103  # +3 epochs
        assert state.validators[6].withdrawable_epoch == 115  # +15 epochs

    def test_prepare_withdrawals_parent_block_full_default(self):
        """Test that parent_block_full=True (default) sets parent block as full"""
        spec = MagicMock()
        spec.Gwei = int
        spec.get_current_epoch.return_value = 100

        state = MagicMock()
        state.latest_block_hash = b"\x00" * 32
        state.latest_execution_payload_bid = MagicMock()
        state.latest_execution_payload_bid.block_hash = b"\x00" * 32

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                prepare_process_withdrawals(spec, state)

        # Both hashes should match and be non-zero (parent block full)
        assert state.latest_block_hash == state.latest_execution_payload_bid.block_hash
        assert state.latest_block_hash != b"\x00" * 32

    def test_prepare_withdrawals_parent_block_empty(self):
        """Test that parent_block_empty=True sets parent block as empty"""
        spec = MagicMock()
        spec.Gwei = int
        spec.get_current_epoch.return_value = 100

        state = MagicMock()
        state.latest_block_hash = b"\x01" * 32
        state.latest_execution_payload_bid = MagicMock()
        state.latest_execution_payload_bid.block_hash = b"\x01" * 32

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                prepare_process_withdrawals(spec, state, parent_block_empty=True)

        # latest_block_hash should be zeros, bid.block_hash should be non-zero (mismatch = empty)
        assert state.latest_block_hash == b"\x00" * 32
        assert state.latest_execution_payload_bid.block_hash == b"\x01" * 32
        assert state.latest_block_hash != state.latest_execution_payload_bid.block_hash

    def test_prepare_builder_balances(self):
        """Test that builder_balances parameter sets builder balances correctly"""
        spec = MagicMock()
        spec.MIN_ACTIVATION_BALANCE = 32_000_000_000
        spec.Gwei = int
        spec.get_current_epoch.return_value = 100
        spec.BuilderPendingWithdrawal = MagicMock(side_effect=lambda **kwargs: kwargs)

        state = MagicMock()
        state.builder_pending_withdrawals = []
        state.validators = [MagicMock() for _ in range(10)]

        # Create mock builders
        builder0 = MagicMock()
        builder0.execution_address = b"\x42" * 20
        builder0.balance = 0  # Initial balance
        builder1 = MagicMock()
        builder1.execution_address = b"\x43" * 20
        builder1.balance = 0  # Initial balance
        state.builders = [builder0, builder1]

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                prepare_process_withdrawals(
                    spec,
                    state,
                    builder_indices=[0, 1],
                    builder_withdrawal_amounts={0: 1_000_000_000, 1: 2_000_000_000},
                    builder_balances={0: 50_000_000_000, 1: 100_000_000_000},
                )

        # Verify builder balances were set
        assert builder0.balance == 50_000_000_000
        assert builder1.balance == 100_000_000_000

    def test_prepare_builder_execution_addresses(self):
        """Test that builder_execution_addresses parameter sets addresses correctly"""
        spec = MagicMock()
        spec.MIN_ACTIVATION_BALANCE = 32_000_000_000
        spec.Gwei = int
        spec.get_current_epoch.return_value = 100
        spec.BuilderPendingWithdrawal = MagicMock(side_effect=lambda **kwargs: kwargs)
        spec.ExecutionAddress = lambda x: x  # Pass through for mock

        state = MagicMock()
        state.builder_pending_withdrawals = []
        state.validators = [MagicMock() for _ in range(10)]

        # Create mock builder
        builder0 = MagicMock()
        builder0.execution_address = b"\x00" * 20  # Initial address
        builder0.balance = 100_000_000_000
        state.builders = [builder0]

        custom_address = b"\xab" * 20

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                prepare_process_withdrawals(
                    spec,
                    state,
                    builder_indices=[0],
                    builder_withdrawal_amounts={0: 1_000_000_000},
                    builder_execution_addresses={0: custom_address},
                )

        # Verify execution address was set
        assert builder0.execution_address == custom_address
        # Verify the pending withdrawal uses the custom address
        assert state.builder_pending_withdrawals[0]["fee_recipient"] == custom_address

    def test_prepare_validator_balances(self):
        """Test that validator_balances parameter sets balances correctly"""
        spec = MagicMock()
        spec.Gwei = int
        spec.get_current_epoch.return_value = 100

        state = MagicMock()
        state.balances = [0] * 10
        state.validators = [MagicMock() for _ in range(10)]

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                prepare_process_withdrawals(
                    spec,
                    state,
                    validator_balances={2: 50_000_000_000, 5: 100_000_000_000},
                )

        assert state.balances[2] == 50_000_000_000
        assert state.balances[5] == 100_000_000_000
        assert state.balances[0] == 0  # Unchanged

    def test_prepare_validator_effective_balances(self):
        """Test that validator_effective_balances parameter sets effective balances"""
        spec = MagicMock()
        spec.Gwei = int
        spec.get_current_epoch.return_value = 100

        state = MagicMock()
        state.validators = [MagicMock() for _ in range(10)]
        for v in state.validators:
            v.effective_balance = 0

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                prepare_process_withdrawals(
                    spec,
                    state,
                    validator_effective_balances={3: 32_000_000_000, 7: 16_000_000_000},
                )

        assert state.validators[3].effective_balance == 32_000_000_000
        assert state.validators[7].effective_balance == 16_000_000_000
        assert state.validators[0].effective_balance == 0  # Unchanged

    def test_prepare_validator_activation_epoch_offsets(self):
        """Test that validator_activation_epoch_offsets sets activation_epoch correctly"""
        spec = MagicMock()
        spec.Gwei = int
        spec.get_current_epoch.return_value = 100

        state = MagicMock()
        state.validators = [MagicMock() for _ in range(10)]
        for v in state.validators:
            v.activation_epoch = 0

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                prepare_process_withdrawals(
                    spec,
                    state,
                    validator_activation_epoch_offsets={2: 5, 4: 10},
                )

        # activation_epoch should be current_epoch + offset
        assert state.validators[2].activation_epoch == 105  # 100 + 5
        assert state.validators[4].activation_epoch == 110  # 100 + 10
        assert state.validators[0].activation_epoch == 0  # Unchanged

    def test_prepare_validator_exit_epoch_offsets(self):
        """Test that validator_exit_epoch_offsets sets exit_epoch correctly"""
        spec = MagicMock()
        spec.Gwei = int
        spec.get_current_epoch.return_value = 100

        state = MagicMock()
        state.validators = [MagicMock() for _ in range(10)]
        for v in state.validators:
            v.exit_epoch = 2**64 - 1  # FAR_FUTURE_EPOCH

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                prepare_process_withdrawals(
                    spec,
                    state,
                    validator_exit_epoch_offsets={1: 1, 3: 5},
                )

        # exit_epoch should be current_epoch + offset
        assert state.validators[1].exit_epoch == 101  # 100 + 1
        assert state.validators[3].exit_epoch == 105  # 100 + 5
        assert state.validators[0].exit_epoch == 2**64 - 1  # Unchanged

    def test_prepare_next_withdrawal_validator_index(self):
        """Test that next_withdrawal_validator_index parameter sets the index"""
        spec = MagicMock()
        spec.Gwei = int
        spec.get_current_epoch.return_value = 100

        state = MagicMock()
        state.next_withdrawal_validator_index = 0

        with patch("tests.infra.helpers.withdrawals.is_post_gloas", return_value=True):
            with patch("tests.infra.helpers.withdrawals.is_post_electra", return_value=True):
                prepare_process_withdrawals(
                    spec,
                    state,
                    next_withdrawal_validator_index=42,
                )

        assert state.next_withdrawal_validator_index == 42
