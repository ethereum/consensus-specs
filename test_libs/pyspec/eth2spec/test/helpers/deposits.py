# Access constants from spec pkg reference.
import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import get_domain, DepositData, verify_merkle_branch, Deposit, ZERO_HASH
from eth2spec.test.helpers.keys import pubkeys, privkeys
from eth2spec.utils.bls import bls_sign
from eth2spec.utils.merkle_minimal import calc_merkle_tree_from_leaves, get_merkle_root, get_merkle_proof
from eth2spec.utils.minimal_ssz import signing_root


def build_deposit_data(state, pubkey, privkey, amount):
    deposit_data = DepositData(
        pubkey=pubkey,
        # insecurely use pubkey as withdrawal key as well
        withdrawal_credentials=spec.BLS_WITHDRAWAL_PREFIX_BYTE + hash(pubkey)[1:],
        amount=amount,
    )
    signature = bls_sign(
        message_hash=signing_root(deposit_data),
        privkey=privkey,
        domain=get_domain(
            state,
            spec.DOMAIN_DEPOSIT,
        )
    )
    deposit_data.signature = signature
    return deposit_data


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
