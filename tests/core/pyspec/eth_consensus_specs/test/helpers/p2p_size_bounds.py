from eth_consensus_specs.test.helpers.forks import is_post_heze


def build_max_size_attestation(spec):
    aggregation_bits = spec.AggregationBits(
        data=[True] * (spec.MAX_VALIDATORS_PER_COMMITTEE * spec.MAX_COMMITTEES_PER_SLOT)
    )
    return spec.Attestation(
        aggregation_bits=spec.AggregationBits(data=aggregation_bits),
        data=spec.AttestationData(),
        signature=spec.BLSSignature(),
        committee_bits=spec.CommitteeBits(),
    )


def build_max_size_indexed_attestation(spec):
    attesting_indices = spec.AttestingIndices(
        data=[spec.ValidatorIndex(0)]
        * (spec.MAX_VALIDATORS_PER_COMMITTEE * spec.MAX_COMMITTEES_PER_SLOT)
    )
    return spec.IndexedAttestation(
        attesting_indices=spec.AttestingIndices(data=attesting_indices),
        data=spec.AttestationData(),
        signature=spec.BLSSignature(),
    )


def build_max_size_payload_attestation(spec):
    return spec.PayloadAttestation(
        aggregation_bits=spec.PTCBits(data=[True] * spec.PTC_SIZE),
        data=spec.PayloadAttestationData(),
        signature=spec.BLSSignature(),
    )


def build_max_size_attester_slashing(spec):
    return spec.AttesterSlashing(
        attestation_1=build_max_size_indexed_attestation(spec),
        attestation_2=build_max_size_indexed_attestation(spec),
    )


def build_max_size_signed_aggregate_and_proof(spec):
    aggregate_and_proof = spec.AggregateAndProof(
        aggregator_index=spec.ValidatorIndex(0),
        aggregate=build_max_size_attestation(spec),
        selection_proof=spec.BLSSignature(),
    )
    return spec.SignedAggregateAndProof(
        message=aggregate_and_proof,
        signature=spec.BLSSignature(),
    )


def build_max_size_signed_execution_payload_bid(spec):
    blob_kzg_commitments = spec.BlobKZGCommitments(
        data=[spec.KZGCommitment()] * spec.MAX_BLOB_COMMITMENTS_PER_BLOCK
    )
    bid = spec.ExecutionPayloadBid(
        blob_kzg_commitments=spec.BlobKZGCommitments(data=blob_kzg_commitments)
    )
    return spec.SignedExecutionPayloadBid(message=bid, signature=spec.BLSSignature())


def build_max_size_data_column_sidecar(spec):
    column = spec.DataColumn(data=[spec.Cell()] * spec.MAX_BLOB_COMMITMENTS_PER_BLOCK)
    kzg_proofs = spec.KZGProofs(data=[spec.KZGProof()] * spec.MAX_BLOB_COMMITMENTS_PER_BLOCK)
    return spec.DataColumnSidecar(
        index=spec.ColumnIndex(0),
        column=spec.DataColumn(data=column),
        kzg_proofs=spec.KZGProofs(data=kzg_proofs),
        slot=spec.Slot(0),
        beacon_block_root=spec.Root(),
    )


def build_max_size_partial_data_column_sidecar(spec):
    cells_present_bitmap = spec.CellsBitList(data=[True] * spec.MAX_BLOB_COMMITMENTS_PER_BLOCK)
    partial_column = spec.DataColumn(data=[spec.Cell()] * spec.MAX_BLOB_COMMITMENTS_PER_BLOCK)
    kzg_proofs = spec.KZGProofs(data=[spec.KZGProof()] * spec.MAX_BLOB_COMMITMENTS_PER_BLOCK)
    return spec.PartialDataColumnSidecar(
        cells_present_bitmap=spec.CellsBitList(data=cells_present_bitmap),
        partial_column=spec.DataColumn(data=partial_column),
        kzg_proofs=spec.KZGProofs(data=kzg_proofs),
    )


def build_max_size_signed_inclusion_list(spec):
    transactions_size = spec.config.MAX_TRANSACTIONS_BYTES_PER_INCLUSION_LIST
    transactions = spec.Transactions.of(spec.Transaction(data=list(b"\x00" * transactions_size)))
    inclusion_list = spec.InclusionList(
        slot=spec.Slot(0),
        validator_index=spec.ValidatorIndex(0),
        dependent_root=spec.Root(),
        transactions=transactions,
    )
    return spec.SignedInclusionList(message=inclusion_list, signature=spec.BLSSignature())


def build_max_size_signed_execution_proof(spec):
    return spec.SignedExecutionProof(
        message=spec.ExecutionProof(
            proof_data=spec.ProofData(data=[0] * spec.MAX_PROOF_SIZE),
            proof_type=spec.ProofType(0),
            public_input=spec.PublicInput(),
        ),
        validator_index=spec.ValidatorIndex(0),
        signature=spec.BLSSignature(),
    )


def get_max_signed_aggregate_and_proof_size(spec):
    return spec.MAX_SIGNED_AGGREGATE_AND_PROOF_SIZE


def get_max_attester_slashing_size(spec):
    return spec.MAX_ATTESTER_SLASHING_SIZE


def get_max_data_column_sidecar_size(spec):
    return spec.MAX_DATA_COLUMN_SIDECAR_SIZE


def get_max_partial_data_column_sidecar_size(spec):
    return spec.MAX_PARTIAL_DATA_COLUMN_SIDECAR_SIZE


def get_max_signed_execution_payload_bid_size(spec):
    size = spec.MAX_SIGNED_EXECUTION_PAYLOAD_BID_SIZE
    if is_post_heze(spec):
        size = spec.MAX_SIGNED_EXECUTION_PAYLOAD_BID_SIZE_HEZE
    return size


def get_max_signed_inclusion_list_size(spec):
    return spec.MAX_SIGNED_INCLUSION_LIST_SIZE


def get_max_signed_execution_proof_size(spec):
    return spec.MAX_SIGNED_EXECUTION_PROOF_SIZE
