from eth2spec.phase0 import spec
from eth2spec.utils.merkle_minimal import get_merkle_root, calc_merkle_tree_from_leaves, get_merkle_proof
from typing import List


def create_genesis_state(deposits: List[spec.Deposit]) -> spec.BeaconState:
    deposit_root = get_merkle_root((tuple([spec.hash(dep.data.serialize()) for dep in deposits])))

    return spec.get_genesis_beacon_state(
        deposits,
        genesis_time=0,
        genesis_eth1_data=spec.Eth1Data(
            deposit_root=deposit_root,
            deposit_count=len(deposits),
            block_hash=spec.ZERO_HASH,
        ),
    )


def create_deposits(pubkeys: List[spec.BLSPubkey], withdrawal_cred: List[spec.Bytes32]) -> List[spec.Deposit]:

    # Mock proof of possession
    proof_of_possession = b'\x33' * 96

    deposit_data = [
        spec.DepositData(
            pubkey=pubkeys[i],
            withdrawal_credentials=spec.BLS_WITHDRAWAL_PREFIX_BYTE + withdrawal_cred[i][1:],
            amount=spec.MAX_DEPOSIT_AMOUNT,
            proof_of_possession=proof_of_possession,
        ) for i in range(len(pubkeys))
    ]

    # Fill tree with existing deposits
    deposit_data_leaves = [spec.hash(data.serialize()) for data in deposit_data]
    tree = calc_merkle_tree_from_leaves(tuple(deposit_data_leaves))

    return [
        spec.Deposit(
            proof=list(get_merkle_proof(tree, item_index=i)),
            index=i,
            data=deposit_data[i]
        ) for i in range(len(deposit_data))
    ]
