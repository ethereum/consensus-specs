import pytest

from py_ecc import bls

from build.phase0 import spec

from build.phase0.utils.merkle_minimal import (
    calc_merkle_tree_from_leaves,
    get_merkle_proof,
    get_merkle_root,
)
from build.phase0.spec import (
    Deposit,
    DepositData,
    DepositInput,
    Eth1Data,
    get_genesis_beacon_state,
    verify_merkle_branch,
    hash,
)


privkeys_list = [i+1 for i in range(1000)]
pubkeys_list = [bls.privtopub(privkey) for privkey in privkeys_list]
pubkey_to_privkey = {pubkey: privkey for privkey, pubkey in zip(privkeys_list, pubkeys_list)}


@pytest.fixture
def privkeys():
    return privkeys_list


@pytest.fixture
def pubkeys():
    return pubkeys_list


def overwrite_spec_config(config):
    for field in config:
        setattr(spec, field, config[field])
        if field == "LATEST_RANDAO_MIXES_LENGTH":
            spec.BeaconState.fields['latest_randao_mixes'][1] = config[field]
        elif field == "SHARD_COUNT":
            spec.BeaconState.fields['latest_crosslinks'][1] = config[field]
        elif field == "SLOTS_PER_HISTORICAL_ROOT":
            spec.BeaconState.fields['latest_block_roots'][1] = config[field]
            spec.BeaconState.fields['latest_state_roots'][1] = config[field]
            spec.HistoricalBatch.fields['block_roots'][1] = config[field]
            spec.HistoricalBatch.fields['state_roots'][1] = config[field]
        elif field == "LATEST_ACTIVE_INDEX_ROOTS_LENGTH":
            spec.BeaconState.fields['latest_active_index_roots'][1] = config[field]
        elif field == "LATEST_SLASHED_EXIT_LENGTH":
            spec.BeaconState.fields['latest_slashed_balances'][1] = config[field]


@pytest.fixture
def config():
    return {
        "SHARD_COUNT": 8,
        "MIN_ATTESTATION_INCLUSION_DELAY": 2,
        "TARGET_COMMITTEE_SIZE": 4,
        "SLOTS_PER_EPOCH": 8,
        "GENESIS_EPOCH": spec.GENESIS_SLOT // 8,
        "SLOTS_PER_HISTORICAL_ROOT": 64,
        "LATEST_RANDAO_MIXES_LENGTH": 64,
        "LATEST_ACTIVE_INDEX_ROOTS_LENGTH": 64,
        "LATEST_SLASHED_EXIT_LENGTH": 64,
    }


@pytest.fixture(autouse=True)
def overwrite_config(config):
    overwrite_spec_config(config)


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

@pytest.fixture
def num_validators():
    return 100


@pytest.fixture
def deposit_data_leaves():
    return list()


@pytest.fixture
def state(num_validators, deposit_data_leaves):
    return create_genesis_state(num_validators, deposit_data_leaves)
