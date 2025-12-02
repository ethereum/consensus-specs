"""
This file is a port of the `test_sanity_slots` test to the new
linear, non-yield-based tracing system.
It serves as the simplest "hello world" for the new framework.
"""

from eth2spec.test.context import (
    spec_state_test,
    with_all_phases,
)
from tests.infra.trace import spec_trace


@with_all_phases
@spec_state_test
@spec_trace
def test_linear_sanity_slots(spec, state):
    """
    Run a sanity test checking that `process_slot` works.
    This demonstrates the simplest possible state transition.
    """
    # Advance the state by one slot
    # We must re-assign the `state` variable, as `process_slot`
    # is a pure function that returns a new, modified state.
    spec.process_slot(state)
