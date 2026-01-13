# EIP-8025 -- Proof Engine

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Constants](#constants)
  - [Execution](#execution)
  - [Custom types](#custom-types)
  - [Domain types](#domain-types)
- [Configuration](#configuration)
- [Containers](#containers)
  - [`PublicInput`](#publicinput)
  - [`ExecutionProof`](#executionproof)
  - [`ProofAttributes`](#proofattributes)
- [Proof engine](#proof-engine)
  - [`verify_execution_proof`](#verify_execution_proof)
  - [`verify_new_payload_request_header`](#verify_new_payload_request_header)
  - [`request_proofs`](#request_proofs)
  - [`get_proofs`](#get_proofs)

<!-- mdformat-toc end -->

## Introduction

This document contains the Proof Engine specification. The Proof Engine enables
stateless validation of execution payloads through execution proofs.

## Constants

### Execution

| Name                               | Value               |
| ---------------------------------- | ------------------- |
| `MAX_EXECUTION_PROOFS_PER_PAYLOAD` | `uint64(4)`         |
| `MAX_PROOF_SIZE`                   | `307200` (= 300KiB) |

### Custom types

| Name         | SSZ equivalent | Description                              |
| ------------ | -------------- | ---------------------------------------- |
| `ProofGenId` | `Bytes8`       | Identifier for tracking proof generation |
| `ProofType`  | `uint8`        | The type identifier for the proof        |

### Domain types

| Name                     | Value                      |
| ------------------------ | -------------------------- |
| `DOMAIN_EXECUTION_PROOF` | `DomainType('0x0D000000')` |

## Configuration

*Note*: The configuration values are not definitive.

| Name                            | Value         |
| ------------------------------- | ------------- |
| `MIN_REQUIRED_EXECUTION_PROOFS` | `uint64(1)`   |
| `MAX_WHITELISTED_PROVERS`       | `uint64(256)` |

## Containers

### `PublicInput`

```python
class PublicInput(Container):
    new_payload_request_root: Root
```

### `ExecutionProof`

```python
class ExecutionProof(Container):
    proof_data: ByteList[MAX_PROOF_SIZE]
    proof_type: ProofType
    public_input: PublicInput
```

### `ProofAttributes`

```python
@dataclass
class ProofAttributes(object):
    proof_types: List[ProofType]
```

## Proof engine

The implementation-dependent `ProofEngine` protocol encapsulates the proof
sub-system logic via proof verification and generation functions.

The body of these functions are implementation dependent.

### `verify_execution_proof`

```python
def verify_execution_proof(
    self: ProofEngine,
    execution_proof: ExecutionProof,
) -> bool:
    """
    Verify an execution proof.
    Return ``True`` if proof is valid.
    """
    ...
```

### `verify_new_payload_request_header`

```python
def verify_new_payload_request_header(
    self: ProofEngine,
    new_payload_request_header: NewPayloadRequestHeader,
) -> bool:
    """
    Verify the given payload request header.
    Return ``True`` if proof requirements are satisfied.
    """
    ...
```

### `request_proofs`

```python
def request_proofs(
    self: ProofEngine,
    new_payload_request: NewPayloadRequest,
    proof_attributes: ProofAttributes,
) -> ProofGenId:
    """
    Request proof generation for a new payload request with specified proof attributes.
    Returns a ``ProofGenId`` to track the generation request.
    """
    ...
```

### `get_proofs`

```python
def get_proofs(
    self: ProofEngine,
    proof_gen_id: ProofGenId,
) -> List[ExecutionProof]:
    """
    Retrieve all generated proofs for a generation request.
    """
    ...
```
