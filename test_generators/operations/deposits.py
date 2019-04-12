from eth2spec.phase0 import spec
from eth_utils import (
    to_dict, to_tuple
)
from gen_base import gen_suite, gen_typing
from preset_loader import loader
from eth2spec.debug.encode import encode
from eth2spec.utils.minimal_ssz import signing_root
from eth2spec.utils.merkle_minimal import get_merkle_root, calc_merkle_tree_from_leaves, get_merkle_proof

from typing import List, Tuple

import genesis
import keys
from py_ecc import bls


def build_deposit_data(state,
                       pubkey: spec.BLSPubkey,
                       withdrawal_cred: spec.Bytes32,
                       privkey: int,
                       amount: int):
    deposit_data = spec.DepositData(
        pubkey=pubkey,
        withdrawal_credentials=spec.BLS_WITHDRAWAL_PREFIX_BYTE + withdrawal_cred[1:],
        amount=amount,
        proof_of_possession=spec.EMPTY_SIGNATURE,
    )
    deposit_data.proof_of_possession = bls.sign(
        message_hash=signing_root(deposit_data),
        privkey=privkey,
        domain=spec.get_domain(
            state.fork,
            spec.get_current_epoch(state),
            spec.DOMAIN_DEPOSIT,
        )
    )
    return deposit_data


def build_deposit(state,
                  deposit_data_leaves: List[spec.Bytes32],
                  pubkey: spec.BLSPubkey,
                  withdrawal_cred: spec.Bytes32,
                  privkey: int,
                  amount: int) -> spec.Deposit:

    deposit_data = build_deposit_data(state, pubkey, withdrawal_cred, privkey, amount)

    item = spec.hash(deposit_data.serialize())
    index = len(deposit_data_leaves)
    deposit_data_leaves.append(item)
    tree = calc_merkle_tree_from_leaves(tuple(deposit_data_leaves))
    proof = list(get_merkle_proof(tree, item_index=index))

    deposit = spec.Deposit(
        proof=list(proof),
        index=index,
        data=deposit_data,
    )

    return deposit


def build_deposit_for_index(initial_validator_count: int, index: int) -> Tuple[spec.Deposit, spec.BeaconState, List[spec.Bytes32]]:
    genesis_deposits = genesis.create_deposits(
        keys.pubkeys[:initial_validator_count],
        keys.withdrawal_creds[:initial_validator_count]
    )
    state = genesis.create_genesis_state(genesis_deposits)

    deposit_data_leaves = [spec.hash(dep.data.serialize()) for dep in genesis_deposits]

    deposit = build_deposit(
        state,
        deposit_data_leaves,
        keys.pubkeys[index],
        keys.withdrawal_creds[index],
        keys.privkeys[index],
        spec.MAX_DEPOSIT_AMOUNT,
    )

    state.latest_eth1_data.deposit_root = get_merkle_root(tuple(deposit_data_leaves))
    state.latest_eth1_data.deposit_count = len(deposit_data_leaves)

    return deposit, state, deposit_data_leaves


@to_dict
def valid_deposit():
    new_dep, state, leaves = build_deposit_for_index(10, 10)
    state.latest_eth1_data.deposit_root = get_merkle_root(tuple(leaves))
    state.latest_eth1_data.deposit_count = len(leaves)
    yield 'case', 'valid deposit to add new validator'
    yield 'pre', encode(state, spec.BeaconState)
    yield 'deposit', encode(new_dep, spec.Deposit)
    spec.process_deposit(state, new_dep)
    yield 'post', encode(state, spec.BeaconState)


@to_dict
def valid_topup():
    new_dep, state, leaves = build_deposit_for_index(10, 3)
    state.latest_eth1_data.deposit_root = get_merkle_root(tuple(leaves))
    state.latest_eth1_data.deposit_count = len(leaves)
    yield 'case', 'valid deposit to top-up existing validator'
    yield 'pre', encode(state, spec.BeaconState)
    yield 'deposit', encode(new_dep, spec.Deposit)
    spec.process_deposit(state, new_dep)
    yield 'post', encode(state, spec.BeaconState)


@to_dict
def invalid_deposit_index():
    new_dep, state, leaves = build_deposit_for_index(10, 10)
    state.latest_eth1_data.deposit_root = get_merkle_root(tuple(leaves))
    state.latest_eth1_data.deposit_count = len(leaves)
    # Mess up deposit index, 1 too small
    state.deposit_index = 9

    yield 'case', 'invalid deposit index'
    yield 'pre', encode(state, spec.BeaconState)
    yield 'deposit', encode(new_dep, spec.Deposit)
    yield 'post', None

@to_dict
def invalid_deposit_proof():
    new_dep, state, leaves = build_deposit_for_index(10, 10)
    state.latest_eth1_data.deposit_root = get_merkle_root(tuple(leaves))
    state.latest_eth1_data.deposit_count = len(leaves)
    # Make deposit proof invalid (at bottom of proof)
    new_dep.proof[-1] = spec.ZERO_HASH

    yield 'case', 'invalid deposit proof'
    yield 'pre', encode(state, spec.BeaconState)
    yield 'deposit', encode(new_dep, spec.Deposit)
    yield 'post', None


@to_tuple
def deposit_cases():
    yield valid_deposit()
    yield valid_topup()
    yield invalid_deposit_index()
    yield invalid_deposit_proof()


def mini_deposits_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    presets = loader.load_presets(configs_path, 'minimal')
    spec.apply_constants_preset(presets)

    return ("deposit_minimal", "deposits", gen_suite.render_suite(
        title="deposit operation",
        summary="Test suite for deposit type operation processing",
        forks_timeline="testing",
        forks=["phase0"],
        config="minimal",
        handler="core",
        test_cases=deposit_cases()))


def full_deposits_suite(configs_path: str) -> gen_typing.TestSuiteOutput:
    presets = loader.load_presets(configs_path, 'mainnet')
    spec.apply_constants_preset(presets)

    return ("deposit_full", "deposits", gen_suite.render_suite(
        title="deposit operation",
        summary="Test suite for deposit type operation processing",
        forks_timeline="mainnet",
        forks=["phase0"],
        config="mainnet",
        handler="core",
        test_cases=deposit_cases()))
