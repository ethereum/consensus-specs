from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with
from eth2spec.test.context import (
    spec_state_test,
    with_electra_and_later,
)

#  ***********************
#  * CONSOLIDATION TESTS *
#  ***********************


@with_electra_and_later
@spec_state_test
def test_basic_pending_consolidation(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    # append pending consolidation
    state.pending_consolidations.append(
        spec.PendingConsolidation(source_index=source_index, target_index=target_index)
    )
    # Set withdrawable epoch to current epoch to allow processing
    state.validators[source_index].withdrawable_epoch = current_epoch
    # Set the target withdrawal credential to eth1
    eth1_withdrawal_credential = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    )
    state.validators[target_index].withdrawal_credentials = eth1_withdrawal_credential

    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # Pending consolidation was successfully processed
    assert (
        state.validators[target_index].withdrawal_credentials[:1]
        == spec.COMPOUNDING_WITHDRAWAL_PREFIX
    )
    assert state.balances[target_index] == 2 * spec.MIN_ACTIVATION_BALANCE
    assert state.balances[source_index] == 0
    assert state.pending_consolidations == []


@with_electra_and_later
@spec_state_test
def test_consolidation_not_yet_withdrawable_validator(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    # append pending consolidation
    state.pending_consolidations.append(
        spec.PendingConsolidation(source_index=source_index, target_index=target_index)
    )
    # Set the target to eth1 withdrawal credentials
    eth1_withdrawal_credential = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    )
    state.validators[target_index].withdrawal_credentials = eth1_withdrawal_credential
    # Initiate exit of source validator
    spec.initiate_validator_exit(state, source_index)

    pre_pending_consolidations = state.pending_consolidations.copy()
    pre_balances = state.balances.copy()
    pre_target_withdrawal_credential = state.validators[
        target_index
    ].withdrawal_credentials[:1]

    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # Pending consolidation is not processed
    # Balances are unchanged
    assert state.balances[source_index] == pre_balances[0]
    assert state.balances[target_index] == pre_balances[1]
    # Target withdrawal credential is unchanged
    assert (
        state.validators[target_index].withdrawal_credentials[:1]
        == pre_target_withdrawal_credential
    )
    # Pending consolidation is still in the queue
    assert state.pending_consolidations == pre_pending_consolidations


@with_electra_and_later
@spec_state_test
def test_skip_consolidation_when_source_slashed(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source0_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target0_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source1_index = spec.get_active_validator_indices(state, current_epoch)[2]
    target1_index = spec.get_active_validator_indices(state, current_epoch)[3]
    # append pending consolidation
    state.pending_consolidations.append(
        spec.PendingConsolidation(
            source_index=source0_index, target_index=target0_index
        )
    )
    state.pending_consolidations.append(
        spec.PendingConsolidation(
            source_index=source1_index, target_index=target1_index
        )
    )

    eth1_withdrawal_credential = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    )
    state.validators[target0_index].withdrawal_credentials = eth1_withdrawal_credential
    state.validators[target1_index].withdrawal_credentials = eth1_withdrawal_credential

    # Set withdrawable epoch of sources to current epoch to allow processing
    state.validators[source0_index].withdrawable_epoch = spec.get_current_epoch(state)
    state.validators[source1_index].withdrawable_epoch = spec.get_current_epoch(state)

    # set first source as slashed
    state.validators[source0_index].slashed = True
    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # first pending consolidation should not be processed
    assert state.balances[target0_index] == spec.MIN_ACTIVATION_BALANCE
    assert state.balances[source0_index] == spec.MIN_ACTIVATION_BALANCE
    assert (
        state.validators[target0_index].withdrawal_credentials[:1]
        == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
    )
    # second pending consolidation should be processed: first one is skipped and doesn't block the queue
    assert state.balances[target1_index] == 2 * spec.MIN_ACTIVATION_BALANCE
    assert state.balances[source1_index] == 0
    assert (
        state.validators[target1_index].withdrawal_credentials[:1]
        == spec.COMPOUNDING_WITHDRAWAL_PREFIX
    )


@with_electra_and_later
@spec_state_test
def test_all_consolidation_cases_together(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_index = [
        spec.get_active_validator_indices(state, current_epoch)[i] for i in range(4)
    ]
    target_index = [
        spec.get_active_validator_indices(state, current_epoch)[4 + i] for i in range(4)
    ]
    state.pending_consolidations = [
        spec.PendingConsolidation(
            source_index=source_index[i], target_index=target_index[i]
        )
        for i in range(4)
    ]
    # Set withdrawable epoch to current epoch for first and last source validators
    for i in [0, 2]:
        state.validators[source_index[i]].withdrawable_epoch = current_epoch
    # Set second source validator as slashed
    state.validators[source_index[1]].slashed = True
    # Set targets withdrawal credentials to eth1
    eth1_withdrawal_credential = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    )
    for i in range(4):
        state.validators[target_index[i]].withdrawal_credentials = (
            eth1_withdrawal_credential
        )
    # Initiate exit of third source validator
    spec.initiate_validator_exit(state, 2)

    pre_balances = state.balances.copy()
    pre_target_withdrawal_prefixes = [
        state.validators[target_index[i]].withdrawal_credentials[:1]
        for i in [0, 1, 2, 3]
    ]
    pre_pending_consolidations = state.pending_consolidations.copy()
    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # First consolidation is successfully processed
    assert (
        state.validators[target_index[0]].withdrawal_credentials[:1]
        == spec.COMPOUNDING_WITHDRAWAL_PREFIX
    )
    assert state.balances[target_index[0]] == 2 * spec.MIN_ACTIVATION_BALANCE
    assert state.balances[source_index[0]] == 0
    # All other consolidations are not processed
    for i in [1, 2, 3]:
        assert (
            state.validators[target_index[i]].withdrawal_credentials[:1]
            == pre_target_withdrawal_prefixes[i]
        )
        assert state.balances[source_index[i]] == pre_balances[source_index[i]]
        assert state.balances[target_index[i]] == pre_balances[target_index[i]]
    # First consolidation is processed, second is skipped, last two are left in the queue
    state.pending_consolidations = pre_pending_consolidations[2:]
