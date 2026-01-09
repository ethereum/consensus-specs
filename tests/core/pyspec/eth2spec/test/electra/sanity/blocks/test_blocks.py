from eth2spec.test.context import (
    default_activation_threshold,
    scaled_churn_balances_exceed_activation_exit_churn_limit,
    single_phase,
    spec_state_test,
    spec_test,
    with_all_phases_from_to,
    with_custom_state,
    with_presets,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
    transition_unsigned_block,
)
from eth2spec.test.helpers.bls_to_execution_changes import (
    get_signed_address_change,
)
from eth2spec.test.helpers.constants import (
    ELECTRA,
    GLOAS,
    MINIMAL,
)
from eth2spec.test.helpers.deposits import (
    prepare_deposit_request,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash_for_block,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    transition_to,
)
from eth2spec.test.helpers.voluntary_exits import (
    prepare_signed_exits,
)
from eth2spec.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential_with_balance,
    set_eth1_withdrawal_credential_with_balance,
)


@with_all_phases_from_to(ELECTRA, GLOAS)
@spec_state_test
def test_basic_el_withdrawal_request(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    validator_index = 0
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield "pre", state

    validator_pubkey = state.validators[validator_index].pubkey
    withdrawal_request = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=validator_pubkey,
    )
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_requests.withdrawals = [withdrawal_request]
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_all_phases_from_to(ELECTRA, GLOAS)
@spec_state_test
def test_basic_btec_and_el_withdrawal_request_in_same_block(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    validator_index = 0
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)

    address = b"\x22" * 20
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

    yield "blocks", [signed_block]
    yield "post", state

    validator = state.validators[validator_index]
    assert validator.exit_epoch == state.earliest_exit_epoch
    # Check if BTEC was applied
    is_execution_address = (
        validator.withdrawal_credentials[:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
    )
    is_correct_source_address = validator.withdrawal_credentials[12:] == address
    assert is_execution_address and is_correct_source_address


@with_all_phases_from_to(ELECTRA, GLOAS)
@spec_state_test
def test_basic_btec_before_el_withdrawal_request(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    validator_index = 0
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield "pre", state

    # block_1 contains a BTEC operation of the given validator
    address = b"\x22" * 20
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
    is_execution_address = (
        validator.withdrawal_credentials[:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
    )
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

    yield "blocks", [signed_block_1, signed_block_2]
    yield "post", state

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_all_phases_from_to(ELECTRA, GLOAS)
@spec_state_test
def test_cl_exit_and_el_withdrawal_request_in_same_block(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    validator_index = 0
    address = b"\x22" * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield "pre", state

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

    yield "blocks", [signed_block]
    yield "post", state

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_all_phases_from_to(ELECTRA, GLOAS)
@spec_state_test
def test_multiple_el_partial_withdrawal_requests_same_validator(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    validator_index = 0
    address = b"\x22" * 20
    balance = spec.MIN_ACTIVATION_BALANCE + 2000000000
    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index, balance, balance, address
    )

    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield "pre", state

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

    yield "blocks", [signed_block]
    yield "post", state

    assert len(state.pending_partial_withdrawals) == 2
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH


@with_all_phases_from_to(ELECTRA, GLOAS)
@spec_state_test
def test_multiple_el_partial_withdrawal_requests_different_validator(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    validator_indices = [1, 2]
    addresses = [bytes([v * 0x11]) * 20 for v in validator_indices]
    balances = [spec.MIN_ACTIVATION_BALANCE + v * 2000000000 for v in validator_indices]

    for validator_index, address, balance in zip(validator_indices, addresses, balances):
        set_compounding_withdrawal_credential_with_balance(
            spec, state, validator_index, balance, balance, address
        )
        assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield "pre", state

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

    yield "blocks", [signed_block]
    yield "post", state

    assert len(state.pending_partial_withdrawals) == 2
    for validator_index in validator_indices:
        assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH


@with_all_phases_from_to(ELECTRA, GLOAS)
@spec_state_test
def test_withdrawal_and_withdrawal_request_same_validator(spec, state):
    # Give a validator an excess balance
    validator_index = 0
    excess_balance = 200000
    balance = spec.MAX_EFFECTIVE_BALANCE + excess_balance
    address = b"\x22" * 20
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
    expected_withdrawals = spec.get_expected_withdrawals(state).withdrawals
    assert len(expected_withdrawals) == 1
    assert expected_withdrawals[0].validator_index == validator_index

    yield "pre", state

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

    yield "blocks", [signed_block]
    yield "post", state

    # Ensure the withdrawal request was unsuccessful
    assert len(state.pending_partial_withdrawals) == 0


@with_all_phases_from_to(ELECTRA, GLOAS)
@spec_state_test
def test_withdrawal_and_switch_to_compounding_request_same_validator(spec, state):
    # Give a validator an excess balance
    validator_index = 0
    excess_balance = 200000
    balance = spec.MAX_EFFECTIVE_BALANCE + excess_balance
    address = b"\x22" * 20
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
    expected_withdrawals = spec.get_expected_withdrawals(state).withdrawals
    assert len(expected_withdrawals) == 1
    assert expected_withdrawals[0].validator_index == validator_index

    yield "pre", state

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

    yield "blocks", [signed_block]
    yield "post", state

    # Ensure the validator has compounding credentials now
    assert spec.is_compounding_withdrawal_credential(
        state.validators[validator_index].withdrawal_credentials
    )
    # Ensure there was no excess balance pending deposit
    assert len(state.pending_deposits) == 0


@with_all_phases_from_to(ELECTRA, GLOAS)
@spec_state_test
def test_deposit_request_with_same_pubkey_different_withdrawal_credentials(spec, state):
    # signify the eth1 bridge deprecation
    state.deposit_requests_start_index = state.eth1_deposit_index

    # prepare three deposit requests, where
    # 1st and 3rd have the same pubkey but different withdrawal credentials
    deposit_request_0 = prepare_deposit_request(
        spec,
        len(state.validators),
        spec.MIN_ACTIVATION_BALANCE,
        state.eth1_deposit_index,
        signed=True,
    )
    deposit_request_1 = prepare_deposit_request(
        spec,
        len(state.validators) + 1,
        spec.MIN_ACTIVATION_BALANCE,
        state.eth1_deposit_index + 1,
        signed=True,
    )
    deposit_request_2 = prepare_deposit_request(
        spec,
        len(state.validators),
        spec.MIN_ACTIVATION_BALANCE,
        state.eth1_deposit_index + 2,
        signed=True,
        withdrawal_credentials=(spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20),
    )

    # build a block with deposit requests
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_requests.deposits = [
        deposit_request_0,
        deposit_request_1,
        deposit_request_2,
    ]
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)

    yield "pre", state

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    # check deposit requests are processed correctly
    for i, deposit_request in enumerate(block.body.execution_requests.deposits):
        assert state.pending_deposits[i] == spec.PendingDeposit(
            pubkey=deposit_request.pubkey,
            withdrawal_credentials=deposit_request.withdrawal_credentials,
            amount=deposit_request.amount,
            signature=deposit_request.signature,
            slot=signed_block.message.slot,
        )


@with_all_phases_from_to(ELECTRA, GLOAS)
@spec_state_test
def test_deposit_request_max_per_payload(spec, state):
    # signify the eth1 bridge deprecation
    state.deposit_requests_start_index = state.eth1_deposit_index

    validator_index = len(state.validators)
    deposit_requests = []
    for i in range(spec.MAX_DEPOSIT_REQUESTS_PER_PAYLOAD):
        deposit_requests.append(
            prepare_deposit_request(
                spec,
                validator_index,
                spec.EFFECTIVE_BALANCE_INCREMENT,
                state.eth1_deposit_index + i,
                signed=True,
            )
        )

    # build a block with deposit requests
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_requests.deposits = deposit_requests
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)

    yield "pre", state

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    # check deposit requests are processed correctly
    assert len(state.pending_deposits) == len(deposit_requests)
    for i, deposit_request in enumerate(block.body.execution_requests.deposits):
        assert state.pending_deposits[i] == spec.PendingDeposit(
            pubkey=deposit_request.pubkey,
            withdrawal_credentials=deposit_request.withdrawal_credentials,
            amount=deposit_request.amount,
            signature=deposit_request.signature,
            slot=signed_block.message.slot,
        )


@with_all_phases_from_to(ELECTRA, GLOAS)
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
    a_addr = b"\xaa" * 20
    assert state.validators[a_index].exit_epoch == spec.FAR_FUTURE_EPOCH
    set_eth1_withdrawal_credential_with_balance(
        spec,
        state,
        a_index,
        # Given a balance of 31.9 ETH
        # An excess balance isn't required for consolidations
        balance=31_900_000_000,
        # And given an effect balance of 32.0 ETH
        # It's possible that its effective balance hasn't been updated yet
        effective_balance=32_000_000_000,
        address=a_addr,
    )
    # Set withdrawable epoch to current epoch to allow processing
    state.validators[a_index].withdrawable_epoch = current_epoch

    # Initialize validator B (0x02 validator with 64.0 ETH)
    b_index = spec.get_active_validator_indices(state, current_epoch)[1]
    b_addr = b"\xbb" * 20
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
        spec.PendingConsolidation(source_index=a_index, target_index=b_index)
    ]

    # Add a pending partial withdrawal for 32 ETH from B
    state.pending_partial_withdrawals = [
        spec.PendingPartialWithdrawal(
            validator_index=b_index,
            amount=spec.MIN_ACTIVATION_BALANCE,
            withdrawable_epoch=current_epoch,
        )
    ]

    yield "pre", state

    # Process a block to process the pending withdrawal/consolidation
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block_a = state_transition_and_sign_block(spec, state, block)

    # Process another block to trigger epoch processing
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block_b = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block_a, signed_block_b]
    yield "post", state

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
    # Validator B's balance should be less than its effective balance, hysteria
    assert state.balances[b_index] < state.validators[b_index].effective_balance


@with_all_phases_from_to(ELECTRA, GLOAS)
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_consolidation_requests_when_pending_consolidation_queue_is_full(spec, state):
    # Move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # Fill up the queue with invalid pending consolidations
    # Making these legit would be too much work
    # One less than the limit, to ensure another can be added
    state.pending_consolidations = [
        spec.PendingConsolidation(source_index=0x1111, target_index=0x2222)
    ] * (spec.PENDING_CONSOLIDATIONS_LIMIT - 1)

    # This will consolidate 0->1, 2->3, 4->5, ...
    consolidation_requests = []
    for i in range(0, 2 * spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD, 2):
        # Setup the source validator
        current_epoch = spec.get_current_epoch(state)
        source_index = spec.get_active_validator_indices(state, current_epoch)[i + 0]
        source_address = b"\x11" * 20
        set_eth1_withdrawal_credential_with_balance(
            spec,
            state,
            source_index,
            address=source_address,
            effective_balance=spec.MIN_ACTIVATION_BALANCE,
            balance=spec.MIN_ACTIVATION_BALANCE,
        )
        # Setup the target validator
        target_index = spec.get_active_validator_indices(state, current_epoch)[i + 1]
        set_compounding_withdrawal_credential_with_balance(spec, state, target_index)

        # Make the consolidation request
        consolidation_requests.append(
            spec.ConsolidationRequest(
                source_address=source_address,
                source_pubkey=state.validators[source_index].pubkey,
                target_pubkey=state.validators[target_index].pubkey,
            )
        )

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_requests.consolidations = consolidation_requests
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    # Ensure another consolidation was added and the other one was rejected
    assert len(state.pending_consolidations) == spec.PENDING_CONSOLIDATIONS_LIMIT


@with_all_phases_from_to(ELECTRA, GLOAS)
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_switch_to_compounding_requests_when_pending_consolidation_queue_is_full(spec, state):
    # Move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # Fill up the queue with invalid pending consolidations
    # Making these legit would be too much work
    #
    # Note: If a client optimizes the `process_consolidation_request` function to be a single
    # function with a for-loop, it's possible that they stop processing all consolidation requests
    # after the consolidation request. For this reason, the pending consolidations queue in this
    # test starts off as full and consolidations requests are made.
    state.pending_consolidations = [
        spec.PendingConsolidation(source_index=0x1111, target_index=0x2222)
    ] * spec.PENDING_CONSOLIDATIONS_LIMIT

    # This will contain two requests:
    #   1. A regular consolidation request
    #   2. A switch to compounding request
    consolidation_requests = []

    # Setup the source validator
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    source_address = b"\x11" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec,
        state,
        source_index,
        address=source_address,
        effective_balance=spec.MIN_ACTIVATION_BALANCE,
        balance=spec.MIN_ACTIVATION_BALANCE,
    )

    # Setup the target validator
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    set_compounding_withdrawal_credential_with_balance(spec, state, target_index)

    # Make the consolidation request
    consolidation_requests.append(
        spec.ConsolidationRequest(
            source_address=source_address,
            source_pubkey=state.validators[source_index].pubkey,
            target_pubkey=state.validators[target_index].pubkey,
        )
    )

    # Make the switch to compounding validator request
    # We can reuse the source validator because it wasn't processed
    consolidation_requests.append(
        spec.ConsolidationRequest(
            source_address=source_address,
            source_pubkey=state.validators[source_index].pubkey,
            target_pubkey=state.validators[source_index].pubkey,
        )
    )

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_requests.consolidations = consolidation_requests
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    # Ensure the pending consolidations queue is still full
    assert len(state.pending_consolidations) == spec.PENDING_CONSOLIDATIONS_LIMIT
    # Ensure the validators have been upgraded to compounding validators
    assert spec.has_compounding_withdrawal_credential(state.validators[source_index])


@with_all_phases_from_to(ELECTRA, GLOAS)
@spec_state_test
def test_switch_to_compounding_requests_when_too_little_consolidation_churn_limit(spec, state):
    # Move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # We didn't use the `scaled_churn_balances_exceed_activation_exit_churn_limit` state, so this
    # state shouldn't have enough churn to process any consolidation requests.
    assert spec.get_consolidation_churn_limit(state) <= spec.MIN_ACTIVATION_BALANCE

    # This will contain two requests:
    #   1. A regular consolidation request
    #   2. A switch to compounding request
    consolidation_requests = []

    # Setup the source validator
    current_epoch = spec.get_current_epoch(state)
    source_index = spec.get_active_validator_indices(state, current_epoch)[0]
    source_address = b"\x11" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec,
        state,
        source_index,
        address=source_address,
        effective_balance=spec.MIN_ACTIVATION_BALANCE,
        balance=spec.MIN_ACTIVATION_BALANCE,
    )

    # Setup the target validator
    target_index = spec.get_active_validator_indices(state, current_epoch)[1]
    set_compounding_withdrawal_credential_with_balance(spec, state, target_index)

    # Make the consolidation request
    consolidation_requests.append(
        spec.ConsolidationRequest(
            source_address=source_address,
            source_pubkey=state.validators[source_index].pubkey,
            target_pubkey=state.validators[target_index].pubkey,
        )
    )

    # Make the switch to compounding validator request
    # We can reuse the source validator because it wasn't processed
    consolidation_requests.append(
        spec.ConsolidationRequest(
            source_address=source_address,
            source_pubkey=state.validators[source_index].pubkey,
            target_pubkey=state.validators[source_index].pubkey,
        )
    )

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_requests.consolidations = consolidation_requests
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    # Ensure the validators have been upgraded to compounding validators
    assert spec.has_compounding_withdrawal_credential(state.validators[source_index])


@with_all_phases_from_to(ELECTRA, GLOAS)
@with_presets([MINIMAL], "Keep the size of the test reasonable")
@spec_state_test
def test_withdrawal_requests_when_pending_withdrawal_queue_is_full(spec, state):
    # Move state forward SHARD_COMMITTEE_PERIOD epochs to allow for withdrawal
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # Fill up the queue with invalid pending withdrawals
    # Making these legit would be too much work
    # One less than the limit, to ensure another can be added
    state.pending_partial_withdrawals = [
        spec.PendingPartialWithdrawal(
            validator_index=0x1111,
            amount=spec.Gwei(1),
            # Withdrawable next epoch, so they aren't processed now
            withdrawable_epoch=spec.get_current_epoch(state) + 1,
        )
    ] * (spec.PENDING_PARTIAL_WITHDRAWALS_LIMIT - 1)

    # Setup a compounding validator with an excess balance
    index = 0
    address = b"\x22" * 20
    balance = spec.MIN_ACTIVATION_BALANCE + spec.EFFECTIVE_BALANCE_INCREMENT
    set_compounding_withdrawal_credential_with_balance(
        spec, state, index, balance, balance, address
    )
    assert state.validators[index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield "pre", state

    # Setup two withdrawal requests with different amounts
    withdrawal_request_1 = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=state.validators[index].pubkey,
        amount=spec.Gwei(1),
    )
    withdrawal_request_2 = spec.WithdrawalRequest(
        source_address=address,
        validator_pubkey=state.validators[index].pubkey,
        amount=spec.Gwei(2),
    )

    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_requests.withdrawals = [withdrawal_request_1, withdrawal_request_2]
    block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    # Ensure the pending withdrawals queue is full
    assert len(state.pending_partial_withdrawals) == spec.PENDING_PARTIAL_WITHDRAWALS_LIMIT
    # Ensure the last pending withdrawal is for the first withdrawal request
    last_withdrawal = state.pending_partial_withdrawals[spec.PENDING_PARTIAL_WITHDRAWALS_LIMIT - 1]
    assert last_withdrawal.validator_index == index
    assert last_withdrawal.amount == withdrawal_request_1.amount
    assert withdrawal_request_1.amount != withdrawal_request_2.amount


@with_all_phases_from_to(ELECTRA, GLOAS)
@with_presets([MINIMAL], "need sufficient consolidation churn limit")
@with_custom_state(
    balances_fn=scaled_churn_balances_exceed_activation_exit_churn_limit,
    threshold_fn=default_activation_threshold,
)
@spec_test
@single_phase
def test_multi_epoch_consolidation_chain(spec, state):
    """
    This doesn't work the has I had envisioned, but I guess that's a good reason to keep it. When
    chaining consolidations like this, the transferred balance is limited by the effective balance
    of the source validator, which doesn't update until after all consolidations are processed.
    Given that all validators have the same balance, this is effectively a consolidation from the
    first validator in the consolidation to the final target validator.
    """

    # Move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    # Check that we're at the first slot of the epoch
    assert state.slot % spec.SLOTS_PER_EPOCH == 0
    current_epoch = spec.get_current_epoch(state)

    # This will consolidate 0->1, 1->2, 2->3, ...
    consolidation_request_count = 0
    for i in range(spec.SLOTS_PER_EPOCH):
        consolidation_requests = []
        for j in range(0, spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD):
            # Setup the source validator
            k = i * spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD + j
            source_index = spec.get_active_validator_indices(state, current_epoch)[k]
            source_address = b"\x11" * 20
            set_compounding_withdrawal_credential_with_balance(
                spec,
                state,
                source_index,
                effective_balance=spec.MIN_ACTIVATION_BALANCE,
                balance=spec.MIN_ACTIVATION_BALANCE,
                address=source_address,
            )
            # Setup the target validator
            k = i * spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD + j + 1
            target_index = spec.get_active_validator_indices(state, current_epoch)[k]
            set_compounding_withdrawal_credential_with_balance(
                spec,
                state,
                target_index,
                effective_balance=spec.MIN_ACTIVATION_BALANCE,
                balance=spec.MIN_ACTIVATION_BALANCE,
            )

            # Make the consolidation request
            consolidation_requests.append(
                spec.ConsolidationRequest(
                    source_address=source_address,
                    source_pubkey=state.validators[source_index].pubkey,
                    target_pubkey=state.validators[target_index].pubkey,
                )
            )
            consolidation_request_count += 1

        block = build_empty_block_for_next_slot(spec, state)
        block.body.execution_requests.consolidations = consolidation_requests
        block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
        transition_unsigned_block(spec, state, block)

    # Check that we're in the next epoch
    assert spec.get_current_epoch(state) == current_epoch + 1
    # Check that validators at the beginning of the chain are exited
    assert len(state.pending_consolidations) == consolidation_request_count
    for i in range(consolidation_request_count):
        assert state.validators[i].exit_epoch != spec.FAR_FUTURE_EPOCH

    # Remove MIN_VALIDATOR_WITHDRAWABILITY_DELAY to speed things up
    for i, consolidation in enumerate(state.pending_consolidations):
        state.validators[consolidation.source_index].withdrawable_epoch = (
            state.validators[consolidation.source_index].exit_epoch + 1
        )

    # Get the first slot that consolidations will be processed
    first_consolidation = state.pending_consolidations[0]
    first_slot = (
        state.validators[first_consolidation.source_index].withdrawable_epoch * spec.SLOTS_PER_EPOCH
    )
    # Get the last slot that consolidations will be processed
    final_consolidation = state.pending_consolidations[consolidation_request_count - 1]
    last_slot = (
        state.validators[final_consolidation.source_index].withdrawable_epoch * spec.SLOTS_PER_EPOCH
    )

    # Transition to the slot/epoch when the first consolidation will be processed
    transition_to(spec, state, first_slot - 1)
    # Ensure the none of the pending consolidations were processed
    assert len(state.pending_consolidations) == consolidation_request_count

    yield "pre", state

    # Process slots until all pending consolidations are processed
    blocks = []
    for _ in range(last_slot - first_slot + 1):
        block = build_empty_block_for_next_slot(spec, state)
        block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)
        blocks.append(state_transition_and_sign_block(spec, state, block))

    yield "blocks", blocks
    yield "post", state

    # Ensure all pending consolidations have been processed
    assert len(state.pending_consolidations) == 0
    # Check that the final target validator's effective balance changed.
    # The effective balance of the 2nd to last (~32ETH) validator is added to it.
    final_target_validator = state.validators[final_consolidation.target_index]
    assert final_target_validator.effective_balance > spec.MIN_ACTIVATION_BALANCE
    assert final_target_validator.effective_balance <= 2 * spec.MIN_ACTIVATION_BALANCE
