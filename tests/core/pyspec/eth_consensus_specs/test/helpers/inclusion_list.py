from functools import lru_cache
from random import randbytes

from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.utils.ssz.ssz_impl import hash_tree_root
from eth_consensus_specs.utils.ssz.ssz_typing import Vector


def get_empty_inclusion_list(spec, state, slot=None, validator_index=None):
    """
    Build an empty inclusion list for ``slot``. Slot must be greater than or equal to the current slot in ``state``.
    """
    if slot is None:
        slot = state.slot
    if slot < state.slot:
        raise Exception("get_empty_inclusion_list cannot build inclusion lists for past slots")

    committee = spec.get_inclusion_list_committee(state, slot)
    committee_root = hash_tree_root(
        Vector[spec.ValidatorIndex, spec.INCLUSION_LIST_COMMITTEE_SIZE](*committee)
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


def get_empty_signed_inclusion_list(
    spec,
    state,
    slot=None,
    validator_index=None,
):
    """
    Build an empty signed inclusion list for ``slot``. Slot must be greater than or equal to the current slot in ``state``.
    """
    empty_inclusion_list = get_empty_inclusion_list(spec, state, slot, validator_index)
    signed_inclusion_list = sign_inclusion_list(spec, state, empty_inclusion_list)

    return signed_inclusion_list


def get_sample_inclusion_list(
    spec,
    state,
    slot=None,
    validator_index=None,
    transactions=None,
    max_transaction_size=200,
    max_transaction_count=10,
):
    """
    Build a sample inclusion list for ``slot``. Slot must be greater than or equal to the current slot in ``state``.
    When ``transactions`` is provided, ``max_transaction_size`` and ``max_transaction_count`` are ignored.
    """
    inclusion_list = get_empty_inclusion_list(spec, state, slot, validator_index)
    inclusion_list.transactions = (
        get_sample_transactions(spec, max_transaction_size, max_transaction_count)
        if transactions is None
        else transactions
    )

    return inclusion_list


def get_sample_signed_inclusion_list(
    spec,
    state,
    slot=None,
    validator_index=None,
    transactions=None,
    max_transaction_size=200,
    max_transaction_count=10,
):
    """
    Build a sample signed inclusion list for ``slot``. Slot must be greater than or equal to the current slot in ``state``.
    When ``transactions`` is provided, ``max_transaction_size`` and ``max_transaction_count`` are ignored.
    """
    sample_inclusion_list = get_sample_inclusion_list(
        spec,
        state,
        slot,
        validator_index,
        transactions,
        max_transaction_size,
        max_transaction_count,
    )
    signed_inclusion_list = sign_inclusion_list(spec, state, sample_inclusion_list)

    return signed_inclusion_list


def get_sample_transactions(spec, max_transaction_size=200, max_transaction_count=10):
    """
    Build a list of sample transactions.
    """
    transaction_size = min(max_transaction_size, spec.config.MAX_BYTES_PER_INCLUSION_LIST)
    transaction_count = min(
        max_transaction_count,
        spec.config.MAX_BYTES_PER_INCLUSION_LIST // transaction_size
        if transaction_size
        else spec.config.MAX_BYTES_PER_INCLUSION_LIST,
    )

    assert transaction_size >= 0 and transaction_count >= 0

    transactions = [spec.Transaction(randbytes(transaction_size)) for _ in range(transaction_count)]

    return transactions


def sign_inclusion_list(spec, state, inclusion_list):
    """
    Sign an inclusion list.
    """
    privkey = privkeys[inclusion_list.validator_index]
    signature = spec.get_inclusion_list_signature(state, inclusion_list, privkey)

    return spec.SignedInclusionList(message=inclusion_list, signature=signature)


def run_with_inclusion_list_store(spec, func):
    """
    This helper runs the given ``func`` with monkeypatched ``cached_or_new_inclusion_list_store``
    that returns cached inclusion list store, or a new one if none exists.
    """

    @lru_cache(maxsize=1)
    def cached_or_new_inclusion_list_store():
        return spec.InclusionListStore()

    cached_or_new_inclusion_list_store_backup = spec.cached_or_new_inclusion_list_store
    spec.cached_or_new_inclusion_list_store = cached_or_new_inclusion_list_store

    try:
        func()
    finally:
        spec.cached_or_new_inclusion_list_store = cached_or_new_inclusion_list_store_backup
        cached_or_new_inclusion_list_store.cache_clear()
