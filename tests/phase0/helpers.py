from copy import deepcopy

from py_ecc import bls

import build.phase0.spec as spec
from build.phase0.utils.minimal_ssz import signed_root
from build.phase0.spec import (
    # constants
    EMPTY_SIGNATURE,
    # SSZ
    AttestationData,
    Deposit,
    DepositInput,
    DepositData,
    Eth1Data,
    # functions
    get_block_root,
    get_current_epoch,
    get_domain,
    get_empty_block,
    get_epoch_start_slot,
    get_genesis_beacon_state,
    verify_merkle_branch,
    hash,
)
from build.phase0.utils.merkle_minimal import (
    calc_merkle_tree_from_leaves,
    get_merkle_proof,
    get_merkle_root,
)


privkeys_list = [i + 1 for i in range(1000)]
pubkeys_list = [bls.privtopub(privkey) for privkey in privkeys_list]
pubkey_to_privkey = {pubkey: privkey for privkey, pubkey in zip(privkeys_list, pubkeys_list)}


def create_mock_genesis_validator_deposits(num_validators, deposit_data_leaves):
    deposit_timestamp = 0
    proof_of_possession = b'\x33' * 96

    deposit_data_list = []
    for i in range(num_validators):
        pubkey = pubkeys_list[i]
        privkey = pubkey_to_privkey[pubkey]
        deposit_data = DepositData(
            amount=spec.MAX_DEPOSIT_AMOUNT,
            timestamp=deposit_timestamp,
            deposit_input=DepositInput(
                pubkey=pubkey,
                withdrawal_credentials=privkey.to_bytes(32, byteorder='big'),
                proof_of_possession=proof_of_possession,
            ),
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
            deposit_data=deposit_data_list[i]
        ))
    return genesis_validator_deposits, root


def create_genesis_state(num_validators, deposit_data_leaves):
    initial_deposits, deposit_root = create_mock_genesis_validator_deposits(num_validators, deposit_data_leaves)
    return get_genesis_beacon_state(
        initial_deposits,
        genesis_time=0,
        genesis_eth1_data=Eth1Data(
            deposit_root=deposit_root,
            block_hash=spec.ZERO_HASH,
        ),
    )


def build_empty_block_for_next_slot(state):
    empty_block = get_empty_block()
    empty_block.slot = state.slot + 1
    previous_block_header = deepcopy(state.latest_block_header)
    if previous_block_header.state_root == spec.ZERO_HASH:
        previous_block_header.state_root = state.hash_tree_root()
    empty_block.previous_block_root = previous_block_header.hash_tree_root()
    return empty_block


def build_deposit_data(state, pubkey, privkey, amount):
    deposit_input = DepositInput(
        pubkey=pubkey,
        withdrawal_credentials=privkey.to_bytes(32, byteorder='big'),
        proof_of_possession=EMPTY_SIGNATURE,
    )
    proof_of_possession = bls.sign(
        message_hash=signed_root(deposit_input),
        privkey=privkey,
        domain=get_domain(
            state.fork,
            get_current_epoch(state),
            spec.DOMAIN_DEPOSIT,
        )
    )
    deposit_input.proof_of_possession = proof_of_possession
    deposit_data = DepositData(
        amount=amount,
        timestamp=0,
        deposit_input=deposit_input,
    )
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
