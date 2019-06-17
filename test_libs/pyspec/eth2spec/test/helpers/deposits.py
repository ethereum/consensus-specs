from eth2spec.test.helpers.keys import pubkeys, privkeys
from eth2spec.utils.bls import bls_sign
from eth2spec.utils.merkle_minimal import calc_merkle_tree_from_leaves, get_merkle_root, get_merkle_proof
from eth2spec.utils.ssz.ssz_impl import signing_root


def build_deposit_data(spec, state, pubkey, privkey, amount, withdrawal_credentials, signed=False):
    deposit_data = spec.DepositData(
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
                  deposit_data_leaves,
                  pubkey,
                  privkey,
                  amount,
                  withdrawal_credentials,
                  signed):
    deposit_data = build_deposit_data(spec, state, pubkey, privkey, amount, withdrawal_credentials, signed)

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


def prepare_state_and_deposit(spec, state, validator_index, amount, withdrawal_credentials=None, signed=False):
    """
    Prepare the state for the deposit, and create a deposit for the given validator, depositing the given amount.
    """
    pre_validator_count = len(state.validators)
    # fill previous deposits with zero-hash
    deposit_data_leaves = [spec.ZERO_HASH] * pre_validator_count

    pubkey = pubkeys[validator_index]
    privkey = privkeys[validator_index]

    # insecurely use pubkey as withdrawal key if no credentials provided
    if withdrawal_credentials is None:
        withdrawal_credentials = spec.int_to_bytes(spec.BLS_WITHDRAWAL_PREFIX, length=1) + spec.hash(pubkey)[1:]

    deposit, root, deposit_data_leaves = build_deposit(
        spec,
        state,
        deposit_data_leaves,
        pubkey,
        privkey,
        amount,
        withdrawal_credentials,
        signed,
    )

    state.eth1_data.deposit_root = root
    state.eth1_data.deposit_count = len(deposit_data_leaves)
    return deposit
