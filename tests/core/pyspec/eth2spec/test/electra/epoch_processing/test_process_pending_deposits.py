from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with
from eth2spec.test.context import (
    spec_state_test,
    with_electra_and_later,
)
from eth2spec.test.helpers.deposits import (
    build_pending_deposit_top_up,
)
from tests.core.pyspec.eth2spec.test.helpers.deposits import build_deposit_data
from eth2spec.test.helpers.state import next_epoch_via_block

from eth2spec.test.helpers.keys import privkeys, pubkeys


def run_process_pending_deposits(spec, state):
    yield from run_epoch_processing_with(
        spec, state, 'process_pending_deposits')


@with_electra_and_later
@spec_state_test
def test_pending_deposit_over_max(spec, state):
    # pick an amount that adds to less than churn limit
    amount = 100
    overmax = spec.MAX_PENDING_DEPOSITS_PER_EPOCH_PROCESSING + 1
    for i in range(overmax):
        state.pending_deposits.append(
            spec.PendingDeposit(
                pubkey=state.validators[i].pubkey,
                withdrawal_credentials=(
                    state.validators[i].withdrawal_credentials
                ),
                amount=amount,
                slot=spec.GENESIS_SLOT,
            )
        )
    assert len(state.pending_deposits) == overmax, \
        "pending deposits is not overmax"
    # the remaining deposit over MAX_PENDING_DEPOSITS_PER_EPOCH_PROCESSING
    # should remain in pending_deposits
    yield from run_process_pending_deposits(spec, state)
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
    # set deposit_requests_start_index to something high
    state.deposit_requests_start_index = 100000000000000000
    # set deposit_balance_to_consume to some initial amount
    state.deposit_balance_to_consume = amount
    yield from run_process_pending_deposits(spec, state)
    # deposit_balance_to_consume was reset to 0
    assert state.deposit_balance_to_consume == 0
    # deposit was postponed and not processed
    assert len(state.pending_deposits) == 1


@with_electra_and_later
@spec_state_test
def test_pending_deposit_not_finalized(spec, state):
    amount = spec.MIN_ACTIVATION_BALANCE
    # set slot to something not finalized
    # deposit is not finalized yet, so it is postponed
    state.pending_deposits.append(spec.PendingDeposit(
        pubkey=state.validators[0].pubkey,
        withdrawal_credentials=state.validators[0].withdrawal_credentials,
        amount=amount,
        slot=spec.get_current_epoch(state) + 1,
    ))
    # skip the bridge validation
    state.deposit_requests_start_index = 0
    # set deposit_balance_to_consume to some initial amount
    state.deposit_balance_to_consume = amount
    yield from run_process_pending_deposits(spec, state)
    # deposit_balance_to_consume was reset to 0
    assert state.deposit_balance_to_consume == 0
    # deposit was postponed and not processed
    assert len(state.pending_deposits) == 1


@with_electra_and_later
@spec_state_test
def test_pending_deposit_validator_withdrawn(spec, state):
    amount = spec.MIN_ACTIVATION_BALANCE
    index = 0
    withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX +
        spec.hash(pubkeys[index])[1:]
    )
    compounding_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX +
        spec.hash(pubkeys[index])[1:]
    )
    # advance the state
    next_epoch_via_block(spec, state)
    state.validators[index].withdrawal_credentials = withdrawal_credentials
    previous_epoch = spec.get_current_epoch(state) - 1
    # set validator to be exited by current epoch
    state.validators[index].exit_epoch = previous_epoch
    # set validator to be withdrawable by current epoch
    state.validators[index].withdrawable_epoch = previous_epoch
    deposit_data = build_deposit_data(spec,
                                      pubkeys[index],
                                      privkeys[index],
                                      amount,
                                      compounding_credentials,
                                      signed=True)
    # set withdrawal credentials to compounding but should not switch since
    # validator is already withdrawing
    state.pending_deposits.append(spec.PendingDeposit(
        pubkey=pubkeys[index],
        withdrawal_credentials=compounding_credentials,
        amount=amount,
        slot=spec.GENESIS_SLOT,
        signature=deposit_data.signature,
    ))
    # skip the bridge validation
    state.deposit_requests_start_index = 0
    # set deposit_balance_to_consume to some initial amount
    state.deposit_balance_to_consume = amount
    # reset balance for assert
    state.balances[0] = 0
    old_validator_count = len(state.validators)
    yield from run_process_pending_deposits(spec, state)
    btc = state.deposit_balance_to_consume
    # deposit_balance_to_consume was reset to 0
    assert btc == 0
    # deposit was processed
    assert state.pending_deposits == []
    # balance increases because of withdraw
    assert state.balances[0] == amount
    # churn limit was not reached
    assert not amount > spec.get_activation_exit_churn_limit(state)
    # validator count should stay the same
    assert len(state.validators) == old_validator_count


@with_electra_and_later
@spec_state_test
def test_pending_deposit_validator_exiting_but_not_withdrawn(spec, state):
    amount = spec.MIN_ACTIVATION_BALANCE
    hash = spec.hash(state.validators[0].pubkey)[1:]
    withdrawal_credentials = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + hash
    # advance the state
    next_epoch_via_block(spec, state)
    state.validators[0].withdrawal_credentials = withdrawal_credentials
    # set validator to be withdrawable by current epoch
    state.validators[0].exit_epoch = spec.get_current_epoch(state) - 1
    state.validators[0].withdrawable_epoch = spec.FAR_FUTURE_EPOCH
    state.pending_deposits.append(spec.PendingDeposit(
        pubkey=state.validators[0].pubkey,
        withdrawal_credentials=state.validators[0].withdrawal_credentials,
        amount=amount,
        slot=spec.GENESIS_SLOT,
    ))
    # skip the bridge validation
    state.deposit_requests_start_index = 0
    # set deposit_balance_to_consume to some initial amount
    state.deposit_balance_to_consume = amount

    yield from run_process_pending_deposits(spec, state)
    # deposit_balance_to_consume was reset to 0
    assert state.deposit_balance_to_consume == 0
    # deposit was postponed and not processed
    assert len(state.pending_deposits) == 1


@with_electra_and_later
@spec_state_test
def test_pending_deposit_not_in_validator_set(spec, state):
    index = 2000
    amount = spec.MIN_ACTIVATION_BALANCE
    withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX +
        spec.hash(pubkeys[index])[1:]
    )
    deposit_data = build_deposit_data(spec,
                                      pubkeys[index],
                                      privkeys[index],
                                      amount,
                                      withdrawal_credentials,
                                      signed=True)
    state.pending_deposits.append(spec.PendingDeposit(
        pubkey=pubkeys[index],
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
        slot=spec.GENESIS_SLOT,
        signature=deposit_data.signature,
    ))
    value_error = False
    try:
        yield from run_process_pending_deposits(spec, state)
    except ValueError:
        value_error = True

    assert value_error


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
    # No leftover deposit balance to consume
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
def test_pending_deposit_balance_equal_churn_with_compounding(spec, state):
    index = 0
    withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX +
        spec.hash(pubkeys[index])[1:]
    )
    compounding_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX +
        spec.hash(pubkeys[index])[1:]
    )
    amount = spec.get_activation_exit_churn_limit(state)
    state.validators[index].withdrawal_credentials = withdrawal_credentials
    deposit_data = build_deposit_data(spec,
                                      pubkeys[index],
                                      privkeys[index],
                                      amount,
                                      compounding_credentials,
                                      signed=True)
    # set withdrawal credentials to compounding but should not switch since
    # validator is already withdrawing
    state.pending_deposits.append(spec.PendingDeposit(
        pubkey=pubkeys[index],
        withdrawal_credentials=compounding_credentials,
        amount=amount,
        slot=spec.GENESIS_SLOT,
        signature=deposit_data.signature,
    ))
    pre_balance = state.balances[index]

    yield from run_process_pending_deposits(spec, state)

    assert state.balances[index] == pre_balance + amount
    assert state.deposit_balance_to_consume == 0
    assert state.pending_deposits == []
    current_credentials = state.validators[0].withdrawal_credentials
    # validator is not exited, so it should not switch to compounding
    assert current_credentials == withdrawal_credentials


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
    wantedBalanceToConsume = spec.get_activation_exit_churn_limit(state)
    assert state.deposit_balance_to_consume == wantedBalanceToConsume
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
    # No leftover deposit balance to consume
    assert state.deposit_balance_to_consume == 0
    # queue emptied
    assert state.pending_deposits == []


@with_electra_and_later
@spec_state_test
def test_multiple_pending_deposits_below_churn(spec, state):
    amount = 10**9
    state.pending_deposits.append(
        build_pending_deposit_top_up(spec, state,
                                     validator_index=0, amount=amount)
    )
    state.pending_deposits.append(
        build_pending_deposit_top_up(spec, state,
                                     validator_index=1, amount=amount)
    )
    pre_balances = state.balances.copy()

    yield from run_process_pending_deposits(spec, state)

    for i in [0, 1]:
        assert state.balances[i] == pre_balances[i] + amount
    # No leftover deposit balance to consume
    assert state.deposit_balance_to_consume == 0
    assert state.pending_deposits == []


@with_electra_and_later
@spec_state_test
def test_multiple_pending_deposits_above_churn(spec, state):
    # set third deposit to be over the churn
    amount = (spec.get_activation_exit_churn_limit(state) // 3) + 1
    for i in [0, 1, 2]:
        state.pending_deposits.append(
            build_pending_deposit_top_up(spec, state,
                                         validator_index=i, amount=amount)
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
        build_pending_deposit_top_up(spec, state,
                                     validator_index=2, amount=amount)
    ]


@with_electra_and_later
@spec_state_test
def test_skipped_deposit_exiting_validator(spec, state):
    index = 0
    amount = spec.MIN_ACTIVATION_BALANCE
    state.pending_deposits.append(
        build_pending_deposit_top_up(spec, state,
                                     validator_index=index, amount=amount)
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
def test_multiple_skipped_deposits_exiting_validators(spec, state):
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    for i in [0, 1, 2]:
        # Append pending deposit for validator i
        state.pending_deposits.append(
            build_pending_deposit_top_up(spec, state,
                                         validator_index=i, amount=amount)
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
def test_multiple_pending_one_skipped(spec, state):
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    for i in [0, 1, 2]:
        state.pending_deposits.append(
            build_pending_deposit_top_up(spec, state,
                                         validator_index=i, amount=amount)
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
        build_pending_deposit_top_up(spec, state,
                                     validator_index=1, amount=amount)
    ]


@with_electra_and_later
@spec_state_test
def test_mixture_of_skipped_and_above_churn(spec, state):
    amount01 = spec.EFFECTIVE_BALANCE_INCREMENT
    amount2 = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    # First two validators have small deposit, third validators a large one
    for i in [0, 1]:
        state.pending_deposits.append(
            build_pending_deposit_top_up(spec, state,
                                         validator_index=i,
                                         amount=amount01)
        )
    state.pending_deposits.append(
        build_pending_deposit_top_up(spec, state,
                                     validator_index=2,
                                     amount=amount2)
    )
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
    # Deposit is not processed
    wanted_balance = spec.get_activation_exit_churn_limit(state) - amount01
    assert state.deposit_balance_to_consume == wanted_balance
    # second and third deposit still in the queue
    assert state.pending_deposits == [
        build_pending_deposit_top_up(spec, state,
                                     validator_index=2, amount=amount2),
        build_pending_deposit_top_up(spec, state,
                                     validator_index=1, amount=amount01)
    ]


@with_electra_and_later
@spec_state_test
def test_processing_deposit_of_withdrawable_validator(spec, state):
    index = 0
    amount = spec.MIN_ACTIVATION_BALANCE
    state.pending_deposits.append(
        build_pending_deposit_top_up(spec, state,
                                     validator_index=index,
                                     amount=amount)
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
def test_processing_deposit_of_withdrawable_validator_not_churned(spec, state):
    amount = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    for i in [0, 1]:
        state.pending_deposits.append(
            build_pending_deposit_top_up(spec, state,
                                         validator_index=i, amount=amount)
        )
    pre_balances = state.balances.copy()
    # Initiate the first validator's exit
    spec.initiate_validator_exit(state, 0)
    # Set epoch to withdrawable epoch + 1 to allow processing of the deposit
    withdraw_epoch = state.validators[0].withdrawable_epoch
    state.slot = spec.SLOTS_PER_EPOCH * (withdraw_epoch + 1)
    # Don't use run_epoch_processing_with to avoid penalties being applied
    yield 'pre', state
    spec.process_pending_deposits(state)
    yield 'post', state
    # First deposit is processed though above churn limit
    assert state.balances[0] == pre_balances[0] + amount
    # Second deposit is not processed because above churn
    assert state.balances[1] == pre_balances[1]
    # Second deposit is not processed
    # First deposit does not consume any.
    wanted_limit = spec.get_activation_exit_churn_limit(state)
    assert state.deposit_balance_to_consume == wanted_limit
    assert state.pending_deposits == [
        build_pending_deposit_top_up(spec, state,
                                     validator_index=1, amount=amount)
    ]
