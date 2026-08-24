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
  - [New `PublicInput`](#new-publicinput)
  - [New `ExecutionProof`](#new-executionproof)
  - [New `SignedExecutionProof`](#new-signedexecutionproof)

<!-- mdformat-toc end -->

## Introduction

These are the beacon-chain specifications to add EIP-8025, enabling stateless
validation of execution payloads through execution proofs.

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

### New `PublicInput`

```python
class PublicInput(ProgressiveContainer(active_fields=[1])):
    beacon_block_root: Root
```

### New `ExecutionProof`

```python
class ExecutionProof(Container):
    proof_data: ProofData
    proof_type: ProofType
    public_input: PublicInput
```

### New `SignedExecutionProof`

```python
class SignedExecutionProof(Container):
    message: ExecutionProof
    validator_index: ValidatorIndex
    signature: BLSSignature
```
