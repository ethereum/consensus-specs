from random import Random

from eth2spec.test.context import expect_assertion_error
from eth2spec.test.helpers.forks import is_post_altair
from eth2spec.test.helpers.keys import pubkeys, privkeys
from eth2spec.test.helpers.state import get_balance
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
    if is_post_altair(spec):
        state.inactivity_scores[index] = 0
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


def prepare_state_and_deposit(spec, state, validator_index, amount,
                              pubkey=None,
                              privkey=None,
                              withdrawal_credentials=None,
                              signed=False):
    """
    Prepare the state for the deposit, and create a deposit for the given validator, depositing the given amount.
    """
    deposit_data_list = []

    if pubkey is None:
        pubkey = pubkeys[validator_index]

    if privkey is None:
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


def build_deposit_receipt(spec,
                          index,
                          pubkey,
                          privkey,
                          amount,
                          withdrawal_credentials,
                          signed):
    deposit_data = build_deposit_data(spec, pubkey, privkey, amount, withdrawal_credentials, signed=signed)
    return spec.DepositReceipt(
        pubkey=deposit_data.pubkey,
        withdrawal_credentials=deposit_data.withdrawal_credentials,
        amount=deposit_data.amount,
        signature=deposit_data.signature,
        index=index)


def prepare_deposit_receipt(spec, validator_index, amount,
                            index=None,
                            pubkey=None,
                            privkey=None,
                            withdrawal_credentials=None,
                            signed=False):
    """
    Create a deposit receipt for the given validator, depositing the given amount.
    """
    if index is None:
        index = validator_index

    if pubkey is None:
        pubkey = pubkeys[validator_index]

    if privkey is None:
        privkey = privkeys[validator_index]

    # insecurely use pubkey as withdrawal key if no credentials provided
    if withdrawal_credentials is None:
        withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(pubkey)[1:]

    return build_deposit_receipt(
        spec,
        index,
        pubkey,
        privkey,
        amount,
        withdrawal_credentials,
        signed,
    )

#
# Run processing
#


def run_deposit_processing(spec, state, deposit, validator_index, valid=True, effective=True):
    """
    Run ``process_deposit``, yielding:
      - pre-state ('pre')
      - deposit ('deposit')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    pre_validator_count = len(state.validators)
    pre_balance = 0
    is_top_up = False
    # is a top-up
    if validator_index < pre_validator_count:
        is_top_up = True
        pre_balance = get_balance(state, validator_index)
        pre_effective_balance = state.validators[validator_index].effective_balance

    yield 'pre', state
    yield 'deposit', deposit

    if not valid:
        expect_assertion_error(lambda: spec.process_deposit(state, deposit))
        yield 'post', None
        return

    spec.process_deposit(state, deposit)

    yield 'post', state

    if not effective or not bls.KeyValidate(deposit.data.pubkey):
        assert len(state.validators) == pre_validator_count
        assert len(state.balances) == pre_validator_count
        if is_top_up:
            assert get_balance(state, validator_index) == pre_balance
    else:
        if is_top_up:
            # Top-ups do not change effective balance
            assert state.validators[validator_index].effective_balance == pre_effective_balance
            assert len(state.validators) == pre_validator_count
            assert len(state.balances) == pre_validator_count
        else:
            # new validator
            assert len(state.validators) == pre_validator_count + 1
            assert len(state.balances) == pre_validator_count + 1
            effective_balance = min(spec.MAX_EFFECTIVE_BALANCE, deposit.data.amount)
            effective_balance -= effective_balance % spec.EFFECTIVE_BALANCE_INCREMENT
            assert state.validators[validator_index].effective_balance == effective_balance

        assert get_balance(state, validator_index) == pre_balance + deposit.data.amount

    assert state.eth1_deposit_index == state.eth1_data.deposit_count


def run_deposit_processing_with_specific_fork_version(
        spec,
        state,
        fork_version,
        valid=True,
        effective=True):
    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE

    pubkey = pubkeys[validator_index]
    privkey = privkeys[validator_index]
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(pubkey)[1:]

    deposit_message = spec.DepositMessage(pubkey=pubkey, withdrawal_credentials=withdrawal_credentials, amount=amount)
    domain = spec.compute_domain(domain_type=spec.DOMAIN_DEPOSIT, fork_version=fork_version)
    deposit_data = spec.DepositData(
        pubkey=pubkey, withdrawal_credentials=withdrawal_credentials, amount=amount,
        signature=bls.Sign(privkey, spec.compute_signing_root(deposit_message, domain))
    )
    deposit, root, _ = deposit_from_context(spec, [deposit_data], 0)

    state.eth1_deposit_index = 0
    state.eth1_data.deposit_root = root
    state.eth1_data.deposit_count = 1

    yield from run_deposit_processing(spec, state, deposit, validator_index, valid=valid, effective=effective)


def run_deposit_receipt_processing(spec, state, deposit_receipt, validator_index, valid=True, effective=True):
    """
    Run ``process_deposit_receipt``, yielding:
      - pre-state ('pre')
      - deposit_receipt ('deposit_receipt')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    pre_validator_count = len(state.validators)
    pre_balance = 0
    is_top_up = False
    # is a top-up
    if validator_index < pre_validator_count:
        is_top_up = True
        pre_balance = get_balance(state, validator_index)
        pre_effective_balance = state.validators[validator_index].effective_balance

    yield 'pre', state
    yield 'deposit_receipt', deposit_receipt

    if not valid:
        expect_assertion_error(lambda: spec.process_deposit_receipt(state, deposit_receipt))
        yield 'post', None
        return

    spec.process_deposit_receipt(state, deposit_receipt)

    yield 'post', state

    if not effective or not bls.KeyValidate(deposit_receipt.pubkey):
        assert len(state.validators) == pre_validator_count
        assert len(state.balances) == pre_validator_count
        if is_top_up:
            assert get_balance(state, validator_index) == pre_balance
    else:
        if is_top_up:
            # Top-ups do not change effective balance
            assert state.validators[validator_index].effective_balance == pre_effective_balance
            assert len(state.validators) == pre_validator_count
            assert len(state.balances) == pre_validator_count
        else:
            # new validator
            assert len(state.validators) == pre_validator_count + 1
            assert len(state.balances) == pre_validator_count + 1
            effective_balance = min(spec.MAX_EFFECTIVE_BALANCE, deposit_receipt.amount)
            effective_balance -= effective_balance % spec.EFFECTIVE_BALANCE_INCREMENT
            assert state.validators[validator_index].effective_balance == effective_balance

        assert get_balance(state, validator_index) == pre_balance + deposit_receipt.amount


def run_deposit_receipt_processing_with_specific_fork_version(
        spec,
        state,
        fork_version,
        valid=True,
        effective=True):
    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE

    pubkey = pubkeys[validator_index]
    privkey = privkeys[validator_index]
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(pubkey)[1:]

    deposit_message = spec.DepositMessage(pubkey=pubkey, withdrawal_credentials=withdrawal_credentials, amount=amount)
    domain = spec.compute_domain(domain_type=spec.DOMAIN_DEPOSIT, fork_version=fork_version)
    deposit_data = spec.DepositData(
        pubkey=pubkey, withdrawal_credentials=withdrawal_credentials, amount=amount,
        signature=bls.Sign(privkey, spec.compute_signing_root(deposit_message, domain))
    )
    deposit_receipt = spec.DepositReceipt(
        pubkey=deposit_data.pubkey,
        withdrawal_credentials=deposit_data.withdrawal_credentials,
        amount=deposit_data.amount,
        signature=deposit_data.signature,
        index=validator_index)

    yield from run_deposit_receipt_processing(
        spec,
        state,
        deposit_receipt,
        validator_index,
        valid=valid,
        effective=effective
    )
