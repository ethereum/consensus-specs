import random

from eth2spec.utils.ssz.ssz_impl import hash_tree_root
from eth2spec.utils.ssz.ssz_typing import List


def get_empty_inclusion_list(spec, state, slot=None, validator_index=None):
    """
    Build empty inclusion list for ``slot``. Slot must be greater than or equal to the current slot in ``state``.
    """
    if slot is None:
        slot = state.slot
    if slot < state.slot:
        raise Exception("get_empty_inclusion_list cannot build inclusion lists for past slots")

    committee = spec.get_inclusion_list_committee(state, slot)
    committee_root = hash_tree_root(
        List[spec.ValidatorIndex, spec.INCLUSION_LIST_COMMITTEE_SIZE](committee)
    )

    if validator_index is None:
        validator_index = committee[0]
    else:
        assert validator_index in committee

    empty_inclusion_list = spec.InclusionList()
    empty_inclusion_list.slot = slot
    empty_inclusion_list.validator_index = validator_index
    empty_inclusion_list.inclusion_list_committee_root = committee_root
    empty_inclusion_list.transactions = []

    return empty_inclusion_list


def get_sample_inclusion_list(
    spec,
    state,
    rng=random.Random(7805),
    slot=None,
    validator_index=None,
    max_transaction_count=1,
    is_valid_inclusion_list=True,
):
    """
    Build sample inclusion list for ``slot``. Slot must be greater than or equal to the current slot in ``state``.
    """
    inclusion_list = get_empty_inclusion_list(spec, state, slot, validator_index)
    inclusion_list.transactions = get_sample_inclusion_list_transactions(
        spec, state, rng, max_transaction_count, is_valid_inclusion_list
    )

    return inclusion_list


def get_sample_inclusion_list_transactions(
    spec,
    state,
    rng=random.Random(7805),
    max_transaction_count=1,
    is_valid_inclusion_list=True,
):
    """
    Build sample inclusion list transactions for ``slot``. Slot must be greater than or equal to the current slot in ``state``.
    """
    transaction_size = 200
    transaction_count = min(
        max_transaction_count, spec.config.MAX_BYTES_PER_INCLUSION_LIST // transaction_size
    )
    transactions = [spec.Transaction(b"\x99" * transaction_size) for _ in range(transaction_count)]

    return transactions


def run_with_inclusion_list(spec, inclusion_list, func):
    """
    This helper runs the given ``func`` with monkeypatched ``retrieve_inclusion_list_transactions``
    that returns ``inclusion_list.transactions``.
    """

    def retrieve_inclusion_list_transactions(state, slot):
        return inclusion_list.transactions

    retrieve_inclusion_list_transactions_backup = spec.retrieve_inclusion_list_transactions
    spec.retrieve_inclusion_list_transactions = retrieve_inclusion_list_transactions

    class AtomicBoolean:
        value = False

    is_called = AtomicBoolean()

    def wrap(flag: AtomicBoolean):
        yield from func()
        flag.value = True

    try:
        yield from wrap(is_called)
    finally:
        spec.retrieve_inclusion_list_transactions = retrieve_inclusion_list_transactions_backup
    assert is_called.value
