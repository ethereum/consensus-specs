# EIP-8025 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Types](#types)
  - [New `ProofData`](#new-proofdata)
  - [New `ProofType`](#new-prooftype)
  - [New `VersionedHashes`](#new-versionedhashes)
- [Constants](#constants)
  - [Execution](#execution)
  - [Domains](#domains)
- [Containers](#containers)
  - [New `SSZNewPayloadRequest`](#new-ssznewpayloadrequest)
  - [New `PublicInput`](#new-publicinput)
  - [New `ExecutionProof`](#new-executionproof)
  - [New `ExecutionProofEnvelope`](#new-executionproofenvelope)
  - [New `SignedExecutionProofEnvelope`](#new-signedexecutionproofenvelope)
- [Helpers](#helpers)
  - [New `get_supported_proof_types`](#new-get_supported_proof_types)
- [Execution proof verification](#execution-proof-verification)
  - [New `verify_execution_proof_envelope`](#new-verify_execution_proof_envelope)
  - [New `get_execution_proof`](#new-get_execution_proof)
  - [New `process_execution_proof`](#new-process_execution_proof)

<!-- mdformat-toc end -->

## Introduction

These are the beacon-chain specifications that introduce execution proofs which
enable constant time stateless validation of execution payloads.

Execution proofs are non-consensus artifacts. Verifying or storing one does not
change beacon-chain state, fork choice, or Gloas payload status.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md)
and imports proof types from [proof-engine.md](./proof-engine.md).

## Types

### New `ProofData`

```python
class ProofData(ByteList):
    """
    The opaque proof bytes of an execution proof.
    """

    LIMIT = MAX_PROOF_SIZE
```

### New `ProofType`

```python
class ProofType(Uint8):
    """
    The identifier of the proof system, guest program, and version associated
    with an execution proof.
    """
```

### New `VersionedHashes`

```python
class VersionedHashes(List[VersionedHash]):
    """
    The versioned hashes for blobs associated with an execution payload.
    """

    LIMIT = MAX_BLOB_COMMITMENTS_PER_BLOCK
```

## Constants

### Execution

*Note*: The execution values are not definitive.

| Name                        | Value                                  |
| --------------------------- | -------------------------------------- |
| `MAX_PROOF_SIZE`            | `Uint64(4194304)` (= 4,096 KiB, 4 MiB) |
| `STATELESS_INPUT_SCHEMA_ID` | `Uint16(0x1501)`                       |

`STATELESS_INPUT_SCHEMA_ID` encodes the Amsterdam protocol fork (`0x15`) and
schema revision (`0x01`).

### Domains

| Name                     | Value                      |
| ------------------------ | -------------------------- |
| `DOMAIN_EXECUTION_PROOF` | `DomainType('0x0F000000')` |

## Containers

### New `SSZNewPayloadRequest`

```python
class SSZNewPayloadRequest(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=4)

    execution_payload: ExecutionPayload
    versioned_hashes: VersionedHashes
    parent_beacon_block_root: Root
    execution_requests: ExecutionRequests
```

### New `PublicInput`

```python
class PublicInput(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=4)

    new_payload_request_root: Root
    successful_validation: Boolean
    chain_id: Uint64
    schema_id: Uint16
```

### New `ExecutionProof`

```python
class ExecutionProof(Container):
    proof_data: ProofData
    proof_type: ProofType
    public_input: PublicInput
```

### New `ExecutionProofEnvelope`

```python
class ExecutionProofEnvelope(Container):
    proof_data: ProofData
    proof_type: ProofType
    beacon_block_root: Root
```

### New `SignedExecutionProofEnvelope`

```python
class SignedExecutionProofEnvelope(Container):
    message: ExecutionProofEnvelope
    validator_index: ValidatorIndex
    signature: BLSSignature
```

## Helpers

### New `get_supported_proof_types`

*Note*: The initial proof type assignments are provisional. A `ProofType`
identifies an immutable combination of proof system, guest program, and version.
Assignments MUST NOT be reused.

```python
def get_supported_proof_types() -> set[ProofType]:
    """
    Return the supported execution proof types.
    """
    return {
        ProofType(1),
        ProofType(2),
        ProofType(3),
    }
```

## Execution proof verification

### New `verify_execution_proof_envelope`

```python
def verify_execution_proof_envelope(
    state: BeaconState,
    signed_proof_envelope: SignedExecutionProofEnvelope,
) -> None:
    """
    Verify an execution proof envelope against the beacon state.
    The execution proof itself is verified separately by the proof engine.
    """
    proof_envelope = signed_proof_envelope.message
    assert signed_proof_envelope.validator_index < len(state.validators)
    assert len(proof_envelope.proof_data) > 0
    assert proof_envelope.proof_type in get_supported_proof_types()

    # Verify the prover is an active validator
    validator = state.validators[signed_proof_envelope.validator_index]
    assert is_active_validator(validator, get_current_epoch(state))

    # Verify the prover signature
    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof_envelope, domain)
    assert bls.Verify(validator.pubkey, signing_root, signed_proof_envelope.signature)
```

### New `get_execution_proof`

```python
def get_execution_proof(
    state: BeaconState,
    proof_envelope: ExecutionProofEnvelope,
    payload_envelope: ExecutionPayloadEnvelope,
) -> ExecutionProof:
    """
    Construct the ``ExecutionProof`` for submission to the proof engine.
    """
    # Construct the proof-system public input from the accepted execution payload
    bid = state.latest_execution_payload_bid
    new_payload_request = SSZNewPayloadRequest(
        execution_payload=payload_envelope.payload,
        versioned_hashes=VersionedHashes(
            data=[
                kzg_commitment_to_versioned_hash(commitment)
                for commitment in bid.blob_kzg_commitments
            ]
        ),
        parent_beacon_block_root=payload_envelope.parent_beacon_block_root,
        execution_requests=payload_envelope.execution_requests,
    )
    public_input = PublicInput(
        new_payload_request_root=hash_tree_root(new_payload_request),
        successful_validation=Boolean(True),
        chain_id=DEPOSIT_CHAIN_ID,
        schema_id=STATELESS_INPUT_SCHEMA_ID,
    )
    return ExecutionProof(
        proof_data=proof_envelope.proof_data,
        proof_type=proof_envelope.proof_type,
        public_input=public_input,
    )
```

### New `process_execution_proof`

```python
def process_execution_proof(
    state: BeaconState,
    signed_proof_envelope: SignedExecutionProofEnvelope,
    payload_envelope: ExecutionPayloadEnvelope,
    proof_engine: ProofEngine,
) -> None:
    """
    Authenticate and verify an execution proof envelope.
    """
    verify_execution_proof_envelope(
        state,
        signed_proof_envelope,
    )

    proof = get_execution_proof(
        state,
        signed_proof_envelope.message,
        payload_envelope,
    )
    assert proof_engine.verify_execution_proof(proof)
```
