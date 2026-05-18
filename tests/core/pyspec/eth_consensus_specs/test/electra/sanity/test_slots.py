from eth_consensus_specs.test.context import (
    spec_state_test,
    with_electra_and_later,
)
from eth_consensus_specs.test.helpers.deposits import prepare_pending_deposit
from eth_consensus_specs.test.helpers.state import transition_to


def run_epoch_processing(spec, state, pending_deposits=None, pending_consolidations=None):
    if pending_deposits is None:
        pending_deposits = []
    if pending_consolidations is None:
        pending_consolidations = []
    # Transition to the last slot of the epoch
    slot = state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH) - 1
    transition_to(spec, state, slot)
    state.pending_deposits = pending_deposits
    state.pending_consolidations = pending_consolidations
    yield "pre", state
    yield "slots", 1
    spec.process_slots(state, state.slot + 1)
    yield "post", state

    assert state.pending_deposits == []
    assert state.pending_consolidations == []


@with_electra_and_later
@spec_state_test
def test_pending_deposit_extra_gwei(spec, state):
    # Deposit where the amount has a little extra gwei
    index = len(state.validators)
    deposit = prepare_pending_deposit(
        spec,
        validator_index=index,
        # The deposit amount includes some gwei (the +1 at the end)
        amount=spec.MIN_ACTIVATION_BALANCE + spec.Gwei(1),
        signed=True,
    )

    yield from run_epoch_processing(spec, state, pending_deposits=[deposit])

    # Check deposit balance is applied correctly
    assert state.balances[index] == deposit.amount
    assert state.validators[index].effective_balance == spec.MIN_ACTIVATION_BALANCE


@with_electra_and_later
@spec_state_test
def test_multiple_pending_deposits_same_pubkey(spec, state):
    # Create multiple deposits with the same pubkey
    index = len(state.validators)
    deposit = prepare_pending_deposit(
        spec, validator_index=index, amount=spec.MIN_ACTIVATION_BALANCE, signed=True
    )
    pending_deposits = [deposit, deposit]

    yield from run_epoch_processing(spec, state, pending_deposits=pending_deposits)

    # Check deposit balance is applied correctly
    assert state.balances[index] == sum(d.amount for d in pending_deposits)
    assert state.validators[index].effective_balance == spec.MIN_ACTIVATION_BALANCE


@with_electra_and_later
@spec_state_test
def test_multiple_pending_deposits_same_pubkey_different_signature(spec, state):
    # Create multiple deposits with the same pubkey, but only the first has a valid signature
    index = len(state.validators)

    # First deposit with valid signature
    deposit0 = prepare_pending_deposit(
        spec, validator_index=index, amount=spec.MIN_ACTIVATION_BALANCE // 2, signed=True
    )

    # Second deposit without signature
    deposit1 = prepare_pending_deposit(
        spec, validator_index=index, amount=spec.MIN_ACTIVATION_BALANCE // 2, signed=False
    )

    pending_deposits = [deposit0, deposit1]

    yield from run_epoch_processing(spec, state, pending_deposits=pending_deposits)

    # Check that both deposits are accepted
    assert state.balances[index] == deposit0.amount + deposit1.amount
    assert state.validators[index].effective_balance == spec.MIN_ACTIVATION_BALANCE


@with_electra_and_later
@spec_state_test
def test_multiple_pending_deposits_same_pubkey_compounding(spec, state):
    # Create multiple deposits with the same pubkey and compounding creds
    index = len(state.validators)
    deposit = prepare_pending_deposit(
        spec,
        validator_index=index,
        amount=spec.MIN_ACTIVATION_BALANCE,
        signed=True,
        withdrawal_credentials=(spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20),
    )
    pending_deposits = [deposit, deposit]

    yield from run_epoch_processing(spec, state, pending_deposits=pending_deposits)

    # Check deposit balance is applied correctly
    assert state.balances[index] == sum(d.amount for d in pending_deposits)
    assert state.validators[index].effective_balance == state.balances[index]


@with_electra_and_later
@spec_state_test
def test_multiple_pending_deposits_same_pubkey_below_upward_threshold(spec, state):
    # Create multiple deposits with top up lower than the upward threshold
    index = len(state.validators)
    deposit_0 = prepare_pending_deposit(
        spec,
        validator_index=index,
        amount=(spec.MIN_ACTIVATION_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT),
        signed=True,
    )
    deposit_1 = prepare_pending_deposit(
        spec, validator_index=index, amount=spec.EFFECTIVE_BALANCE_INCREMENT, signed=True
    )
    pending_deposits = [deposit_0, deposit_1]

    yield from run_epoch_processing(spec, state, pending_deposits=pending_deposits)

    # Check deposit balance is applied correctly
    assert state.balances[index] == sum(d.amount for d in pending_deposits)
    assert state.validators[index].effective_balance == deposit_0.amount


@with_electra_and_later
@spec_state_test
def test_multiple_pending_deposits_same_pubkey_above_upward_threshold(spec, state):
    # Create multiple deposits with top up greater than the upward threshold
    index = len(state.validators)
    deposit_0 = prepare_pending_deposit(
        spec,
        validator_index=index,
        amount=(spec.MIN_ACTIVATION_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT),
        signed=True,
    )
    amount = (
        spec.EFFECTIVE_BALANCE_INCREMENT
        // spec.HYSTERESIS_QUOTIENT
        * spec.HYSTERESIS_UPWARD_MULTIPLIER
        + 1
    )
    deposit_1 = prepare_pending_deposit(spec, validator_index=index, amount=amount, signed=True)
    pending_deposits = [deposit_0, deposit_1]

    yield from run_epoch_processing(spec, state, pending_deposits)

    # Check deposit balance is applied correctly
    balance = state.balances[index]
    assert balance == sum(d.amount for d in pending_deposits)
    assert (
        state.validators[index].effective_balance
        == balance - balance % spec.EFFECTIVE_BALANCE_INCREMENT
    )


@with_electra_and_later
@spec_state_test
def test_pending_consolidation(spec, state):
    # Create pending consolidation
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    # Set withdrawable epoch to current epoch to allow processing
    state.validators[source_index].withdrawable_epoch = current_epoch
    # Set the source withdrawal credential to eth1
    state.validators[source_index].withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    )
    # Set the target withdrawal credential to compounding
    state.validators[target_index].withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    )
    pending_consolidations = [
        spec.PendingConsolidation(source_index=source_index, target_index=target_index)
    ]

    assert state.balances[source_index] == spec.MIN_ACTIVATION_BALANCE
    assert state.validators[source_index].effective_balance == spec.MIN_ACTIVATION_BALANCE
    assert state.balances[target_index] == spec.MIN_ACTIVATION_BALANCE
    assert state.validators[target_index].effective_balance == spec.MIN_ACTIVATION_BALANCE

    yield from run_epoch_processing(spec, state, pending_consolidations=pending_consolidations)

    # Check the consolidation is processed correctly
    assert state.balances[source_index] == 0
    assert state.validators[source_index].effective_balance == 0
    assert state.balances[target_index] == spec.MIN_ACTIVATION_BALANCE * 2
    assert state.validators[target_index].effective_balance == spec.MIN_ACTIVATION_BALANCE * 2
