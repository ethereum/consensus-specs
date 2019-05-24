from copy import deepcopy

from py_ecc import bls

from eth2spec.utils.minimal_ssz import signing_root
from eth2spec.utils.merkle_minimal import (
    calc_merkle_tree_from_leaves,
    get_merkle_proof,
    get_merkle_root,
)

privkeys = [i + 1 for i in range(1024)]
pubkeys = [bls.privtopub(privkey) for privkey in privkeys]
pubkey_to_privkey = {pubkey: privkey for privkey, pubkey in zip(privkeys, pubkeys)}


def advance_slot(state) -> None:
    state.slot += 1


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


def create_mock_genesis_validator_deposits(num_validators, deposit_data_leaves=None):
    if not deposit_data_leaves:
        deposit_data_leaves = []
    signature = b'\x33' * 96

    deposit_data_list = []
    for i in range(num_validators):
        pubkey = pubkeys[i]
        deposit_data = spec.DepositData(
            pubkey=pubkey,
            # insecurely use pubkey as withdrawal key as well
            withdrawal_credentials=spec.BLS_WITHDRAWAL_PREFIX_BYTE + spec.hash(pubkey)[1:],
            amount=spec.MAX_EFFECTIVE_BALANCE,
            signature=signature,
        )
        item = deposit_data.hash_tree_root()
        deposit_data_leaves.append(item)
        tree = calc_merkle_tree_from_leaves(tuple(deposit_data_leaves))
        root = get_merkle_root((tuple(deposit_data_leaves)))
        proof = list(get_merkle_proof(tree, item_index=i))
        assert spec.verify_merkle_branch(item, proof, spec.DEPOSIT_CONTRACT_TREE_DEPTH, i, root)
        deposit_data_list.append(deposit_data)

    genesis_validator_deposits = []
    for i in range(num_validators):
        genesis_validator_deposits.append(spec.Deposit(
            proof=list(get_merkle_proof(tree, item_index=i)),
            index=i,
            data=deposit_data_list[i]
        ))
    return genesis_validator_deposits, root


def create_genesis_state(num_validators, deposit_data_leaves=None):
    initial_deposits, deposit_root = create_mock_genesis_validator_deposits(
        num_validators,
        deposit_data_leaves,
    )
    return spec.get_genesis_beacon_state(
        initial_deposits,
        genesis_time=0,
        genesis_eth1_data=spec.Eth1Data(
            deposit_root=deposit_root,
            deposit_count=len(initial_deposits),
            block_hash=spec.ZERO_HASH,
        ),
    )


def build_empty_block_for_next_slot(state):
    empty_block = spec.BeaconBlock()
    empty_block.slot = state.slot + 1
    empty_block.body.eth1_data.deposit_count = state.deposit_index
    previous_block_header = deepcopy(state.latest_block_header)
    if previous_block_header.state_root == spec.ZERO_HASH:
        previous_block_header.state_root = state.hash_tree_root()
    empty_block.parent_root = signing_root(previous_block_header)
    return empty_block


def build_deposit_data(state, pubkey, privkey, amount):
    deposit_data = spec.DepositData(
        pubkey=pubkey,
        # insecurely use pubkey as withdrawal key as well
        withdrawal_credentials=spec.BLS_WITHDRAWAL_PREFIX_BYTE + spec.hash(pubkey)[1:],
        amount=amount,
    )
    signature = bls.sign(
        message_hash=signing_root(deposit_data),
        privkey=privkey,
        domain=spec.bls_domain(spec.DOMAIN_DEPOSIT),
    )
    deposit_data.signature = signature
    return deposit_data


def build_attestation_data(state, slot, shard):
    assert state.slot >= slot

    if slot == state.slot:
        block_root = build_empty_block_for_next_slot(state).parent_root
    else:
        block_root = spec.get_block_root_at_slot(state, slot)

    current_epoch_start_slot = spec.get_epoch_start_slot(spec.get_current_epoch(state))
    if slot < current_epoch_start_slot:
        epoch_boundary_root = spec.get_block_root(state, spec.get_previous_epoch(state))
    elif slot == current_epoch_start_slot:
        epoch_boundary_root = block_root
    else:
        epoch_boundary_root = spec.get_block_root(state, spec.get_current_epoch(state))

    if slot < current_epoch_start_slot:
        justified_epoch = state.previous_justified_epoch
        justified_block_root = state.previous_justified_root
    else:
        justified_epoch = state.current_justified_epoch
        justified_block_root = state.current_justified_root

    crosslinks = (
        state.current_crosslinks if spec.slot_to_epoch(slot) == spec.get_current_epoch(state)
        else state.previous_crosslinks
    )
    parent_crosslink = crosslinks[shard]
    return spec.AttestationData(
        beacon_block_root=block_root,
        source_epoch=justified_epoch,
        source_root=justified_block_root,
        target_epoch=spec.slot_to_epoch(slot),
        target_root=epoch_boundary_root,
        crosslink=spec.Crosslink(
            shard=shard,
            start_epoch=parent_crosslink.end_epoch,
            end_epoch=min(spec.slot_to_epoch(slot), parent_crosslink.end_epoch + spec.MAX_EPOCHS_PER_CROSSLINK),
            data_root=spec.ZERO_HASH,
            parent_root=spec.hash_tree_root(parent_crosslink),
        ),
    )


def build_voluntary_exit(state, epoch, validator_index, privkey):
    voluntary_exit = spec.VoluntaryExit(
        epoch=epoch,
        validator_index=validator_index,
    )
    voluntary_exit.signature = bls.sign(
        message_hash=signing_root(voluntary_exit),
        privkey=privkey,
        domain=spec.get_domain(
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
    assert spec.verify_merkle_branch(item, proof, spec.DEPOSIT_CONTRACT_TREE_DEPTH, index, root)

    deposit = spec.Deposit(
        proof=list(proof),
        index=index,
        data=deposit_data,
    )

    return deposit, root, deposit_data_leaves


def get_valid_proposer_slashing(state):
    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    privkey = pubkey_to_privkey[state.validator_registry[validator_index].pubkey]
    slot = state.slot

    header_1 = spec.BeaconBlockHeader(
        slot=slot,
        parent_root=spec.ZERO_HASH,
        state_root=spec.ZERO_HASH,
        body_root=spec.ZERO_HASH,
    )
    header_2 = deepcopy(header_1)
    header_2.parent_root = b'\x02' * 32
    header_2.slot = slot + 1

    domain = spec.get_domain(
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

    return spec.ProposerSlashing(
        proposer_index=validator_index,
        header_1=header_1,
        header_2=header_2,
    )


def get_valid_attester_slashing(state):
    attestation_1 = get_valid_attestation(state)
    attestation_2 = deepcopy(attestation_1)
    attestation_2.data.target_root = b'\x01' * 32

    return spec.AttesterSlashing(
        attestation_1=spec.convert_to_indexed(state, attestation_1),
        attestation_2=spec.convert_to_indexed(state, attestation_2),
    )


def get_valid_attestation(state, slot=None):
    if slot is None:
        slot = state.slot

    if spec.slot_to_epoch(slot) == spec.get_current_epoch(state):
        shard = (state.latest_start_shard + slot) % spec.SLOTS_PER_EPOCH
    else:
        previous_shard_delta = spec.get_shard_delta(state, spec.get_previous_epoch(state))
        shard = (state.latest_start_shard - previous_shard_delta + slot) % spec.SHARD_COUNT

    attestation_data = build_attestation_data(state, slot, shard)

    crosslink_committee = spec.get_crosslink_committee(
        state,
        attestation_data.target_epoch,
        attestation_data.crosslink.shard,
    )

    committee_size = len(crosslink_committee)
    bitfield_length = (committee_size + 7) // 8
    aggregation_bitfield = b'\xC0' + b'\x00' * (bitfield_length - 1)
    custody_bitfield = b'\x00' * bitfield_length
    attestation = spec.Attestation(
        aggregation_bitfield=aggregation_bitfield,
        data=attestation_data,
        custody_bitfield=custody_bitfield,
    )
    participants = spec.get_attesting_indices(
        state,
        attestation.data,
        attestation.aggregation_bitfield,
    )
    assert len(participants) == 2

    signatures = []
    for validator_index in participants:
        privkey = privkeys[validator_index]
        signatures.append(
            get_attestation_signature(
                state,
                attestation.data,
                privkey
            )
        )

    attestation.aggregation_signature = bls.aggregate_signatures(signatures)
    return attestation


def get_valid_transfer(state, slot=None, sender_index=None, amount=None, fee=None):
    if slot is None:
        slot = state.slot
    current_epoch = spec.get_current_epoch(state)
    if sender_index is None:
        sender_index = spec.get_active_validator_indices(state, current_epoch)[-1]
    recipient_index = spec.get_active_validator_indices(state, current_epoch)[0]
    transfer_pubkey = pubkeys[-1]
    transfer_privkey = privkeys[-1]

    if fee is None:
        fee = get_balance(state, sender_index) // 32
    if amount is None:
        amount = get_balance(state, sender_index) - fee

    transfer = spec.Transfer(
        sender=sender_index,
        recipient=recipient_index,
        amount=amount,
        fee=fee,
        slot=slot,
        pubkey=transfer_pubkey,
        signature=spec.ZERO_HASH,
    )
    transfer.signature = bls.sign(
        message_hash=signing_root(transfer),
        privkey=transfer_privkey,
        domain=spec.get_domain(
            state=state,
            domain_type=spec.DOMAIN_TRANSFER,
            message_epoch=spec.get_current_epoch(state),
        )
    )

    # ensure withdrawal_credentials reproducable
    state.validator_registry[transfer.sender].withdrawal_credentials = (
        spec.BLS_WITHDRAWAL_PREFIX_BYTE + spec.hash(transfer.pubkey)[1:]
    )

    return transfer


def get_attestation_signature(state, attestation_data, privkey, custody_bit=0b0):
    message_hash = spec.AttestationDataAndCustodyBit(
        data=attestation_data,
        custody_bit=custody_bit,
    ).hash_tree_root()

    return bls.sign(
        message_hash=message_hash,
        privkey=privkey,
        domain=spec.get_domain(
            state=state,
            domain_type=spec.DOMAIN_ATTESTATION,
            message_epoch=attestation_data.target_epoch,
        )
    )


def fill_aggregate_attestation(state, attestation):
    crosslink_committee = spec.get_crosslink_committee(
        state,
        attestation.data.target_epoch,
        attestation.data.crosslink.shard,
    )
    for i in range(len(crosslink_committee)):
        attestation.aggregation_bitfield = set_bitfield_bit(attestation.aggregation_bitfield, i)


def add_attestation_to_state(state, attestation, slot):
    block = build_empty_block_for_next_slot(state)
    block.slot = slot
    block.body.attestations.append(attestation)
    spec.state_transition(state, block)


def next_slot(state):
    """
    Transition to the next slot via an empty block.
    Return the empty block that triggered the transition.
    """
    block = build_empty_block_for_next_slot(state)
    spec.state_transition(state, block)
    return block


def next_epoch(state):
    """
    Transition to the start slot of the next epoch via an empty block.
    Return the empty block that triggered the transition.
    """
    block = build_empty_block_for_next_slot(state)
    block.slot += spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
    spec.state_transition(state, block)
    return block


def get_state_root(state, slot) -> bytes:
    """
    Return the state root at a recent ``slot``.
    """
    assert slot < state.slot <= slot + spec.SLOTS_PER_HISTORICAL_ROOT
    return state.latest_state_roots[slot % spec.SLOTS_PER_HISTORICAL_ROOT]
