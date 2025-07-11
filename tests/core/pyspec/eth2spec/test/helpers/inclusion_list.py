from eth2spec.utils.ssz.ssz_impl import hash_tree_root
from eth2spec.utils.ssz.ssz_typing import Vector


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


def get_sample_inclusion_list(
    spec,
    state,
    slot=None,
    validator_index=None,
    max_transaction_count=10,
):
    """
    Build sample inclusion list for ``slot``. Slot must be greater than or equal to the current slot in ``state``.
    """
    inclusion_list = get_empty_inclusion_list(spec, state, slot, validator_index)
    inclusion_list.transactions = get_sample_inclusion_list_transactions(
        spec, max_transaction_count
    )

    return inclusion_list


def get_sample_inclusion_list_transactions(spec, max_transaction_count):
    """
    Build sample inclusion list transactions for ``slot``. Slot must be greater than or equal to the current slot in ``state``.
    """
    transaction_size = 200
    transaction_count = min(
        max_transaction_count, spec.config.MAX_BYTES_PER_INCLUSION_LIST // transaction_size
    )
    transactions = [spec.Transaction(b"\x99" * transaction_size) for _ in range(transaction_count)]

    return transactions
