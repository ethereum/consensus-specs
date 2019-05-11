from copy import deepcopy

from py_ecc import bls

from typing import List

import eth2spec.phase0.spec as spec
from eth2spec.phase0.spec import (
    # constants
    ZERO_HASH,
    # SSZ
    Attestation,
    IndexedAttestation,
    AttestationData,
    AttestationDataAndCustodyBit,
    AttesterSlashing,
    BeaconBlock,
    BeaconState,
    BeaconBlockHeader,
    Deposit,
    DepositData,
    Eth1Data,
    ProposerSlashing,
    Transfer,
    VoluntaryExit,
    # functions
    convert_to_indexed,
    get_active_validator_indices,
    get_attesting_indices,
    get_block_root,
    get_block_root_at_slot,
    get_crosslink_committee,
    get_current_epoch,
    get_domain,
    get_epoch_start_slot,
    get_previous_epoch,
    get_shard_delta,
    hash_tree_root,
    slot_to_epoch,
    verify_merkle_branch,
    hash,
)
from eth2spec.phase0.state_transition import (
    state_transition, state_transition_to
)
from eth2spec.utils.merkle_minimal import (
    calc_merkle_tree_from_leaves,
    get_merkle_proof,
    get_merkle_root,
)
from eth2spec.utils.minimal_ssz import signing_root

privkeys = [i + 1 for i in range(1024)]
pubkeys = [bls.privtopub(privkey) for privkey in privkeys]
pubkey_to_privkey = {pubkey: privkey for privkey, pubkey in zip(privkeys, pubkeys)}


def get_balance(state, index):
    return state.balances[index]


def set_bitfield_bit(bitfield, i):
    """
    Set the bit in ``bitfield`` at position ``i`` to ``1``.
    """
    byte_index = i // 8
    bit_index = i % 8
    return (
            bitfield[:byte_index] +
            bytes([bitfield[byte_index] | (1 << bit_index)]) +
            bitfield[byte_index + 1:]
    )


def build_mock_validator(i: int, balance: int):
    pubkey = pubkeys[i]
    # insecurely use pubkey as withdrawal key as well
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX_BYTE + hash(pubkey)[1:]
    return spec.Validator(
        pubkey=pubkeys[i],
        withdrawal_credentials=withdrawal_credentials,
        activation_eligibility_epoch=spec.FAR_FUTURE_EPOCH,
        activation_epoch=spec.FAR_FUTURE_EPOCH,
        exit_epoch=spec.FAR_FUTURE_EPOCH,
        withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
        effective_balance=min(balance - balance % spec.EFFECTIVE_BALANCE_INCREMENT, spec.MAX_EFFECTIVE_BALANCE)
    )


def create_genesis_state(num_validators):
    deposit_root = b'\x42' * 32

    state = spec.BeaconState(
        genesis_time=0,
        deposit_index=num_validators,
        latest_eth1_data=Eth1Data(
            deposit_root=deposit_root,
            deposit_count=num_validators,
            block_hash=spec.ZERO_HASH,
        ))

    # We "hack" in the initial validators,
    #  as it is much faster than creating and processing genesis deposits for every single test case.
    state.balances = [spec.MAX_EFFECTIVE_BALANCE] * num_validators
    state.validator_registry = [build_mock_validator(i, state.balances[i]) for i in range(num_validators)]

    # Process genesis activations
    for validator in state.validator_registry:
        if validator.effective_balance >= spec.MAX_EFFECTIVE_BALANCE:
            validator.activation_eligibility_epoch = spec.GENESIS_EPOCH
            validator.activation_epoch = spec.GENESIS_EPOCH

    genesis_active_index_root = hash_tree_root(get_active_validator_indices(state, spec.GENESIS_EPOCH))
    for index in range(spec.LATEST_ACTIVE_INDEX_ROOTS_LENGTH):
        state.latest_active_index_roots[index] = genesis_active_index_root

    return state


def make_block_signature(state, block):
    assert block.slot == state.slot or block.slot == state.slot + 1
    if block.slot == state.slot:
        proposer_index = spec.get_beacon_proposer_index(state)
    else:
        # use stub state to get proposer index of next slot
        stub_state = deepcopy(state)
        next_slot(stub_state)
        proposer_index = spec.get_beacon_proposer_index(stub_state)

    privkey = privkeys[proposer_index]

    block.body.randao_reveal = bls.sign(
        privkey=privkey,
        message_hash=hash_tree_root(slot_to_epoch(block.slot)),
        domain=get_domain(
            state,
            message_epoch=slot_to_epoch(block.slot),
            domain_type=spec.DOMAIN_RANDAO,
        )
    )
    block.signature = bls.sign(
        message_hash=signing_root(block),
        privkey=privkey,
        domain=get_domain(
            state,
            spec.DOMAIN_BEACON_PROPOSER,
            slot_to_epoch(block.slot)))
    return block


def build_empty_block(state, slot=None, signed=False):
    if slot is None:
        slot = state.slot
    empty_block = BeaconBlock()
    empty_block.slot = slot
    empty_block.body.eth1_data.deposit_count = state.deposit_index
    previous_block_header = deepcopy(state.latest_block_header)
    if previous_block_header.state_root == spec.ZERO_HASH:
        previous_block_header.state_root = state.hash_tree_root()
    empty_block.previous_block_root = signing_root(previous_block_header)

    if signed:
        make_block_signature(state, empty_block)

    return empty_block


def build_empty_block_for_next_slot(state, signed=False):
    return build_empty_block(state, state.slot + 1, signed=signed)


def build_deposit_data(state, pubkey, privkey, amount):
    deposit_data = DepositData(
        pubkey=pubkey,
        # insecurely use pubkey as withdrawal key as well
        withdrawal_credentials=spec.BLS_WITHDRAWAL_PREFIX_BYTE + hash(pubkey)[1:],
        amount=amount,
    )
    signature = bls.sign(
        message_hash=signing_root(deposit_data),
        privkey=privkey,
        domain=get_domain(
            state,
            spec.DOMAIN_DEPOSIT,
        )
    )
    deposit_data.signature = signature
    return deposit_data


def build_attestation_data(state, slot, shard):
    assert state.slot >= slot

    if slot == state.slot:
        block_root = build_empty_block_for_next_slot(state).previous_block_root
    else:
        block_root = get_block_root_at_slot(state, slot)

    current_epoch_start_slot = get_epoch_start_slot(get_current_epoch(state))
    if slot < current_epoch_start_slot:
        epoch_boundary_root = get_block_root(state, get_previous_epoch(state))
    elif slot == current_epoch_start_slot:
        epoch_boundary_root = block_root
    else:
        epoch_boundary_root = get_block_root(state, get_current_epoch(state))

    if slot < current_epoch_start_slot:
        justified_epoch = state.previous_justified_epoch
        justified_block_root = state.previous_justified_root
    else:
        justified_epoch = state.current_justified_epoch
        justified_block_root = state.current_justified_root

    crosslinks = state.current_crosslinks if slot_to_epoch(slot) == get_current_epoch(
        state) else state.previous_crosslinks
    return AttestationData(
        shard=shard,
        beacon_block_root=block_root,
        source_epoch=justified_epoch,
        source_root=justified_block_root,
        target_epoch=slot_to_epoch(slot),
        target_root=epoch_boundary_root,
        crosslink_data_root=spec.ZERO_HASH,
        previous_crosslink_root=hash_tree_root(crosslinks[shard]),
    )


def build_voluntary_exit(state, epoch, validator_index, privkey):
    voluntary_exit = VoluntaryExit(
        epoch=epoch,
        validator_index=validator_index,
    )
    voluntary_exit.signature = bls.sign(
        message_hash=signing_root(voluntary_exit),
        privkey=privkey,
        domain=get_domain(
            state=state,
            domain_type=spec.DOMAIN_VOLUNTARY_EXIT,
            message_epoch=epoch,
        )
    )

    return voluntary_exit


def build_deposit(state,
                  deposit_data_leaves,
                  pubkey,
                  privkey,
                  amount):
    deposit_data = build_deposit_data(state, pubkey, privkey, amount)

    item = deposit_data.hash_tree_root()
    index = len(deposit_data_leaves)
    deposit_data_leaves.append(item)
    tree = calc_merkle_tree_from_leaves(tuple(deposit_data_leaves))
    root = get_merkle_root((tuple(deposit_data_leaves)))
    proof = list(get_merkle_proof(tree, item_index=index))
    assert verify_merkle_branch(item, proof, spec.DEPOSIT_CONTRACT_TREE_DEPTH, index, root)

    deposit = Deposit(
        proof=list(proof),
        index=index,
        data=deposit_data,
    )

    return deposit, root, deposit_data_leaves


def get_valid_proposer_slashing(state):
    current_epoch = get_current_epoch(state)
    validator_index = get_active_validator_indices(state, current_epoch)[-1]
    privkey = pubkey_to_privkey[state.validator_registry[validator_index].pubkey]
    slot = state.slot

    header_1 = BeaconBlockHeader(
        slot=slot,
        previous_block_root=ZERO_HASH,
        state_root=ZERO_HASH,
        block_body_root=ZERO_HASH,
    )
    header_2 = deepcopy(header_1)
    header_2.previous_block_root = b'\x02' * 32
    header_2.slot = slot + 1

    domain = get_domain(
        state=state,
        domain_type=spec.DOMAIN_BEACON_PROPOSER,
    )
    header_1.signature = bls.sign(
        message_hash=signing_root(header_1),
        privkey=privkey,
        domain=domain,
    )
    header_2.signature = bls.sign(
        message_hash=signing_root(header_2),
        privkey=privkey,
        domain=domain,
    )

    return ProposerSlashing(
        proposer_index=validator_index,
        header_1=header_1,
        header_2=header_2,
    )


def get_valid_attester_slashing(state):
    attestation_1 = get_valid_attestation(state)
    attestation_2 = deepcopy(attestation_1)
    attestation_2.data.target_root = b'\x01' * 32

    make_attestation_signature(state, attestation_2)

    return AttesterSlashing(
        attestation_1=convert_to_indexed(state, attestation_1),
        attestation_2=convert_to_indexed(state, attestation_2),
    )


def get_valid_attestation(state, slot=None):
    if slot is None:
        slot = state.slot

    if slot_to_epoch(slot) == get_current_epoch(state):
        shard = (state.latest_start_shard + slot) % spec.SLOTS_PER_EPOCH
    else:
        previous_shard_delta = get_shard_delta(state, get_previous_epoch(state))
        shard = (state.latest_start_shard - previous_shard_delta + slot) % spec.SHARD_COUNT

    attestation_data = build_attestation_data(state, slot, shard)

    crosslink_committee = get_crosslink_committee(state, attestation_data.target_epoch, attestation_data.shard)

    committee_size = len(crosslink_committee)
    bitfield_length = (committee_size + 7) // 8
    aggregation_bitfield = b'\xC0' + b'\x00' * (bitfield_length - 1)
    custody_bitfield = b'\x00' * bitfield_length
    attestation = Attestation(
        aggregation_bitfield=aggregation_bitfield,
        data=attestation_data,
        custody_bitfield=custody_bitfield,
    )
    make_attestation_signature(state, attestation)
    return attestation


def make_aggregate_attestation_signature(state: BeaconState, data: AttestationData, participants: List[int]):
    signatures = []
    for validator_index in participants:
        privkey = privkeys[validator_index]
        signatures.append(
            get_attestation_signature(
                state,
                data,
                privkey
            )
        )

    return bls.aggregate_signatures(signatures)


def make_indexed_attestation_signature(state, indexed_attestation: IndexedAttestation):
    participants = indexed_attestation.custody_bit_0_indices + indexed_attestation.custody_bit_1_indices
    indexed_attestation.signature = make_aggregate_attestation_signature(state, indexed_attestation.data, participants)


def make_attestation_signature(state, attestation: Attestation):
    participants = get_attesting_indices(
        state,
        attestation.data,
        attestation.aggregation_bitfield,
    )

    attestation.signature = make_aggregate_attestation_signature(state, attestation.data, participants)


def get_valid_transfer(state, slot=None, sender_index=None, amount=None, fee=None):
    if slot is None:
        slot = state.slot
    current_epoch = get_current_epoch(state)
    if sender_index is None:
        sender_index = get_active_validator_indices(state, current_epoch)[-1]
    recipient_index = get_active_validator_indices(state, current_epoch)[0]
    transfer_pubkey = pubkeys[-1]
    transfer_privkey = privkeys[-1]

    if fee is None:
        fee = get_balance(state, sender_index) // 32
    if amount is None:
        amount = get_balance(state, sender_index) - fee

    transfer = Transfer(
        sender=sender_index,
        recipient=recipient_index,
        amount=amount,
        fee=fee,
        slot=slot,
        pubkey=transfer_pubkey,
        signature=ZERO_HASH,
    )
    transfer.signature = bls.sign(
        message_hash=signing_root(transfer),
        privkey=transfer_privkey,
        domain=get_domain(
            state=state,
            domain_type=spec.DOMAIN_TRANSFER,
            message_epoch=get_current_epoch(state),
        )
    )

    # ensure withdrawal_credentials reproducable
    state.validator_registry[transfer.sender].withdrawal_credentials = (
            spec.BLS_WITHDRAWAL_PREFIX_BYTE + spec.hash(transfer.pubkey)[1:]
    )

    return transfer


def get_attestation_signature(state, attestation_data, privkey, custody_bit=0b0):
    message_hash = AttestationDataAndCustodyBit(
        data=attestation_data,
        custody_bit=custody_bit,
    ).hash_tree_root()

    return bls.sign(
        message_hash=message_hash,
        privkey=privkey,
        domain=get_domain(
            state=state,
            domain_type=spec.DOMAIN_ATTESTATION,
            message_epoch=attestation_data.target_epoch,
        )
    )


def fill_aggregate_attestation(state, attestation):
    crosslink_committee = get_crosslink_committee(state, attestation.data.target_epoch, attestation.data.shard)
    for i in range(len(crosslink_committee)):
        attestation.aggregation_bitfield = set_bitfield_bit(attestation.aggregation_bitfield, i)


def add_attestation_to_state(state, attestation, slot):
    block = build_empty_block_for_next_slot(state)
    block.slot = slot
    block.body.attestations.append(attestation)
    state_transition_to(state, block.slot)
    make_block_signature(state, block)
    state_transition(state, block)


def next_slot(state):
    """
    Transition to the next slot.
    """
    state_transition_to(state, state.slot + 1)


def next_epoch(state):
    """
    Transition to the start slot of the next epoch
    """
    slot = state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
    state_transition_to(state, slot)


def apply_empty_block(state):
    """
    Transition via an empty block (on current slot, assuming no block has been applied yet).
    :return: the empty block that triggered the transition.
    """
    block = build_empty_block(state)
    state_transition(state, block)
    return block


def get_state_root(state, slot) -> bytes:
    """
    Return the state root at a recent ``slot``.
    """
    assert slot < state.slot <= slot + spec.SLOTS_PER_HISTORICAL_ROOT
    return state.latest_state_roots[slot % spec.SLOTS_PER_HISTORICAL_ROOT]


def prepare_state_and_deposit(state, validator_index, amount):
    """
    Prepare the state for the deposit, and create a deposit for the given validator, depositing the given amount.
    """
    pre_validator_count = len(state.validator_registry)
    # fill previous deposits with zero-hash
    deposit_data_leaves = [ZERO_HASH] * pre_validator_count

    pubkey = pubkeys[validator_index]
    privkey = privkeys[validator_index]
    deposit, root, deposit_data_leaves = build_deposit(
        state,
        deposit_data_leaves,
        pubkey,
        privkey,
        amount,
    )

    state.latest_eth1_data.deposit_root = root
    state.latest_eth1_data.deposit_count = len(deposit_data_leaves)
    return deposit
