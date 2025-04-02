from random import Random

from eth2spec.test.context import expect_assertion_error
from eth2spec.test.helpers.forks import is_post_altair, is_post_electra
from eth2spec.test.helpers.keys import pubkeys, privkeys
from eth2spec.test.helpers.state import get_balance
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_to
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


def build_deposit_data(spec, pubkey, privkey, amount, withdrawal_credentials, fork_version=None, signed=False):
    deposit_data = spec.DepositData(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
    )
    if signed:
        sign_deposit_data(spec, deposit_data, privkey, fork_version)
    return deposit_data


def sign_deposit_data(spec, deposit_data, privkey, fork_version=None):
    deposit_message = spec.DepositMessage(
        pubkey=deposit_data.pubkey,
        withdrawal_credentials=deposit_data.withdrawal_credentials,
        amount=deposit_data.amount)
    if fork_version is not None:
        domain = spec.compute_domain(domain_type=spec.DOMAIN_DEPOSIT, fork_version=fork_version)
    else:
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


def prepare_deposit_request(spec, validator_index, amount,
                            index=None,
                            pubkey=None,
                            privkey=None,
                            withdrawal_credentials=None,
                            signed=False):
    """
    Create a deposit request for the given validator, depositing the given amount.
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

    deposit_data = build_deposit_data(spec, pubkey, privkey, amount, withdrawal_credentials, signed=signed)
    return spec.DepositRequest(
        pubkey=deposit_data.pubkey,
        withdrawal_credentials=deposit_data.withdrawal_credentials,
        amount=deposit_data.amount,
        signature=deposit_data.signature,
        index=index
    )


def prepare_pending_deposit(spec, validator_index, amount,
                            pubkey=None,
                            privkey=None,
                            withdrawal_credentials=None,
                            fork_version=None,
                            signed=False,
                            slot=None):
    """
    Create a pending deposit for the given validator, depositing the given amount.
    """
    if pubkey is None:
        pubkey = pubkeys[validator_index]

    if privkey is None:
        privkey = privkeys[validator_index]

    # insecurely use pubkey as withdrawal key if no credentials provided
    if withdrawal_credentials is None:
        withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(pubkey)[1:]

    # use GENESIS_SLOT which is always finalized if no slot provided
    if slot is None:
        slot = spec.GENESIS_SLOT

    deposit_data = build_deposit_data(spec,
                                      pubkey,
                                      privkey,
                                      amount,
                                      withdrawal_credentials,
                                      fork_version,
                                      signed)

    return spec.PendingDeposit(
        pubkey=deposit_data.pubkey,
        amount=deposit_data.amount,
        withdrawal_credentials=deposit_data.withdrawal_credentials,
        signature=deposit_data.signature,
        slot=slot,
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
    pre_effective_balance = 0
    is_top_up = False
    # is a top-up
    if validator_index < pre_validator_count:
        is_top_up = True
        pre_balance = get_balance(state, validator_index)
        pre_effective_balance = state.validators[validator_index].effective_balance

    if is_post_electra(spec):
        pre_pending_deposits_count = len(state.pending_deposits)

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
        if is_post_electra(spec):
            assert len(state.pending_deposits) == pre_pending_deposits_count
    else:
        if is_top_up:
            # Top-ups don't add validators
            assert len(state.validators) == pre_validator_count
            assert len(state.balances) == pre_validator_count
        else:
            # new validator is added
            assert len(state.validators) == pre_validator_count + 1
            assert len(state.balances) == pre_validator_count + 1
        if not is_post_electra(spec):
            if is_top_up:
                # Top-ups do not change effective balance
                assert state.validators[validator_index].effective_balance == pre_effective_balance
            else:
                effective_balance = min(spec.MAX_EFFECTIVE_BALANCE, deposit.data.amount)
                effective_balance -= effective_balance % spec.EFFECTIVE_BALANCE_INCREMENT
                assert state.validators[validator_index].effective_balance == effective_balance
            assert get_balance(state, validator_index) == pre_balance + deposit.data.amount
        else:
            # no balance or effective balance changes on deposit processing post electra
            assert get_balance(state, validator_index) == pre_balance
            assert state.validators[validator_index].effective_balance == pre_effective_balance
            # new correct balance deposit queued up
            assert len(state.pending_deposits) == pre_pending_deposits_count + 1
            assert state.pending_deposits[pre_pending_deposits_count].pubkey == deposit.data.pubkey
            assert state.pending_deposits[
                pre_pending_deposits_count].withdrawal_credentials == deposit.data.withdrawal_credentials
            assert state.pending_deposits[pre_pending_deposits_count].amount == deposit.data.amount
            assert state.pending_deposits[pre_pending_deposits_count].signature == deposit.data.signature
            assert state.pending_deposits[pre_pending_deposits_count].slot == spec.GENESIS_SLOT

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


def run_deposit_request_processing(
        spec,
        state,
        deposit_request,
        validator_index,
        effective=True):

    """
    Run ``process_deposit_request``, yielding:
      - pre-state ('pre')
      - deposit_request ('deposit_request')
      - post-state ('post').
    """
    assert is_post_electra(spec)

    pre_validator_count = len(state.validators)
    pre_balance = 0
    is_top_up = False
    # is a top-up
    if validator_index < pre_validator_count:
        is_top_up = True
        pre_balance = get_balance(state, validator_index)
        pre_effective_balance = state.validators[validator_index].effective_balance

    yield 'pre', state
    yield 'deposit_request', deposit_request

    spec.process_deposit_request(state, deposit_request)

    yield 'post', state

    # New validator is only created after the pending_deposits processing
    assert len(state.validators) == pre_validator_count
    assert len(state.balances) == pre_validator_count

    if is_top_up:
        assert state.validators[validator_index].effective_balance == pre_effective_balance
        assert state.balances[validator_index] == pre_balance

    pending_deposit = spec.PendingDeposit(
        pubkey=deposit_request.pubkey,
        withdrawal_credentials=deposit_request.withdrawal_credentials,
        amount=deposit_request.amount,
        signature=deposit_request.signature,
        slot=state.slot,
    )

    assert state.pending_deposits == [pending_deposit]


def run_pending_deposit_applying(spec, state, pending_deposit, validator_index, effective=True):
    """
    Enqueue ``pending_deposit`` and run epoch processing with ``process_pending_deposits``, yielding:
      - pre-state ('pre')
      - post-state ('post').
    """
    assert is_post_electra(spec)

    # ensure the transition from eth1 bridge is complete
    state.deposit_requests_start_index = state.eth1_deposit_index

    # ensure there is enough churn to apply the deposit
    if pending_deposit.amount > spec.get_activation_exit_churn_limit(state):
        state.deposit_balance_to_consume = pending_deposit.amount - spec.get_activation_exit_churn_limit(state)

    # append pending deposit
    state.pending_deposits.append(pending_deposit)

    # run to the very beginning of the epoch processing to avoid
    # any updates to the validator registry (e.g. ejections)
    run_epoch_processing_to(spec, state, "process_justification_and_finalization")

    pre_validator_count = len(state.validators)
    pre_balance = 0
    pre_effective_balance = 0
    is_top_up = False
    # is a top-up
    if validator_index < pre_validator_count:
        is_top_up = True
        pre_balance = get_balance(state, validator_index)
        pre_effective_balance = state.validators[validator_index].effective_balance

    yield 'pre', state

    spec.process_pending_deposits(state)

    yield 'post', state

    if effective:
        if is_top_up:
            # Top-ups don't add validators
            assert len(state.validators) == pre_validator_count
            assert len(state.balances) == pre_validator_count
            # Top-ups do not change effective balance
            assert state.validators[validator_index].effective_balance == pre_effective_balance
        else:
            # new validator is added
            assert len(state.validators) == pre_validator_count + 1
            assert len(state.balances) == pre_validator_count + 1
            # effective balance is set correctly
            max_effective_balance = spec.get_max_effective_balance(state.validators[validator_index])
            effective_balance = min(max_effective_balance, pending_deposit.amount)
            effective_balance -= effective_balance % spec.EFFECTIVE_BALANCE_INCREMENT
            actual_effective_balance_after_deposit = state.validators[validator_index].effective_balance
            assert actual_effective_balance_after_deposit == effective_balance
        actual_balance_after_deposit = get_balance(state, validator_index)
        assert actual_balance_after_deposit == pre_balance + pending_deposit.amount
    else:
        assert len(state.validators) == pre_validator_count
        assert len(state.balances) == pre_validator_count
        if is_top_up:
            assert get_balance(state, validator_index) == pre_balance

    assert len(state.pending_deposits) == 0
