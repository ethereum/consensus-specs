from random import Random

from eth2spec.test.helpers.keys import pubkeys, privkeys
from eth2spec.utils import bls
from eth2spec.utils.merkle_minimal import calc_merkle_tree_from_leaves, get_merkle_proof
from eth2spec.utils.ssz.ssz_impl import hash_tree_root
from eth2spec.utils.ssz.ssz_typing import List


def mock_deposit(spec, state, index):
    """
    Mock validator at ``index`` as having just made a deposit
    """
    assert spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))
    state.validators[index].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH
    state.validators[index].activation_epoch = spec.FAR_FUTURE_EPOCH
    state.validators[index].effective_balance = spec.MAX_EFFECTIVE_BALANCE
    assert not spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))


def build_deposit_data(spec, pubkey, privkey, amount, withdrawal_credentials, signed=False):
    deposit_data = spec.DepositData(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
    )
    if signed:
        sign_deposit_data(spec, deposit_data, privkey)
    return deposit_data


def sign_deposit_data(spec, deposit_data, privkey):
    deposit_message = spec.DepositMessage(
        pubkey=deposit_data.pubkey,
        withdrawal_credentials=deposit_data.withdrawal_credentials,
        amount=deposit_data.amount)
    domain = spec.compute_domain(spec.DOMAIN_DEPOSIT)
    signing_root = spec.compute_signing_root(deposit_message, domain)
    deposit_data.signature = bls.Sign(privkey, signing_root)


def build_deposit(spec,
                  deposit_data_list,
                  pubkey,
                  privkey,
                  amount,
                  withdrawal_credentials,
                  signed):
    deposit_data = build_deposit_data(spec, pubkey, privkey, amount, withdrawal_credentials, signed=signed)
    index = len(deposit_data_list)
    deposit_data_list.append(deposit_data)
    return deposit_from_context(spec, deposit_data_list, index)


def deposit_from_context(spec, deposit_data_list, index):
    deposit_data = deposit_data_list[index]
    root = hash_tree_root(List[spec.DepositData, 2**spec.DEPOSIT_CONTRACT_TREE_DEPTH](*deposit_data_list))
    tree = calc_merkle_tree_from_leaves(tuple([d.hash_tree_root() for d in deposit_data_list]))
    proof = (
        list(get_merkle_proof(tree, item_index=index, tree_len=32))
        + [len(deposit_data_list).to_bytes(32, 'little')]
    )
    leaf = deposit_data.hash_tree_root()
    assert spec.is_valid_merkle_branch(leaf, proof, spec.DEPOSIT_CONTRACT_TREE_DEPTH + 1, index, root)
    deposit = spec.Deposit(proof=proof, data=deposit_data)

    return deposit, root, deposit_data_list


def prepare_full_genesis_deposits(spec,
                                  amount,
                                  deposit_count,
                                  min_pubkey_index=0,
                                  signed=False,
                                  deposit_data_list=None):
    if deposit_data_list is None:
        deposit_data_list = []
    genesis_deposits = []
    for pubkey_index in range(min_pubkey_index, min_pubkey_index + deposit_count):
        pubkey = pubkeys[pubkey_index]
        privkey = privkeys[pubkey_index]
        # insecurely use pubkey as withdrawal key if no credentials provided
        withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(pubkey)[1:]
        deposit, root, deposit_data_list = build_deposit(
            spec,
            deposit_data_list=deposit_data_list,
            pubkey=pubkey,
            privkey=privkey,
            amount=amount,
            withdrawal_credentials=withdrawal_credentials,
            signed=signed,
        )
        genesis_deposits.append(deposit)

    return genesis_deposits, root, deposit_data_list


def prepare_random_genesis_deposits(spec,
                                    deposit_count,
                                    max_pubkey_index,
                                    min_pubkey_index=0,
                                    max_amount=None,
                                    min_amount=None,
                                    deposit_data_list=None,
                                    rng=Random(3131)):
    if max_amount is None:
        max_amount = spec.MAX_EFFECTIVE_BALANCE
    if min_amount is None:
        min_amount = spec.MIN_DEPOSIT_AMOUNT
    if deposit_data_list is None:
        deposit_data_list = []
    deposits = []
    for _ in range(deposit_count):
        pubkey_index = rng.randint(min_pubkey_index, max_pubkey_index)
        pubkey = pubkeys[pubkey_index]
        privkey = privkeys[pubkey_index]
        amount = rng.randint(min_amount, max_amount)
        random_byte = bytes([rng.randint(0, 255)])
        withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(random_byte)[1:]
        deposit, root, deposit_data_list = build_deposit(
            spec,
            deposit_data_list=deposit_data_list,
            pubkey=pubkey,
            privkey=privkey,
            amount=amount,
            withdrawal_credentials=withdrawal_credentials,
            signed=True,
        )
        deposits.append(deposit)
    return deposits, root, deposit_data_list


def prepare_state_and_deposit(spec, state, validator_index, amount, withdrawal_credentials=None, signed=False):
    """
    Prepare the state for the deposit, and create a deposit for the given validator, depositing the given amount.
    """
    deposit_data_list = []

    pubkey = pubkeys[validator_index]
    privkey = privkeys[validator_index]

    # insecurely use pubkey as withdrawal key if no credentials provided
    if withdrawal_credentials is None:
        withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(pubkey)[1:]

    deposit, root, deposit_data_list = build_deposit(
        spec,
        deposit_data_list,
        pubkey,
        privkey,
        amount,
        withdrawal_credentials,
        signed,
    )

    state.eth1_deposit_index = 0
    state.eth1_data.deposit_root = root
    state.eth1_data.deposit_count = len(deposit_data_list)
    return deposit
