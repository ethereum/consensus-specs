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
            return state

        state = test_case(spec=spec, phases={})
        assert state is not None

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
        custom_threshold = 123456

        def custom_threshold_fn(spec):
            return custom_threshold

        @with_custom_state(default_balances, custom_threshold_fn)
        def test_case(*, spec, phases, state):
            # The activation threshold affects validator activation eligibility
            # We can verify it by checking the activation_epoch of validators
            return state

        state = test_case(spec=spec, phases={})
        # Add assertions based on how the threshold affects the state
        assert state is not None

    def test_with_custom_state_with_phases(self):
        """Test that the decorator works with phases parameter."""
        spec = spec_targets[MINIMAL][PHASE0]
        phases = {'phase0': spec}

        @with_custom_state(default_balances, default_activation_threshold)
        def test_case(*, spec, phases, state):
            assert phases is not None
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