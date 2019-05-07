from copy import deepcopy

import pytest

from py_ecc import bls
import eth2spec.phase0.spec as spec

from eth2spec.utils.minimal_ssz import signing_root
from eth2spec.phase0.spec import (
    # constants
    ZERO_HASH,
    SLOTS_PER_HISTORICAL_ROOT,
    # SSZ
    Deposit,
    Transfer,
    VoluntaryExit,
    # functions
    get_active_validator_indices,
    get_beacon_proposer_index,
    get_block_root_at_slot,
    get_current_epoch,
    get_domain,
    process_slot,
    verify_merkle_branch,
    state_transition,
    hash,
)
from eth2spec.utils.merkle_minimal import (
    calc_merkle_tree_from_leaves,
    get_merkle_proof,
    get_merkle_root,
)
from .helpers import (
    advance_slot,
    get_balance,
    build_deposit_data,
    build_empty_block_for_next_slot,
    fill_aggregate_attestation,
    get_state_root,
    get_valid_attestation,
    get_valid_attester_slashing,
    get_valid_proposer_slashing,
    next_slot,
    privkeys,
    pubkeys,
)


# mark entire file as 'sanity'
pytestmark = pytest.mark.sanity


def test_slot_transition(state):
    test_state = deepcopy(state)
    process_slot(test_state)
    advance_slot(test_state)
    assert test_state.slot == state.slot + 1
    assert get_state_root(test_state, state.slot) == state.hash_tree_root()
    return test_state


def test_empty_block_transition(state):
    test_state = deepcopy(state)

    block = build_empty_block_for_next_slot(test_state)
    state_transition(test_state, block)

    assert len(test_state.eth1_data_votes) == len(state.eth1_data_votes) + 1
    assert get_block_root_at_slot(test_state, state.slot) == block.previous_block_root

    return state, [block], test_state


def test_skipped_slots(state):
    test_state = deepcopy(state)
    block = build_empty_block_for_next_slot(test_state)
    block.slot += 3

    state_transition(test_state, block)

    assert test_state.slot == block.slot
    for slot in range(state.slot, test_state.slot):
        assert get_block_root_at_slot(test_state, slot) == block.previous_block_root

    return state, [block], test_state


def test_empty_epoch_transition(state):
    test_state = deepcopy(state)
    block = build_empty_block_for_next_slot(test_state)
    block.slot += spec.SLOTS_PER_EPOCH

    state_transition(test_state, block)

    assert test_state.slot == block.slot
    for slot in range(state.slot, test_state.slot):
        assert get_block_root_at_slot(test_state, slot) == block.previous_block_root

    return state, [block], test_state


def test_empty_epoch_transition_not_finalizing(state):
    test_state = deepcopy(state)
    block = build_empty_block_for_next_slot(test_state)
    block.slot += spec.SLOTS_PER_EPOCH * 5

    state_transition(test_state, block)

    assert test_state.slot == block.slot
    assert test_state.finalized_epoch < get_current_epoch(test_state) - 4
    for index in range(len(test_state.validator_registry)):
        assert get_balance(test_state, index) < get_balance(state, index)

    return state, [block], test_state


def test_proposer_slashing(state):
    test_state = deepcopy(state)
    proposer_slashing = get_valid_proposer_slashing(state)
    validator_index = proposer_slashing.proposer_index

    #
    # Add to state via block transition
    #
    block = build_empty_block_for_next_slot(test_state)
    block.body.proposer_slashings.append(proposer_slashing)
    state_transition(test_state, block)

    assert not state.validator_registry[validator_index].slashed

    slashed_validator = test_state.validator_registry[validator_index]
    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
    # lost whistleblower reward
    assert get_balance(test_state, validator_index) < get_balance(state, validator_index)

    return state, [block], test_state


def test_attester_slashing(state):
    test_state = deepcopy(state)
    attester_slashing = get_valid_attester_slashing(state)
    validator_index = attester_slashing.attestation_1.custody_bit_0_indices[0]

    #
    # Add to state via block transition
    #
    block = build_empty_block_for_next_slot(test_state)
    block.body.attester_slashings.append(attester_slashing)
    state_transition(test_state, block)

    assert not state.validator_registry[validator_index].slashed

    slashed_validator = test_state.validator_registry[validator_index]
    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
    # lost whistleblower reward
    assert get_balance(test_state, validator_index) < get_balance(state, validator_index)

    proposer_index = get_beacon_proposer_index(test_state)
    # gained whistleblower reward
    assert (
        get_balance(test_state, proposer_index) >
        get_balance(state, proposer_index)
    )

    return state, [block], test_state


def test_deposit_in_block(state):
    pre_state = deepcopy(state)
    test_deposit_data_leaves = [ZERO_HASH] * len(pre_state.validator_registry)

    index = len(test_deposit_data_leaves)
    pubkey = pubkeys[index]
    privkey = privkeys[index]
    deposit_data = build_deposit_data(pre_state, pubkey, privkey, spec.MAX_EFFECTIVE_BALANCE)

    item = deposit_data.hash_tree_root()
    test_deposit_data_leaves.append(item)
    tree = calc_merkle_tree_from_leaves(tuple(test_deposit_data_leaves))
    root = get_merkle_root((tuple(test_deposit_data_leaves)))
    proof = list(get_merkle_proof(tree, item_index=index))
    assert verify_merkle_branch(item, proof, spec.DEPOSIT_CONTRACT_TREE_DEPTH, index, root)

    deposit = Deposit(
        proof=list(proof),
        index=index,
        data=deposit_data,
    )

    pre_state.latest_eth1_data.deposit_root = root
    pre_state.latest_eth1_data.deposit_count = len(test_deposit_data_leaves)
    post_state = deepcopy(pre_state)
    block = build_empty_block_for_next_slot(post_state)
    block.body.deposits.append(deposit)

    state_transition(post_state, block)
    assert len(post_state.validator_registry) == len(state.validator_registry) + 1
    assert len(post_state.balances) == len(state.balances) + 1
    assert get_balance(post_state, index) == spec.MAX_EFFECTIVE_BALANCE
    assert post_state.validator_registry[index].pubkey == pubkeys[index]

    return pre_state, [block], post_state


def test_deposit_top_up(state):
    pre_state = deepcopy(state)
    test_deposit_data_leaves = [ZERO_HASH] * len(pre_state.validator_registry)

    validator_index = 0
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    pubkey = pubkeys[validator_index]
    privkey = privkeys[validator_index]
    deposit_data = build_deposit_data(pre_state, pubkey, privkey, amount)

    merkle_index = len(test_deposit_data_leaves)
    item = deposit_data.hash_tree_root()
    test_deposit_data_leaves.append(item)
    tree = calc_merkle_tree_from_leaves(tuple(test_deposit_data_leaves))
    root = get_merkle_root((tuple(test_deposit_data_leaves)))
    proof = list(get_merkle_proof(tree, item_index=merkle_index))
    assert verify_merkle_branch(item, proof, spec.DEPOSIT_CONTRACT_TREE_DEPTH, merkle_index, root)

    deposit = Deposit(
        proof=list(proof),
        index=merkle_index,
        data=deposit_data,
    )

    pre_state.latest_eth1_data.deposit_root = root
    pre_state.latest_eth1_data.deposit_count = len(test_deposit_data_leaves)
    block = build_empty_block_for_next_slot(pre_state)
    block.body.deposits.append(deposit)

    pre_balance = get_balance(pre_state, validator_index)
    post_state = deepcopy(pre_state)
    state_transition(post_state, block)
    assert len(post_state.validator_registry) == len(pre_state.validator_registry)
    assert len(post_state.balances) == len(pre_state.balances)
    assert get_balance(post_state, validator_index) == pre_balance + amount

    return pre_state, [block], post_state


def test_attestation(state):
    state.slot = spec.SLOTS_PER_EPOCH
    test_state = deepcopy(state)
    attestation = get_valid_attestation(state)

    #
    # Add to state via block transition
    #
    attestation_block = build_empty_block_for_next_slot(test_state)
    attestation_block.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY
    attestation_block.body.attestations.append(attestation)
    state_transition(test_state, attestation_block)

    assert len(test_state.current_epoch_attestations) == len(state.current_epoch_attestations) + 1


    #
    # Epoch transition should move to previous_epoch_attestations
    #
    pre_current_epoch_attestations = deepcopy(test_state.current_epoch_attestations)

    epoch_block = build_empty_block_for_next_slot(test_state)
    epoch_block.slot += spec.SLOTS_PER_EPOCH
    state_transition(test_state, epoch_block)

    assert len(test_state.current_epoch_attestations) == 0
    assert test_state.previous_epoch_attestations == pre_current_epoch_attestations

    return state, [attestation_block, epoch_block], test_state


def test_voluntary_exit(state):
    pre_state = deepcopy(state)
    validator_index = get_active_validator_indices(
        pre_state,
        get_current_epoch(pre_state)
    )[-1]

    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow for exit
    pre_state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    post_state = deepcopy(pre_state)

    voluntary_exit = VoluntaryExit(
        epoch=get_current_epoch(pre_state),
        validator_index=validator_index,
    )
    voluntary_exit.signature = bls.sign(
        message_hash=signing_root(voluntary_exit),
        privkey=privkeys[validator_index],
        domain=get_domain(
            state=pre_state,
            domain_type=spec.DOMAIN_VOLUNTARY_EXIT,
        )
    )

    #
    # Add to state via block transition
    #
    initiate_exit_block = build_empty_block_for_next_slot(post_state)
    initiate_exit_block.body.voluntary_exits.append(voluntary_exit)
    state_transition(post_state, initiate_exit_block)

    assert post_state.validator_registry[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH

    #
    # Process within epoch transition
    #
    exit_block = build_empty_block_for_next_slot(post_state)
    exit_block.slot += spec.SLOTS_PER_EPOCH
    state_transition(post_state, exit_block)

    assert post_state.validator_registry[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH

    return pre_state, [initiate_exit_block, exit_block], post_state


def test_transfer(state):
    # overwrite default 0 to test
    spec.MAX_TRANSFERS = 1

    pre_state = deepcopy(state)
    current_epoch = get_current_epoch(pre_state)
    sender_index = get_active_validator_indices(pre_state, current_epoch)[-1]
    recipient_index = get_active_validator_indices(pre_state, current_epoch)[0]
    transfer_pubkey = pubkeys[-1]
    transfer_privkey = privkeys[-1]
    amount = get_balance(pre_state, sender_index)
    pre_transfer_recipient_balance = get_balance(pre_state, recipient_index)
    transfer = Transfer(
        sender=sender_index,
        recipient=recipient_index,
        amount=amount,
        fee=0,
        slot=pre_state.slot + 1,
        pubkey=transfer_pubkey,
    )
    transfer.signature = bls.sign(
        message_hash=signing_root(transfer),
        privkey=transfer_privkey,
        domain=get_domain(
            state=pre_state,
            domain_type=spec.DOMAIN_TRANSFER,
        )
    )

    # ensure withdrawal_credentials reproducable
    pre_state.validator_registry[sender_index].withdrawal_credentials = (
        spec.BLS_WITHDRAWAL_PREFIX_BYTE + hash(transfer_pubkey)[1:]
    )
    # un-activate so validator can transfer
    pre_state.validator_registry[sender_index].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH

    post_state = deepcopy(pre_state)
    #
    # Add to state via block transition
    #
    block = build_empty_block_for_next_slot(post_state)
    block.body.transfers.append(transfer)
    state_transition(post_state, block)

    sender_balance = get_balance(post_state, sender_index)
    recipient_balance = get_balance(post_state, recipient_index)
    assert sender_balance == 0
    assert recipient_balance == pre_transfer_recipient_balance + amount

    return pre_state, [block], post_state


def test_balance_driven_status_transitions(state):
    current_epoch = get_current_epoch(state)
    validator_index = get_active_validator_indices(state, current_epoch)[-1]

    assert state.validator_registry[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    # set validator balance to below ejection threshold
    state.validator_registry[validator_index].effective_balance = spec.EJECTION_BALANCE

    post_state = deepcopy(state)
    #
    # trigger epoch transition
    #
    block = build_empty_block_for_next_slot(post_state)
    block.slot += spec.SLOTS_PER_EPOCH
    state_transition(post_state, block)

    assert post_state.validator_registry[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH

    return state, [block], post_state


def test_historical_batch(state):
    state.slot += spec.SLOTS_PER_HISTORICAL_ROOT - (state.slot % spec.SLOTS_PER_HISTORICAL_ROOT) - 1

    post_state = deepcopy(state)

    block = build_empty_block_for_next_slot(post_state)

    state_transition(post_state, block)

    assert post_state.slot == block.slot
    assert get_current_epoch(post_state) % (spec.SLOTS_PER_HISTORICAL_ROOT // spec.SLOTS_PER_EPOCH) == 0
    assert len(post_state.historical_roots) == len(state.historical_roots) + 1

    return state, [block], post_state


def test_eth1_data_votes(state):
    post_state = deepcopy(state)

    expected_votes = 0
    assert len(state.eth1_data_votes) == expected_votes

    blocks = []
    for _ in range(spec.SLOTS_PER_ETH1_VOTING_PERIOD - 1):
        block = build_empty_block_for_next_slot(post_state)
        state_transition(post_state, block)
        expected_votes += 1
        assert len(post_state.eth1_data_votes) == expected_votes
        blocks.append(block)

    block = build_empty_block_for_next_slot(post_state)
    state_transition(post_state, block)
    blocks.append(block)

    assert post_state.slot % spec.SLOTS_PER_ETH1_VOTING_PERIOD == 0
    assert len(post_state.eth1_data_votes) == 1

    return state, blocks, post_state
