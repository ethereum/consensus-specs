from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with
from eth2spec.test.context import (
    spec_state_test,
    with_electra_and_later,
)
from eth2spec.test.helpers.deposits import (
    build_pending_deposit_top_up,
)


def run_process_pending_deposits(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_pending_deposits')

@with_electra_and_later
@spec_state_test
def test_pending_deposit_over_max(spec, state):
    # pick an amount that adds to less than churn limit
    amount = 100 
    overmax = spec.MAX_PENDING_DEPOSITS_PER_EPOCH_PROCESSING + 1
    for i in range(overmax):
        state.pending_deposits.append(spec.PendingDeposit(
        pubkey=state.validators[i].pubkey,
        withdrawal_credentials=state.validators[i].withdrawal_credentials,
        amount=amount,
        slot=spec.GENESIS_SLOT,
        ))
    assert len(state.pending_deposits) == overmax,"pending deposits is not over max"
    yield from run_process_pending_deposits(spec, state)
    # the remaining deposit over MAX_PENDING_DEPOSITS_PER_EPOCH_PROCESSING should remain in pending_deposits
    assert len(state.pending_deposits) == 1

@with_electra_and_later
@spec_state_test
def test_pending_deposit_eth1_bridge_not_applied(spec, state):
    amount = spec.MIN_ACTIVATION_BALANCE
    # deposit is not finalized yet, so it is postponed
    state.pending_deposits.append(spec.PendingDeposit(
        pubkey=state.validators[0].pubkey,
        withdrawal_credentials=state.validators[0].withdrawal_credentials,
        amount=amount,
        slot=1,
    ))
    # set deposit_requests_start_index to something high so that deposit is not processed
    state.deposit_requests_start_index = 100000000000000000
    # set deposit_balance_to_consume to some initial amount to see its removal later on in the test
    state.deposit_balance_to_consume = amount
    yield from run_process_pending_deposits(spec, state)
    # deposit_balance_to_consume was reset to 0
    assert state.deposit_balance_to_consume == 0
    # deposit was postponed and not processed
    assert len(state.pending_deposits) == 1


@with_electra_and_later
@spec_state_test
def test_pending_deposit_deposit_not_finalized(spec, state):
    amount = spec.MIN_ACTIVATION_BALANCE
    # set slot to something not finalized
    slot=spec.compute_start_slot_at_epoch(state.finalized_checkpoint.epoch+1)
    # deposit is not finalized yet, so it is postponed
    state.pending_deposits.append(spec.PendingDeposit(
        pubkey=state.validators[0].pubkey,
        withdrawal_credentials=state.validators[0].withdrawal_credentials,
        amount=amount,
        slot=slot,
    ))
    # set deposit_requests_start_index to something low so that we skip the bridge validation
    state.deposit_requests_start_index = 0
    print("deposit indexes",state.eth1_deposit_index,state.deposit_requests_start_index)
    # set deposit_balance_to_consume to some initial amount to see its removal later on in the test
    state.deposit_balance_to_consume = amount
    yield from run_process_pending_deposits(spec, state)
    # deposit_balance_to_consume was reset to 0
    assert state.deposit_balance_to_consume == 0
    # deposit was postponed and not processed
    assert len(state.pending_deposits) == 1



@with_electra_and_later
@spec_state_test
def test_pending_deposit_min_activation_balance(spec, state):
    index = 0
    amount = spec.MIN_ACTIVATION_BALANCE
    state.pending_deposits.append(
        build_pending_deposit_top_up(spec, state, index, amount)
    )
    pre_balance = state.balances[index]

    yield from run_process_pending_deposits(spec, state)

    assert state.balances[index] == pre_balance + amount
    # No leftover deposit balance to consume when there are no deposits left to process
    assert state.deposit_balance_to_consume == 0
    assert state.pending_deposits == []


@with_electra_and_later
@spec_state_test
def test_pending_deposit_balance_equal_churn(spec, state):
    index = 0
    amount = spec.get_activation_exit_churn_limit(state)
    state.pending_deposits.append(
        build_pending_deposit_top_up(spec, state, index, amount)
    )
    pre_balance = state.balances[index]

    yield from run_process_pending_deposits(spec, state)

    assert state.balances[index] == pre_balance + amount
    assert state.deposit_balance_to_consume == 0
    assert state.pending_deposits == []


@with_electra_and_later
@spec_state_test
def test_pending_deposit_balance_above_churn(spec, state):
    index = 0
    amount = spec.get_activation_exit_churn_limit(state) + 1
    state.pending_deposits.append(
        build_pending_deposit_top_up(spec, state, index, amount)
    )
    pre_balance = state.balances[index]

    yield from run_process_pending_deposits(spec, state)

    # deposit was above churn, balance hasn't changed
    assert state.balances[index] == pre_balance
    # deposit balance to consume is the full churn limit
    assert state.deposit_balance_to_consume == spec.get_activation_exit_churn_limit(
        state
    )
    # deposit is still in the queue
    assert state.pending_deposits == [
        build_pending_deposit_top_up(spec, state, index, amount)
    ]


@with_electra_and_later
@spec_state_test
def test_pending_deposit_preexisting_churn(spec, state):
    index = 0
    amount = 10**9 + 1
    state.deposit_balance_to_consume = 2 * amount
    state.pending_deposits.append(
        build_pending_deposit_top_up(spec, state, index, amount)
    )
    pre_balance = state.balances[index]

    yield from run_process_pending_deposits(spec, state)

    # balance was deposited correctly
    assert state.balances[index] == pre_balance + amount
    # No leftover deposit balance to consume when there are no deposits left to process
    assert state.deposit_balance_to_consume == 0
    # queue emptied
    assert state.pending_deposits == []


@with_electra_and_later
@spec_state_test
def test_multiple_pending_deposits_below_churn(spec, state):
    amount = 10**9
    state.pending_deposits.append(
        build_pending_deposit_top_up(spec, state, validator_index=0, amount=amount)
    )
    state.pending_deposits.append(
        build_pending_deposit_top_up(spec, state, validator_index=1, amount=amount)
    )
    pre_balances = state.balances.copy()

    yield from run_process_pending_deposits(spec, state)

    for i in [0, 1]:
        assert state.balances[i] == pre_balances[i] + amount
    # No leftover deposit balance to consume when there are no deposits left to process
    assert state.deposit_balance_to_consume == 0
    assert state.pending_deposits == []


@with_electra_and_later
@spec_state_test
def test_multiple_pending_deposits_above_churn(spec, state):
    # set third deposit to be over the churn
    amount = (spec.get_activation_exit_churn_limit(state) // 3) + 1
    for i in [0, 1, 2]:
        state.pending_deposits.append(
            build_pending_deposit_top_up(spec, state, validator_index=i, amount=amount)
        )
    pre_balances = state.balances.copy()

    yield from run_process_pending_deposits(spec, state)

    # First two deposits are processed, third is not because above churn
    for i in [0, 1]:
        assert state.balances[i] == pre_balances[i] + amount
    assert state.balances[2] == pre_balances[2]
    # Only first two subtract from the deposit balance to consume
    assert (
        state.deposit_balance_to_consume
        == spec.get_activation_exit_churn_limit(state) - 2 * amount
    )
    # third deposit is still in the queue
    assert state.pending_deposits == [
        build_pending_deposit_top_up(spec, state, validator_index=2, amount=amount)
    ]


@with_electra_and_later
@spec_state_test
def test_skipped_deposit_exiting_validator(spec, state):
    index = 0
    amount = spec.MIN_ACTIVATION_BALANCE
    state.pending_deposits.append(build_pending_deposit_top_up(spec, state, validator_index=index, amount=amount))
    pre_pending_deposits = state.pending_deposits.copy()
    pre_balance = state.balances[index]
    # Initiate the validator's exit
    spec.initiate_validator_exit(state, index)

    yield from run_process_pending_deposits(spec, state)

    # Deposit is skipped because validator is exiting
    assert state.balances[index] == pre_balance
    # All deposits either processed or postponed, no leftover deposit balance to consume
    assert state.deposit_balance_to_consume == 0
    # The deposit is still in the queue
    assert state.pending_deposits == pre_pending_deposits


@with_electra_and_later
@spec_state_test
def test_multiple_skipped_deposits_exiting_validators(spec, state):
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    for i in [0, 1, 2]:
        # Append pending deposit for validator i
        state.pending_deposits.append(build_pending_deposit_top_up(spec, state, validator_index=i, amount=amount))

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
def test_multiple_pending_one_skipped(spec, state):
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    for i in [0, 1, 2]:
        state.pending_deposits.append(build_pending_deposit_top_up(spec, state, validator_index=i, amount=amount))
    pre_balances = state.balances.copy()
    # Initiate the second validator's exit
    spec.initiate_validator_exit(state, 1)

    yield from run_process_pending_deposits(spec, state)

    # First and last deposit are processed, second is not because of exiting
    for i in [0, 2]:
        assert state.balances[i] == pre_balances[i] + amount
    assert state.balances[1] == pre_balances[1]
    # All deposits either processed or postponed, no leftover deposit balance to consume
    assert state.deposit_balance_to_consume == 0
    # second deposit is still in the queue
    assert state.pending_deposits == [build_pending_deposit_top_up(spec, state, validator_index=1, amount=amount)]


@with_electra_and_later
@spec_state_test
def test_mixture_of_skipped_and_above_churn(spec, state):
    amount01 = spec.EFFECTIVE_BALANCE_INCREMENT
    amount2 = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    # First two validators have small deposit, third validators a large one
    for i in [0, 1]:
        state.pending_deposits.append(build_pending_deposit_top_up(spec, state, validator_index=i, amount=amount01))
    state.pending_deposits.append(build_pending_deposit_top_up(spec, state, validator_index=2, amount=amount2))
    pre_balances = state.balances.copy()
    # Initiate the second validator's exit
    spec.initiate_validator_exit(state, 1)

    yield from run_process_pending_deposits(spec, state)

    # First deposit is processed
    assert state.balances[0] == pre_balances[0] + amount01
    # Second deposit is postponed, third is above churn
    for i in [1, 2]:
        assert state.balances[i] == pre_balances[i]
    # First deposit consumes some deposit balance
    # Deposit balance to consume is not reset because third deposit is not processed
    assert state.deposit_balance_to_consume == spec.get_activation_exit_churn_limit(state) - amount01
    # second and third deposit still in the queue, but second is appended at the end
    assert state.pending_deposits == [build_pending_deposit_top_up(spec, state, validator_index=2, amount=amount2),
                                      build_pending_deposit_top_up(spec, state, validator_index=1, amount=amount01)]


@with_electra_and_later
@spec_state_test
def test_processing_deposit_of_withdrawable_validator(spec, state):
    index = 0
    amount = spec.MIN_ACTIVATION_BALANCE
    state.pending_deposits.append(build_pending_deposit_top_up(spec, state, validator_index=index, amount=amount))
    pre_balance = state.balances[index]
    # Initiate the validator's exit
    spec.initiate_validator_exit(state, index)
    # Set epoch to withdrawable epoch + 1 to allow processing of the deposit
    state.slot = spec.SLOTS_PER_EPOCH * (state.validators[index].withdrawable_epoch + 1)

    yield from run_process_pending_deposits(spec, state)

    # Deposit is correctly processed
    assert state.balances[index] == pre_balance + amount
    # No leftover deposit balance to consume when there are no deposits left to process
    assert state.deposit_balance_to_consume == 0
    assert state.pending_deposits == []


@with_electra_and_later
@spec_state_test
def test_processing_deposit_of_withdrawable_validator_does_not_get_churned(spec, state):
    amount = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    for i in [0, 1]:
        state.pending_deposits.append(build_pending_deposit_top_up(spec, state, validator_index=i, amount=amount))
    pre_balances = state.balances.copy()
    # Initiate the first validator's exit
    spec.initiate_validator_exit(state, 0)
    # Set epoch to withdrawable epoch + 1 to allow processing of the deposit
    state.slot = spec.SLOTS_PER_EPOCH * (state.validators[0].withdrawable_epoch + 1)
    # Don't use run_epoch_processing_with to avoid penalties being applied
    yield 'pre', state
    spec.process_pending_deposits(state)
    yield 'post', state
    # First deposit is processed though above churn limit, because validator is withdrawable
    assert state.balances[0] == pre_balances[0] + amount
    # Second deposit is not processed because above churn
    assert state.balances[1] == pre_balances[1]
    # Second deposit is not processed, so there's leftover deposit balance to consume.
    # First deposit does not consume any.
    assert state.deposit_balance_to_consume == spec.get_activation_exit_churn_limit(state)
    assert state.pending_deposits == [build_pending_deposit_top_up(spec, state, validator_index=1, amount=amount)]
