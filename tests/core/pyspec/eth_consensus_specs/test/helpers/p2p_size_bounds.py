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


def build_max_size_signed_execution_proof_envelope(spec):
    return spec.SignedExecutionProofEnvelope(
        message=spec.ExecutionProofEnvelope(
            proof_data=spec.ProofData(data=[0] * spec.MAX_PROOF_SIZE),
            proof_type=spec.ProofType(0),
            beacon_block_root=spec.Root(),
        ),
        validator_index=spec.ValidatorIndex(0),
        signature=spec.BLSSignature(),
    )


def get_max_signed_inclusion_list_size(spec):
    return spec.MAX_SIGNED_INCLUSION_LIST_SIZE


def get_max_signed_execution_proof_envelope_size(spec):
    return spec.MAX_SIGNED_EXECUTION_PROOF_ENVELOPE_SIZE
