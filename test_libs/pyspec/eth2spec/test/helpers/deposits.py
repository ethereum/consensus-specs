from eth2spec.test.helpers.keys import pubkeys, privkeys
from eth2spec.utils.bls import bls_sign
from eth2spec.utils.merkle_minimal import calc_merkle_tree_from_leaves, get_merkle_root, get_merkle_proof
from eth2spec.utils.ssz.ssz_impl import signing_root, hash_tree_root
from eth2spec.utils.ssz.ssz_typing import List
from eth2spec.phase0.spec import DepositData


def build_deposit_data(spec, state, pubkey, privkey, amount, withdrawal_credentials, signed=False):
    deposit_data = DepositData(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
    )
    if signed:
        sign_deposit_data(spec, state, deposit_data, privkey)
    return deposit_data


def sign_deposit_data(spec, state, deposit_data, privkey):
    signature = bls_sign(
        message_hash=signing_root(deposit_data),
        privkey=privkey,
        domain=spec.get_domain(
            state,
            spec.DOMAIN_DEPOSIT,
        )
    )
    deposit_data.signature = signature


def build_deposit(spec,
                  state,
                  deposit_data_list,
                  pubkey,
                  privkey,
                  amount,
                  withdrawal_credentials,
                  signed):
    deposit_data = build_deposit_data(spec, state, pubkey, privkey, amount, withdrawal_credentials, signed)
    deposit_data_list.append(deposit_data)
    index = len(deposit_data_list)
    root = hash_tree_root(List[DepositData, 2**32](*deposit_data_list))
    tree = calc_merkle_tree_from_leaves(tuple([d.hash_tree_root() for d in deposit_data_list]))
    proof = list(get_merkle_proof(tree, item_index=index)) + [index.to_bytes(32, 'little')]
    leaf = deposit_data.hash_tree_root()
    assert spec.verify_merkle_branch(leaf, proof, spec.DEPOSIT_CONTRACT_TREE_DEPTH + 1, index, root)
    deposit = spec.Deposit(proof, index, deposit_data)

    return deposit, root, deposit_data_leaves


def prepare_state_and_deposit(spec, state, validator_index, amount, withdrawal_credentials=None, signed=False):
    """
    Prepare the state for the deposit, and create a deposit for the given validator, depositing the given amount.
    """
    deposit_data_list = []

    pubkey = pubkeys[validator_index]
    privkey = privkeys[validator_index]

    # insecurely use pubkey as withdrawal key if no credentials provided
    if withdrawal_credentials is None:
        withdrawal_credentials = spec.int_to_bytes(spec.BLS_WITHDRAWAL_PREFIX, length=1) + spec.hash(pubkey)[1:]

    deposit, root, deposit_data_list = build_deposit(
        spec,
        state,
        deposit_data_list,
        pubkey,
        privkey,
        amount,
        withdrawal_credentials,
        signed,
    )

    state.eth1_data.deposit_root = root
    state.eth1_data.deposit_count = len(deposit_data_list)
    return deposit
