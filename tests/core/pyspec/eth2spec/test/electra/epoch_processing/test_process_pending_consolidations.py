from eth2spec.test.helpers.epoch_processing import (
    run_epoch_processing_with,
    run_epoch_processing_to,
)
from eth2spec.test.context import (
    spec_state_test,
    with_electra_and_later,
)
from eth2spec.test.helpers.state import (
    next_epoch_with_full_participation,
)
from eth2spec.test.helpers.withdrawals import (
    set_eth1_withdrawal_credential_with_balance,
    set_compounding_withdrawal_credential_with_balance,
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
    eth1_withdrawal_credential = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    state.validators[target_index].withdrawal_credentials = eth1_withdrawal_credential

    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # Pending consolidation was successfully processed
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
    eth1_withdrawal_credential = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    state.validators[target_index].withdrawal_credentials = eth1_withdrawal_credential
    # Initiate exit of source validator
    spec.initiate_validator_exit(state, source_index)

    pre_pending_consolidations = state.pending_consolidations.copy()
    pre_balances = state.balances.copy()

    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # Pending consolidation is not processed
    # Balances are unchanged
    assert state.balances[source_index] == pre_balances[0]
    assert state.balances[target_index] == pre_balances[1]
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
        spec.PendingConsolidation(source_index=source0_index, target_index=target0_index)
    )
    state.pending_consolidations.append(
        spec.PendingConsolidation(source_index=source1_index, target_index=target1_index)
    )

    eth1_withdrawal_credential = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
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
    # second pending consolidation should be processed: first one is skipped and doesn't block the queue
    assert state.balances[target1_index] == 2 * spec.MIN_ACTIVATION_BALANCE
    assert state.balances[source1_index] == 0


@with_electra_and_later
@spec_state_test
def test_all_consolidation_cases_together(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_index = [spec.get_active_validator_indices(state, current_epoch)[i] for i in range(4)]
    target_index = [
        spec.get_active_validator_indices(state, current_epoch)[4 + i] for i in range(4)
    ]
    state.pending_consolidations = [
        spec.PendingConsolidation(source_index=source_index[i], target_index=target_index[i])
        for i in range(4)
    ]
    # Set withdrawable epoch to current epoch for first and last source validators
    for i in [0, 2]:
        state.validators[source_index[i]].withdrawable_epoch = current_epoch
    # Set second source validator as slashed
    state.validators[source_index[1]].slashed = True
    # Set targets withdrawal credentials to eth1
    eth1_withdrawal_credential = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    for i in range(4):
        state.validators[target_index[i]].withdrawal_credentials = eth1_withdrawal_credential
    # Initiate exit of third source validator
    spec.initiate_validator_exit(state, 2)

    pre_balances = state.balances.copy()
    pre_pending_consolidations = state.pending_consolidations.copy()
    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # First consolidation is successfully processed
    assert state.balances[target_index[0]] == 2 * spec.MIN_ACTIVATION_BALANCE
    assert state.balances[source_index[0]] == 0
    # All other consolidations are not processed
    for i in [1, 2, 3]:
        assert state.balances[source_index[i]] == pre_balances[source_index[i]]
        assert state.balances[target_index[i]] == pre_balances[target_index[i]]
    # First consolidation is processed, second is skipped, last two are left in the queue
    state.pending_consolidations = pre_pending_consolidations[2:]


@with_electra_and_later
@spec_state_test
def test_pending_consolidation_future_epoch(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    # initiate source exit
    spec.initiate_validator_exit(state, source_index)
    # set withdrawable_epoch to exit_epoch + 1
    state.validators[source_index].withdrawable_epoch = state.validators[
        source_index
    ].exit_epoch + spec.Epoch(1)
    # append pending consolidation
    state.pending_consolidations.append(
        spec.PendingConsolidation(source_index=source_index, target_index=target_index)
    )
    # Set the target withdrawal credential to eth1
    eth1_withdrawal_credential = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    state.validators[target_index].withdrawal_credentials = eth1_withdrawal_credential

    # Advance to withdrawable_epoch - 1 with full participation
    target_epoch = state.validators[source_index].withdrawable_epoch - spec.Epoch(1)
    while spec.get_current_epoch(state) < target_epoch:
        next_epoch_with_full_participation(spec, state)

    # Obtain state before the call to process_pending_consolidations
    state_before_consolidation = state.copy()
    run_epoch_processing_to(spec, state_before_consolidation, "process_pending_consolidations")

    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # Pending consolidation was successfully processed
    expected_source_balance = (
        state_before_consolidation.balances[source_index] - spec.MIN_ACTIVATION_BALANCE
    )
    expected_target_balance = (
        state_before_consolidation.balances[target_index] + spec.MIN_ACTIVATION_BALANCE
    )
    assert state.balances[source_index] == expected_source_balance
    assert state.balances[target_index] == expected_target_balance
    assert state.pending_consolidations == []


@with_electra_and_later
@spec_state_test
def test_pending_consolidation_compounding_creds(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    # initiate source exit
    spec.initiate_validator_exit(state, source_index)
    # set withdrawable_epoch to exit_epoch + 1
    state.validators[source_index].withdrawable_epoch = state.validators[
        source_index
    ].exit_epoch + spec.Epoch(1)
    # append pending consolidation
    state.pending_consolidations.append(
        spec.PendingConsolidation(source_index=source_index, target_index=target_index)
    )
    # Set the source and the target withdrawal credential to compounding
    state.validators[source_index].withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    )
    state.validators[target_index].withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x12" * 20
    )

    # Advance to withdrawable_epoch - 1 with full participation
    target_epoch = state.validators[source_index].withdrawable_epoch - spec.Epoch(1)
    while spec.get_current_epoch(state) < target_epoch:
        next_epoch_with_full_participation(spec, state)

    # Obtain state before the call to process_pending_consolidations
    state_before_consolidation = state.copy()
    run_epoch_processing_to(spec, state_before_consolidation, "process_pending_consolidations")

    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # Pending consolidation was successfully processed
    expected_target_balance = (
        spec.MIN_ACTIVATION_BALANCE + state_before_consolidation.balances[target_index]
    )
    assert state.balances[target_index] == expected_target_balance
    # All source balance is active and moved to the target,
    # because the source validator has compounding credentials
    assert state.balances[source_index] == (
        state_before_consolidation.balances[source_index] - spec.MIN_ACTIVATION_BALANCE
    )
    assert state.pending_consolidations == []

    # Pending balance deposit to the target is not created,
    # because the target already has compounding credentials
    assert len(state.pending_deposits) == 0


@with_electra_and_later
@spec_state_test
def test_pending_consolidation_with_pending_deposit(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    # initiate source exit
    spec.initiate_validator_exit(state, source_index)
    # set withdrawable_epoch to exit_epoch + 1
    source = state.validators[source_index]
    source.withdrawable_epoch = source.exit_epoch + spec.Epoch(1)
    # append pending consolidation
    state.pending_consolidations.append(
        spec.PendingConsolidation(source_index=source_index, target_index=target_index)
    )
    # append pending deposit
    pending_deposit = spec.PendingDeposit(
        pubkey=source.pubkey,
        withdrawal_credentials=source.withdrawal_credentials,
        amount=spec.MIN_ACTIVATION_BALANCE,
        signature=spec.bls.G2_POINT_AT_INFINITY,
        slot=spec.GENESIS_SLOT,
    )
    state.pending_deposits.append(pending_deposit)
    # Set the source and the target withdrawal credential to compounding
    state.validators[source_index].withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    )
    state.validators[target_index].withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x12" * 20
    )

    # Advance to withdrawable_epoch - 1 with full participation
    target_epoch = source.withdrawable_epoch - spec.Epoch(1)
    while spec.get_current_epoch(state) < target_epoch:
        next_epoch_with_full_participation(spec, state)

    # Obtain state before the call to process_pending_balance_deposits
    state_before_consolidation = state.copy()
    run_epoch_processing_to(spec, state_before_consolidation, "process_pending_consolidations")

    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # Pending consolidation was successfully processed
    expected_target_balance = (
        spec.MIN_ACTIVATION_BALANCE + state_before_consolidation.balances[target_index]
    )
    assert state.balances[target_index] == expected_target_balance
    assert state.balances[source_index] == (
        state_before_consolidation.balances[source_index] - spec.MIN_ACTIVATION_BALANCE
    )
    assert state.pending_consolidations == []

    # Pending deposit to the source was not processed.
    # It should only be processed in the next epoch transition
    assert state.pending_deposits == [pending_deposit]


@with_electra_and_later
@spec_state_test
def test_pending_consolidation_source_balance_less_than_max_effective(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    # append pending consolidation
    state.pending_consolidations.append(
        spec.PendingConsolidation(source_index=source_index, target_index=target_index)
    )
    # Set withdrawable epoch to current epoch to allow processing
    state.validators[source_index].withdrawable_epoch = current_epoch
    # Set source and target withdrawal credential to eth1
    set_eth1_withdrawal_credential_with_balance(spec, state, source_index)
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)
    # Set the source balance to be less than effective_balance
    pre_balance_source = (
        state.validators[source_index].effective_balance - spec.EFFECTIVE_BALANCE_INCREMENT // 8
    )
    state.balances[source_index] = pre_balance_source

    pre_balance_target = state.balances[target_index]

    assert state.balances[source_index] < spec.get_max_effective_balance(
        state.validators[source_index]
    )

    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # Pending consolidation was successfully processed
    assert state.balances[target_index] == pre_balance_target + pre_balance_source
    assert state.balances[source_index] == 0
    assert state.pending_consolidations == []


@with_electra_and_later
@spec_state_test
def test_pending_consolidation_source_balance_greater_than_max_effective(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    # append pending consolidation
    state.pending_consolidations.append(
        spec.PendingConsolidation(source_index=source_index, target_index=target_index)
    )
    # Set withdrawable epoch to current epoch to allow processing
    state.validators[source_index].withdrawable_epoch = current_epoch
    # Set source and target withdrawal credential to eth1
    set_eth1_withdrawal_credential_with_balance(spec, state, source_index)
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)
    # Set the source balance to be greater than effective_balance
    excess_source_balance = spec.EFFECTIVE_BALANCE_INCREMENT // 8
    pre_balance_source = state.validators[source_index].effective_balance + excess_source_balance
    state.balances[source_index] = pre_balance_source

    pre_balance_target = state.balances[target_index]

    source_max_effective_balance = spec.get_max_effective_balance(state.validators[source_index])
    assert state.balances[source_index] > source_max_effective_balance

    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # Pending consolidation was successfully processed
    assert state.balances[target_index] == pre_balance_target + source_max_effective_balance
    assert state.balances[source_index] == excess_source_balance
    assert state.pending_consolidations == []


@with_electra_and_later
@spec_state_test
def test_pending_consolidation_source_balance_less_than_max_effective_compounding(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    # append pending consolidation
    state.pending_consolidations.append(
        spec.PendingConsolidation(source_index=source_index, target_index=target_index)
    )
    # Set withdrawable epoch to current epoch to allow processing
    state.validators[source_index].withdrawable_epoch = current_epoch
    # Set source and target withdrawal credential to compounding
    set_compounding_withdrawal_credential_with_balance(spec, state, source_index)
    set_compounding_withdrawal_credential_with_balance(spec, state, target_index)
    # Set the source balance to be less than effective_balance
    pre_balance_source = (
        state.validators[source_index].effective_balance - spec.EFFECTIVE_BALANCE_INCREMENT // 8
    )
    state.balances[source_index] = pre_balance_source

    pre_balance_target = state.balances[target_index]

    assert state.balances[source_index] < spec.get_max_effective_balance(
        state.validators[source_index]
    )

    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # Pending consolidation was successfully processed
    assert state.balances[target_index] == pre_balance_target + pre_balance_source
    assert state.balances[source_index] == 0
    assert state.pending_consolidations == []


@with_electra_and_later
@spec_state_test
def test_pending_consolidation_source_balance_greater_than_max_effective_compounding(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    # append pending consolidation
    state.pending_consolidations.append(
        spec.PendingConsolidation(source_index=source_index, target_index=target_index)
    )
    # Set withdrawable epoch to current epoch to allow processing
    state.validators[source_index].withdrawable_epoch = current_epoch
    # Set source and target withdrawal credential to compounding
    set_compounding_withdrawal_credential_with_balance(spec, state, source_index)
    set_compounding_withdrawal_credential_with_balance(spec, state, target_index)
    # Set the source balance to be greater than effective_balance
    excess_source_balance = spec.EFFECTIVE_BALANCE_INCREMENT // 8
    pre_balance_source = state.validators[source_index].effective_balance + excess_source_balance
    state.balances[source_index] = pre_balance_source

    pre_balance_target = state.balances[target_index]

    source_max_effective_balance = spec.get_max_effective_balance(state.validators[source_index])
    assert state.balances[source_index] > source_max_effective_balance

    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # Pending consolidation was successfully processed
    assert state.balances[target_index] == pre_balance_target + source_max_effective_balance
    assert state.balances[source_index] == excess_source_balance
    assert state.pending_consolidations == []


#  *******************************
#  * CONSOLIDATION BALANCE TESTS *
#  *******************************


def prepare_consolidation_and_state(
    spec, state, source_index, target_index, creds_type, balance_to_eb, eb_to_min_ab, eb_to_max_eb
):
    assert creds_type in ["comp", "eth1"]
    assert balance_to_eb in ["<", "=", ">"]
    assert eb_to_min_ab in ["<", "=", ">"]
    assert eb_to_max_eb in ["<", "="]
    if creds_type == "eth1":
        assert eb_to_min_ab == eb_to_max_eb
    else:
        assert (eb_to_min_ab, eb_to_max_eb) in [("<", "<"), ("=", "<"), (">", "<"), (">", "=")]

    # append pending consolidation
    current_epoch = spec.get_current_epoch(state)
    state.pending_consolidations.append(
        spec.PendingConsolidation(source_index=source_index, target_index=target_index)
    )
    # Set withdrawable epoch to current epoch to allow processing
    state.validators[source_index].withdrawable_epoch = current_epoch

    # Set source and target withdrawal credentials
    if creds_type == "eth1":
        set_eth1_withdrawal_credential_with_balance(spec, state, source_index)
    else:
        set_compounding_withdrawal_credential_with_balance(spec, state, source_index)
    set_compounding_withdrawal_credential_with_balance(spec, state, target_index)

    # Set source balances
    source = state.validators[source_index]
    max_eb = spec.get_max_effective_balance(source)
    if eb_to_min_ab == "<":
        source.effective_balance = spec.MIN_ACTIVATION_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT
    elif eb_to_min_ab == "=":
        source.effective_balance = spec.MIN_ACTIVATION_BALANCE
    elif eb_to_max_eb == "<":
        source.effective_balance = (max_eb - spec.MIN_ACTIVATION_BALANCE) // 2
    else:
        # eb_to_max_eb == '='
        source.effective_balance = max_eb

    if balance_to_eb == "<":
        state.balances[source_index] = (
            source.effective_balance - spec.EFFECTIVE_BALANCE_INCREMENT // 2
        )
    elif balance_to_eb == "=":
        state.balances[source_index] = source.effective_balance
    else:
        state.balances[source_index] = (
            source.effective_balance + spec.EFFECTIVE_BALANCE_INCREMENT // 2
        )


def run_balance_computation_test(spec, state, instance_tuples):
    max_index = 0
    for creds_type, balance_to_eb, eb_to_min_ab, eb_to_max_eb in instance_tuples:
        source_index = max_index
        target_index = max_index + 1
        prepare_consolidation_and_state(
            spec,
            state,
            source_index,
            target_index,
            creds_type,
            balance_to_eb,
            eb_to_min_ab,
            eb_to_max_eb,
        )
        max_index += 2

    pre_state = state.copy()

    yield from run_epoch_processing_with(spec, state, "process_pending_consolidations")

    # Check balances are moved correctly
    for source_index in range(0, max_index, 2):
        target_index = source_index + 1
        consolidated_balance = min(
            pre_state.validators[source_index].effective_balance, pre_state.balances[source_index]
        )
        assert (
            state.balances[source_index] == pre_state.balances[source_index] - consolidated_balance
        )
        assert (
            state.balances[target_index] == pre_state.balances[target_index] + consolidated_balance
        )


@with_electra_and_later
@spec_state_test
def test_pending_consolidation_balance_computation_eth1(spec, state):
    instances = []
    for balance_to_eb in ["<", "=", ">"]:
        for eb_to_min_ab, eb_to_max_eb in [("<", "<"), ("=", "=")]:
            instances.append(("eth1", balance_to_eb, eb_to_min_ab, eb_to_max_eb))

    yield from run_balance_computation_test(spec, state, instances)


@with_electra_and_later
@spec_state_test
def test_pending_consolidation_balance_computation_compounding(spec, state):
    instances = []
    for balance_to_eb in ["<", "=", ">"]:
        for eb_to_min_ab, eb_to_max_eb in [("<", "<"), ("=", "<"), (">", "<"), (">", "=")]:
            instances.append(("comp", balance_to_eb, eb_to_min_ab, eb_to_max_eb))

    yield from run_balance_computation_test(spec, state, instances)
