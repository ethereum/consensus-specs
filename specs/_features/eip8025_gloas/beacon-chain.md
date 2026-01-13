# EIP-8025 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`SignedExecutionProof`](#signedexecutionproof)
    - [`ExecutionPayloadHeaderEnvelope`](#executionpayloadheaderenvelope)
    - [`SignedExecutionPayloadHeaderEnvelope`](#signedexecutionpayloadheaderenvelope)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution payload processing](#execution-payload-processing)
    - [Modified `process_execution_payload`](#modified-process_execution_payload)
    - [New `verify_execution_payload_header_envelope_signature`](#new-verify_execution_payload_header_envelope_signature)
    - [New `process_execution_payload_header`](#new-process_execution_payload_header)
  - [Execution proof handlers](#execution-proof-handlers)
    - [New `process_signed_execution_proof`](#new-process_signed_execution_proof)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus specs for EIP-8025, enabling stateless
validation of execution payloads through execution proofs.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md)
and imports proof types from
[eip8025/proof-engine.md](../eip8025/proof-engine.md).

## Containers

### New containers

#### `SignedExecutionProof`

```python
class SignedExecutionProof(Container):
    message: ExecutionProof
    builder_index: BuilderIndex
    signature: BLSSignature
```

#### `ExecutionPayloadHeaderEnvelope`

```python
class ExecutionPayloadHeaderEnvelope(Container):
    payload: ExecutionPayloadHeader
    execution_requests: ExecutionRequests
    builder_index: BuilderIndex
    beacon_block_root: Root
    slot: Slot
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    state_root: Root
```

#### `SignedExecutionPayloadHeaderEnvelope`

```python
class SignedExecutionPayloadHeaderEnvelope(Container):
    message: ExecutionPayloadHeaderEnvelope
    signature: BLSSignature
```

## Beacon chain state transition function

### Execution payload processing

#### Modified `process_execution_payload`

*Note*: `process_execution_payload` is modified in EIP-8025 to require both
`ExecutionEngine` and `ProofEngine` for validation.

```python
def process_execution_payload(
    state: BeaconState,
    signed_envelope: SignedExecutionPayloadEnvelope,
    execution_engine: ExecutionEngine,
    proof_engine: ProofEngine,
    verify: bool = True,
) -> None:
    envelope = signed_envelope.message
    payload = envelope.payload

    # Verify signature
    if verify:
        assert verify_execution_payload_envelope_signature(state, signed_envelope)

    # Cache latest block header state root
    previous_state_root = hash_tree_root(state)
    if state.latest_block_header.state_root == Root():
        state.latest_block_header.state_root = previous_state_root

    # Verify consistency with the beacon block
    assert envelope.beacon_block_root == hash_tree_root(state.latest_block_header)
    assert envelope.slot == state.slot

    # Verify consistency with the committed bid
    committed_bid = state.latest_execution_payload_bid
    assert envelope.builder_index == committed_bid.builder_index
    assert committed_bid.blob_kzg_commitments_root == hash_tree_root(envelope.blob_kzg_commitments)
    assert committed_bid.prev_randao == payload.prev_randao

    # Verify consistency with expected withdrawals
    assert hash_tree_root(payload.withdrawals) == hash_tree_root(state.payload_expected_withdrawals)

    # Verify the gas_limit
    assert committed_bid.gas_limit == payload.gas_limit
    # Verify the block hash
    assert committed_bid.block_hash == payload.block_hash
    # Verify consistency of the parent hash with respect to the previous execution payload
    assert payload.parent_hash == state.latest_block_hash
    # Verify timestamp
    assert payload.timestamp == compute_time_at_slot(state, state.slot)
    # Verify commitments are under limit
    assert (
        len(envelope.blob_kzg_commitments)
        <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
    )
    # Verify the execution payload is valid via ExecutionEngine
    versioned_hashes = [
        kzg_commitment_to_versioned_hash(commitment) for commitment in envelope.blob_kzg_commitments
    ]
    requests = envelope.execution_requests
    new_payload_request = NewPayloadRequest(
        execution_payload=payload,
        versioned_hashes=versioned_hashes,
        parent_beacon_block_root=state.latest_block_header.parent_root,
        execution_requests=requests,
    )
    assert execution_engine.verify_and_notify_new_payload(new_payload_request)

    # [New in EIP-8025] Verify via ProofEngine
    new_payload_request_header = NewPayloadRequestHeader(
        execution_payload_header=ExecutionPayloadHeader(
            parent_hash=payload.parent_hash,
            fee_recipient=payload.fee_recipient,
            state_root=payload.state_root,
            receipts_root=payload.receipts_root,
            logs_bloom=payload.logs_bloom,
            prev_randao=payload.prev_randao,
            block_number=payload.block_number,
            gas_limit=payload.gas_limit,
            gas_used=payload.gas_used,
            timestamp=payload.timestamp,
            extra_data=payload.extra_data,
            base_fee_per_gas=payload.base_fee_per_gas,
            block_hash=payload.block_hash,
            transactions_root=hash_tree_root(payload.transactions),
            withdrawals_root=hash_tree_root(payload.withdrawals),
            blob_gas_used=payload.blob_gas_used,
            excess_blob_gas=payload.excess_blob_gas,
        ),
        versioned_hashes=versioned_hashes,
        parent_beacon_block_root=state.latest_block_header.parent_root,
        execution_requests=requests,
    )
    assert proof_engine.verify_new_payload_request_header(new_payload_request_header)

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(requests.deposits, process_deposit_request)
    for_ops(requests.withdrawals, process_withdrawal_request)
    for_ops(requests.consolidations, process_consolidation_request)

    # Queue the builder payment
    payment = state.builder_pending_payments[SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH]
    amount = payment.withdrawal.amount
    if amount > 0:
        state.builder_pending_withdrawals.append(payment.withdrawal)
    state.builder_pending_payments[SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH] = (
        BuilderPendingPayment()
    )

    # Cache the execution payload hash
    state.execution_payload_availability[state.slot % SLOTS_PER_HISTORICAL_ROOT] = 0b1
    state.latest_block_hash = payload.block_hash

    # Verify the state root
    if verify:
        assert envelope.state_root == hash_tree_root(state)
```

#### New `verify_execution_payload_header_envelope_signature`

```python
def verify_execution_payload_header_envelope_signature(
    state: BeaconState, signed_envelope: SignedExecutionPayloadHeaderEnvelope
) -> bool:
    builder_index = signed_envelope.message.builder_index
    if builder_index == BUILDER_INDEX_SELF_BUILD:
        validator_index = state.latest_block_header.proposer_index
        pubkey = state.validators[validator_index].pubkey
    else:
        pubkey = state.builders[builder_index].pubkey

    signing_root = compute_signing_root(
        signed_envelope.message, get_domain(state, DOMAIN_BEACON_BUILDER)
    )
    return bls.Verify(pubkey, signing_root, signed_envelope.signature)
```

#### New `process_execution_payload_header`

*Note*: `process_execution_payload_header` is the stateless equivalent of
`process_execution_payload`. It processes execution payload headers using
execution proofs for validation instead of the `ExecutionEngine`.

```python
def process_execution_payload_header(
    state: BeaconState,
    signed_envelope: SignedExecutionPayloadHeaderEnvelope,
    proof_engine: ProofEngine,
    verify: bool = True,
) -> None:
    envelope = signed_envelope.message
    payload = envelope.payload

    # Verify signature
    if verify:
        assert verify_execution_payload_header_envelope_signature(state, signed_envelope)

    # Cache latest block header state root
    previous_state_root = hash_tree_root(state)
    if state.latest_block_header.state_root == Root():
        state.latest_block_header.state_root = previous_state_root

    # Verify consistency with the beacon block
    assert envelope.beacon_block_root == hash_tree_root(state.latest_block_header)
    assert envelope.slot == state.slot

    # Verify consistency with the committed bid
    committed_bid = state.latest_execution_payload_bid
    assert envelope.builder_index == committed_bid.builder_index
    assert committed_bid.blob_kzg_commitments_root == hash_tree_root(envelope.blob_kzg_commitments)
    assert committed_bid.prev_randao == payload.prev_randao

    # Verify consistency with expected withdrawals
    assert payload.withdrawals_root == hash_tree_root(state.payload_expected_withdrawals)

    # Verify the gas_limit
    assert committed_bid.gas_limit == payload.gas_limit
    # Verify the block hash
    assert committed_bid.block_hash == payload.block_hash
    # Verify consistency of the parent hash with respect to the previous execution payload
    assert payload.parent_hash == state.latest_block_hash
    # Verify timestamp
    assert payload.timestamp == compute_time_at_slot(state, state.slot)
    # Verify commitments are under limit
    assert (
        len(envelope.blob_kzg_commitments)
        <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
    )

    # [New in EIP-8025] Verify the execution payload request header using execution proofs
    versioned_hashes = [
        kzg_commitment_to_versioned_hash(commitment) for commitment in envelope.blob_kzg_commitments
    ]
    requests = envelope.execution_requests
    new_payload_request_header = NewPayloadRequestHeader(
        execution_payload_header=payload,
        versioned_hashes=versioned_hashes,
        parent_beacon_block_root=state.latest_block_header.parent_root,
        execution_requests=requests,
    )

    # Verify sufficient proofs exist via ProofEngine
    assert proof_engine.verify_new_payload_request_header(new_payload_request_header)

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(requests.deposits, process_deposit_request)
    for_ops(requests.withdrawals, process_withdrawal_request)
    for_ops(requests.consolidations, process_consolidation_request)

    # Queue the builder payment
    payment = state.builder_pending_payments[SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH]
    amount = payment.withdrawal.amount
    if amount > 0:
        state.builder_pending_withdrawals.append(payment.withdrawal)
    state.builder_pending_payments[SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH] = (
        BuilderPendingPayment()
    )

    # Cache the execution payload hash
    state.execution_payload_availability[state.slot % SLOTS_PER_HISTORICAL_ROOT] = 0b1
    state.latest_block_hash = payload.block_hash

    # Verify the state root
    if verify:
        assert envelope.state_root == hash_tree_root(state)
```

### Execution proof handlers

*Note*: Proof storage is implementation-dependent, managed by the `ProofEngine`.

#### New `process_signed_execution_proof`

```python
def process_signed_execution_proof(
    state: BeaconState,
    signed_proof: SignedExecutionProof,
    proof_engine: ProofEngine,
) -> None:
    """
    Handler for SignedExecutionProof.
    """
    proof_message = signed_proof.message
    builder_index = signed_proof.builder_index

    # Determine pubkey based on builder_index
    if builder_index == BUILDER_INDEX_SELF_BUILD:
        validator_index = state.latest_block_header.proposer_index
        pubkey = state.validators[validator_index].pubkey
    else:
        pubkey = state.builders[builder_index].pubkey

    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof_message, domain)
    assert bls.Verify(pubkey, signing_root, signed_proof.signature)

    # Verify the execution proof
    assert proof_engine.verify_execution_proof(proof_message)
```
