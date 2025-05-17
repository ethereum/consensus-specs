from eth2spec.test.context import (
    always_bls,
    default_activation_threshold,
    scaled_churn_balances_exceed_activation_exit_churn_limit,
    single_phase,
    spec_state_test,
    spec_test,
    with_custom_state,
    with_electra_and_later,
    with_presets,
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.deposits import prepare_pending_deposit
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with
from eth2spec.test.helpers.state import (
    advance_finality_to,
    next_epoch_with_full_participation,
    set_full_participation,
)


def run_process_pending_deposits(spec, state):
    yield from run_epoch_processing_with(spec, state, "process_pending_deposits")


def _ensure_enough_churn_to_process_deposits(spec, state):
    state.deposit_balance_to_consume = sum(d.amount for d in state.pending_deposits)


def _prepare_eth1_bridge_deprecation(spec, state, eth1_bridge_flags):
    new_pending_deposits = []
    validator_index_base = len(state.validators)
    deposit_request_slot = spec.Slot(1)
    for index, eth1_bridge in enumerate(eth1_bridge_flags):
        validator_index = validator_index_base + index
        slot = spec.GENESIS_SLOT if eth1_bridge else deposit_request_slot
        pending_deposit = prepare_pending_deposit(
            spec,
            validator_index=validator_index,
            amount=spec.MIN_ACTIVATION_BALANCE,
            signed=True,
            slot=slot,
        )
        new_pending_deposits.append(pending_deposit)

        # Eth1 bridge deposits instantly yield new validator records
        if eth1_bridge:
            spec.add_validator_to_registry(
                state, pending_deposit.pubkey, pending_deposit.withdrawal_credentials, spec.Gwei(0)
            )
            state.eth1_deposit_index += 1

    # Advance state to make pending deposits finalized
    advance_finality_to(spec, state, spec.compute_epoch_at_slot(deposit_request_slot) + 1)

    # Add pending deposits
    for pending_deposit in new_pending_deposits:
        state.pending_deposits.append(pending_deposit)

    # Ensure there is enough churn to process them all
    _ensure_enough_churn_to_process_deposits(spec, state)

    return state, new_pending_deposits


def _check_pending_deposits_induced_new_validators(
    spec, state, pre_validator_count, applied_pending_deposits
):
    assert pre_validator_count + len(applied_pending_deposits) == len(state.validators)

    eth1_bridge_deposits = [d for d in applied_pending_deposits if d.slot == spec.GENESIS_SLOT]
    deposit_requests = [d for d in applied_pending_deposits if d.slot > spec.GENESIS_SLOT]

    # Eth1 bridge deposits should induce new validators in the first place
    for index, deposit in enumerate(eth1_bridge_deposits):
        validator_index = pre_validator_count + index
        validator = state.validators[validator_index]
        assert state.balances[validator_index] == deposit.amount
        assert validator.pubkey == deposit.pubkey
        # Effective balance is updated after pending deposits by process_effective_balance_updates
        assert validator.effective_balance == spec.Gwei(0)
        assert validator.withdrawal_credentials == deposit.withdrawal_credentials

    # then deposit requests go
    for index, deposit in enumerate(deposit_requests):
        validator_index = pre_validator_count + len(eth1_bridge_deposits) + index
        validator = state.validators[validator_index]
        assert state.balances[validator_index] == deposit.amount
        assert validator.pubkey == deposit.pubkey
        assert validator.withdrawal_credentials == deposit.withdrawal_credentials
        # Validators induced from deposit requests get instant update of the EB
        assert validator.effective_balance == deposit.amount


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_eth1_bridge_transition_pending(spec, state):
    # There are pending Eth1 bridge deposits
    # state.eth1_deposit_index < state.deposit_requests_start_index
    pre_validator_count = len(state.validators)
    state.eth1_data.deposit_count = len(state.validators) + 3
    state.deposit_requests_start_index = state.eth1_data.deposit_count

    state, new_pending_deposits = _prepare_eth1_bridge_deprecation(spec, state, [True, True, False])
    assert state.eth1_deposit_index < state.deposit_requests_start_index

    yield from run_process_pending_deposits(spec, state)

    # Eth1 bridge deposits were applied
    _check_pending_deposits_induced_new_validators(
        spec, state, pre_validator_count, new_pending_deposits[:2]
    )
    # deposit request was postponed and not processed
    assert state.pending_deposits == new_pending_deposits[2:]
    # deposit_balance_to_consume was reset to 0
    assert state.deposit_balance_to_consume == 0


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_eth1_bridge_transition_not_applied(spec, state):
    # There are pending Eth1 bridge deposits
    # state.eth1_deposit_index < state.deposit_requests_start_index
    pre_validator_count = len(state.validators)
    state.eth1_data.deposit_count = len(state.validators) + 3
    state.deposit_requests_start_index = state.eth1_data.deposit_count

    state, new_pending_deposits = _prepare_eth1_bridge_deprecation(spec, state, [False, True, True])
    assert state.eth1_deposit_index < state.deposit_requests_start_index

    yield from run_process_pending_deposits(spec, state)

    # no pending deposit was processed, however Eth1 bridge deposits induced new validators
    assert pre_validator_count + 2 == len(state.validators)
    assert state.pending_deposits == new_pending_deposits
    # deposit_balance_to_consume was reset to 0
    assert state.deposit_balance_to_consume == 0


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_eth1_bridge_transition_complete(spec, state):
    # There is no pending Eth1 bridge deposits
    # state.eth1_deposit_index == state.deposit_requests_start_index
    pre_validator_count = len(state.validators)
    state.eth1_data.deposit_count = len(state.validators) + 2
    state.deposit_requests_start_index = state.eth1_data.deposit_count

    state, new_pending_deposits = _prepare_eth1_bridge_deprecation(spec, state, [True, False, True])
    assert state.eth1_deposit_index == state.deposit_requests_start_index

    yield from run_process_pending_deposits(spec, state)

    # all deposits were applied
    assert state.pending_deposits == []
    _check_pending_deposits_induced_new_validators(
        spec, state, pre_validator_count, new_pending_deposits
    )
    # deposit_balance_to_consume was reset to 0
    assert state.deposit_balance_to_consume == 0


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_not_finalized(spec, state):
    # complete eth1 bridge transition
    state.deposit_requests_start_index = 0
    # advance state three epochs into the future
    for _ in range(0, 3):
        next_epoch_with_full_participation(spec, state)
    # create pending deposits
    pre_validator_count = len(state.validators)
    for index in range(0, 2):
        state.pending_deposits.append(
            prepare_pending_deposit(
                spec,
                validator_index=pre_validator_count + index,
                amount=spec.MIN_ACTIVATION_BALANCE,
                signed=True,
                slot=state.slot + index,
            )
        )
    new_pending_deposits = state.pending_deposits.copy()

    # finalize a slot before the slot of the first deposit
    advance_finality_to(spec, state, spec.get_current_epoch(state) - 1)

    # process pending deposits
    # the slot of the first deposit will be finalized before the call to process_pending_deposits
    set_full_participation(spec, state)
    _ensure_enough_churn_to_process_deposits(spec, state)

    yield from run_process_pending_deposits(spec, state)

    # deposit_balance_to_consume was reset to 0
    assert state.deposit_balance_to_consume == 0
    # second deposit was not processed as it hasn't been finalized
    assert state.pending_deposits == new_pending_deposits[1:]
    _check_pending_deposits_induced_new_validators(
        spec, state, pre_validator_count, new_pending_deposits[:1]
    )


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_limit_is_reached(spec, state):
    # set pending deposits to the maximum
    amount = spec.EFFECTIVE_BALANCE_INCREMENT * 1
    for i in range(spec.MAX_PENDING_DEPOSITS_PER_EPOCH + 2):
        wc = state.validators[i].withdrawal_credentials
        pd = prepare_pending_deposit(spec, i, amount, withdrawal_credentials=wc, signed=True)
        state.pending_deposits.append(pd)
    new_pending_deposits = state.pending_deposits.copy()

    # process pending deposits
    pre_balances = state.balances.copy()
    _ensure_enough_churn_to_process_deposits(spec, state)

    yield from run_process_pending_deposits(spec, state)

    # deposit_balance_to_consume was reset to 0
    assert state.deposit_balance_to_consume == 0
    # no deposits above limit were processed
    assert state.pending_deposits == new_pending_deposits[spec.MAX_PENDING_DEPOSITS_PER_EPOCH :]
    for i in range(spec.MAX_PENDING_DEPOSITS_PER_EPOCH):
        assert state.balances[i] == pre_balances[i] + amount
    for i in range(spec.MAX_PENDING_DEPOSITS_PER_EPOCH, spec.MAX_PENDING_DEPOSITS_PER_EPOCH + 2):
        assert state.balances[i] == pre_balances[i]


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_balance_equal_churn(spec, state):
    index = 0
    amount = spec.get_activation_exit_churn_limit(state)
    state.pending_deposits.append(prepare_pending_deposit(spec, index, amount))
    pre_balance = state.balances[index]

    yield from run_process_pending_deposits(spec, state)

    assert state.balances[index] == pre_balance + amount
    assert state.deposit_balance_to_consume == 0
    assert state.pending_deposits == []


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_balance_above_churn(spec, state):
    index = 0
    amount = spec.get_activation_exit_churn_limit(state) + 1
    state.pending_deposits.append(prepare_pending_deposit(spec, index, amount))
    pre_balance = state.balances[index]

    yield from run_process_pending_deposits(spec, state)

    # deposit was above churn, balance hasn't changed
    assert state.balances[index] == pre_balance
    # deposit balance to consume is the full churn limit
    wantedBalanceToConsume = spec.get_activation_exit_churn_limit(state)
    assert state.deposit_balance_to_consume == wantedBalanceToConsume
    # deposit is still in the queue
    assert state.pending_deposits == [prepare_pending_deposit(spec, index, amount)]


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_preexisting_churn(spec, state):
    index = 0
    amount = spec.EFFECTIVE_BALANCE_INCREMENT + 1
    state.deposit_balance_to_consume = 2 * amount
    state.pending_deposits.append(prepare_pending_deposit(spec, index, amount))
    pre_balance = state.balances[index]

    yield from run_process_pending_deposits(spec, state)

    # balance was deposited correctly
    assert state.balances[index] == pre_balance + amount
    # No leftover deposit balance to consume
    assert state.deposit_balance_to_consume == 0
    # queue emptied
    assert state.pending_deposits == []


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_multiple_pending_deposits_below_churn(spec, state):
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    state.pending_deposits.append(prepare_pending_deposit(spec, validator_index=0, amount=amount))
    state.pending_deposits.append(prepare_pending_deposit(spec, validator_index=1, amount=amount))
    pre_balances = state.balances.copy()

    yield from run_process_pending_deposits(spec, state)

    for i in [0, 1]:
        assert state.balances[i] == pre_balances[i] + amount
    # No leftover deposit balance to consume
    assert state.deposit_balance_to_consume == 0
    assert state.pending_deposits == []


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_multiple_pending_deposits_above_churn(spec, state):
    # set third deposit to be over the churn
    amount = (spec.get_activation_exit_churn_limit(state) // 3) + 1
    for i in [0, 1, 2]:
        state.pending_deposits.append(
            prepare_pending_deposit(spec, validator_index=i, amount=amount)
        )
    pre_balances = state.balances.copy()

    yield from run_process_pending_deposits(spec, state)

    # First two deposits are processed, third is not because above churn
    for i in [0, 1]:
        assert state.balances[i] == pre_balances[i] + amount
    assert state.balances[2] == pre_balances[2]
    # Only first two subtract from the deposit balance to consume
    assert (
        state.deposit_balance_to_consume == spec.get_activation_exit_churn_limit(state) - 2 * amount
    )
    # third deposit is still in the queue
    assert state.pending_deposits == [
        prepare_pending_deposit(spec, validator_index=2, amount=amount)
    ]


@with_electra_and_later
@spec_state_test
@always_bls
def test_process_pending_deposits_multiple_for_new_validator(spec, state):
    """
    - There are three pending deposits in the state, all pointing to the same public key.
    - The public key does not exist in the beacon state.
    - The first pending deposit has an invalid signature and should be ignored.
    - The second pending deposit has a valid signature and the validator should be created.
    - The third pending deposit has a valid signature and should be applied.
    """
    # A new validator, pubkey doesn't exist in the state
    validator_index = len(state.validators)
    amount = spec.EFFECTIVE_BALANCE_INCREMENT

    # Add pending deposits to the state
    # Provide different amounts so we can tell which were applied
    state.pending_deposits.append(
        prepare_pending_deposit(spec, validator_index, amount * 1, signed=False)
    )
    state.pending_deposits.append(
        prepare_pending_deposit(spec, validator_index, amount * 2, signed=True)
    )
    state.pending_deposits.append(
        prepare_pending_deposit(spec, validator_index, amount * 4, signed=True)
    )

    yield from run_process_pending_deposits(spec, state)

    # The second and third deposits were applied
    assert state.balances[validator_index] == amount * 6
    # No more pending deposits
    assert state.pending_deposits == []


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_skipped_deposit_exiting_validator(spec, state):
    index = 0
    amount = spec.MIN_ACTIVATION_BALANCE
    state.pending_deposits.append(
        prepare_pending_deposit(spec, validator_index=index, amount=amount)
    )
    pre_pending_deposits = state.pending_deposits.copy()
    pre_balance = state.balances[index]
    # Initiate the validator's exit
    spec.initiate_validator_exit(state, index)

    yield from run_process_pending_deposits(spec, state)

    # Deposit is skipped because validator is exiting
    assert state.balances[index] == pre_balance
    # All deposits either processed or postponed
    assert state.deposit_balance_to_consume == 0
    # The deposit is still in the queue
    assert state.pending_deposits == pre_pending_deposits


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_multiple_skipped_deposits_exiting_validators(spec, state):
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    for i in [0, 1, 2]:
        # Append pending deposit for validator i
        state.pending_deposits.append(
            prepare_pending_deposit(spec, validator_index=i, amount=amount)
        )

        # Initiate the exit of validator i
        spec.initiate_validator_exit(state, i)
    pre_pending_deposits = state.pending_deposits.copy()
    pre_balances = state.balances.copy()

    yield from run_process_pending_deposits(spec, state)

    # All deposits are postponed, no balance changes
    assert state.balances == pre_balances
    # All deposits are postponed, no leftover deposit balance to consume
    assert state.deposit_balance_to_consume == 0
    # All deposits still in the queue, in the same order
    assert state.pending_deposits == pre_pending_deposits


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_multiple_pending_one_skipped(spec, state):
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    for i in [0, 1, 2]:
        state.pending_deposits.append(
            prepare_pending_deposit(spec, validator_index=i, amount=amount)
        )
    pre_balances = state.balances.copy()
    # Initiate the second validator's exit
    spec.initiate_validator_exit(state, 1)

    yield from run_process_pending_deposits(spec, state)

    # First and last deposit are processed, second is not because of exiting
    for i in [0, 2]:
        assert state.balances[i] == pre_balances[i] + amount
    assert state.balances[1] == pre_balances[1]
    # All deposits either processed or postponed
    assert state.deposit_balance_to_consume == 0
    # second deposit is still in the queue
    assert state.pending_deposits == [
        prepare_pending_deposit(spec, validator_index=1, amount=amount)
    ]


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_mixture_of_skipped_and_above_churn(spec, state):
    amount1 = spec.EFFECTIVE_BALANCE_INCREMENT
    amount2 = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    # First two validators have small deposit, third validators a large one
    for i in [0, 1]:
        state.pending_deposits.append(
            prepare_pending_deposit(spec, validator_index=i, amount=amount1)
        )
    state.pending_deposits.append(prepare_pending_deposit(spec, validator_index=2, amount=amount2))
    pre_balances = state.balances.copy()
    # Initiate the second validator's exit
    spec.initiate_validator_exit(state, 1)

    yield from run_process_pending_deposits(spec, state)

    # First deposit is processed
    assert state.balances[0] == pre_balances[0] + amount1
    # Second deposit is postponed, third is above churn
    for i in [1, 2]:
        assert state.balances[i] == pre_balances[i]
    # First deposit consumes some deposit balance
    # Deposit is not processed
    wanted_balance = spec.get_activation_exit_churn_limit(state) - amount1
    assert state.deposit_balance_to_consume == wanted_balance
    # second and third deposit still in the queue
    assert state.pending_deposits == [
        prepare_pending_deposit(spec, validator_index=2, amount=amount2),
        prepare_pending_deposit(spec, validator_index=1, amount=amount1),
    ]


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_withdrawable_validator(spec, state):
    index = 0
    amount = spec.MIN_ACTIVATION_BALANCE
    state.pending_deposits.append(
        prepare_pending_deposit(spec, validator_index=index, amount=amount)
    )
    pre_balance = state.balances[index]
    # Initiate the validator's exit
    spec.initiate_validator_exit(state, index)
    # Set epoch to withdrawable epoch + 1 to allow processing of the deposit
    withdrawable_epoch = state.validators[index].withdrawable_epoch
    state.slot = spec.SLOTS_PER_EPOCH * (withdrawable_epoch + 1)

    yield from run_process_pending_deposits(spec, state)

    # Deposit is correctly processed
    assert state.balances[index] == pre_balance + amount
    # No leftover deposit balance to consume
    assert state.deposit_balance_to_consume == 0
    assert state.pending_deposits == []


@with_electra_and_later
@spec_state_test
def test_process_pending_deposits_withdrawable_validator_not_churned(spec, state):
    amount = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    for i in [0, 1]:
        state.pending_deposits.append(
            prepare_pending_deposit(spec, validator_index=i, amount=amount)
        )
    pre_balances = state.balances.copy()
    # Initiate the first validator's exit
    spec.initiate_validator_exit(state, 0)
    # Set epoch to withdrawable epoch + 1 to allow processing of the deposit
    withdraw_epoch = state.validators[0].withdrawable_epoch
    state.slot = spec.SLOTS_PER_EPOCH * (withdraw_epoch + 1)
    # Don't use run_epoch_processing_with to avoid penalties being applied
    yield "pre", state
    spec.process_pending_deposits(state)
    yield "post", state
    # First deposit is processed though above churn limit
    assert state.balances[0] == pre_balances[0] + amount
    # Second deposit is not processed because above churn
    assert state.balances[1] == pre_balances[1]
    # Second deposit is not processed
    # First deposit does not consume any.
    wanted_limit = spec.get_activation_exit_churn_limit(state)
    assert state.deposit_balance_to_consume == wanted_limit
    assert state.pending_deposits == [
        prepare_pending_deposit(spec, validator_index=1, amount=amount)
    ]


@with_electra_and_later
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_process_pending_deposits_scaled_churn(spec, state):
    index = 0
    amount = spec.get_activation_exit_churn_limit(state)
    state.pending_deposits.append(prepare_pending_deposit(spec, index, amount))
    pre_balance = state.balances[index]

    yield from run_process_pending_deposits(spec, state)

    assert state.balances[index] == pre_balance + amount
    assert state.deposit_balance_to_consume == 0
    assert state.pending_deposits == []
