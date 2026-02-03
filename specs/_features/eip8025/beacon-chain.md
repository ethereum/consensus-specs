# EIP-8025 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Types](#types)
- [Constants](#constants)
  - [Execution](#execution)
  - [Domains](#domains)
- [Configuration](#configuration)
- [Containers](#containers)
  - [New `PublicInput`](#new-publicinput)
  - [New `ExecutionProof`](#new-executionproof)
  - [New `SignedExecutionProof`](#new-signedexecutionproof)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Modified `process_block`](#modified-process_block)
    - [Execution payload](#execution-payload)
      - [New `NewPayloadRequestHeader`](#new-newpayloadrequestheader)
      - [Modified `process_execution_payload`](#modified-process_execution_payload)
  - [Execution proof](#execution-proof)
    - [New `process_execution_proof`](#new-process_execution_proof)

<!-- mdformat-toc end -->

## Introduction

These are the beacon-chain specifications to add EIP-8025, enabling stateless
validation of execution payloads through execution proofs.

*Note*: This specification is built upon [Fulu](../../fulu/beacon-chain.md) and
imports proof types from [proof-engine.md](./proof-engine.md).

## Types

| Name        | SSZ equivalent | Description                       |
| ----------- | -------------- | --------------------------------- |
| `ProofType` | `uint8`        | The type identifier for the proof |

## Constants

### Execution

*Note*: The execution values are not definitive.

| Name             | Value               |
| ---------------- | ------------------- |
| `MAX_PROOF_SIZE` | `307200` (= 300KiB) |

### Domains

| Name                     | Value                      |
| ------------------------ | -------------------------- |
| `DOMAIN_EXECUTION_PROOF` | `DomainType('0x0D000000')` |

## Configuration

*Note*: The configuration values are not definitive.

| Name                      | Value         |
| ------------------------- | ------------- |
| `MAX_WHITELISTED_PROVERS` | `uint64(256)` |

## Containers

### New `PublicInput`

```python
class PublicInput(Container):
    new_payload_request_root: Root
```

### New `ExecutionProof`

```python
class ExecutionProof(Container):
    proof_data: ByteList[MAX_PROOF_SIZE]
    proof_type: ProofType
    public_input: PublicInput
```

### New `SignedExecutionProof`

```python
class SignedExecutionProof(Container):
    message: ExecutionProof
    prover_pubkey: BLSPubkey
    signature: BLSSignature
```

## Beacon chain state transition function

### Block processing

#### Modified `process_block`

*Note*: `process_block` is modified in EIP-8025 to pass `PROOF_ENGINE` to
`process_execution_payload`.

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_withdrawals(state, block.body.execution_payload)
    # [Modified in EIP8025]
    process_execution_payload(state, block.body, EXECUTION_ENGINE, PROOF_ENGINE)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### Execution payload

##### New `NewPayloadRequestHeader`

```python
@dataclass
class NewPayloadRequestHeader(object):
    execution_payload_header: ExecutionPayloadHeader
    versioned_hashes: Sequence[VersionedHash]
    parent_beacon_block_root: Root
    execution_requests: ExecutionRequests
```

##### Modified `process_execution_payload`

*Note*: `process_execution_payload` is modified in EIP-8025 to require both
`ExecutionEngine` and `ProofEngine` for validation.

```python
def process_execution_payload(
    state: BeaconState,
    body: BeaconBlockBody,
    execution_engine: ExecutionEngine,
    proof_engine: ProofEngine,
) -> None:
    payload = body.execution_payload

    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_time_at_slot(state, state.slot)
    # Verify commitments are under limit
    assert (
        len(body.blob_kzg_commitments)
        <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
    )

    # Compute list of versioned hashes
    versioned_hashes = [
        kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments
    ]

    # Verify the execution payload is valid via ExecutionEngine
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
            execution_requests=body.execution_requests,
        )
    )

    # [New in EIP8025]
    # Verify via ProofEngine
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
        execution_requests=body.execution_requests,
    )
    assert proof_engine.verify_new_payload_request_header(new_payload_request_header)

    # Cache execution payload header
    state.latest_execution_payload_header = ExecutionPayloadHeader(
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
    )
```

### Execution proof

*Note*: Proof storage is implementation-dependent, managed by the `ProofEngine`.

#### New `process_execution_proof`

```python
def process_execution_proof(
    state: BeaconState,
    signed_proof: SignedExecutionProof,
    proof_engine: ProofEngine,
) -> None:
    proof_message = signed_proof.message
    prover_pubkey = signed_proof.prover_pubkey

    # Verify prover is whitelisted
    validator_pubkeys = [v.pubkey for v in state.validators]
    assert prover_pubkey in validator_pubkeys
    validator_index = ValidatorIndex(validator_pubkeys.index(prover_pubkey))
    assert is_active_validator(state.validators[validator_index], get_current_epoch(state))

    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof_message, domain)
    assert bls.Verify(prover_pubkey, signing_root, signed_proof.signature)

    # Verify the execution proof
    assert proof_engine.verify_execution_proof(proof_message)
```
