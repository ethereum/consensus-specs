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
- [Containers](#containers)
  - [New `PublicInput`](#new-publicinput)
  - [New `ExecutionProof`](#new-executionproof)
  - [New `SignedExecutionProof`](#new-signedexecutionproof)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution proof](#execution-proof)
    - [New `process_execution_proof`](#new-process_execution_proof)

<!-- mdformat-toc end -->

## Introduction

These are the beacon-chain specifications to add EIP-8025, enabling stateless
validation of execution payloads through execution proofs.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md)
and imports proof types from [proof-engine.md](./proof-engine.md).

## Types

| Name        | SSZ equivalent | Description                       |
| ----------- | -------------- | --------------------------------- |
| `ProofType` | `uint8`        | The type identifier for the proof |

## Constants

### Execution

*Note*: The execution values are not definitive.

| Name             | Value                |
| ---------------- | -------------------- |
| `MAX_PROOF_SIZE` | `409600` (= 400 KiB) |

### Domains

| Name                     | Value                      |
| ------------------------ | -------------------------- |
| `DOMAIN_EXECUTION_PROOF` | `DomainType('0x0E000000')` |

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
    validator_index: ValidatorIndex
    signature: BLSSignature
```

## Beacon chain state transition function

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

    # Verify prover is an active validator
    validator = state.validators[signed_proof.validator_index]
    assert is_active_validator(validator, get_current_epoch(state))

    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof_message, domain)
    assert bls.Verify(validator.pubkey, signing_root, signed_proof.signature)

    # Verify the execution proof
    assert proof_engine.verify_execution_proof(proof_message)
```
