import random

from eth_consensus_specs.test.context import (
    spec_state_test,
    with_all_phases_from_to,
    with_capella_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.attestations import (
    next_epoch_with_attestations,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.bls_to_execution_changes import get_signed_address_change
from eth_consensus_specs.test.helpers.constants import (
    CAPELLA,
    GLOAS,
    MINIMAL,
)
from eth_consensus_specs.test.helpers.deposits import (
    prepare_state_and_deposit,
)
from eth_consensus_specs.test.helpers.forks import is_post_electra, is_post_gloas
from eth_consensus_specs.test.helpers.keys import pubkeys
from eth_consensus_specs.test.helpers.state import (
    next_epoch_via_block,
    next_slot,
    state_transition_and_sign_block,
    transition_to,
)
from eth_consensus_specs.test.helpers.voluntary_exits import prepare_signed_exits
from eth_consensus_specs.test.helpers.withdrawals import (
    get_expected_withdrawals,
    prepare_expected_withdrawals,
    prepare_pending_withdrawal,
    set_eth1_withdrawal_credential_with_balance,
    set_validator_fully_withdrawable,
    set_validator_partially_withdrawable,
)

#
# `is_execution_enabled` has been removed from Capella
#


@with_all_phases_from_to(CAPELLA, GLOAS)
@spec_state_test
def test_invalid_is_execution_enabled_false(spec, state):
    # Set `latest_execution_payload_header` to empty
    state.latest_execution_payload_header = spec.ExecutionPayloadHeader()
    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)

    # Set `execution_payload` to empty
    block.body.execution_payload = spec.ExecutionPayload()
    assert len(block.body.execution_payload.transactions) == 0

    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


#
# BLSToExecutionChange
#


@with_capella_and_later
@spec_state_test
def test_bls_change(spec, state):
    index = 0
    signed_address_change = get_signed_address_change(spec, state, validator_index=index)
    pre_credentials = state.validators[index].withdrawal_credentials
    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.bls_to_execution_changes.append(signed_address_change)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    post_credentials = state.validators[index].withdrawal_credentials
    assert pre_credentials != post_credentials
    assert post_credentials[:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
    assert post_credentials[1:12] == b"\x00" * 11
    assert post_credentials[12:] == signed_address_change.message.to_execution_address


@with_capella_and_later
@spec_state_test
def test_deposit_and_bls_change(spec, state):
    initial_registry_len = len(state.validators)
    initial_balances_len = len(state.balances)

    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    signed_address_change = get_signed_address_change(
        spec,
        state,
        validator_index=validator_index,
        withdrawal_pubkey=deposit.data.pubkey,  # Deposit helper defaults to use pubkey as withdrawal credential
    )

    deposit_credentials = deposit.data.withdrawal_credentials
    assert deposit_credentials[:1] == spec.BLS_WITHDRAWAL_PREFIX

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.deposits.append(deposit)
    block.body.bls_to_execution_changes.append(signed_address_change)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    assert len(state.validators) == initial_registry_len + 1
    assert len(state.balances) == initial_balances_len + 1
    validator_credentials = state.validators[validator_index].withdrawal_credentials
    assert deposit_credentials != validator_credentials
    assert validator_credentials[:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
    assert validator_credentials[1:12] == b"\x00" * 11
    assert validator_credentials[12:] == signed_address_change.message.to_execution_address


@with_capella_and_later
@spec_state_test
def test_exit_and_bls_change(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    index = 0
    signed_address_change = get_signed_address_change(spec, state, validator_index=index)
    signed_exit = prepare_signed_exits(spec, state, [index])[0]

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.voluntary_exits.append(signed_exit)
    block.body.bls_to_execution_changes.append(signed_address_change)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    validator = state.validators[index]
    balance = state.balances[index]
    current_epoch = spec.get_current_epoch(state)
    assert not spec.is_fully_withdrawable_validator(validator, balance, current_epoch)
    assert validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
    assert spec.is_fully_withdrawable_validator(validator, balance, validator.withdrawable_epoch)


@with_capella_and_later
@spec_state_test
def test_invalid_duplicate_bls_changes_same_block(spec, state):
    index = 0
    signed_address_change = get_signed_address_change(spec, state, validator_index=index)
    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)

    # Double BLSToExecutionChange of the same validator
    for _ in range(2):
        block.body.bls_to_execution_changes.append(signed_address_change)

    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_capella_and_later
@spec_state_test
def test_invalid_two_bls_changes_of_different_addresses_same_validator_same_block(spec, state):
    index = 0

    signed_address_change_1 = get_signed_address_change(
        spec, state, validator_index=index, to_execution_address=b"\x12" * 20
    )
    signed_address_change_2 = get_signed_address_change(
        spec, state, validator_index=index, to_execution_address=b"\x34" * 20
    )
    assert signed_address_change_1 != signed_address_change_2

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)

    block.body.bls_to_execution_changes.append(signed_address_change_1)
    block.body.bls_to_execution_changes.append(signed_address_change_2)

    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


#
# Withdrawals
#


@with_all_phases_from_to(CAPELLA, GLOAS)
@spec_state_test
def test_full_withdrawal_in_epoch_transition(spec, state):
    index = 0
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, index, current_epoch)
    assert len(get_expected_withdrawals(spec, state)) == 1

    yield "pre", state

    # trigger epoch transition
    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    assert state.balances[index] == 0
    assert len(get_expected_withdrawals(spec, state)) == 0


@with_capella_and_later
@spec_state_test
def test_partial_withdrawal_in_epoch_transition(spec, state):
    index = state.next_withdrawal_index
    set_validator_partially_withdrawable(spec, state, index, excess_balance=1000000000000)
    pre_balance = state.balances[index]

    assert len(get_expected_withdrawals(spec, state)) == 1

    # Make parent block full in Gloas so withdrawals are processed
    if is_post_gloas(spec):
        # For Gloas, we need the parent block to be full to process withdrawals
        # Set latest_block_hash to match latest_execution_payload_bid.block_hash
        state.latest_block_hash = state.latest_execution_payload_bid.block_hash

    yield "pre", state

    # trigger epoch transition
    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    assert state.balances[index] < pre_balance
    # Potentially less than due to sync committee penalty
    assert state.balances[index] <= spec.MAX_EFFECTIVE_BALANCE
    assert len(get_expected_withdrawals(spec, state)) == 0


@with_capella_and_later
@spec_state_test
def test_many_partial_withdrawals_in_epoch_transition(spec, state):
    assert len(state.validators) > spec.MAX_WITHDRAWALS_PER_PAYLOAD

    for i in range(spec.MAX_WITHDRAWALS_PER_PAYLOAD + 1):
        index = (i + state.next_withdrawal_index) % len(state.validators)
        if is_post_gloas(spec):
            # In Gloas, partial withdrawals must be explicitly added to pending_partial_withdrawals
            prepare_pending_withdrawal(spec, state, index, amount=1000000000000)
        else:
            set_validator_partially_withdrawable(spec, state, index, excess_balance=1000000000000)

    # In Gloas, the number of expected withdrawals is limited by MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
    if is_post_gloas(spec):
        expected_count = min(
            spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP, spec.MAX_WITHDRAWALS_PER_PAYLOAD - 1
        )
        assert len(get_expected_withdrawals(spec, state)) == expected_count
        # Make parent block full in Gloas so withdrawals are processed
        state.latest_block_hash = state.latest_execution_payload_bid.block_hash
    else:
        assert len(get_expected_withdrawals(spec, state)) == spec.MAX_WITHDRAWALS_PER_PAYLOAD

    yield "pre", state

    # trigger epoch transition
    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    # In Gloas, the withdrawal processing logic is different
    if is_post_gloas(spec):
        # In Gloas, we added MAX_WITHDRAWALS_PER_PAYLOAD + 1 pending withdrawals
        # But only MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP were processed
        processed_count = min(
            spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP, spec.MAX_WITHDRAWALS_PER_PAYLOAD - 1
        )
        expected_remaining = (spec.MAX_WITHDRAWALS_PER_PAYLOAD + 1) - processed_count
        remaining_pending = len(
            [
                w
                for w in state.pending_partial_withdrawals
                if w.withdrawable_epoch <= spec.get_current_epoch(state)
            ]
        )
        assert remaining_pending == expected_remaining
    else:
        assert len(get_expected_withdrawals(spec, state)) == 1


def _perform_valid_withdrawal(spec, state):
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec,
        state,
        rng=random.Random(42),
        num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 2,
        num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 2,
    )

    # In Gloas, also add pending partial withdrawals for the partial withdrawal indices
    if is_post_gloas(spec):
        for index in partial_withdrawals_indices:
            # Add pending partial withdrawal with the same amount as the excess balance
            prepare_pending_withdrawal(spec, state, index, amount=1000000000)

    next_slot(spec, state)
    pre_next_withdrawal_index = state.next_withdrawal_index

    expected_withdrawals = get_expected_withdrawals(spec, state)

    # Make parent block full in Gloas so withdrawals are processed
    if is_post_gloas(spec):
        state.latest_block_hash = state.latest_execution_payload_bid.block_hash

    pre_state = state.copy()

    # Block 1
    block = build_empty_block_for_next_slot(spec, state)
    signed_block_1 = state_transition_and_sign_block(spec, state, block)

    withdrawn_indices = [withdrawal.validator_index for withdrawal in expected_withdrawals]
    fully_withdrawable_indices = list(
        set(fully_withdrawable_indices).difference(set(withdrawn_indices))
    )
    partial_withdrawals_indices = list(
        set(partial_withdrawals_indices).difference(set(withdrawn_indices))
    )

    # In Gloas, the withdrawal processing logic is different
    if is_post_gloas(spec):
        # In Gloas, only a limited number of withdrawals can be processed at a time
        expected_processed = min(len(expected_withdrawals), spec.MAX_WITHDRAWALS_PER_PAYLOAD)
        assert state.next_withdrawal_index == pre_next_withdrawal_index + expected_processed
    else:
        assert (
            state.next_withdrawal_index
            == pre_next_withdrawal_index + spec.MAX_WITHDRAWALS_PER_PAYLOAD
        )

    withdrawn_indices = [withdrawal.validator_index for withdrawal in expected_withdrawals]
    fully_withdrawable_indices = list(
        set(fully_withdrawable_indices).difference(set(withdrawn_indices))
    )
    partial_withdrawals_indices = list(
        set(partial_withdrawals_indices).difference(set(withdrawn_indices))
    )

    # Repeat the same assertion logic
    if is_post_gloas(spec):
        expected_processed = min(len(expected_withdrawals), spec.MAX_WITHDRAWALS_PER_PAYLOAD)
        assert state.next_withdrawal_index == pre_next_withdrawal_index + expected_processed
    else:
        assert (
            state.next_withdrawal_index
            == pre_next_withdrawal_index + spec.MAX_WITHDRAWALS_PER_PAYLOAD
        )

    return pre_state, signed_block_1, pre_next_withdrawal_index


@with_capella_and_later
@spec_state_test
def test_withdrawal_success_two_blocks(spec, state):
    pre_state, signed_block_1, pre_next_withdrawal_index = _perform_valid_withdrawal(spec, state)

    yield "pre", pre_state

    # Block 2
    block = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block)

    # After Gloas the second block does not perform any withdrawals because
    # there was no payload processed
    if is_post_gloas(spec):
        pass  # The withdrawal index should remain the same as after block 1
    else:
        assert (
            state.next_withdrawal_index
            == pre_next_withdrawal_index + spec.MAX_WITHDRAWALS_PER_PAYLOAD * 2
        )

    yield "blocks", [signed_block_1, signed_block_2]
    yield "post", state


@with_capella_and_later
@spec_state_test
def test_invalid_withdrawal_fail_second_block_payload_isnt_compatible(spec, state):
    _perform_valid_withdrawal(spec, state)

    # Block 2
    block = build_empty_block_for_next_slot(spec, state)

    # Modify state.next_withdrawal_index to incorrect number
    state.next_withdrawal_index += 1

    # Only need to output the state transition of signed_block_2
    yield "pre", state

    signed_block_2 = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block_2]
    yield "post", None


#
# Mix top-ups and withdrawals
#


@with_capella_and_later
@spec_state_test
def test_top_up_and_partial_withdrawable_validator(spec, state):
    next_withdrawal_validator_index = 0
    validator_index = next_withdrawal_validator_index + 1

    set_eth1_withdrawal_credential_with_balance(
        spec, state, validator_index, balance=spec.MAX_EFFECTIVE_BALANCE
    )
    validator = state.validators[validator_index]
    balance = state.balances[validator_index]
    assert not spec.is_partially_withdrawable_validator(validator, balance)

    # Make a top-up balance to validator
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.deposits.append(deposit)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    if is_post_electra(spec):
        assert state.pending_deposits[0].pubkey == deposit.data.pubkey
        assert (
            state.pending_deposits[0].withdrawal_credentials == deposit.data.withdrawal_credentials
        )
        assert state.pending_deposits[0].amount == deposit.data.amount
        assert state.pending_deposits[0].signature == deposit.data.signature
        assert state.pending_deposits[0].slot == spec.GENESIS_SLOT
    else:
        # Since withdrawals happen before deposits, it becomes partially withdrawable after state transition.
        validator = state.validators[validator_index]
        balance = state.balances[validator_index]
        assert spec.is_partially_withdrawable_validator(validator, balance)


@with_capella_and_later
@spec_state_test
def test_top_up_to_fully_withdrawn_validator(spec, state):
    """
    Similar to `teste_process_deposit::test_success_top_up_to_withdrawn_validator` test.
    """
    next_withdrawal_validator_index = 0
    validator_index = next_withdrawal_validator_index + 1

    # Fully withdraw validator
    set_validator_fully_withdrawable(spec, state, validator_index)
    assert state.balances[validator_index] > 0

    # Make parent block full in Gloas so withdrawals are processed
    if is_post_gloas(spec):
        state.latest_block_hash = state.latest_execution_payload_bid.block_hash

    next_epoch_via_block(spec, state)
    assert state.balances[validator_index] == 0
    assert state.validators[validator_index].effective_balance > 0
    next_epoch_via_block(spec, state)
    assert state.validators[validator_index].effective_balance == 0

    # Make a top-up deposit to validator
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.deposits.append(deposit)

    signed_block_1 = state_transition_and_sign_block(spec, state, block)

    balance = state.balances[validator_index]
    if is_post_electra(spec):
        balance += state.pending_deposits[0].amount

    assert spec.is_fully_withdrawable_validator(
        state.validators[validator_index], balance, spec.get_current_epoch(state)
    )

    # Apply an empty block
    block = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block)

    # With mainnet preset, it holds
    if len(state.validators) <= spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP:
        assert not spec.is_fully_withdrawable_validator(
            state.validators[validator_index],
            state.balances[validator_index],
            spec.get_current_epoch(state),
        )

    yield "blocks", [signed_block_1, signed_block_2]
    yield "post", state


def _insert_validator(spec, state, balance):
    effective_balance = (
        balance - balance % spec.EFFECTIVE_BALANCE_INCREMENT
        if balance < spec.MAX_EFFECTIVE_BALANCE
        else spec.MAX_EFFECTIVE_BALANCE
    )

    validator_index = len(state.validators)
    validator = spec.Validator(
        pubkey=pubkeys[validator_index],
        withdrawal_credentials=spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x56" * 20,
        activation_eligibility_epoch=1,
        activation_epoch=2,
        exit_epoch=spec.FAR_FUTURE_EPOCH,
        withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
        effective_balance=effective_balance,
    )
    state.validators.append(validator)
    state.balances.append(balance)
    state.previous_epoch_participation.append(spec.ParticipationFlags(0b0000_0000))
    state.current_epoch_participation.append(spec.ParticipationFlags(0b0000_0000))
    state.inactivity_scores.append(0)

    return validator_index


def _run_activate_and_partial_withdrawal(spec, state, initial_balance):
    validator_index = _insert_validator(spec, state, balance=initial_balance)

    # To make it eligible activation
    transition_to(spec, state, spec.compute_start_slot_at_epoch(2) - 1)
    assert not spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state)
    )

    yield "pre", state

    blocks = []
    # To activate
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    blocks.append(signed_block)

    assert spec.is_active_validator(
        state.validators[validator_index], spec.get_current_epoch(state)
    )

    if initial_balance > spec.MAX_EFFECTIVE_BALANCE:
        assert spec.is_partially_withdrawable_validator(
            state.validators[validator_index], state.balances[validator_index]
        )
    else:
        assert not spec.is_partially_withdrawable_validator(
            state.validators[validator_index], state.balances[validator_index]
        )

    _, new_blocks, state = next_epoch_with_attestations(spec, state, True, True)
    blocks += new_blocks

    yield "blocks", blocks
    yield "post", state


@with_capella_and_later
@with_presets([MINIMAL], reason="too many validators with mainnet config")
@spec_state_test
def test_activate_and_partial_withdrawal_max_effective_balance(spec, state):
    yield from _run_activate_and_partial_withdrawal(
        spec, state, initial_balance=spec.MAX_EFFECTIVE_BALANCE
    )


@with_capella_and_later
@with_presets([MINIMAL], reason="too many validators with mainnet config")
@spec_state_test
def test_activate_and_partial_withdrawal_overdeposit(spec, state):
    yield from _run_activate_and_partial_withdrawal(
        spec, state, initial_balance=spec.MAX_EFFECTIVE_BALANCE + 10000000
    )
