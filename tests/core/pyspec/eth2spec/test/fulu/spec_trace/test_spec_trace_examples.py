"""
Example tests using the spec_trace decorator.

This demonstrates the automatic test vector generation system described in:
https://github.com/ethereum/consensus-specs/issues/4603
"""

import pytest

from eth2spec.test.context import (
    default_activation_threshold,
    single_phase,
    spec_test,
    with_custom_state,
    with_phases,
)
from eth2spec.test.helpers.spec_trace import spec_trace


@with_phases(["fulu"])
@spec_test
@with_custom_state(
    balances_fn=lambda spec: [spec.MAX_EFFECTIVE_BALANCE] * 64,
    threshold_fn=default_activation_threshold,
)
@single_phase
@spec_trace()
def test_simple_slot_processing_with_trace(spec, state):
    """
    Example test that processes a few slots.
    All spec calls are automatically traced.
    """
    # Get initial churn limit
    _ = spec.get_validator_activation_churn_limit(state)

    # Process some slots
    spec.process_slots(state, state.slot + 10)

    # Should automatically generate:
    # - load_state (first use of state)
    # - spec_call for get_validator_activation_churn_limit
    # - spec_call for process_slots
    # - assert_state (final state)


@with_phases(["fulu"])
@spec_test
@with_custom_state(
    balances_fn=lambda spec: [spec.MAX_EFFECTIVE_BALANCE] * 128,
    threshold_fn=default_activation_threshold,
)
@single_phase
@spec_trace()
def test_manual_state_modification_with_trace(spec, state):
    """
    Example showing manual state modification detection.
    When state is manually changed, a new load_state is generated.
    """
    # Call spec method
    _ = spec.get_validator_activation_churn_limit(state)

    # Process slots
    spec.process_slots(state, state.slot + 15)

    # Manually modify state (this should trigger assert + load)
    state.validators[0].effective_balance = 0

    # Continue processing
    spec.process_slot(state)
    spec.process_epoch(state)

    # Should automatically generate:
    # - load_state (initial state)
    # - spec_call for get_validator_activation_churn_limit
    # - spec_call for process_slots
    # - assert_state (before manual modification)
    # - load_state (after manual modification)
    # - spec_call for process_slot
    # - spec_call for process_epoch
    # - assert_state (final)


@with_phases(["fulu"])
@spec_test
@with_custom_state(
    balances_fn=lambda spec: [spec.MAX_EFFECTIVE_BALANCE] * 256,
    threshold_fn=default_activation_threshold,
)
@single_phase
@spec_trace()
def test_complex_scenario_with_trace(spec, state):
    """
    More complex test showing multiple operations.
    Demonstrates automatic handling of various spec calls.
    """
    # Multiple spec operations
    _ = spec.get_total_active_balance(state)
    _ = spec.get_base_reward(state, 0)

    # Advance to next epoch
    next_epoch_slot = (spec.get_current_epoch(state) + 1) * spec.SLOTS_PER_EPOCH
    spec.process_slots(state, next_epoch_slot)

    # Check epoch advanced
    assert spec.get_current_epoch(state) > 0, "Should have advanced to next epoch"

    # All calls traced automatically!


@with_phases(["fulu"])
@spec_test
@with_custom_state(
    balances_fn=lambda spec: [spec.MAX_EFFECTIVE_BALANCE] * 512,
    threshold_fn=default_activation_threshold,
)
@single_phase
def test_without_trace_decorator(spec, state):
    """
    Control test: same operations but WITHOUT @spec_trace.
    No trace files are generated.
    """
    _ = spec.get_validator_activation_churn_limit(state)
    spec.process_slots(state, state.slot + 10)

    # This test runs normally but doesn't generate trace vectors


# ============================================================================
# Manual proxy usage example (without decorator)
# ============================================================================


def example_manual_proxy_usage():
    """
    Example of using the proxy manually without the decorator.
    This is useful for more control over the tracing process.

    Note: This is a placeholder example showing the API. In real usage:
        from eth2spec.fulu import mainnet as spec
        from eth2spec.test.helpers.spec_trace import create_spec_proxy

        spec_proxy = create_spec_proxy(spec, fork_name='fulu', output_dir=Path('./custom_traces'))
        spec_proxy.process_slots(state, 10)
        spec_proxy.save_trace(Path('./custom_traces/my_test.yaml'))
    """
    pass  # Placeholder function demonstrating API


# ============================================================================
# Pytest configuration for trace tests
# ============================================================================


def pytest_configure(config):
    """Register custom markers for trace tests."""
    config.addinivalue_line("markers", "spec_trace: tests that generate automatic trace vectors")


if __name__ == "__main__":
    # Run tests with: pytest test_spec_trace_examples.py -v
    pytest.main([__file__, "-v"])
