"""
Example tests for slot processing and builder payments for testing spec tracing.
"""

from eth2spec.test.context import (
    spec_state_test,
    with_all_phases,
    with_gloas_and_later,
)
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with
from eth2spec.test.helpers.state import next_epoch
from tests.infra.trace import spec_trace


@with_all_phases
@spec_state_test
@spec_trace
def test_linear_sanity_slots_222(spec, state):
    """
    Run a sanity test checking that `process_slot` works.
    This demonstrates the simplest possible state transition.
    """
    # Advance the state by one slot
    # We must re-assign the `state` variable, as `process_slot`
    # is a pure function that returns a new, modified state.
    spec.process_slot(state)


def create_builder_pending_payment(spec, builder_index, amount, weight=0, fee_recipient=None):
    """Create a BuilderPendingPayment for testing."""
    if fee_recipient is None:
        fee_recipient = spec.ExecutionAddress()

    return spec.BuilderPendingPayment(
        weight=weight,
        withdrawal=spec.BuilderPendingWithdrawal(
            fee_recipient=fee_recipient,
            amount=amount,
            builder_index=builder_index,
            withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
        ),
    )


@with_gloas_and_later
@spec_state_test
@spec_trace
def test_builder_333(spec, state):
    """Testing different types of inputs and outputs."""
    # this is from builder payments test
    # Advance past genesis epochs
    next_epoch(spec, state)
    next_epoch(spec, state)

    # this has enough state mutations within and without the spec
    # Populate the first SLOTS_PER_EPOCH with payments to ensure they're not empty
    for i in range(spec.SLOTS_PER_EPOCH):
        payment = create_builder_pending_payment(spec, i, spec.MIN_ACTIVATION_BALANCE, 1)
        state.builder_pending_payments[i] = payment

    for _ in run_epoch_processing_with(spec, state, "process_builder_pending_payments"):
        pass
    # this is just to get weird enough inputs and outputs
    epoch = spec.get_current_epoch(state)
    spec.get_seed(state, epoch, spec.DOMAIN_BEACON_PROPOSER)
