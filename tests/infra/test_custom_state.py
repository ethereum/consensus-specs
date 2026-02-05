from eth2spec.phase0 import spec as phase0_spec
from eth2spec.test.helpers.typing import Spec, SpecForks
from tests.infra.context import with_custom_state


def test_custom_state_matrix():
    """
    Verifies with_custom_state with various inputs.
    Checks the expected balances.
    """
    test_cases = [
        # Case 1: Standard 32 ETH threshold
        {
            "give": 100 * 10**9,
            "threshold": 32 * 10**9,
            "expected_balance": 100 * 10**9,
        },
        # Case 2: Custom 16 ETH threshold
        {
            "give": 55 * 10**9,
            "threshold": 16 * 10**9,
            "expected_balance": 55 * 10**9,
        },
        # Case 3: Boundary Condition (Balance == Threshold)
        {
            "give": 32 * 10**9,
            "threshold": 32 * 10**9,
            "expected_balance": 32 * 10**9,
        },
    ]

    for i, case in enumerate(test_cases):
        # Prepare the helpers using lambda - turn the numbers to functions that the decorator expects
        balance_fn = lambda spec: [case["give"]]
        threshold_fn = lambda spec: case["threshold"]

        # Define the decorated function dynamically
        @with_custom_state(balances_fn=balance_fn, threshold_fn=threshold_fn)
        def check_state_logic(spec: Spec, phases: SpecForks, state, **kwargs):
            return state.balances[0]

        phases = {phase0_spec.fork: phase0_spec}
        result = check_state_logic(spec=phase0_spec, phases=phases)

        error_message = (
            f"Failed on case {i + 1}: Given {case['give']}, Expected {case['expected_balance']}"
        )
        assert result == case["expected_balance"], error_message
