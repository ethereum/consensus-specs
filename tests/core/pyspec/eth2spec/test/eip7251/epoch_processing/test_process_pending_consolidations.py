from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with
from eth2spec.test.context import (
    spec_state_test,
    with_eip7251_and_later,
)

#  ***********************
#  * CONSOLIDATION TESTS *
#  ***********************


@with_eip7251_and_later
@spec_state_test
def test_basic_pending_consolidation(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    # append pending consolidation
    state.pending_consolidations.append(spec.PendingConsolidation(source_index=source_index, target_index=target_index))
    # Set withdrawable epoch to current epoch to allow processing
    state.validators[source_index].withdrawable_epoch = spec.get_current_epoch(state)
    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    assert state.balances[target_index] == 2 * spec.MIN_ACTIVATION_BALANCE
    assert state.balances[source_index] == 0


@with_eip7251_and_later
@spec_state_test
def test_skip_consolidation_when_source_slashed(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source0_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target0_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source1_index = spec.get_active_validator_indices(state, current_epoch)[2]
    target1_index = spec.get_active_validator_indices(state, current_epoch)[3]
    # append pending consolidation
    state.pending_consolidations.append(
        spec.PendingConsolidation(source_index=source0_index, target_index=target0_index)
    )
    state.pending_consolidations.append(
        spec.PendingConsolidation(source_index=source1_index, target_index=target1_index)
    )

    # Set withdrawable epoch of sources to current epoch to allow processing
    state.validators[source0_index].withdrawable_epoch = spec.get_current_epoch(state)
    state.validators[source1_index].withdrawable_epoch = spec.get_current_epoch(state)

    # set first source as slashed
    state.validators[source0_index].slashed = True
    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # first pending consolidation should not be processed
    assert state.balances[target0_index] == spec.MIN_ACTIVATION_BALANCE
    assert state.balances[source0_index] == spec.MIN_ACTIVATION_BALANCE
    # second pending consolidation should be processed: first one is skipped and doesn't block the queue
    assert state.balances[target1_index] == 2 * spec.MIN_ACTIVATION_BALANCE
    assert state.balances[source1_index] == 0
