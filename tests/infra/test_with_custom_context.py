import pytest

from eth2spec.test.context import (
    with_custom_state,
    default_activation_threshold,
    default_balances,
    zero_activation_threshold,
)
from eth2spec.test.helpers.constants import MINIMAL, PHASE0
from eth2spec.test.helpers.specs import spec_targets


class TestWithCustomState:
    """Test suite for with_custom_state decorator."""

    def test_with_custom_state_injects_state_view(self):
        """Test that the decorator injects a BeaconState with expected properties."""
        spec = spec_targets[MINIMAL][PHASE0]

        @with_custom_state(default_balances, default_activation_threshold)
        def test_case(*, spec, phases, state):
            # Verify the state is properly initialized
            assert len(state.validators) > 0
            assert len(state.balances) > 0
            # Verify balances match default_balances (MAX_EFFECTIVE_BALANCE)
            assert all(b == spec.MAX_EFFECTIVE_BALANCE for b in state.balances)
            # Verify validators are activated (balance >= threshold)
            assert all(v.activation_epoch == spec.GENESIS_EPOCH for v in state.validators)
            return state

        state = test_case(spec=spec, phases={})
        assert state is not None
        # Verify state properties outside the decorated function
        assert len(state.validators) == spec.SLOTS_PER_EPOCH * 8
        assert state.fork.current_version == spec.config.GENESIS_FORK_VERSION

    def test_with_custom_state_custom_balances(self):
        """Test that custom balances are applied to the state."""
        spec = spec_targets[MINIMAL][PHASE0]
        custom_balance = spec.MAX_EFFECTIVE_BALANCE * 2

        def custom_balances(spec):
            return [custom_balance] * 4  # 4 validators

        @with_custom_state(custom_balances, default_activation_threshold)
        def test_case(*, spec, phases, state):
            return state

        state = test_case(spec=spec, phases={})
        assert len(state.balances) == 4
        assert all(balance == custom_balance for balance in state.balances)

    def test_with_custom_state_custom_activation_threshold(self):
        """Test that custom activation threshold is applied."""
        spec = spec_targets[MINIMAL][PHASE0]

        # Case 1: Low threshold -> Validators should be active
        low_threshold = 100

        def low_threshold_fn(spec):
            return low_threshold

        @with_custom_state(default_balances, low_threshold_fn)
        def test_case_active(*, spec, phases, state):
            # The activation threshold is low, so validators should be active
            assert all(v.activation_epoch == spec.GENESIS_EPOCH for v in state.validators)
            return state

        state_active = test_case_active(spec=spec, phases={})
        assert state_active is not None

        # Case 2: High threshold -> Validators should NOT be active
        # Set threshold higher than default balance (MAX_EFFECTIVE_BALANCE)
        high_threshold = spec.MAX_EFFECTIVE_BALANCE + 1

        def high_threshold_fn(spec):
            return high_threshold

        @with_custom_state(default_balances, high_threshold_fn)
        def test_case_inactive(*, spec, phases, state):
            # The activation threshold is high, so validators should NOT be active
            assert all(v.activation_epoch == spec.FAR_FUTURE_EPOCH for v in state.validators)
            return state

        state_inactive = test_case_inactive(spec=spec, phases={})
        assert state_inactive is not None

    def test_with_custom_state_with_phases(self):
        """
        Test that the decorator works with phases parameter.

        The decorator wraps the test function and must ensure that arguments
        provided by the test runner (like 'phases') are correctly passed through
        to the inner function.
        """
        spec = spec_targets[MINIMAL][PHASE0]
        phases = {"phase0": spec}

        @with_custom_state(default_balances, default_activation_threshold)
        def test_case(*, spec, phases, state):
            assert phases is not None
            assert "phase0" in phases
            return state

        state = test_case(spec=spec, phases=phases)
        assert state is not None

    def test_with_custom_state_multiple_calls(self):
        """Test that multiple decorated functions work independently."""
        spec = spec_targets[MINIMAL][PHASE0]

        balance1 = spec.MAX_EFFECTIVE_BALANCE
        balance2 = spec.MAX_EFFECTIVE_BALANCE * 2

        @with_custom_state(lambda _: [balance1], default_activation_threshold)
        def test_case1(*, spec, phases, state):
            return state.balances[0]

        @with_custom_state(lambda _: [balance2], default_activation_threshold)
        def test_case2(*, spec, phases, state):
            return state.balances[0]

        assert test_case1(spec=spec, phases={}) == balance1
        assert test_case2(spec=spec, phases={}) == balance2
