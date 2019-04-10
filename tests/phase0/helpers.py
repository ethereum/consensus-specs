from copy import deepcopy

from py_ecc import bls

import build.phase0.spec as spec
from build.phase0.utils.minimal_ssz import signing_root
from build.phase0.spec import (
    # constants
    EMPTY_SIGNATURE,
    ZERO_HASH,
    # SSZ
    Attestation,
    AttestationData,
    AttestationDataAndCustodyBit,
    AttesterSlashing,
    BeaconBlockHeader,
    Deposit,
    DepositData,
    Eth1Data,
    ProposerSlashing,
    VoluntaryExit,
    # functions
    convert_to_indexed,
    get_active_validator_indices,
    get_attestation_participants,
    get_block_root,
    get_crosslink_committee_for_attestation,
    get_crosslink_committees_at_slot,
    get_current_epoch,
    get_domain,
    get_empty_block,
    get_epoch_start_slot,
    get_genesis_beacon_state,
    slot_to_epoch,
    verify_merkle_branch,
    hash,
)
from build.phase0.utils.merkle_minimal import (
    calc_merkle_tree_from_leaves,
    get_merkle_proof,
    get_merkle_root,
)


privkeys = [i + 1 for i in range(1000)]
pubkeys = [bls.privtopub(privkey) for privkey in privkeys]
pubkey_to_privkey = {pubkey: privkey for privkey, pubkey in zip(privkeys, pubkeys)}


def create_mock_genesis_validator_deposits(num_validators, deposit_data_leaves=None):
    if not deposit_data_leaves:
        deposit_data_leaves = []
    proof_of_possession = b'\x33' * 96

    deposit_data_list = []
    for i in range(num_validators):
        pubkey = pubkeys[i]
        deposit_data = DepositData(
            pubkey=pubkey,
            # insecurely use pubkey as withdrawal key as well
            withdrawal_credentials=spec.BLS_WITHDRAWAL_PREFIX_BYTE + hash(pubkey)[1:],
            amount=spec.MAX_DEPOSIT_AMOUNT,
            proof_of_possession=proof_of_possession,
        )
        item = hash(deposit_data.serialize())
        deposit_data_leaves.append(item)
        tree = calc_merkle_tree_from_leaves(tuple(deposit_data_leaves))
        root = get_merkle_root((tuple(deposit_data_leaves)))
        proof = list(get_merkle_proof(tree, item_index=i))
        assert verify_merkle_branch(item, proof, spec.DEPOSIT_CONTRACT_TREE_DEPTH, i, root)
        deposit_data_list.append(deposit_data)

    genesis_validator_deposits = []
    for i in range(num_validators):
        genesis_validator_deposits.append(Deposit(
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
    return get_genesis_beacon_state(
        initial_deposits,
        genesis_time=0,
        genesis_eth1_data=Eth1Data(
            deposit_root=deposit_root,
            deposit_count=len(initial_deposits),
            block_hash=spec.ZERO_HASH,
        ),
    )


def force_registry_change_at_next_epoch(state):
    # artificially trigger registry update at next epoch transition
    state.finalized_epoch = get_current_epoch(state) - 1
    for crosslink in state.latest_crosslinks:
        crosslink.epoch = state.finalized_epoch
    state.validator_registry_update_epoch = state.finalized_epoch - 1


def build_empty_block_for_next_slot(state):
    empty_block = get_empty_block()
    empty_block.slot = state.slot + 1
    previous_block_header = deepcopy(state.latest_block_header)
    if previous_block_header.state_root == spec.ZERO_HASH:
        previous_block_header.state_root = state.hash_tree_root()
    empty_block.previous_block_root = signing_root(previous_block_header)
    return empty_block


def build_deposit_data(state, pubkey, privkey, amount):
    deposit_data = DepositData(
        pubkey=pubkey,
        # insecurely use pubkey as withdrawal key as well
        withdrawal_credentials=spec.BLS_WITHDRAWAL_PREFIX_BYTE + hash(pubkey)[1:],
        amount=amount,
        proof_of_possession=EMPTY_SIGNATURE,
    )
    proof_of_possession = bls.sign(
        message_hash=signing_root(deposit_data),
        privkey=privkey,
        domain=get_domain(
            state.fork,
            get_current_epoch(state),
            spec.DOMAIN_DEPOSIT,
        )
    )
    deposit_data.proof_of_possession = proof_of_possession
    return deposit_data


def build_attestation_data(state, slot, shard):
    assert state.slot >= slot

    block_root = build_empty_block_for_next_slot(state).previous_block_root

    epoch_start_slot = get_epoch_start_slot(get_current_epoch(state))
    if epoch_start_slot == slot:
        epoch_boundary_root = block_root
    else:
        get_block_root(state, epoch_start_slot)

    if slot < epoch_start_slot:
        justified_block_root = state.previous_justified_root
    else:
        justified_block_root = state.current_justified_root

    return AttestationData(
        slot=slot,
        shard=shard,
        beacon_block_root=block_root,
        source_epoch=state.current_justified_epoch,
        source_root=justified_block_root,
        target_root=epoch_boundary_root,
        crosslink_data_root=spec.ZERO_HASH,
        previous_crosslink=deepcopy(state.latest_crosslinks[shard]),
    )


def build_voluntary_exit(state, epoch, validator_index, privkey):
    voluntary_exit = VoluntaryExit(
        epoch=epoch,
        validator_index=validator_index,
        signature=EMPTY_SIGNATURE,
    )
    voluntary_exit.signature = bls.sign(
        message_hash=signing_root(voluntary_exit),
        privkey=privkey,
        domain=get_domain(
            fork=state.fork,
            epoch=epoch,
            domain_type=spec.DOMAIN_VOLUNTARY_EXIT,
        )
    )

    return voluntary_exit


def build_deposit(state,
                  deposit_data_leaves,
                  pubkey,
                  privkey,
                  amount):
    deposit_data = build_deposit_data(state, pubkey, privkey, amount)

    item = hash(deposit_data.serialize())
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
    validator_index = get_active_validator_indices(state.validator_registry, current_epoch)[-1]
    privkey = pubkey_to_privkey[state.validator_registry[validator_index].pubkey]
    slot = state.slot

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
        fork=state.fork,
        epoch=get_current_epoch(state),
        domain_type=spec.DOMAIN_BEACON_BLOCK,
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
    attestation_2.data.target_root = b'\x01'*32

    return AttesterSlashing(
        attestation_1=convert_to_indexed(state, attestation_1),
        attestation_2=convert_to_indexed(state, attestation_2),
    )


def get_valid_attestation(state, slot=None):
    if slot is None:
        slot = state.slot
    shard = state.latest_start_shard
    attestation_data = build_attestation_data(state, slot, shard)

    crosslink_committee = get_crosslink_committee_for_attestation(state, attestation_data)

    committee_size = len(crosslink_committee)
    bitfield_length = (committee_size + 7) // 8
    aggregation_bitfield = b'\xC0' + b'\x00' * (bitfield_length - 1)
    custody_bitfield = b'\x00' * bitfield_length
    attestation = Attestation(
        aggregation_bitfield=aggregation_bitfield,
        data=attestation_data,
        custody_bitfield=custody_bitfield,
        aggregate_signature=EMPTY_SIGNATURE,
    )
    participants = get_attestation_participants(
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


def get_attestation_signature(state, attestation_data, privkey, custody_bit=0b0):
    message_hash = AttestationDataAndCustodyBit(
        data=attestation_data,
        custody_bit=custody_bit,
    ).hash_tree_root()

    return bls.sign(
        message_hash=message_hash,
        privkey=privkey,
        domain=get_domain(
            fork=state.fork,
            epoch=slot_to_epoch(attestation_data.slot),
            domain_type=spec.DOMAIN_ATTESTATION,
        )
    )
