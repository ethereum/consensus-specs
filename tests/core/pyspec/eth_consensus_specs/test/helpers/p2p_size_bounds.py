def build_max_size_signed_inclusion_list(spec):
    # The largest valid list: MAX_TRANSACTIONS_BYTES_PER_INCLUSION_LIST one-byte transactions,
    # each costing its byte plus a 4-byte SSZ offset
    transaction_count = spec.config.MAX_TRANSACTIONS_BYTES_PER_INCLUSION_LIST
    transactions = spec.Transactions.of(
        *[spec.Transaction(data=[0]) for _ in range(transaction_count)]
    )
    inclusion_list = spec.InclusionList(
        slot=spec.Slot(0),
        validator_index=spec.ValidatorIndex(0),
        dependent_root=spec.Root(),
        transactions=transactions,
    )
    return spec.SignedInclusionList(message=inclusion_list, signature=spec.BLSSignature())


def get_max_signed_inclusion_list_size(spec):
    return spec.MAX_SIGNED_INCLUSION_LIST_SIZE
