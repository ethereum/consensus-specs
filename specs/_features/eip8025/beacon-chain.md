# EIP-8025 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Types](#types)
  - [New `ProofData`](#new-proofdata)
  - [New `ProofType`](#new-prooftype)
- [Constants](#constants)
  - [Execution](#execution)
  - [Domains](#domains)
- [Containers](#containers)
  - [Modified `NewPayloadRequest`](#modified-newpayloadrequest)
  - [New `PublicInput`](#new-publicinput)
  - [New `ExecutionProof`](#new-executionproof)
  - [New `ExecutionProofEnvelope`](#new-executionproofenvelope)
  - [New `SignedExecutionProofEnvelope`](#new-signedexecutionproofenvelope)
- [Execution proof verification](#execution-proof-verification)
  - [New `validate_execution_proof_envelope`](#new-validate_execution_proof_envelope)
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
class ProofData(ProgressiveByteList):
    """
    The opaque proof bytes of an execution proof.
    """
```

### New `ProofType`

```python
class ProofType(Uint8):
    """
    The identifier of the proof system, guest program, and version associated
    with an execution proof.
    """
```

## Constants

### Execution

*Note*: The execution values are not definitive.

| Name                    | Value                                                        |
| ----------------------- | ------------------------------------------------------------ |
| `MAX_PROOF_SIZE`        | `Uint64(4194304)` (= 4,096 KiB, 4 MiB)                       |
| `SUPPORTED_PROOF_TYPES` | `set[ProofType]([ProofType(1), ProofType(2), ProofType(3)])` |

The initial proof type assignments are provisional. A `ProofType` identifies an
immutable combination of proof system, guest program, and version. Assignments
MUST NOT be reused. A future fork may change `SUPPORTED_PROOF_TYPES`.

### Domains

| Name                     | Value                      |
| ------------------------ | -------------------------- |
| `DOMAIN_EXECUTION_PROOF` | `DomainType('0x0F000000')` |

## Containers

### Modified `NewPayloadRequest`

```python
class NewPayloadRequest(ProgressiveContainer(active_fields=[1] * 4)):
    execution_payload: ExecutionPayload
    versioned_hashes: List[VersionedHash, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    parent_beacon_block_root: Root
    execution_requests: ExecutionRequests
```

### New `PublicInput`

```python
class PublicInput(ProgressiveContainer(active_fields=[1])):
    new_payload_request_root: Root
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

## Execution proof verification

### New `validate_execution_proof_envelope`

```python
def validate_execution_proof_envelope(
    state: BeaconState,
    signed_proof_envelope: SignedExecutionProofEnvelope,
    payload_envelope: ExecutionPayloadEnvelope,
) -> ExecutionProof:
    """Authenticate the envelope and construct the ``ExecutionProof``."""
    proof_envelope = signed_proof_envelope.message
    assert proof_envelope.beacon_block_root == payload_envelope.beacon_block_root
    assert signed_proof_envelope.validator_index < len(state.validators)
    assert len(proof_envelope.proof_data) > 0
    assert len(proof_envelope.proof_data) <= MAX_PROOF_SIZE
    assert proof_envelope.proof_type in SUPPORTED_PROOF_TYPES

    # Verify the prover is an active validator
    validator = state.validators[signed_proof_envelope.validator_index]
    assert is_active_validator(validator, get_current_epoch(state))

    # Verify the prover signature
    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof_envelope, domain)
    assert bls.Verify(validator.pubkey, signing_root, signed_proof_envelope.signature)

    # Construct the proof-system public input from the accepted execution payload
    bid = state.latest_execution_payload_bid
    new_payload_request = NewPayloadRequest(
        execution_payload=payload_envelope.payload,
        versioned_hashes=[
            kzg_commitment_to_versioned_hash(commitment) for commitment in bid.blob_kzg_commitments
        ],
        parent_beacon_block_root=payload_envelope.parent_beacon_block_root,
        execution_requests=payload_envelope.execution_requests,
    )
    public_input = PublicInput(new_payload_request_root=hash_tree_root(new_payload_request))
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
    """Authenticate and verify an execution proof envelope."""
    # Verify the execution proof
    proof = validate_execution_proof_envelope(
        state,
        signed_proof_envelope,
        payload_envelope,
    )
    assert proof_engine.verify_execution_proof(proof)
```
