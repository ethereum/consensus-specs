from copy import deepcopy

from eth2spec.utils import bls

from eth2spec.test.helpers.state import get_balance, state_transition_and_sign_block, next_slot
from eth2spec.test.helpers.block import build_empty_block_for_next_slot, build_empty_block, sign_block, \
    transition_unsigned_block
from eth2spec.test.helpers.keys import privkeys, pubkeys
from eth2spec.test.helpers.attester_slashings import get_valid_attester_slashing, get_indexed_attestation_participants
from eth2spec.test.helpers.proposer_slashings import get_valid_proposer_slashing
from eth2spec.test.helpers.attestations import get_valid_attestation
from eth2spec.test.helpers.deposits import prepare_state_and_deposit

from eth2spec.test.context import spec_state_test, with_all_phases, expect_assertion_error, always_bls


@with_all_phases
@spec_state_test
def test_prev_slot_block_transition(spec, state):
    # Go to clean slot
    spec.process_slots(state, state.slot + 1)
    # Make a block for it
    block = build_empty_block(spec, state, slot=state.slot)
    proposer_index = spec.get_beacon_proposer_index(state)
    # Transition to next slot, above block will not be invalid on top of new state.
    spec.process_slots(state, state.slot + 1)

    yield 'pre', state
    # State is beyond block slot, but the block can still be realistic when invalid.
    # Try the transition, and update the state root to where it is halted. Then sign with the supposed proposer.
    expect_assertion_error(lambda: transition_unsigned_block(spec, state, block))
    block.state_root = state.hash_tree_root()
    signed_block = sign_block(spec, state, block, proposer_index=proposer_index)
    yield 'blocks', [signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
def test_same_slot_block_transition(spec, state):
    # Same slot on top of pre-state, but move out of slot 0 first.
    spec.process_slots(state, state.slot + 1)

    block = build_empty_block(spec, state, slot=state.slot)

    yield 'pre', state

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state


@with_all_phases
@spec_state_test
def test_empty_block_transition(spec, state):
    pre_slot = state.slot
    pre_eth1_votes = len(state.eth1_data_votes)

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert len(state.eth1_data_votes) == pre_eth1_votes + 1
    assert spec.get_block_root_at_slot(state, pre_slot) == signed_block.message.parent_root
    assert spec.get_randao_mix(state, spec.get_current_epoch(state)) != spec.Bytes32()


@with_all_phases
@spec_state_test
def test_invalid_state_root(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    block.state_root = b"\xaa" * 32
    signed_block = sign_block(spec, state, block)

    expect_assertion_error(lambda: spec.state_transition(state, signed_block))

    yield 'blocks', [signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
@always_bls
def test_zero_block_sig(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    invalid_signed_block = spec.SignedBeaconBlock(message=block)
    expect_assertion_error(lambda: spec.state_transition(state, invalid_signed_block))

    yield 'blocks', [invalid_signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_block_sig(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    domain = spec.get_domain(state, spec.DOMAIN_BEACON_PROPOSER, spec.compute_epoch_at_slot(block.slot))
    signing_root = spec.compute_signing_root(block, domain)
    invalid_signed_block = spec.SignedBeaconBlock(
        message=block,
        signature=bls.Sign(123456, signing_root)
    )
    expect_assertion_error(lambda: spec.state_transition(state, invalid_signed_block))

    yield 'blocks', [invalid_signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_proposer_index_sig_from_expected_proposer(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    expect_proposer_index = block.proposer_index

    # Set invalid proposer index but correct signature wrt expected proposer
    active_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state))
    active_indices = [i for i in active_indices if i != block.proposer_index]
    block.proposer_index = active_indices[0]  # invalid proposer index

    invalid_signed_block = sign_block(spec, state, block, expect_proposer_index)

    expect_assertion_error(lambda: spec.state_transition(state, invalid_signed_block))

    yield 'blocks', [invalid_signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_proposer_index_sig_from_proposer_index(spec, state):
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)

    # Set invalid proposer index but correct signature wrt proposer_index
    active_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state))
    active_indices = [i for i in active_indices if i != block.proposer_index]
    block.proposer_index = active_indices[0]  # invalid proposer index

    invalid_signed_block = sign_block(spec, state, block, block.proposer_index)

    expect_assertion_error(lambda: spec.state_transition(state, invalid_signed_block))

    yield 'blocks', [invalid_signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
def test_skipped_slots(spec, state):
    pre_slot = state.slot
    yield 'pre', state

    block = build_empty_block(spec, state, state.slot + 4)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.slot == block.slot
    assert spec.get_randao_mix(state, spec.get_current_epoch(state)) != spec.Bytes32()
    for slot in range(pre_slot, state.slot):
        assert spec.get_block_root_at_slot(state, slot) == block.parent_root


@with_all_phases
@spec_state_test
def test_empty_epoch_transition(spec, state):
    pre_slot = state.slot
    yield 'pre', state

    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.slot == block.slot
    for slot in range(pre_slot, state.slot):
        assert spec.get_block_root_at_slot(state, slot) == block.parent_root


@with_all_phases
@spec_state_test
def test_empty_epoch_transition_not_finalizing(spec, state):
    # Don't run for non-minimal configs, it takes very long, and the effect
    # of calling finalization/justification is just the same as with the minimal configuration.
    if spec.SLOTS_PER_EPOCH > 8:
        return

    # copy for later balance lookups.
    pre_balances = list(state.balances)
    yield 'pre', state

    spec.process_slots(state, state.slot + (spec.SLOTS_PER_EPOCH * 5))
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.slot == block.slot
    assert state.finalized_checkpoint.epoch < spec.get_current_epoch(state) - 4
    for index in range(len(state.validators)):
        assert state.balances[index] < pre_balances[index]


@with_all_phases
@spec_state_test
def test_proposer_slashing(spec, state):
    # copy for later balance lookups.
    pre_state = deepcopy(state)
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)
    validator_index = proposer_slashing.signed_header_1.message.proposer_index

    assert not state.validators[validator_index].slashed

    yield 'pre', state

    #
    # Add to state via block transition
    #
    block = build_empty_block_for_next_slot(spec, state)
    block.body.proposer_slashings.append(proposer_slashing)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    # check if slashed
    slashed_validator = state.validators[validator_index]
    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
    # lost whistleblower reward
    assert get_balance(state, validator_index) < get_balance(pre_state, validator_index)


@with_all_phases
@spec_state_test
def test_attester_slashing(spec, state):
    # copy for later balance lookups.
    pre_state = deepcopy(state)

    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)
    validator_index = get_indexed_attestation_participants(spec, attester_slashing.attestation_1)[0]

    assert not state.validators[validator_index].slashed

    yield 'pre', state

    #
    # Add to state via block transition
    #
    block = build_empty_block_for_next_slot(spec, state)
    block.body.attester_slashings.append(attester_slashing)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    slashed_validator = state.validators[validator_index]
    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
    # lost whistleblower reward
    assert get_balance(state, validator_index) < get_balance(pre_state, validator_index)

    proposer_index = spec.get_beacon_proposer_index(state)
    # gained whistleblower reward
    assert (
        get_balance(state, proposer_index) >
        get_balance(pre_state, proposer_index)
    )


@with_all_phases
@spec_state_test
def test_proposer_after_inactive_index(spec, state):
    # disable some low validator index to check after for
    inactive_index = 10
    state.validators[inactive_index].exit_epoch = spec.get_current_epoch(state)

    # skip forward, get brand new proposers
    state.slot = spec.SLOTS_PER_EPOCH * 2
    block = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, block)

    while True:
        next_slot(spec, state)
        proposer_index = spec.get_beacon_proposer_index(state)
        if proposer_index > inactive_index:
            # found a proposer that has a higher index than a disabled validator
            yield 'pre', state
            # test if the proposer can be recognized correctly after the inactive validator
            signed_block = state_transition_and_sign_block(spec, state, build_empty_block(spec, state))
            yield 'blocks', [signed_block]
            yield 'post', state
            break


@with_all_phases
@spec_state_test
def test_high_proposer_index(spec, state):
    # disable a good amount of validators to make the active count lower, for a faster test
    current_epoch = spec.get_current_epoch(state)
    for i in range(len(state.validators) // 3):
        state.validators[i].exit_epoch = current_epoch

    # skip forward, get brand new proposers
    state.slot = spec.SLOTS_PER_EPOCH * 2
    block = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, block)

    active_count = len(spec.get_active_validator_indices(state, current_epoch))
    while True:
        next_slot(spec, state)
        proposer_index = spec.get_beacon_proposer_index(state)
        if proposer_index >= active_count:
            # found a proposer that has a higher index than the active validator count
            yield 'pre', state
            # test if the proposer can be recognized correctly, even while it has a high index.
            signed_block = state_transition_and_sign_block(spec, state, build_empty_block(spec, state))
            yield 'blocks', [signed_block]
            yield 'post', state
            break


@with_all_phases
@spec_state_test
def test_expected_deposit_in_block(spec, state):
    # Make the state expect a deposit, then don't provide it.
    state.eth1_data.deposit_count += 1
    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield 'blocks', [signed_block]
    yield 'post', None


@with_all_phases
@spec_state_test
def test_deposit_in_block(spec, state):
    initial_registry_len = len(state.validators)
    initial_balances_len = len(state.balances)

    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.deposits.append(deposit)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert len(state.validators) == initial_registry_len + 1
    assert len(state.balances) == initial_balances_len + 1
    assert get_balance(state, validator_index) == spec.MAX_EFFECTIVE_BALANCE
    assert state.validators[validator_index].pubkey == pubkeys[validator_index]


@with_all_phases
@spec_state_test
def test_deposit_top_up(spec, state):
    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount)

    initial_registry_len = len(state.validators)
    initial_balances_len = len(state.balances)
    validator_pre_balance = get_balance(state, validator_index)

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.deposits.append(deposit)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert len(state.validators) == initial_registry_len
    assert len(state.balances) == initial_balances_len
    assert get_balance(state, validator_index) == validator_pre_balance + amount


@with_all_phases
@spec_state_test
def test_attestation(spec, state):
    state.slot = spec.SLOTS_PER_EPOCH

    yield 'pre', state

    attestation = get_valid_attestation(spec, state, signed=True)

    # Add to state via block transition
    pre_current_attestations_len = len(state.current_epoch_attestations)
    attestation_block = build_empty_block(spec, state, state.slot + 1 + spec.MIN_ATTESTATION_INCLUSION_DELAY)
    attestation_block.body.attestations.append(attestation)
    signed_attestation_block = state_transition_and_sign_block(spec, state, attestation_block)

    assert len(state.current_epoch_attestations) == pre_current_attestations_len + 1

    # Epoch transition should move to previous_epoch_attestations
    pre_current_attestations_root = spec.hash_tree_root(state.current_epoch_attestations)

    epoch_block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_epoch_block = state_transition_and_sign_block(spec, state, epoch_block)

    yield 'blocks', [signed_attestation_block, signed_epoch_block]
    yield 'post', state

    assert len(state.current_epoch_attestations) == 0
    assert spec.hash_tree_root(state.previous_epoch_attestations) == pre_current_attestations_root


@with_all_phases
@spec_state_test
def test_voluntary_exit(spec, state):
    validator_index = spec.get_active_validator_indices(
        state,
        spec.get_current_epoch(state)
    )[-1]

    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    yield 'pre', state

    voluntary_exit = spec.VoluntaryExit(
        epoch=spec.get_current_epoch(state),
        validator_index=validator_index,
    )
    domain = spec.get_domain(state, spec.DOMAIN_VOLUNTARY_EXIT)
    signing_root = spec.compute_signing_root(voluntary_exit, domain)
    signed_voluntary_exit = spec.SignedVoluntaryExit(
        message=voluntary_exit,
        signature=bls.Sign(privkeys[validator_index], signing_root)
    )

    # Add to state via block transition
    initiate_exit_block = build_empty_block_for_next_slot(spec, state)
    initiate_exit_block.body.voluntary_exits.append(signed_voluntary_exit)
    signed_initiate_exit_block = state_transition_and_sign_block(spec, state, initiate_exit_block)

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH

    # Process within epoch transition
    exit_block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_exit_block = state_transition_and_sign_block(spec, state, exit_block)

    yield 'blocks', [signed_initiate_exit_block, signed_exit_block]
    yield 'post', state

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_all_phases
@spec_state_test
def test_balance_driven_status_transitions(spec, state):
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[-1]

    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    # set validator balance to below ejection threshold
    state.validators[validator_index].effective_balance = spec.EJECTION_BALANCE

    yield 'pre', state

    # trigger epoch transition
    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_all_phases
@spec_state_test
def test_historical_batch(spec, state):
    state.slot += spec.SLOTS_PER_HISTORICAL_ROOT - (state.slot % spec.SLOTS_PER_HISTORICAL_ROOT) - 1
    pre_historical_roots_len = len(state.historical_roots)

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.slot == block.slot
    assert spec.get_current_epoch(state) % (spec.SLOTS_PER_HISTORICAL_ROOT // spec.SLOTS_PER_EPOCH) == 0
    assert len(state.historical_roots) == pre_historical_roots_len + 1


@with_all_phases
@spec_state_test
def test_eth1_data_votes_consensus(spec, state):
    # Don't run when it will take very, very long to simulate. Minimal configuration suffices.
    if spec.EPOCHS_PER_ETH1_VOTING_PERIOD > 2:
        return

    voting_period_slots = spec.EPOCHS_PER_ETH1_VOTING_PERIOD * spec.SLOTS_PER_EPOCH

    offset_block = build_empty_block(spec, state, slot=voting_period_slots - 1)
    state_transition_and_sign_block(spec, state, offset_block)
    yield 'pre', state

    a = b'\xaa' * 32
    b = b'\xbb' * 32
    c = b'\xcc' * 32

    blocks = []

    for i in range(0, voting_period_slots):
        block = build_empty_block_for_next_slot(spec, state)
        # wait for over 50% for A, then start voting B
        block.body.eth1_data.block_hash = b if i * 2 > voting_period_slots else a
        signed_block = state_transition_and_sign_block(spec, state, block)
        blocks.append(signed_block)

    assert len(state.eth1_data_votes) == voting_period_slots
    assert state.eth1_data.block_hash == a

    # transition to next eth1 voting period
    block = build_empty_block_for_next_slot(spec, state)
    block.body.eth1_data.block_hash = c
    signed_block = state_transition_and_sign_block(spec, state, block)
    blocks.append(signed_block)

    yield 'blocks', blocks
    yield 'post', state

    assert state.eth1_data.block_hash == a
    assert state.slot % voting_period_slots == 0
    assert len(state.eth1_data_votes) == 1
    assert state.eth1_data_votes[0].block_hash == c


@with_all_phases
@spec_state_test
def test_eth1_data_votes_no_consensus(spec, state):
    # Don't run when it will take very, very long to simulate. Minimal configuration suffices.
    if spec.EPOCHS_PER_ETH1_VOTING_PERIOD > 2:
        return

    voting_period_slots = spec.EPOCHS_PER_ETH1_VOTING_PERIOD * spec.SLOTS_PER_EPOCH

    pre_eth1_hash = state.eth1_data.block_hash

    offset_block = build_empty_block(spec, state, slot=voting_period_slots - 1)
    state_transition_and_sign_block(spec, state, offset_block)
    yield 'pre', state

    a = b'\xaa' * 32
    b = b'\xbb' * 32

    blocks = []

    for i in range(0, voting_period_slots):
        block = build_empty_block_for_next_slot(spec, state)
        # wait for precisely 50% for A, then start voting B for other 50%
        block.body.eth1_data.block_hash = b if i * 2 >= voting_period_slots else a
        signed_block = state_transition_and_sign_block(spec, state, block)
        blocks.append(signed_block)

    assert len(state.eth1_data_votes) == voting_period_slots
    assert state.eth1_data.block_hash == pre_eth1_hash

    yield 'blocks', blocks
    yield 'post', state
