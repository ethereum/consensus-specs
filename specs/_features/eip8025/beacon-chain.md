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
  - [Proof types](#proof-types)
  - [Domains](#domains)
- [Containers](#containers)
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
and uses the proof-verification interface from
[proof-engine.md](./proof-engine.md).

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

## Constants

### Execution

*Note*: The execution values are not definitive.

| Name                        | Value                                  |
| --------------------------- | -------------------------------------- |
| `MAX_PROOF_SIZE`            | `Uint64(4194304)` (= 4,096 KiB, 4 MiB) |
| `STATELESS_INPUT_SCHEMA_ID` | `Uint16(0x1501)`                       |

`STATELESS_INPUT_SCHEMA_ID` encodes the Amsterdam protocol fork (`0x15`) and
schema revision (`0x01`).

### Proof types

*Note*: These assignments are provisional. The verification key column is the
SHA-256 digest of the raw verification key.

| Proof type     | Stateless validator                    | Proof system            | Verification key (SHA-256)                                           |
| -------------- | -------------------------------------- | ----------------------- | -------------------------------------------------------------------- |
| `ProofType(1)` | ethrex `26.0.0`                        | OpenVM `v2.1.0-preview` | `0x5de0d2feff592e5957c2dfcb613b649751e623a8b28e68187250eaf000eed8d7` |
| `ProofType(2)` | ethrex `26.0.0`                        | SP1 `v6.4.0`            | `0x5e614b666d4f9a60a68d826833b94e2c5afa029b2dc501a45f3656059811a4d7` |
| `ProofType(3)` | ethrex `26.0.0`                        | ZisK `v1.1.0-alpha`     | `0x7f8d16136f2783e9eaef89365cbc34333d06a73f3b77313a72f94a2054e0347e` |
| `ProofType(4)` | reth `0.1.0-rc.3`                      | OpenVM `v2.1.0-preview` | `0xc118d0744d722cef89896b7bd085bd957686b190f55deaed80147b9abe3dba59` |
| `ProofType(5)` | reth `0.1.0-rc.3`                      | SP1 `v6.4.0`            | `0x420933f79a82fcb40880a97f0efb7780e6f939cbf6a0bbec716de24b8033df28` |
| `ProofType(6)` | reth `0.1.0-rc.3`                      | ZisK `v1.1.0-alpha`     | `0x6806dfc26dfdab7aaa6931d832b78f052e08a151d36353bb8662dc54e6766756` |
| `ProofType(7)` | zesu `tests-glamsterdam-devnet@v8.1.4` | ZisK `v1.1.0-alpha`     | `0xad94ad82ad310fda4ab8e8e91e7b4826edaa20e9c4e76f479ed7ca3482e3755c` |

### Domains

| Name                     | Value                      |
| ------------------------ | -------------------------- |
| `DOMAIN_EXECUTION_PROOF` | `DomainType("0x0F000000")` |

## Containers

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

*Note*: A `ProofType` identifies an immutable combination of proof system, guest
program, and version. Assignments MUST NOT be reused. See
[Proof types](#proof-types) for the current assignments.

```python
def get_supported_proof_types() -> set[ProofType]:
    """
    Return the supported execution proof types.
    """
    return {
        ProofType(1),
        ProofType(2),
        ProofType(3),
        ProofType(4),
        ProofType(5),
        ProofType(6),
        ProofType(7),
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
    assert len(proof_envelope.proof_data) != 0
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
    new_payload_request = NewPayloadRequest(
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
