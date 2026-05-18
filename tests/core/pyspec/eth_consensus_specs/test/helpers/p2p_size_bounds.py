from eth_consensus_specs.test.helpers.forks import is_post_heze


def _max_attestation(spec):
    aggregation_bits = spec.AggregationBits(
        [True] * (spec.MAX_VALIDATORS_PER_COMMITTEE * spec.MAX_COMMITTEES_PER_SLOT)
    )
    return spec.Attestation(
        aggregation_bits=aggregation_bits,
        data=spec.AttestationData(),
        signature=spec.BLSSignature(),
        committee_bits=spec.Bitvector[spec.MAX_COMMITTEES_PER_SLOT](),
    )


def _max_indexed_attestation(spec):
    attesting_indices = spec.AttestingIndices(
        [spec.ValidatorIndex(0)]
        * (spec.MAX_VALIDATORS_PER_COMMITTEE * spec.MAX_COMMITTEES_PER_SLOT)
    )
    return spec.IndexedAttestation(
        attesting_indices=attesting_indices,
        data=spec.AttestationData(),
        signature=spec.BLSSignature(),
    )


def _max_payload_attestation(spec):
    return spec.PayloadAttestation(
        aggregation_bits=spec.Bitvector[spec.PTC_SIZE]([True] * spec.PTC_SIZE),
        data=spec.PayloadAttestationData(),
        signature=spec.BLSSignature(),
    )


def build_max_size_attester_slashing(spec):
    return spec.AttesterSlashing(
        attestation_1=_max_indexed_attestation(spec),
        attestation_2=_max_indexed_attestation(spec),
    )


def build_max_size_signed_aggregate_and_proof(spec):
    aggregate_and_proof = spec.AggregateAndProof(
        aggregator_index=spec.ValidatorIndex(0),
        aggregate=_max_attestation(spec),
        selection_proof=spec.BLSSignature(),
    )
    return spec.SignedAggregateAndProof(
        message=aggregate_and_proof,
        signature=spec.BLSSignature(),
    )


def build_max_size_signed_execution_payload_bid(spec):
    blob_kzg_commitments = spec.ProgressiveList[spec.KZGCommitment](
        [spec.KZGCommitment()] * spec.MAX_BLOB_COMMITMENTS_PER_BLOCK
    )
    bid = spec.ExecutionPayloadBid(blob_kzg_commitments=blob_kzg_commitments)
    return spec.SignedExecutionPayloadBid(message=bid, signature=spec.BLSSignature())


def build_max_size_data_column_sidecar(spec):
    column = spec.ProgressiveList[spec.Cell]([spec.Cell()] * spec.MAX_BLOB_COMMITMENTS_PER_BLOCK)
    kzg_proofs = spec.ProgressiveList[spec.KZGProof](
        [spec.KZGProof()] * spec.MAX_BLOB_COMMITMENTS_PER_BLOCK
    )
    return spec.DataColumnSidecar(
        index=spec.ColumnIndex(0),
        column=column,
        kzg_proofs=kzg_proofs,
        slot=spec.Slot(0),
        beacon_block_root=spec.Root(),
    )


def build_max_size_partial_data_column_sidecar(spec):
    cells_present_bitmap = spec.ProgressiveBitlist([True] * spec.MAX_BLOB_COMMITMENTS_PER_BLOCK)
    partial_column = spec.ProgressiveList[spec.Cell](
        [spec.Cell()] * spec.MAX_BLOB_COMMITMENTS_PER_BLOCK
    )
    kzg_proofs = spec.ProgressiveList[spec.KZGProof](
        [spec.KZGProof()] * spec.MAX_BLOB_COMMITMENTS_PER_BLOCK
    )
    return spec.PartialDataColumnSidecar(
        cells_present_bitmap=cells_present_bitmap,
        partial_column=partial_column,
        kzg_proofs=kzg_proofs,
    )


def build_max_size_execution_requests(spec):
    return spec.ExecutionRequests(
        deposits=spec.ProgressiveList[spec.DepositRequest](
            [spec.DepositRequest()] * spec.MAX_DEPOSIT_REQUESTS_PER_PAYLOAD
        ),
        withdrawals=spec.ProgressiveList[spec.WithdrawalRequest](
            [spec.WithdrawalRequest()] * spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD
        ),
        consolidations=spec.ProgressiveList[spec.ConsolidationRequest](
            [spec.ConsolidationRequest()] * spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
        ),
    )


def build_max_size_signed_beacon_block(spec):
    body = spec.BeaconBlockBody(
        randao_reveal=spec.BLSSignature(),
        eth1_data=spec.Eth1Data(),
        graffiti=spec.Bytes32(),
        proposer_slashings=spec.ProgressiveList[spec.ProposerSlashing](
            [spec.ProposerSlashing()] * spec.MAX_PROPOSER_SLASHINGS
        ),
        attester_slashings=spec.ProgressiveList[spec.AttesterSlashing](
            [build_max_size_attester_slashing(spec)] * spec.MAX_ATTESTER_SLASHINGS_ELECTRA
        ),
        attestations=spec.ProgressiveList[spec.Attestation](
            [_max_attestation(spec)] * spec.MAX_ATTESTATIONS_ELECTRA
        ),
        deposits=spec.ProgressiveList[spec.Deposit]([spec.Deposit()] * spec.MAX_DEPOSITS),
        voluntary_exits=spec.ProgressiveList[spec.SignedVoluntaryExit](
            [spec.SignedVoluntaryExit()] * spec.MAX_VOLUNTARY_EXITS
        ),
        sync_aggregate=spec.SyncAggregate(),
        bls_to_execution_changes=spec.ProgressiveList[spec.SignedBLSToExecutionChange](
            [spec.SignedBLSToExecutionChange()] * spec.MAX_BLS_TO_EXECUTION_CHANGES
        ),
        signed_execution_payload_bid=build_max_size_signed_execution_payload_bid(spec),
        payload_attestations=spec.ProgressiveList[spec.PayloadAttestation](
            [_max_payload_attestation(spec)] * spec.MAX_PAYLOAD_ATTESTATIONS
        ),
        parent_execution_requests=build_max_size_execution_requests(spec),
    )
    block = spec.BeaconBlock(
        slot=spec.Slot(0),
        proposer_index=spec.ValidatorIndex(0),
        parent_root=spec.Root(),
        state_root=spec.Root(),
        body=body,
    )
    return spec.SignedBeaconBlock(message=block, signature=spec.BLSSignature())


def build_max_size_signed_inclusion_list(spec):
    bytes_per_length_offset = 4
    payload_size = spec.config.MAX_BYTES_PER_INCLUSION_LIST - bytes_per_length_offset
    transactions = spec.ProgressiveList[spec.Transaction](
        [spec.Transaction(b"\x00" * payload_size)]
    )
    inclusion_list = spec.InclusionList(
        slot=spec.Slot(0),
        validator_index=spec.ValidatorIndex(0),
        inclusion_list_committee_root=spec.Root(),
        transactions=transactions,
    )
    return spec.SignedInclusionList(message=inclusion_list, signature=spec.BLSSignature())


def get_max_signed_aggregate_and_proof_size(spec):
    return spec.MAX_SIGNED_AGGREGATE_AND_PROOF_SIZE


def get_max_attester_slashing_size(spec):
    return spec.MAX_ATTESTER_SLASHING_SIZE


def get_max_data_column_sidecar_size(spec):
    return spec.MAX_DATA_COLUMN_SIDECAR_SIZE


def get_max_partial_data_column_sidecar_size(spec):
    return spec.MAX_PARTIAL_DATA_COLUMN_SIDECAR_SIZE


def get_max_signed_execution_payload_bid_size(spec):
    if is_post_heze(spec):
        return spec.MAX_SIGNED_EXECUTION_PAYLOAD_BID_SIZE_HEZE
    return spec.MAX_SIGNED_EXECUTION_PAYLOAD_BID_SIZE


def get_max_signed_beacon_block_size(spec):
    if is_post_heze(spec):
        return spec.MAX_SIGNED_BEACON_BLOCK_SIZE_HEZE
    return spec.MAX_SIGNED_BEACON_BLOCK_SIZE


def get_max_signed_inclusion_list_size(spec):
    return spec.MAX_SIGNED_INCLUSION_LIST_SIZE
