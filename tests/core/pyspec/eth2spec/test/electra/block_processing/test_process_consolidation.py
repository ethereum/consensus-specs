from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.context import (
    spec_state_test,
    with_electra_and_later,
    with_presets,
    always_bls,
    spec_test,
    single_phase,
    with_custom_state,
    scaled_churn_balances_exceed_activation_exit_churn_limit,
    default_activation_threshold,
)
from eth2spec.test.helpers.keys import pubkey_to_privkey
from eth2spec.test.helpers.consolidations import (
    run_consolidation_processing,
    sign_consolidation,
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
    source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]

    # Set source and target withdrawal credentials to the same eth1 credential
    set_eth1_withdrawal_credential_with_balance(spec, state, source_index)
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(
            epoch=current_epoch, source_index=source_index, target_index=target_index
        ),
        source_privkey,
        target_privkey,
    )

    # Set earliest consolidation epoch to the expected exit epoch
    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    state.earliest_consolidation_epoch = expected_exit_epoch
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    # Set the consolidation balance to consume equal to churn limit
    state.consolidation_balance_to_consume = consolidation_churn_limit

    yield from run_consolidation_processing(spec, state, signed_consolidation)

    # Check consolidation churn is decremented correctly
    assert (
        state.consolidation_balance_to_consume
        == consolidation_churn_limit - spec.MIN_ACTIVATION_BALANCE
    )
    # Check exit epoch
    assert state.validators[0].exit_epoch == expected_exit_epoch


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
    source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]

    # Set source and target withdrawal credentials to the same eth1 credential
    set_eth1_withdrawal_credential_with_balance(spec, state, source_index)
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(
            epoch=current_epoch, source_index=source_index, target_index=target_index
        ),
        source_privkey,
        target_privkey,
    )
    yield from run_consolidation_processing(spec, state, signed_consolidation)

    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    # Check consolidation churn is decremented correctly
    # consolidation_balance_to_consume is replenished to the churn limit since we move to a new consolidation epoch
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    assert (
        state.consolidation_balance_to_consume
        == consolidation_churn_limit - spec.MIN_ACTIVATION_BALANCE
    )
    # Check exit epochs
    assert state.validators[0].exit_epoch == expected_exit_epoch


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
    source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]

    # Set source and target withdrawal credentials to the same eth1 credential
    set_eth1_withdrawal_credential_with_balance(spec, state, source_index)
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(
            epoch=current_epoch, source_index=source_index, target_index=target_index
        ),
        source_privkey,
        target_privkey,
    )

    # Set earliest consolidation epoch to the expected exit epoch
    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    state.earliest_consolidation_epoch = expected_exit_epoch
    # Set some nonzero preexisting churn lower than churn limit and sufficient to process the consolidation
    preexisting_churn = 2 * spec.MIN_ACTIVATION_BALANCE
    state.consolidation_balance_to_consume = preexisting_churn

    yield from run_consolidation_processing(spec, state, signed_consolidation)

    # Check consolidation churn is decremented correctly
    assert (
        state.consolidation_balance_to_consume
        == preexisting_churn - spec.MIN_ACTIVATION_BALANCE
    )
    # Check exit epoch
    assert state.validators[0].exit_epoch == expected_exit_epoch


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
    source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]

    # Set source and target withdrawal credentials to the same eth1 credential
    set_eth1_withdrawal_credential_with_balance(spec, state, source_index)
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(
            epoch=current_epoch, source_index=source_index, target_index=target_index
        ),
        source_privkey,
        target_privkey,
    )

    # Set earliest consolidation epoch to the first available epoch
    state.earliest_consolidation_epoch = spec.compute_activation_exit_epoch(
        current_epoch
    )
    # Set preexisting churn lower than required to process the consolidation
    preexisting_churn = spec.MIN_ACTIVATION_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT
    state.consolidation_balance_to_consume = preexisting_churn

    yield from run_consolidation_processing(spec, state, signed_consolidation)

    # It takes one more epoch to process the consolidation due to insufficient churn
    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch) + 1
    # Check consolidation churn is decremented correctly
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    remainder = spec.MIN_ACTIVATION_BALANCE % preexisting_churn
    assert (
        state.consolidation_balance_to_consume == consolidation_churn_limit - remainder
    )
    # Check exit epoch
    assert state.validators[0].exit_epoch == expected_exit_epoch


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_basic_consolidation_with_compounding_credential(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    # Set the consolidation balance to consume equal to churn limit
    state.consolidation_balance_to_consume = consolidation_churn_limit
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]

    # Set source and target withdrawal credentials to the same eth1 credential
    set_compounding_withdrawal_credential(spec, state, source_index)
    set_compounding_withdrawal_credential(spec, state, target_index)

    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(
            epoch=current_epoch, source_index=source_index, target_index=target_index
        ),
        source_privkey,
        target_privkey,
    )
    yield from run_consolidation_processing(spec, state, signed_consolidation)

    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    # Check consolidation churn is decremented correctly
    assert (
        state.consolidation_balance_to_consume
        == consolidation_churn_limit - spec.MIN_ACTIVATION_BALANCE
    )
    # Check exit epoch
    assert state.validators[0].exit_epoch == expected_exit_epoch


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
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    current_epoch = spec.get_current_epoch(state)

    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    source_validator = state.validators[source_index]
    source_validator.effective_balance = consolidation_churn_limit
    # Churn limit increases due to higher total balance
    updated_consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]

    # Set source and target withdrawal credentials to the same eth1 credential
    set_compounding_withdrawal_credential(spec, state, source_index)
    set_compounding_withdrawal_credential(spec, state, target_index)

    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(
            epoch=current_epoch, source_index=source_index, target_index=target_index
        ),
        source_privkey,
        target_privkey,
    )
    yield from run_consolidation_processing(spec, state, signed_consolidation)

    # validator's effective balance fits into the churn, exit as soon as possible
    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    # Check consolidation churn is decremented correctly
    assert (
        state.consolidation_balance_to_consume
        == updated_consolidation_churn_limit - consolidation_churn_limit
    )
    # Check exit epoch
    assert state.validators[0].exit_epoch == expected_exit_epoch


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
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    current_epoch = spec.get_current_epoch(state)

    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    # Set source balance higher than consolidation churn limit
    state.validators[source_index].effective_balance = 2 * consolidation_churn_limit
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]

    # Set source and target withdrawal credentials to the same eth1 credential
    set_compounding_withdrawal_credential(spec, state, source_index)
    set_compounding_withdrawal_credential(spec, state, target_index)

    # Consolidation churn limit increases due to higher total balance
    new_churn_limit = spec.get_consolidation_churn_limit(state)
    remainder = state.validators[source_index].effective_balance % new_churn_limit
    expected_balance = new_churn_limit - remainder

    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(
            epoch=current_epoch, source_index=source_index, target_index=target_index
        ),
        source_privkey,
        target_privkey,
    )
    yield from run_consolidation_processing(spec, state, signed_consolidation)

    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch) + 1
    # Check consolidation churn is decremented correctly
    assert state.consolidation_balance_to_consume == expected_balance
    # Check exit epoch
    assert state.validators[0].exit_epoch == expected_exit_epoch


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
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    current_epoch = spec.get_current_epoch(state)

    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]

    # Set source and target withdrawal credentials to the same eth1 credential
    set_compounding_withdrawal_credential(spec, state, source_index)
    set_compounding_withdrawal_credential(spec, state, target_index)

    # Set source balance higher than consolidation churn limit
    state.validators[source_index].effective_balance = 3 * consolidation_churn_limit

    new_churn_limit = spec.get_consolidation_churn_limit(state)
    remainder = state.validators[source_index].effective_balance % new_churn_limit
    expected_balance = new_churn_limit - remainder

    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(
            epoch=current_epoch, source_index=source_index, target_index=target_index
        ),
        source_privkey,
        target_privkey,
    )
    yield from run_consolidation_processing(spec, state, signed_consolidation)

    # when exiting a multiple of the churn limit greater than 1, an extra exit epoch is added
    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch) + 2
    assert state.validators[0].exit_epoch == expected_exit_epoch
    # since the earliest exit epoch moves to a new one, consolidation balance is back to full
    assert state.consolidation_balance_to_consume == expected_balance


# Failing tests

@with_electra_and_later
@spec_state_test
def test_invalid_source_equals_target(spec, state):
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator_privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    # Set withdrawal credentials to eth1
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index)

    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(
            epoch=current_epoch,
            source_index=validator_index,
            target_index=validator_index,
        ),
        validator_privkey,
        validator_privkey,
    )
    yield from run_consolidation_processing(
        spec, state, signed_consolidation, valid=False
    )


@with_electra_and_later
@spec_state_test
def test_invalid_exceed_pending_consolidations_limit(spec, state):
    state.pending_consolidations = [
        spec.PendingConsolidation(source_index=0, target_index=1)
    ] * spec.PENDING_CONSOLIDATIONS_LIMIT
    current_epoch = spec.get_current_epoch(state)
    source_privkey = pubkey_to_privkey[state.validators[0].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[1].pubkey]
    # Set source and target withdrawal credentials to the same eth1 credential
    set_eth1_withdrawal_credential_with_balance(spec, state, 0)
    set_eth1_withdrawal_credential_with_balance(spec, state, 1)
    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(epoch=current_epoch, source_index=0, target_index=1),
        source_privkey,
        target_privkey,
    )
    yield from run_consolidation_processing(
        spec, state, signed_consolidation, valid=False
    )


@with_electra_and_later
@spec_state_test
def test_invalid_not_enough_consolidation_churn_available(spec, state):
    state.validators = state.validators[0:2]
    state.pending_consolidations = [
        spec.PendingConsolidation(source_index=0, target_index=1)
    ]
    current_epoch = spec.get_current_epoch(state)
    source_privkey = pubkey_to_privkey[state.validators[0].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[1].pubkey]
    # Set source and target withdrawal credentials to the same eth1 credential
    set_eth1_withdrawal_credential_with_balance(spec, state, 0)
    set_eth1_withdrawal_credential_with_balance(spec, state, 1)
    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(epoch=current_epoch, source_index=0, target_index=1),
        source_privkey,
        target_privkey,
    )
    yield from run_consolidation_processing(
        spec, state, signed_consolidation, valid=False
    )


@with_electra_and_later
@spec_state_test
def test_invalid_exited_source(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_privkey = pubkey_to_privkey[state.validators[0].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[1].pubkey]
    set_eth1_withdrawal_credential_with_balance(spec, state, 0)
    set_eth1_withdrawal_credential_with_balance(spec, state, 1)
    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(epoch=current_epoch, source_index=0, target_index=1),
        source_privkey,
        target_privkey,
    )
    # exit source
    spec.initiate_validator_exit(state, 0)
    yield from run_consolidation_processing(
        spec, state, signed_consolidation, valid=False
    )


@with_electra_and_later
@spec_state_test
def test_invalid_exited_target(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_privkey = pubkey_to_privkey[state.validators[0].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[1].pubkey]
    # Set source and target withdrawal credentials to the same eth1 credential
    set_eth1_withdrawal_credential_with_balance(spec, state, 0)
    set_eth1_withdrawal_credential_with_balance(spec, state, 1)
    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(epoch=current_epoch, source_index=0, target_index=1),
        source_privkey,
        target_privkey,
    )
    # exit target
    spec.initiate_validator_exit(state, 1)
    yield from run_consolidation_processing(
        spec, state, signed_consolidation, valid=False
    )


@with_electra_and_later
@spec_state_test
def test_invalid_inactive_source(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_privkey = pubkey_to_privkey[state.validators[0].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[1].pubkey]
    set_eth1_withdrawal_credential_with_balance(spec, state, 0)
    set_eth1_withdrawal_credential_with_balance(spec, state, 1)
    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(epoch=current_epoch, source_index=0, target_index=1),
        source_privkey,
        target_privkey,
    )
    # set source validator as not yet activated
    state.validators[0].activation_epoch = spec.FAR_FUTURE_EPOCH
    yield from run_consolidation_processing(
        spec, state, signed_consolidation, valid=False
    )


@with_electra_and_later
@spec_state_test
def test_invalid_inactive_target(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_privkey = pubkey_to_privkey[state.validators[0].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[1].pubkey]
    # Set source and target withdrawal credentials to the same eth1 credential
    set_eth1_withdrawal_credential_with_balance(spec, state, 0)
    set_eth1_withdrawal_credential_with_balance(spec, state, 1)
    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(epoch=current_epoch, source_index=0, target_index=1),
        source_privkey,
        target_privkey,
    )
    # set target validator as not yet activated
    state.validators[1].activation_epoch = spec.FAR_FUTURE_EPOCH
    yield from run_consolidation_processing(
        spec, state, signed_consolidation, valid=False
    )


@with_electra_and_later
@spec_state_test
def test_invalid_no_execution_withdrawal_credential(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_privkey = pubkey_to_privkey[state.validators[0].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[1].pubkey]
    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(epoch=current_epoch, source_index=0, target_index=1),
        source_privkey,
        target_privkey,
    )
    yield from run_consolidation_processing(
        spec, state, signed_consolidation, valid=False
    )


@with_electra_and_later
@spec_state_test
def test_invalid_different_credentials(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_privkey = pubkey_to_privkey[state.validators[0].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[1].pubkey]
    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(epoch=current_epoch, source_index=0, target_index=1),
        source_privkey,
        target_privkey,
    )
    # Set source and target withdrawal credentials to different eth1 credentials
    set_eth1_withdrawal_credential_with_balance(spec, state, 0)
    set_eth1_withdrawal_credential_with_balance(spec, state, 1, address=b"\x10" * 20)
    yield from run_consolidation_processing(
        spec, state, signed_consolidation, valid=False
    )


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
@always_bls
def test_invalid_source_signature(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]

    # Set source and target withdrawal credentials to the same eth1 credential
    set_eth1_withdrawal_credential_with_balance(spec, state, source_index)
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(
            epoch=current_epoch, source_index=source_index, target_index=target_index
        ),
        source_privkey,
        target_privkey,
    )

    # Set earliest consolidation epoch to the expected exit epoch
    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    state.earliest_consolidation_epoch = expected_exit_epoch
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    # Set the consolidation balance to consume equal to churn limit
    state.consolidation_balance_to_consume = consolidation_churn_limit

    current_epoch = spec.get_current_epoch(state)
    source_privkey = pubkey_to_privkey[state.validators[0].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[1].pubkey]
    # Set source and target withdrawal credentials to the same eth1 credential
    set_eth1_withdrawal_credential_with_balance(spec, state, 0)
    set_eth1_withdrawal_credential_with_balance(spec, state, 1)
    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(epoch=current_epoch, source_index=0, target_index=1),
        source_privkey,
        target_privkey,
    )

    # Change the pubkey of the source validator, invalidating its signature
    state.validators[0].pubkey = state.validators[1].pubkey

    yield from run_consolidation_processing(
        spec, state, signed_consolidation, valid=False
    )


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
@always_bls
def test_invalid_target_signature(spec, state):
    # This state has 256 validators each with 32 ETH in MINIMAL preset, 128 ETH consolidation churn
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    source_privkey = pubkey_to_privkey[state.validators[source_index].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[target_index].pubkey]

    # Set source and target withdrawal credentials to the same eth1 credential
    set_eth1_withdrawal_credential_with_balance(spec, state, source_index)
    set_eth1_withdrawal_credential_with_balance(spec, state, target_index)

    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(
            epoch=current_epoch, source_index=source_index, target_index=target_index
        ),
        source_privkey,
        target_privkey,
    )

    # Set earliest consolidation epoch to the expected exit epoch
    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    state.earliest_consolidation_epoch = expected_exit_epoch
    consolidation_churn_limit = spec.get_consolidation_churn_limit(state)
    # Set the consolidation balance to consume equal to churn limit
    state.consolidation_balance_to_consume = consolidation_churn_limit

    current_epoch = spec.get_current_epoch(state)
    source_privkey = pubkey_to_privkey[state.validators[0].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[1].pubkey]
    # Set source and target withdrawal credentials to the same eth1 credential
    set_eth1_withdrawal_credential_with_balance(spec, state, 0)
    set_eth1_withdrawal_credential_with_balance(spec, state, 1)
    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(epoch=current_epoch, source_index=0, target_index=1),
        source_privkey,
        target_privkey,
    )

    # Change the pubkey of the target validator, invalidating its signature
    state.validators[1].pubkey = state.validators[2].pubkey

    yield from run_consolidation_processing(
        spec, state, signed_consolidation, valid=False
    )


@with_electra_and_later
@spec_state_test
def test_invalid_before_specified_epoch(spec, state):
    current_epoch = spec.get_current_epoch(state)
    source_privkey = pubkey_to_privkey[state.validators[0].pubkey]
    target_privkey = pubkey_to_privkey[state.validators[1].pubkey]
    # Set source and target withdrawal credentials to the same eth1 credential
    set_eth1_withdrawal_credential_with_balance(spec, state, 0)
    set_eth1_withdrawal_credential_with_balance(spec, state, 1)
    # set epoch=current_epoch + 1, so it's too early to process it
    signed_consolidation = sign_consolidation(
        spec,
        state,
        spec.Consolidation(epoch=current_epoch + 1, source_index=0, target_index=1),
        source_privkey,
        target_privkey,
    )
    yield from run_consolidation_processing(
        spec, state, signed_consolidation, valid=False
    )
