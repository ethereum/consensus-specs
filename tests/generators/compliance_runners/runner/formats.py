"""State-transition operation filenames and SSZ types."""

OPERATION_INPUTS = {
    "attestation": ("attestation", "Attestation"),
    "block_header": ("block_header", "BeaconBlock"),
    "builder_deposit_request": ("builder_deposit_request", "BuilderDepositRequest"),
    "builder_exit_request": ("builder_exit_request", "BuilderExitRequest"),
    "consolidation_request": ("consolidation_request", "ConsolidationRequest"),
    "deposit_request": ("deposit_request", "DepositRequest"),
    "execution_payload_bid": ("execution_payload_bid", "SignedExecutionPayloadBid"),
    "parent_execution_payload": ("block", "BeaconBlock"),
    "payload_attestation": ("payload_attestation", "PayloadAttestation"),
    "proposer_slashing": ("proposer_slashing", "ProposerSlashing"),
    "attester_slashing": ("attester_slashing", "AttesterSlashing"),
    "deposit": ("deposit", "Deposit"),
    "bls_to_execution_change": ("address_change", "SignedBLSToExecutionChange"),
    "voluntary_exit": ("voluntary_exit", "SignedVoluntaryExit"),
    "withdrawal_request": ("withdrawal_request", "WithdrawalRequest"),
    "sync_aggregate": ("sync_aggregate", "SyncAggregate"),
}
