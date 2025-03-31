from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.context import (
    spec_test,
    spec_state_test,
    with_electra_until_eip7732,
    single_phase,
    with_presets,
    with_custom_state,
    scaled_churn_balances_exceed_activation_exit_churn_limit,
    default_activation_threshold,
)
from eth2spec.test.helpers.bls_to_execution_changes import (
    get_signed_address_change,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash_for_block,
)
from eth2spec.test.helpers.voluntary_exits import (
    prepare_signed_exits,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    transition_to,
)
from eth2spec.test.helpers.withdrawals import (
    set_eth1_withdrawal_credential_with_balance,
    set_compounding_withdrawal_credential_with_balance,
)
from eth2spec.test.helpers.deposits import (
    prepare_deposit_request,
)


@with_electra_until_eip7732
@spec_state_test
def test_basic_el_withdrawal_request(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    validator_index = 0
    address = b'\x22' * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield 'pre', state

    validator_pubkey = state.validators[validator_index].pubkey
    withdrawal_request = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
    )
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_requests.withdrawals = [withdrawal_request]
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_electra_until_eip7732
@spec_state_test
def test_basic_btec_and_el_withdrawal_request_in_same_block(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    validator_index = 0
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)

    address = b'\x22' * 20
    signed_address_change = get_signed_address_change(
        spec,
        state,
        validator_index=validator_index,
        to_execution_address=address,
    )
    block.body.bls_to_execution_changes = [signed_address_change]

    validator_pubkey = state.validators[validator_index].pubkey
    withdrawal_request = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
    )
    block.body.execution_requests.withdrawals = [withdrawal_request]

    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    validator = state.validators[validator_index]
    assert validator.exit_epoch == state.earliest_exit_epoch
    # Check if BTEC was applied
    is_execution_address = validator.withdrawal_credentials[:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
    is_correct_source_address = validator.withdrawal_credentials[12:] == address
    assert is_execution_address and is_correct_source_address


@with_electra_until_eip7732
@spec_state_test
def test_basic_btec_before_el_withdrawal_request(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    validator_index = 0
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield 'pre', state

    # block_1 contains a BTEC operation of the given validator
    address = b'\x22' * 20
    signed_address_change = get_signed_address_change(
        spec,
        state,
        validator_index=validator_index,
        to_execution_address=address,
    )
    block_1 = build_empty_block_for_next_slot(spec, state)
    block_1.body.bls_to_execution_changes = [signed_address_change]
    signed_block_1 = state_transition_and_sign_block(spec, state, block_1)

    validator = state.validators[validator_index]
    assert validator.exit_epoch == spec.FAR_FUTURE_EPOCH
    # Check if BTEC is effect
    is_execution_address = validator.withdrawal_credentials[:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
    is_correct_source_address = validator.withdrawal_credentials[12:] == address
    assert is_execution_address and is_correct_source_address

    # block_2 contains an EL-Exit operation of the given validator
    validator_pubkey = state.validators[validator_index].pubkey
    withdrawal_request = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
    )
    block_2 = build_empty_block_for_next_slot(spec, state)
    block_2.body.execution_requests.withdrawals = [withdrawal_request]
    block_2.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block_2)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)

    yield 'blocks', [signed_block_1, signed_block_2]
    yield 'post', state

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_electra_until_eip7732
@spec_state_test
def test_cl_exit_and_el_withdrawal_request_in_same_block(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    validator_index = 0
    address = b'\x22' * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield 'pre', state

    # CL-Exit
    signed_voluntary_exits = prepare_signed_exits(spec, state, indices=[validator_index])
    # EL-Exit
    validator_pubkey = state.validators[validator_index].pubkey
    withdrawal_request = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
    )
    block = build_empty_block_for_next_slot(spec, state)
    block.body.voluntary_exits = signed_voluntary_exits
    block.body.execution_requests.withdrawals = [withdrawal_request]
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_electra_until_eip7732
@spec_state_test
def test_multiple_el_partial_withdrawal_requests_same_validator(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    validator_index = 0
    address = b'\x22' * 20
    balance = spec.MIN_ACTIVATION_BALANCE + 2000000000
    set_compounding_withdrawal_credential_with_balance(spec, state, validator_index, balance, balance, address)

    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield 'pre', state

    validator_pubkey = state.validators[validator_index].pubkey
    withdrawal_request_1 = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=spec.Gwei(1),
    )
    withdrawal_request_2 = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
        amount=spec.Gwei(2),
    )
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_requests.withdrawals = [withdrawal_request_1, withdrawal_request_2]
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert len(state.pending_partial_withdrawals) == 2
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH


@with_electra_until_eip7732
@spec_state_test
def test_multiple_el_partial_withdrawal_requests_different_validator(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    validator_indices = [1, 2]
    addresses = [bytes([v * 0x11]) * 20 for v in validator_indices]
    balances = [spec.MIN_ACTIVATION_BALANCE + v * 2000000000 for v in validator_indices]

    for validator_index, address, balance in zip(validator_indices, addresses, balances):
        set_compounding_withdrawal_credential_with_balance(spec, state, validator_index, balance, balance, address)
        assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield 'pre', state

    withdrawal_requests = []

    for validator_index, address in zip(validator_indices, addresses):
        validator_pubkey = state.validators[validator_index].pubkey
        withdrawal_request = spec.WithdrawalRequest(
            source_address=address,
            validator_pubkey=validator_pubkey,
            amount=spec.Gwei(validator_index),
        )
        withdrawal_requests.append(withdrawal_request)

    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_requests.withdrawals = withdrawal_requests
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert len(state.pending_partial_withdrawals) == 2
    for validator_index in validator_indices:
        assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH


@with_electra_until_eip7732
@spec_state_test
def test_withdrawal_and_withdrawal_request_same_validator(spec, state):
    # Give a validator an excess balance
    validator_index = 0
    excess_balance = 200000
    balance = spec.MAX_EFFECTIVE_BALANCE + excess_balance
    address = b'\x22' * 20
    set_eth1_withdrawal_credential_with_balance(
        spec,
        state,
        validator_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE,
        balance=balance,
        address=address,
    )

    # Ensure the validator has an upcoming withdrawal
    # This will happen before the withdrawal request
    expected_withdrawals, _ = spec.get_expected_withdrawals(state)
    assert len(expected_withdrawals) == 1
    assert expected_withdrawals[0].validator_index == validator_index

    yield 'pre', state

    # Create a 1 gwei withdrawal request for the same validator
    withdrawal_request = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=state.validators[validator_index].pubkey,
        amount=1,
    )

    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_requests.withdrawals = [withdrawal_request]
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    # Ensure the withdrawal request was unsuccessful
    assert len(state.pending_partial_withdrawals) == 0


@with_electra_until_eip7732
@spec_state_test
def test_withdrawal_and_switch_to_compounding_request_same_validator(spec, state):
    # Give a validator an excess balance
    validator_index = 0
    excess_balance = 200000
    balance = spec.MAX_EFFECTIVE_BALANCE + excess_balance
    address = b'\x22' * 20
    set_eth1_withdrawal_credential_with_balance(
        spec,
        state,
        validator_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE,
        balance=balance,
        address=address,
    )

    # Ensure the validator has an upcoming withdrawal
    # This will happen before the withdrawal request
    expected_withdrawals, _ = spec.get_expected_withdrawals(state)
    assert len(expected_withdrawals) == 1
    assert expected_withdrawals[0].validator_index == validator_index

    yield 'pre', state

    # Create a switch to compounding validator request for the same validator
    consolidation_request = spec.ConsolidationRequest(
        source_address=address,
        source_pubkey=state.validators[validator_index].pubkey,
        target_pubkey=state.validators[validator_index].pubkey,
    )

    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_requests.consolidations = [consolidation_request]
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    # Ensure the validator has compounding credentials now
    assert spec.is_compounding_withdrawal_credential(state.validators[validator_index].withdrawal_credentials)
    # Ensure there was no excess balance pending deposit
    assert len(state.pending_deposits) == 0


@with_electra_until_eip7732
@spec_state_test
def test_deposit_request_with_same_pubkey_different_withdrawal_credentials(spec, state):
    # signify the eth1 bridge deprecation
    state.deposit_requests_start_index = state.eth1_deposit_index

    # prepare three deposit requests, where
    # 1st and 3rd have the same pubkey but different withdrawal credentials
    deposit_request_0 = prepare_deposit_request(
        spec, len(state.validators), spec.MIN_ACTIVATION_BALANCE, state.eth1_deposit_index, signed=True)
    deposit_request_1 = prepare_deposit_request(
        spec, len(state.validators) + 1, spec.MIN_ACTIVATION_BALANCE, state.eth1_deposit_index + 1, signed=True)
    deposit_request_2 = prepare_deposit_request(
        spec, len(state.validators), spec.MIN_ACTIVATION_BALANCE, state.eth1_deposit_index + 2, signed=True,
        withdrawal_credentials=(spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b'\x00' * 11 + b'\x11' * 20)
    )

    # build a block with deposit requests
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_requests.deposits = [deposit_request_0, deposit_request_1, deposit_request_2]
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)

    yield 'pre', state

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    # check deposit requests are processed correctly
    for i, deposit_request in enumerate(block.body.execution_requests.deposits):
        assert state.pending_deposits[i] == spec.PendingDeposit(
            pubkey=deposit_request.pubkey,
            withdrawal_credentials=deposit_request.withdrawal_credentials,
            amount=deposit_request.amount,
            signature=deposit_request.signature,
            slot=signed_block.message.slot,
        )


@with_electra_until_eip7732
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_withdrawal_and_consolidation_effective_balance_updates(spec, state):
    # Move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # We are going to process two blocks:
    #   1) A block which processes a withdrawal and consolidation.
    #   2) A block which forces epoch processing to happen.
    # For this to work, we must transition to the 2nd to last slot of the epoch.
    slot = state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH) - 2
    transition_to(spec, state, slot)

    current_epoch = spec.get_current_epoch(state)

    # Initialize validator A (0x01 validator with 31.9 ETH)
    a_index = spec.get_active_validator_indices(state, current_epoch)[0]
    a_addr = b'\xaa' * 20
    assert state.validators[a_index].exit_epoch == spec.FAR_FUTURE_EPOCH
    set_eth1_withdrawal_credential_with_balance(
        spec,
        state,
        a_index,
        # 31.9 ETH
        balance=31_900_000_000,
        address=a_addr,
    )
    # Set withdrawable epoch to current epoch to allow processing
    state.validators[a_index].withdrawable_epoch = current_epoch

    # Initialize validator B (0x02 validator with 64.0 ETH)
    b_index = spec.get_active_validator_indices(state, current_epoch)[1]
    b_addr = b'\xbb' * 20
    assert state.validators[b_index].exit_epoch == spec.FAR_FUTURE_EPOCH
    set_compounding_withdrawal_credential_with_balance(
        spec,
        state,
        b_index,
        # 64 ETH
        balance=64_000_000_000,
        effective_balance=64_000_000_000,
        address=b_addr,
    )

    # Add a pending consolidation from A -> B
    state.validators[a_index].exit_epoch = spec.compute_consolidation_epoch_and_update_churn(
        state, state.validators[a_index].effective_balance
    )
    state.validators[a_index].withdrawable_epoch = current_epoch + 1
    state.pending_consolidations = [
        spec.PendingConsolidation(
            source_index=a_index,
            target_index=b_index
        )
    ]

    # Add a pending partial withdrawal for 32 ETH from B
    state.pending_partial_withdrawals = [
        spec.PendingPartialWithdrawal(
            validator_index=b_index,
            amount=spec.MIN_ACTIVATION_BALANCE,
            withdrawable_epoch=current_epoch,
        )
    ]

    yield 'pre', state

    # Process a block to process the pending withdrawal/consolidation
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block_a = state_transition_and_sign_block(spec, state, block)

    # Process another block to trigger epoch processing
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block_b = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block_a, signed_block_b]
    yield 'post', state

    # Ensure we are in the next epoch
    assert spec.get_current_epoch(state) == current_epoch + 1
    # The pending consolidation should have been processed
    assert state.pending_consolidations == []
    # The pending partial withdrawal should have been processed
    assert state.pending_partial_withdrawals == []
    # Validator A should have exited, consolidation
    assert state.validators[a_index].exit_epoch != spec.FAR_FUTURE_EPOCH
    # Validator B should have an effective balance of 64 ETH
    assert state.validators[b_index].effective_balance == 64 * spec.EFFECTIVE_BALANCE_INCREMENT
