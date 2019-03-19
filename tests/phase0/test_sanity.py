from copy import deepcopy

import pytest

from py_ecc import bls
import build.phase0.spec as spec

from build.phase0.utils.minimal_ssz import signed_root
from build.phase0.spec import (
    # constants
    EMPTY_SIGNATURE,
    ZERO_HASH,
    # SSZ
    Attestation,
    AttestationDataAndCustodyBit,
    BeaconBlockHeader,
    Deposit,
    Transfer,
    ProposerSlashing,
    VoluntaryExit,
    # functions
    get_active_validator_indices,
    get_attestation_participants,
    get_block_root,
    get_crosslink_committees_at_slot,
    get_current_epoch,
    get_domain,
    get_state_root,
    advance_slot,
    cache_state,
    verify_merkle_branch,
    hash,
)
from build.phase0.state_transition import (
    state_transition,
)
from build.phase0.utils.merkle_minimal import (
    calc_merkle_tree_from_leaves,
    get_merkle_proof,
    get_merkle_root,
)
from tests.phase0.helpers import (
    build_attestation_data,
    build_deposit_data,
    build_empty_block_for_next_slot,
)


# mark entire file as 'sanity'
pytestmark = pytest.mark.sanity


def test_slot_transition(state):
    test_state = deepcopy(state)
    cache_state(test_state)
    advance_slot(test_state)
    assert test_state.slot == state.slot + 1
    assert get_state_root(test_state, state.slot) == state.hash_tree_root()
    return test_state


def test_empty_block_transition(state):
    test_state = deepcopy(state)

    block = build_empty_block_for_next_slot(test_state)
    state_transition(test_state, block)

    assert len(test_state.eth1_data_votes) == len(state.eth1_data_votes) + 1
    assert get_block_root(test_state, state.slot) == block.previous_block_root

    return state, [block], test_state


def test_skipped_slots(state):
    test_state = deepcopy(state)
    block = build_empty_block_for_next_slot(test_state)
    block.slot += 3

    state_transition(test_state, block)

    assert test_state.slot == block.slot
    for slot in range(state.slot, test_state.slot):
        assert get_block_root(test_state, slot) == block.previous_block_root

    return state, [block], test_state


def test_empty_epoch_transition(state):
    test_state = deepcopy(state)
    block = build_empty_block_for_next_slot(test_state)
    block.slot += spec.SLOTS_PER_EPOCH

    state_transition(test_state, block)

    assert test_state.slot == block.slot
    for slot in range(state.slot, test_state.slot):
        assert get_block_root(test_state, slot) == block.previous_block_root

    return state, [block], test_state


def test_empty_epoch_transition_not_finalizing(state):
    test_state = deepcopy(state)
    block = build_empty_block_for_next_slot(test_state)
    block.slot += spec.SLOTS_PER_EPOCH * 5

    state_transition(test_state, block)

    assert test_state.slot == block.slot
    assert test_state.finalized_epoch < get_current_epoch(test_state) - 4

    return state, [block], test_state


def test_proposer_slashing(state, pubkeys, privkeys):
    test_state = deepcopy(state)
    current_epoch = get_current_epoch(test_state)
    validator_index = get_active_validator_indices(test_state.validator_registry, current_epoch)[-1]
    privkey = privkeys[validator_index]
    slot = spec.GENESIS_SLOT
    header_1 = BeaconBlockHeader(
        slot=slot,
        previous_block_root=ZERO_HASH,
        state_root=ZERO_HASH,
        block_body_root=ZERO_HASH,
        signature=EMPTY_SIGNATURE,
    )
    header_2 = deepcopy(header_1)
    header_2.previous_block_root = b'\x02' * 32
    header_2.slot = slot + 1

    domain = get_domain(
        fork=test_state.fork,
        epoch=get_current_epoch(test_state),
        domain_type=spec.DOMAIN_BEACON_BLOCK,
    )
    header_1.signature = bls.sign(
        message_hash=signed_root(header_1),
        privkey=privkey,
        domain=domain,
    )
    header_2.signature = bls.sign(
        message_hash=signed_root(header_2),
        privkey=privkey,
        domain=domain,
    )

    proposer_slashing = ProposerSlashing(
        proposer_index=validator_index,
        header_1=header_1,
        header_2=header_2,
    )

    #
    # Add to state via block transition
    #
    block = build_empty_block_for_next_slot(test_state)
    block.body.proposer_slashings.append(proposer_slashing)
    state_transition(test_state, block)

    assert not state.validator_registry[validator_index].initiated_exit
    assert not state.validator_registry[validator_index].slashed

    slashed_validator = test_state.validator_registry[validator_index]
    assert not slashed_validator.initiated_exit
    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
    # lost whistleblower reward
    assert test_state.validator_balances[validator_index] < state.validator_balances[validator_index]

    return state, [block], test_state


def test_deposit_in_block(state, deposit_data_leaves, pubkeys, privkeys):
    pre_state = deepcopy(state)
    test_deposit_data_leaves = deepcopy(deposit_data_leaves)

    index = len(test_deposit_data_leaves)
    pubkey = pubkeys[index]
    privkey = privkeys[index]
    deposit_data = build_deposit_data(pre_state, pubkey, privkey, spec.MAX_DEPOSIT_AMOUNT)

    item = hash(deposit_data.serialize())
    test_deposit_data_leaves.append(item)
    tree = calc_merkle_tree_from_leaves(tuple(test_deposit_data_leaves))
    root = get_merkle_root((tuple(test_deposit_data_leaves)))
    proof = list(get_merkle_proof(tree, item_index=index))
    assert verify_merkle_branch(item, proof, spec.DEPOSIT_CONTRACT_TREE_DEPTH, index, root)

    deposit = Deposit(
        proof=list(proof),
        index=index,
        deposit_data=deposit_data,
    )

    pre_state.latest_eth1_data.deposit_root = root
    post_state = deepcopy(pre_state)
    block = build_empty_block_for_next_slot(post_state)
    block.body.deposits.append(deposit)

    state_transition(post_state, block)
    assert len(post_state.validator_registry) == len(state.validator_registry) + 1
    assert len(post_state.validator_balances) == len(state.validator_balances) + 1
    assert post_state.validator_registry[index].pubkey == pubkeys[index]

    return pre_state, [block], post_state


def test_deposit_top_up(state, pubkeys, privkeys, deposit_data_leaves):
    pre_state = deepcopy(state)
    test_deposit_data_leaves = deepcopy(deposit_data_leaves)

    validator_index = 0
    amount = spec.MAX_DEPOSIT_AMOUNT // 4
    pubkey = pubkeys[validator_index]
    privkey = privkeys[validator_index]
    deposit_data = build_deposit_data(pre_state, pubkey, privkey, amount)

    merkle_index = len(test_deposit_data_leaves)
    item = hash(deposit_data.serialize())
    test_deposit_data_leaves.append(item)
    tree = calc_merkle_tree_from_leaves(tuple(test_deposit_data_leaves))
    root = get_merkle_root((tuple(test_deposit_data_leaves)))
    proof = list(get_merkle_proof(tree, item_index=merkle_index))
    assert verify_merkle_branch(item, proof, spec.DEPOSIT_CONTRACT_TREE_DEPTH, merkle_index, root)

    deposit = Deposit(
        proof=list(proof),
        index=merkle_index,
        deposit_data=deposit_data,
    )

    pre_state.latest_eth1_data.deposit_root = root
    block = build_empty_block_for_next_slot(pre_state)
    block.body.deposits.append(deposit)

    pre_balance = pre_state.validator_balances[validator_index]
    post_state = deepcopy(pre_state)
    state_transition(post_state, block)
    assert len(post_state.validator_registry) == len(pre_state.validator_registry)
    assert len(post_state.validator_balances) == len(pre_state.validator_balances)
    assert post_state.validator_balances[validator_index] == pre_balance + amount

    return pre_state, [block], post_state


def test_attestation(state, pubkeys, privkeys):
    test_state = deepcopy(state)
    slot = state.slot
    shard = state.current_shuffling_start_shard
    attestation_data = build_attestation_data(state, slot, shard)

    crosslink_committees = get_crosslink_committees_at_slot(state, slot)
    crosslink_committee = [committee for committee, _shard in crosslink_committees if _shard == attestation_data.shard][0]

    committee_size = len(crosslink_committee)
    bitfield_length = (committee_size + 7) // 8
    aggregation_bitfield = b'\x01' + b'\x00' * (bitfield_length - 1)
    custody_bitfield = b'\x00' * bitfield_length
    attestation = Attestation(
        aggregation_bitfield=aggregation_bitfield,
        data=attestation_data,
        custody_bitfield=custody_bitfield,
        aggregate_signature=EMPTY_SIGNATURE,
    )
    participants = get_attestation_participants(
        test_state,
        attestation.data,
        attestation.aggregation_bitfield,
    )
    assert len(participants) == 1

    validator_index = participants[0]
    privkey = privkeys[validator_index]

    message_hash = AttestationDataAndCustodyBit(
        data=attestation.data,
        custody_bit=0b0,
    ).hash_tree_root()

    attestation.aggregation_signature = bls.sign(
        message_hash=message_hash,
        privkey=privkey,
        domain=get_domain(
            fork=test_state.fork,
            epoch=get_current_epoch(test_state),
            domain_type=spec.DOMAIN_ATTESTATION,
        )
    )

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


def test_voluntary_exit(state, pubkeys, privkeys):
    pre_state = deepcopy(state)
    validator_index = get_active_validator_indices(
        pre_state.validator_registry,
        get_current_epoch(pre_state)
    )[-1]

    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow for exit
    pre_state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    # artificially trigger registry update at next epoch transition
    pre_state.finalized_epoch = get_current_epoch(pre_state) - 1
    for crosslink in pre_state.latest_crosslinks:
        crosslink.epoch = pre_state.finalized_epoch
    pre_state.validator_registry_update_epoch = pre_state.finalized_epoch - 1

    post_state = deepcopy(pre_state)

    voluntary_exit = VoluntaryExit(
        epoch=get_current_epoch(pre_state),
        validator_index=validator_index,
        signature=EMPTY_SIGNATURE,
    )
    voluntary_exit.signature = bls.sign(
        message_hash=signed_root(voluntary_exit),
        privkey=privkeys[validator_index],
        domain=get_domain(
            fork=pre_state.fork,
            epoch=get_current_epoch(pre_state),
            domain_type=spec.DOMAIN_VOLUNTARY_EXIT,
        )
    )

    #
    # Add to state via block transition
    #
    initiate_exit_block = build_empty_block_for_next_slot(post_state)
    initiate_exit_block.body.voluntary_exits.append(voluntary_exit)
    state_transition(post_state, initiate_exit_block)

    assert not pre_state.validator_registry[validator_index].initiated_exit
    assert post_state.validator_registry[validator_index].initiated_exit
    assert post_state.validator_registry[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    #
    # Process within epoch transition
    #
    exit_block = build_empty_block_for_next_slot(post_state)
    exit_block.slot += spec.SLOTS_PER_EPOCH
    state_transition(post_state, exit_block)

    assert post_state.validator_registry[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH

    return pre_state, [initiate_exit_block, exit_block], post_state


def test_transfer(state, pubkeys, privkeys):
    pre_state = deepcopy(state)
    current_epoch = get_current_epoch(pre_state)
    sender_index = get_active_validator_indices(pre_state.validator_registry, current_epoch)[-1]
    recipient_index = get_active_validator_indices(pre_state.validator_registry, current_epoch)[0]
    transfer_pubkey = pubkeys[-1]
    transfer_privkey = privkeys[-1]
    amount = pre_state.validator_balances[sender_index]
    pre_transfer_recipient_balance = pre_state.validator_balances[recipient_index]
    transfer = Transfer(
        sender=sender_index,
        recipient=recipient_index,
        amount=amount,
        fee=0,
        slot=pre_state.slot + 1,
        pubkey=transfer_pubkey,
        signature=EMPTY_SIGNATURE,
    )
    transfer.signature = bls.sign(
        message_hash=signed_root(transfer),
        privkey=transfer_privkey,
        domain=get_domain(
            fork=pre_state.fork,
            epoch=get_current_epoch(pre_state),
            domain_type=spec.DOMAIN_TRANSFER,
        )
    )

    # ensure withdrawal_credentials reproducable
    pre_state.validator_registry[sender_index].withdrawal_credentials = (
        spec.BLS_WITHDRAWAL_PREFIX_BYTE + hash(transfer_pubkey)[1:]
    )
    # un-activate so validator can transfer
    pre_state.validator_registry[sender_index].activation_epoch = spec.FAR_FUTURE_EPOCH

    post_state = deepcopy(pre_state)
    #
    # Add to state via block transition
    #
    block = build_empty_block_for_next_slot(post_state)
    block.body.transfers.append(transfer)
    state_transition(post_state, block)

    sender_balance = post_state.validator_balances[sender_index]
    recipient_balance = post_state.validator_balances[recipient_index]
    assert sender_balance == 0
    assert recipient_balance == pre_transfer_recipient_balance + amount

    return pre_state, [block], post_state


def test_ejection(state):
    pre_state = deepcopy(state)

    current_epoch = get_current_epoch(pre_state)
    validator_index = get_active_validator_indices(pre_state.validator_registry, current_epoch)[-1]

    assert pre_state.validator_registry[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    # set validator balance to below ejection threshold
    pre_state.validator_balances[validator_index] = spec.EJECTION_BALANCE - 1

    post_state = deepcopy(pre_state)
    #
    # trigger epoch transition
    #
    block = build_empty_block_for_next_slot(post_state)
    block.slot += spec.SLOTS_PER_EPOCH
    state_transition(post_state, block)

    assert post_state.validator_registry[validator_index].initiated_exit == True

    return pre_state, [block], post_state


def test_historical_batch(state):
    pre_state = deepcopy(state)
    pre_state.slot += spec.SLOTS_PER_HISTORICAL_ROOT - (pre_state.slot % spec.SLOTS_PER_HISTORICAL_ROOT) - 1

    post_state = deepcopy(pre_state)

    block = build_empty_block_for_next_slot(post_state)

    state_transition(post_state, block)

    assert post_state.slot == block.slot
    assert get_current_epoch(post_state) % (spec.SLOTS_PER_HISTORICAL_ROOT // spec.SLOTS_PER_EPOCH) == 0
    assert len(post_state.historical_roots) == len(pre_state.historical_roots) + 1

    return pre_state, [block], post_state
