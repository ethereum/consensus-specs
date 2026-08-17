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
  - [New `ExecutionCheckpoint`](#new-executioncheckpoint)
  - [New `ExecutionProofClaim`](#new-executionproofclaim)
  - [New `ExecutionProof`](#new-executionproof)
  - [New `SignedExecutionProof`](#new-signedexecutionproof)
- [Execution proof verification](#execution-proof-verification)
  - [Execution proof](#execution-proof)
    - [New `process_execution_proof`](#new-process_execution_proof)

<!-- mdformat-toc end -->

## Introduction

These are the beacon-chain data and verification specifications for EIP-8025,
which defines recursive proofs of execution-payload validity.

An execution proof exposes an immutable origin and a head. Their chain
relationship is established recursively by authenticating the beacon-block
ancestry from the previous head to the new head, the bids at both endpoints, and
the execution head committed by the new head's post-state.

Execution proofs are non-consensus artifacts. Verifying or storing one does not
change beacon-chain state, fork choice, or Gloas payload status. Client policy
for using a stored proof, including whether it can avoid payload retrieval, is
outside this specification.

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
    Identifies the proof format used by an execution proof.
    """
```

## Constants

### Execution

*Note*: The execution values are not definitive.

| Name                    | Value                                                        |
| ----------------------- | ------------------------------------------------------------ |
| `MAX_PROOF_SIZE`        | `Uint64(4194304)` (= 4,096 KiB, 4 MiB)                       |
| `CHAIN_CONFIG_ROOT`     | `Root()`                                                     |
| `SUPPORTED_PROOF_TYPES` | `set[ProofType]([ProofType(1), ProofType(2), ProofType(3)])` |

The initial proof type assignments are provisional. A `ProofType` identifies an
immutable combination of proof system, guest program, and version. Assignments
MUST NOT be reused. A future fork may change `SUPPORTED_PROOF_TYPES`; during a
migration, an active guest may recursively verify proofs produced by a retired
predecessor type.

### Domains

| Name                     | Value                      |
| ------------------------ | -------------------------- |
| `DOMAIN_EXECUTION_PROOF` | `DomainType('0x0F000000')` |

## Containers

### New `ExecutionCheckpoint`

```python
class ExecutionCheckpoint(Container):
    slot: Slot
    beacon_block_root: Root
```

### New `ExecutionProofClaim`

```python
class ExecutionProofClaim(ProgressiveContainer(active_fields=[1] * 2)):
    origin: ExecutionCheckpoint
    head: ExecutionCheckpoint
```

`origin` identifies the full beacon block where the recursive proof chain began.
It is authenticated by the proof engine and preserved unchanged by every
recursive step. `head` identifies the target full beacon block proven from that
origin.

### New `ExecutionProof`

```python
class ExecutionProof(ProgressiveContainer(active_fields=[1] * 3)):
    proof_data: ProofData
    proof_type: ProofType
    claim: ExecutionProofClaim
```

### New `SignedExecutionProof`

```python
class SignedExecutionProof(Container):
    message: ExecutionProof
    validator_index: ValidatorIndex
    signature: BLSSignature
```

## Execution proof verification

### Execution proof

This helper validates a proof for storage by the `on_execution_proof` handler.
It is not invoked by the beacon state transition function. Any
proof-engine-native artifacts remain implementation-dependent.

#### New `process_execution_proof`

```python
def process_execution_proof(
    state: BeaconState,
    signed_proof: SignedExecutionProof,
    proof_engine: ProofEngine,
) -> None:
    proof_message = signed_proof.message
    assert signed_proof.validator_index < len(state.validators)
    assert len(proof_message.proof_data) > 0
    assert len(proof_message.proof_data) <= MAX_PROOF_SIZE
    assert proof_message.proof_type in SUPPORTED_PROOF_TYPES

    # Verify prover is an active validator
    validator = state.validators[signed_proof.validator_index]
    assert is_active_validator(validator, get_current_epoch(state))

    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof_message, domain)
    assert bls.Verify(validator.pubkey, signing_root, signed_proof.signature)

    # Verify the execution proof
    assert proof_engine.verify_execution_proof(proof_message, CHAIN_CONFIG_ROOT)
```
