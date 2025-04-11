from eth2spec.test.helpers.constants import MAINNET
from eth2spec.test.context import (
    spec_state_test,
    with_electra_and_later,
    with_presets,
)
from eth2spec.test.helpers.keys import pubkey_to_privkey
from eth2spec.test.helpers.voluntary_exits import (
    run_voluntary_exit_processing,
    sign_voluntary_exit,
)

#  ********************
#  * EXIT QUEUE TESTS *
#  ********************


@with_electra_and_later
@spec_state_test
def test_min_balance_exit(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    # This state has 64 validators each with 32 ETH
    current_epoch = spec.get_current_epoch(state)
    expected_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    expected_withdrawable_epoch = (
        expected_exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    churn_limit = spec.get_activation_exit_churn_limit(state)
    # Set the balance to consume equal to churn limit
    state.exit_balance_to_consume = churn_limit

    validator_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]
    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index),
        privkey,
    )

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    # Check exit queue churn is set correctly
    assert state.exit_balance_to_consume == churn_limit - spec.MIN_ACTIVATION_BALANCE
    # Check exit epoch and withdrawable epoch
    assert state.validators[validator_index].exit_epoch == expected_exit_epoch
    assert state.validators[validator_index].withdrawable_epoch == expected_withdrawable_epoch
    # Check earliest_exit_epoch
    assert state.earliest_exit_epoch == expected_exit_epoch


@with_electra_and_later
@spec_state_test
def test_min_balance_exits_up_to_churn(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    # This state has 64 validators each with 32 ETH
    single_validator_balance = spec.MIN_ACTIVATION_BALANCE
    churn_limit = spec.get_activation_exit_churn_limit(state)
    # Set the balance to consume equal to churn limit
    state.exit_balance_to_consume = churn_limit
    num_to_exit = churn_limit // single_validator_balance

    # Exit all but 1 validators, all fit in the churn limit
    for i in range(num_to_exit - 1):
        validator_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[i]
        spec.initiate_validator_exit(state, validator_index)

    validator_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[
        num_to_exit
    ]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]
    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=spec.get_current_epoch(state), validator_index=validator_index),
        privkey,
    )
    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    # Last validator also fits in the churn limit
    expected_exit_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    expected_withdrawable_epoch = (
        expected_exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    # Check exit epoch and withdrawable epoch
    assert state.validators[num_to_exit].exit_epoch == expected_exit_epoch
    assert state.validators[num_to_exit].withdrawable_epoch == expected_withdrawable_epoch
    # Check exit queue churn is set
    assert state.exit_balance_to_consume == churn_limit - single_validator_balance * num_to_exit
    # Check earliest_exit_epoch
    assert state.earliest_exit_epoch == expected_exit_epoch


@with_electra_and_later
@spec_state_test
def test_min_balance_exits_above_churn(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    # This state has 64 validators each with 32 ETH
    single_validator_balance = spec.MIN_ACTIVATION_BALANCE
    expected_exit_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    expected_withdrawable_epoch = (
        expected_exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    churn_limit = spec.get_activation_exit_churn_limit(state)
    # Set the balance to consume equal to churn limit
    state.exit_balance_to_consume = churn_limit
    num_to_exit = churn_limit // single_validator_balance

    # Exit all but 1 validators, all fit in the churn limit
    for i in range(num_to_exit):
        validator_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[i]
        spec.initiate_validator_exit(state, validator_index)

    # Exit one more validator, not fitting in the churn limit
    validator_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[
        num_to_exit
    ]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]
    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=spec.get_current_epoch(state), validator_index=validator_index),
        privkey,
    )
    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    # Check exit epoch and withdrawable epoch. Last validator exits one epoch later
    assert state.validators[num_to_exit].exit_epoch == expected_exit_epoch + 1
    assert state.validators[num_to_exit].withdrawable_epoch == expected_withdrawable_epoch + 1
    # Check exit balance to consume is set correctly
    remainder = (num_to_exit + 1) * single_validator_balance % churn_limit
    assert state.exit_balance_to_consume == churn_limit - remainder
    # Check earliest_exit_epoch
    assert state.earliest_exit_epoch == expected_exit_epoch + 1


@with_electra_and_later
@spec_state_test
@with_presets(
    [MAINNET],
    "With CHURN_LIMIT_QUOTIENT=32, can't change validator balance without changing churn_limit",
)
def test_max_balance_exit(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    churn_limit = spec.get_activation_exit_churn_limit(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    # Set validator effective balance to 2048 ETH
    to_exit = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    state.validators[validator_index].effective_balance = to_exit

    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]
    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index),
        privkey,
    )

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    # Check exit epoch and withdrawable epoch
    earliest_exit_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    additional_epochs = (to_exit - 1) // churn_limit
    expected_exit_epoch = earliest_exit_epoch + additional_epochs
    expected_withdrawable_epoch = (
        expected_exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    assert state.validators[validator_index].exit_epoch == expected_exit_epoch
    assert state.validators[validator_index].withdrawable_epoch == expected_withdrawable_epoch
    # Check exit_balance_to_consume
    assert state.exit_balance_to_consume == (additional_epochs + 1) * churn_limit - to_exit
    # Check earliest_exit_epoch
    assert state.earliest_exit_epoch == expected_exit_epoch


@with_electra_and_later
@spec_state_test
@with_presets(
    [MAINNET],
    "With CHURN_LIMIT_QUOTIENT=32, can't change validator balance without changing churn_limit",
)
def test_exit_with_balance_equal_to_churn_limit(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    churn_limit = spec.get_activation_exit_churn_limit(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    # Set 0th validator effective balance to churn_limit
    state.validators[validator_index].effective_balance = churn_limit

    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]
    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index),
        privkey,
    )
    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    # Validator consumes churn limit fully in the current epoch
    expected_exit_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    expected_withdrawable_epoch = (
        expected_exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    assert state.validators[validator_index].exit_epoch == expected_exit_epoch
    assert state.validators[validator_index].withdrawable_epoch == expected_withdrawable_epoch
    # Check exit_balance_to_consume
    assert state.exit_balance_to_consume == 0
    # Check earliest_exit_epoch
    assert state.earliest_exit_epoch == expected_exit_epoch


@with_electra_and_later
@spec_state_test
@with_presets(
    [MAINNET],
    "With CHURN_LIMIT_QUOTIENT=32, can't change validator balance without changing churn_limit",
)
def test_exit_with_balance_multiple_of_churn_limit(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    churn_limit = spec.get_activation_exit_churn_limit(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    # Set validator effective balance to a multiple of churn_limit
    epochs_to_consume = 3
    state.validators[validator_index].effective_balance = epochs_to_consume * churn_limit

    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]
    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index),
        privkey,
    )
    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    # Validator consumes churn limit fully in epochs_to_consume epochs
    expected_exit_epoch = (
        spec.compute_activation_exit_epoch(spec.get_current_epoch(state)) + epochs_to_consume - 1
    )
    expected_withdrawable_epoch = (
        expected_exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    assert state.validators[validator_index].exit_epoch == expected_exit_epoch
    assert state.validators[validator_index].withdrawable_epoch == expected_withdrawable_epoch
    # Check exit_balance_to_consume
    assert state.exit_balance_to_consume == 0
    # Check earliest_exit_epoch
    assert state.earliest_exit_epoch == expected_exit_epoch


@with_electra_and_later
@spec_state_test
@with_presets(
    [MAINNET],
    "With CHURN_LIMIT_QUOTIENT=32, can't change validator balance without changing churn_limit",
)
def test_exit_existing_churn_and_churn_limit_balance(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    churn_limit = spec.get_activation_exit_churn_limit(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]

    # set exit epoch to the first available one and set exit balance to consume to full churn limit
    earliest_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    state.earliest_exit_epoch = earliest_exit_epoch
    state.exit_balance_to_consume = churn_limit
    # consume some churn in exit epoch
    existing_churn = spec.EFFECTIVE_BALANCE_INCREMENT
    state.exit_balance_to_consume -= existing_churn
    # Set validator effective balance to the churn limit
    state.validators[validator_index].effective_balance = churn_limit

    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]
    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index),
        privkey,
    )
    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    expected_exit_epoch = earliest_exit_epoch + 1
    expected_withdrawable_epoch = (
        expected_exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    # Check exit epoch
    assert state.validators[validator_index].exit_epoch == expected_exit_epoch
    assert state.validators[validator_index].withdrawable_epoch == expected_withdrawable_epoch
    # Check balance consumed in exit epoch is the remainder 1 ETH
    assert state.exit_balance_to_consume == churn_limit - existing_churn
    # check earliest exit epoch
    assert state.earliest_exit_epoch == expected_exit_epoch


@with_electra_and_later
@spec_state_test
@with_presets(
    [MAINNET],
    "With CHURN_LIMIT_QUOTIENT=32, can't change validator balance without changing churn_limit",
)
def test_exit_existing_churn_and_balance_multiple_of_churn_limit(spec, state):
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    current_epoch = spec.get_current_epoch(state)
    churn_limit = spec.get_activation_exit_churn_limit(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]

    # set exit epoch to the first available one and set exit balance to consume to full churn limit
    earliest_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
    state.earliest_exit_epoch = earliest_exit_epoch
    state.exit_balance_to_consume = churn_limit
    # consume some churn in exit epoch
    existing_churn = spec.EFFECTIVE_BALANCE_INCREMENT
    state.exit_balance_to_consume -= existing_churn

    # Set validator effective balance to a multiple of churn_limit
    epochs_to_consume = 3
    state.validators[validator_index].effective_balance = epochs_to_consume * churn_limit

    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]
    signed_voluntary_exit = sign_voluntary_exit(
        spec,
        state,
        spec.VoluntaryExit(epoch=current_epoch, validator_index=validator_index),
        privkey,
    )
    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)

    # Validator fully consumes epochs_to_consume and gets into the next one
    expected_exit_epoch = earliest_exit_epoch + epochs_to_consume
    expected_withdrawable_epoch = (
        expected_exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    assert state.validators[validator_index].exit_epoch == expected_exit_epoch
    assert state.validators[validator_index].withdrawable_epoch == expected_withdrawable_epoch
    # Check exit_balance_to_consume
    assert state.exit_balance_to_consume == churn_limit - existing_churn
    # Check earliest_exit_epoch
    assert state.earliest_exit_epoch == expected_exit_epoch


@with_electra_and_later
@spec_state_test
def test_voluntary_exit_with_pending_deposit(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    validator = state.validators[validator_index]
    privkey = pubkey_to_privkey[validator.pubkey]

    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    # A pending deposit will not prevent an exit
    state.pending_deposits = [
        spec.PendingDeposit(
            pubkey=validator.pubkey,
            withdrawal_credentials=validator.withdrawal_credentials,
            amount=spec.EFFECTIVE_BALANCE_INCREMENT,
            signature=spec.bls.G2_POINT_AT_INFINITY,
            slot=spec.GENESIS_SLOT,
        )
    ]

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit)


@with_electra_and_later
@spec_state_test
def test_invalid_validator_has_pending_withdrawal(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validators[validator_index].pubkey]

    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    state.pending_partial_withdrawals.append(
        spec.PendingPartialWithdrawal(
            validator_index=validator_index,
            amount=1,
            withdrawable_epoch=spec.compute_activation_exit_epoch(current_epoch),
        )
    )

    yield from run_voluntary_exit_processing(spec, state, signed_voluntary_exit, valid=False)
