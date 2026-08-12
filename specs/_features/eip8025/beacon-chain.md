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
  - [New `GuestPublicInput`](#new-guestpublicinput)
  - [New `ExecutionProof`](#new-executionproof)
  - [New `SignedExecutionProof`](#new-signedexecutionproof)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution proof](#execution-proof)
    - [New `process_execution_proof`](#new-process_execution_proof)

<!-- mdformat-toc end -->

## Introduction

These are the beacon-chain specifications to add EIP-8025, enabling stateless
validation of execution payloads through recursive execution proofs.

An execution proof exposes an immutable origin and a head. Their chain
relationship is established recursively by authenticating the beacon-block
ancestry from the previous head to the new head and the signed execution payload
bid committed by each block in that lineage.

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
    The globally allocated identifier of an exact proof-system and guest-program
    version pair.
    """
```

`ProofType(0)` is reserved and MUST NOT identify a production proof system.
Changing the guest predicate or any progressive SSZ schema committed by the
guest requires a new `ProofType` allocation.

## Constants

### Execution

*Note*: The execution values are not definitive.

| Name             | Value                                  |
| ---------------- | -------------------------------------- |
| `MAX_PROOF_SIZE` | `Uint64(4194304)` (= 4,096 KiB, 4 MiB) |

| Name                  | Value          |
| --------------------- | -------------- |
| `PROOF_TYPE_RESERVED` | `ProofType(0)` |

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

`origin` is the configured trusted execution checkpoint, typically selected from
the client's weak subjectivity checkpoint. It is preserved unchanged by every
recursive step. `head` identifies the target full beacon block proven from that
origin.

### New `GuestPublicInput`

```python
class GuestPublicInput(ProgressiveContainer(active_fields=[1] * 3)):
    origin: ExecutionCheckpoint
    head: ExecutionCheckpoint
    chain_config_root: Root
```

`GuestPublicInput` is the complete public input committed by the guest program.
The locally trusted `chain_config_root` is injected at the proof-engine API
boundary and is not transmitted in execution-proof gossip.

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

## Beacon chain state transition function

### Execution proof

Verified execution proofs are recorded by the fork-choice `on_execution_proof`
handler. Any proof-engine-native artifacts remain implementation-dependent.

#### New `process_execution_proof`

```python
def process_execution_proof(
    state: BeaconState,
    signed_proof: SignedExecutionProof,
    proof_engine: ProofEngine,
    trusted_chain_config_root: Root,
) -> None:
    proof_message = signed_proof.message
    assert signed_proof.validator_index < len(state.validators)
    assert len(proof_message.proof_data) > 0
    assert len(proof_message.proof_data) <= MAX_PROOF_SIZE
    assert proof_engine.is_supported_proof_type(proof_message.proof_type)

    # Verify prover is an active validator
    validator = state.validators[signed_proof.validator_index]
    assert is_active_validator(validator, get_current_epoch(state))

    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof_message, domain)
    assert bls.Verify(validator.pubkey, signing_root, signed_proof.signature)

    # Verify the execution proof
    assert proof_engine.verify_execution_proof(proof_message, trusted_chain_config_root)
```
