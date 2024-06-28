from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.context import (
    with_electra_and_later,
    with_presets,
    spec_test,
    single_phase,
    with_custom_state,
    scaled_churn_balances_exceed_activation_exit_churn_limit,
    default_activation_threshold,
    spec_state_test,
)
from eth2spec.test.helpers.withdrawals import (
    set_eth1_withdrawal_credential_with_balance,
    set_compounding_withdrawal_credential,
)

#  ***********************
#  * CONSOLIDATION TESTS *
#  ***********************


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_basic_consolidation_in_current_consolidation_epoch(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]

    # Set source to eth1 credentials
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    # Make consolidation with source address
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )

    # Set target to eth1 credentials
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # Set earliest consolidation epoch to the expected exit epoch
    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    state.earliest_consolidation_epoch = expected_exit_epoch
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    # Set the consolidation balance to consume equal to churn limit
    state.consolidation_balance_to_consume = consolidation_churn_limit

    yield from run_consolidation_processing(spec, state, consolidation)

    # Check consolidation churn is decremented correctly
    assert (
        state.consolidation_balance_to_consume
        == consolidation_churn_limit - spec.MIN_ACTIVATION_BALANCE
    )
    # Check exit epoch
    assert state.validators[source_index].exit_epoch == expected_exit_epoch


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_basic_consolidation_in_new_consolidation_epoch(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    # Set consolidation balance to consume to some arbitrary nonzero value below the churn limit
    state.consolidation_balance_to_consume = spec.EFFECTIVE_BALANCE_INCREMENT
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]

    # Set source to eth1 credentials
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    # Make consolidation with source address
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )

    # Set target to eth1 credentials
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    yield from run_consolidation_processing(spec, state, consolidation)

    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    # Check consolidation churn is decremented correctly
    # consolidation_balance_to_consume is replenished to the churn limit since we move to a new consolidation epoch
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    assert (
        state.consolidation_balance_to_consume
        == consolidation_churn_limit - spec.MIN_ACTIVATION_BALANCE
    )
    # Check exit epochs
    assert state.validators[source_index].exit_epoch == expected_exit_epoch


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_basic_consolidation_with_preexisting_churn(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]

    # Set source to eth1 credentials
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    # Make consolidation with source address
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )

    # Set target to eth1 credentials
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # Set earliest consolidation epoch to the expected exit epoch
    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    state.earliest_consolidation_epoch = expected_exit_epoch
    # Set some nonzero preexisting churn lower than churn limit and sufficient to process the consolidation
    preexisting_churn = 2 * spec.MIN_ACTIVATION_BALANCE
    state.consolidation_balance_to_consume = preexisting_churn

    yield from run_consolidation_processing(spec, state, consolidation)

    # Check consolidation churn is decremented correctly
    assert (
        state.consolidation_balance_to_consume
        == preexisting_churn - spec.MIN_ACTIVATION_BALANCE
    )
    # Check exit epoch
    assert state.validators[source_index].exit_epoch == expected_exit_epoch


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_basic_consolidation_with_insufficient_preexisting_churn(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]

    # Set source to eth1 credentials
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    # Make consolidation with source address
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )

    # Set target to eth1 credentials
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # Set earliest consolidation epoch to the first available epoch
    state.earliest_consolidation_epoch = spec.compute_activation_exit_epoch(
        current_epoch
    )
    # Set preexisting churn lower than required to process the consolidation
    preexisting_churn = spec.MIN_ACTIVATION_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT
    state.consolidation_balance_to_consume = preexisting_churn

    yield from run_consolidation_processing(spec, state, consolidation)

    # It takes one more epoch to process the consolidation due to insufficient churn
    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch) + 1
    # Check consolidation churn is decremented correctly
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    remainder = spec.MIN_ACTIVATION_BALANCE % preexisting_churn
    assert (
        state.consolidation_balance_to_consume == consolidation_churn_limit - remainder
    )
    # Check exit epoch
    assert state.validators[source_index].exit_epoch == expected_exit_epoch


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_basic_consolidation_with_compounding_credentials(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]

    # Set source to eth1 credentials
    source_address = b"\x22" * 20
    set_compounding_withdrawal_credential(
        spec, state, source_index, address=source_address
    )
    # Make consolidation with source address
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )

    # Set target to eth1 credentials
    set_compounding_withdrawal_credential(spec, state, target_index)

    # Set the consolidation balance to consume equal to churn limit
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    state.consolidation_balance_to_consume = consolidation_churn_limit

    yield from run_consolidation_processing(spec, state, consolidation)

    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    # Check consolidation churn is decremented correctly
    assert (
        state.consolidation_balance_to_consume
        == consolidation_churn_limit - spec.MIN_ACTIVATION_BALANCE
    )
    # Check exit epoch
    assert state.validators[source_index].exit_epoch == expected_exit_epoch


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_consolidation_churn_limit_balance(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]

    # Set source to eth1 credentials
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    # Make consolidation with source address
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )

    # Set target to eth1 credentials
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # Set source effective balance to consolidation churn limit
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    state.validators[source_index].effective_balance = consolidation_churn_limit
    # Churn limit increases due to higher total balance
    updated_consolidation_churn_limit = spec.get_consolidation_churn_limit(state)

    yield from run_consolidation_processing(spec, state, consolidation)

    # validator's effective balance fits into the churn, exit as soon as possible
    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    # Check consolidation churn is decremented correctly
    assert (
        state.consolidation_balance_to_consume
        == updated_consolidation_churn_limit - consolidation_churn_limit
    )
    # Check exit epoch
    assert state.validators[source_index].exit_epoch == expected_exit_epoch


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_consolidation_balance_larger_than_churn_limit(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]

    # Set source to eth1 credentials
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    # Make consolidation with source address
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )

    # Set target to eth1 credentials
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # Set source effective balance to 2 * consolidation churn limit
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    state.validators[source_index].effective_balance = 2 * consolidation_churn_limit

    # Consolidation churn limit increases due to higher total balance
    updated_consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    remainder = state.validators[source_index].effective_balance % updated_consolidation_churn_limit
    expected_balance = updated_consolidation_churn_limit - remainder

    yield from run_consolidation_processing(spec, state, consolidation)

    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch) + 1
    # Check consolidation churn is decremented correctly
    assert state.consolidation_balance_to_consume == expected_balance
    # Check exit epoch
    assert state.validators[source_index].exit_epoch == expected_exit_epoch


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_consolidation_balance_through_two_churn_epochs(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]

    # Set source to eth1 credentials
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    # Make consolidation with source address
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )

    # Set target to eth1 credentials
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # Set source balance higher to 3 * consolidation churn limit
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    state.validators[source_index].effective_balance = 3 * consolidation_churn_limit

    new_churn_limit = spec.get_consolidation_churn_limit(state)
    remainder = state.validators[source_index].effective_balance % new_churn_limit
    expected_balance = new_churn_limit - remainder

    yield from run_consolidation_processing(spec, state, consolidation)

    # when exiting a multiple of the churn limit greater than 1, an extra exit epoch is added
    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch) + 2
    assert state.validators[0].exit_epoch == expected_exit_epoch
    # since the earliest exit epoch moves to a new one, consolidation balance is back to full
    assert state.consolidation_balance_to_consume == expected_balance


# Failing tests

@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_incorrect_source_equals_target(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]

    # Set source to eth1 credentials
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    # Make consolidation from source to source
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[source_index].pubkey,
    )

    # Check the the return condition
    assert consolidation.source_pubkey == consolidation.target_pubkey

    yield from run_consolidation_processing(
        spec, state, consolidation, success=False
    )


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_incorrect_exceed_pending_consolidations_limit(spec, state):
    state.pending_consolidations = [
        spec.PendingConsolidation(source_index=0, target_index=1)
    ] * spec.PENDING_CONSOLIDATIONS_LIMIT

    # Set up an otherwise correct consolidation
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # Check the the return condition
    assert len(state.pending_consolidations) == spec.PENDING_CONSOLIDATIONS_LIMIT

    yield from run_consolidation_processing(
        spec, state, consolidation, success=False
    )


@with_electra_and_later
@spec_state_test
@single_phase
def test_incorrect_not_enough_consolidation_churn_available(spec, state):
    state.pending_consolidations = [
        spec.PendingConsolidation(source_index=0, target_index=1)
    ]

    # Set up an otherwise correct consolidation
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )

    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # Check the the return condition
    assert spec.get_consolidation_churn_limit(state) <= spec.MIN_ACTIVATION_BALANCE

    yield from run_consolidation_processing(
        spec, state, consolidation, success=False
    )


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_incorrect_exited_source(spec, state):
    # Set up an otherwise correct consolidation
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # exit source
    spec.initiate_validator_exit(state, source_index)

    # Check the the return condition
    assert state.validators[source_index].exit_epoch != spec.FAR_FUTURE_EPOCH

    yield from run_consolidation_processing(
        spec, state, consolidation, success=False
    )


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_incorrect_exited_target(spec, state):
    # Set up an otherwise correct consolidation
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)
    # exit target
    spec.initiate_validator_exit(state, 1)

    # Check the the return condition
    assert state.validators[target_index].exit_epoch != spec.FAR_FUTURE_EPOCH

    yield from run_consolidation_processing(
        spec, state, consolidation, success=False
    )


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_incorrect_inactive_source(spec, state):
    # Set up an otherwise correct consolidation
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # set source validator as not yet activated
    state.validators[source_index].activation_epoch = spec.FAR_FUTURE_EPOCH

    # Check the the return condition
    assert not spec.is_active_validator(state.validators[source_index], current_epoch)

    yield from run_consolidation_processing(
        spec, state, consolidation, success=False
    )


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_incorrect_inactive_target(spec, state):
    # Set up an otherwise correct consolidation
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # set target validator as not yet activated
    state.validators[1].activation_epoch = spec.FAR_FUTURE_EPOCH

    # Check the the return condition
    assert not spec.is_active_validator(state.validators[target_index], current_epoch)

    yield from run_consolidation_processing(
        spec, state, consolidation, success=False
    )


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_incorrect_no_source_execution_withdrawal_credential(spec, state):
    # Set up a correct consolidation, but source does not have
    # an execution withdrawal credential
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_address = b"\x22" * 20
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # Check the the return condition
    assert not spec.has_execution_withdrawal_credential(state.validators[source_index])

    yield from run_consolidation_processing(
        spec, state, consolidation, success=False
    )


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_incorrect_no_target_execution_withdrawal_credential(spec, state):
    # Set up a correct consolidation, but target does not have
    # an execution withdrawal credential
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )

    # Check the the return condition
    assert not spec.has_execution_withdrawal_credential(state.validators[target_index])

    yield from run_consolidation_processing(
        spec, state, consolidation, success=False
    )


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_incorrect_incorrect_source_address(spec, state):
    # Set up an otherwise correct consolidation
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    # Make consolidation with different source address
    consolidation = spec.ConsolidationRequest(
        source_address=b"\x33" * 20,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=state.validators[target_index].pubkey,
    )
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # Check the the return condition
    assert not state.validators[source_index].withdrawal_credentials[12:] == consolidation.source_address

    yield from run_consolidation_processing(
        spec, state, consolidation, success=False
    )


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_incorrect_unknown_source_pubkey(spec, state):
    # Set up an otherwise correct consolidation
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    # Make consolidation with different source pubkey
    consolidation = spec.ConsolidationRequest(
        source_address=source_address,
        source_pubkey=b"\x00" * 48,
        target_pubkey=state.validators[target_index].pubkey,
    )
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # Check the the return condition
    assert not state.validators[source_index].pubkey == consolidation.source_pubkey

    yield from run_consolidation_processing(
        spec, state, consolidation, success=False
    )


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_incorrect_unknown_target_pubkey(spec, state):
    # Set up an otherwise correct consolidation
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec, state, source_index, address=source_address
    )
    # Make consolidation with different target pubkey
    consolidation = spec.ConsolidationRequest(
        source_address=b"\x33" * 20,
        source_pubkey=state.validators[source_index].pubkey,
        target_pubkey=b"\x00" * 48,
    )
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    # Check the the return condition
    assert not state.validators[target_index].pubkey == consolidation.target_pubkey

    yield from run_consolidation_processing(
        spec, state, consolidation, success=False
    )


def run_consolidation_processing(spec, state, consolidation, success=True):
    """
    Run ``process_consolidation``, yielding:
      - pre-state ('pre')
      - consolidation_request ('consolidation_request')
      - post-state ('post').
    If ``success == False``, ``process_consolidation_request`` would return without any state change.
    """

    if success:
        validator_pubkeys = [v.pubkey for v in state.validators]
        source_index = spec.ValidatorIndex(validator_pubkeys.index(consolidation.source_pubkey))
        target_index = spec.ValidatorIndex(validator_pubkeys.index(consolidation.target_pubkey))
        source_validator = state.validators[source_index]
        target_validator = state.validators[target_index]
        pre_exit_epoch_source = source_validator.exit_epoch
        pre_exit_epoch_target = target_validator.exit_epoch
        pre_pending_consolidations = state.pending_consolidations.copy()
    else:
        pre_state = state.copy()

    yield 'pre', state
    yield 'consolidation_request', consolidation

    spec.process_consolidation_request(state, consolidation)

    yield 'post', state

    if success:
        # Check source and target have execution credentials
        assert spec.has_execution_withdrawal_credential(source_validator)
        assert spec.has_execution_withdrawal_credential(target_validator)
        # Check source address in the consolidation fits the withdrawal credentials
        assert source_validator.withdrawal_credentials[12:] == consolidation.source_address
        # Check source and target are not the same
        assert source_index != target_index
        # Check source and target were not exiting
        assert pre_exit_epoch_source == spec.FAR_FUTURE_EPOCH
        assert pre_exit_epoch_target == spec.FAR_FUTURE_EPOCH
        # Check source is now exiting
        assert state.validators[source_index].exit_epoch < spec.FAR_FUTURE_EPOCH
        # Check that the exit epoch matches earliest_consolidation_epoch
        assert state.validators[source_index].exit_epoch == state.earliest_consolidation_epoch
        # Check that the correct consolidation has been appended
        expected_new_pending_consolidation = spec.PendingConsolidation(
            source_index=source_index,
            target_index=target_index,
        )
        assert state.pending_consolidations == pre_pending_consolidations + [expected_new_pending_consolidation]
    else:
        assert pre_state == state
