from unittest.mock import MagicMock, patch

import pytest

from eth2spec.test.context import spec_state_test, with_all_phases
from tests.infra.helpers.proposer_slashings import (
    assert_process_proposer_slashing,
    prepare_process_proposer_slashing,
)


class TestPrepareProcessProposerSlashing:
    """Test suite for prepare_process_proposer_slashing function"""

    @with_all_phases
    @spec_state_test
    def test_returns_proposer_slashing_and_index(self, spec, state):
        """Test that function returns a ProposerSlashing and validator index"""
        result, proposer_index = prepare_process_proposer_slashing(
            spec, state, parent_root_2=b"\x99" * 32
        )

        # Verify return types
        assert result is not None
        assert isinstance(proposer_index, int)

        # Verify proposer_index matches header
        assert result.signed_header_1.message.proposer_index == proposer_index
        assert result.signed_header_2.message.proposer_index == proposer_index

    @with_all_phases
    @spec_state_test
    def test_headers_identical_by_default(self, spec, state):
        """Test that both headers are identical by default (invalid slashing)"""
        result, _ = prepare_process_proposer_slashing(spec, state)

        header_1 = result.signed_header_1.message
        header_2 = result.signed_header_2.message

        # Headers should be identical (makes slashing invalid)
        assert header_1.slot == header_2.slot
        assert header_1.proposer_index == header_2.proposer_index
        assert header_1.parent_root == header_2.parent_root
        assert header_1.state_root == header_2.state_root
        assert header_1.body_root == header_2.body_root

    @with_all_phases
    @spec_state_test
    def test_parent_root_2_makes_headers_different(self, spec, state):
        """Test that setting parent_root_2 creates different headers (valid slashing)"""
        result, _ = prepare_process_proposer_slashing(spec, state, parent_root_2=b"\x99" * 32)

        header_1 = result.signed_header_1.message
        header_2 = result.signed_header_2.message

        # Slots and proposer indices should match
        assert header_1.slot == header_2.slot
        assert header_1.proposer_index == header_2.proposer_index

        # Parent roots should differ
        assert header_1.parent_root != header_2.parent_root
        assert header_2.parent_root == b"\x99" * 32


class TestAssertProcessProposerSlashing:
    """Test suite for assert_process_proposer_slashing function"""

    def test_state_unchanged_passes_when_states_equal(self):
        """Test that state_unchanged=True passes when states are equal"""
        spec = MagicMock()
        state = MagicMock()
        pre_state = state  # Same object

        # Should not raise
        assert_process_proposer_slashing(spec, state, pre_state, state_unchanged=True)

    def test_state_unchanged_fails_when_states_differ(self):
        """Test that state_unchanged=True fails when states differ"""
        spec = MagicMock()
        state = MagicMock()
        pre_state = MagicMock()  # Different object

        with pytest.raises(AssertionError, match="Expected state to be unchanged"):
            assert_process_proposer_slashing(spec, state, pre_state, state_unchanged=True)

    def test_valid_slashing_passes_all_checks(self):
        """Test that properly configured mocks pass all check_proposer_slashing_effect checks"""
        # Constants
        slashed_index = 42
        proposer_index = 5
        current_epoch = 10
        effective_balance = 32_000_000_000
        pre_balance_slashed = 32_000_000_000
        pre_balance_proposer = 32_000_000_000
        slashings_index = current_epoch % 8192
        min_exit_epoch = current_epoch + 1
        min_withdrawability_delay = 256
        epochs_per_slashings_vector = 8192
        slash_penalty_quotient = 4096
        whistleblower_reward_quotient = 4096

        # Calculate expected values
        slash_penalty = effective_balance // slash_penalty_quotient
        whistleblower_reward = effective_balance // whistleblower_reward_quotient
        expected_withdrawable = max(
            min_exit_epoch + min_withdrawability_delay,
            current_epoch + epochs_per_slashings_vector,
        )

        # Mock spec
        spec = MagicMock()
        spec.get_current_epoch.return_value = current_epoch
        spec.FAR_FUTURE_EPOCH = 2**64 - 1
        spec.compute_activation_exit_epoch.return_value = min_exit_epoch
        spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY = min_withdrawability_delay
        spec.EPOCHS_PER_SLASHINGS_VECTOR = epochs_per_slashings_vector
        spec.get_beacon_proposer_index.return_value = proposer_index
        spec.MIN_SLASHING_PENALTY_QUOTIENT_ELECTRA = slash_penalty_quotient
        spec.WHISTLEBLOWER_REWARD_QUOTIENT_ELECTRA = whistleblower_reward_quotient

        # Mock pre_state validator
        pre_validator = MagicMock()
        pre_validator.exit_epoch = spec.FAR_FUTURE_EPOCH
        pre_validator.withdrawable_epoch = spec.FAR_FUTURE_EPOCH
        pre_validator.effective_balance = effective_balance

        # Mock post_state validator
        post_validator = MagicMock()
        post_validator.slashed = True
        post_validator.exit_epoch = min_exit_epoch
        post_validator.withdrawable_epoch = expected_withdrawable
        post_validator.effective_balance = effective_balance

        # Mock pre_state
        pre_state = MagicMock()
        pre_state.validators = {slashed_index: pre_validator}
        pre_state.balances = {
            slashed_index: pre_balance_slashed,
            proposer_index: pre_balance_proposer,
        }
        pre_state.slashings = {slashings_index: 0}

        # Mock post_state with correct values after slashing
        state = MagicMock()
        state.validators = {slashed_index: post_validator}
        state.balances = {
            slashed_index: pre_balance_slashed - slash_penalty,
            proposer_index: pre_balance_proposer + whistleblower_reward,
        }
        state.slashings = {slashings_index: effective_balance}

        # Mock proposer_slashing
        proposer_slashing = MagicMock()
        proposer_slashing.signed_header_1.message.proposer_index = slashed_index

        # Patch fork detection to return phase0/electra behavior (no altair sync committee, no gloas)
        with patch("eth2spec.test.helpers.proposer_slashings.is_post_altair", return_value=False):
            with patch(
                "eth2spec.test.helpers.proposer_slashings.is_post_electra", return_value=True
            ):
                with patch(
                    "eth2spec.test.helpers.proposer_slashings.is_post_gloas", return_value=False
                ):
                    # Should not raise - all invariants satisfied
                    assert_process_proposer_slashing(spec, state, pre_state, proposer_slashing)
