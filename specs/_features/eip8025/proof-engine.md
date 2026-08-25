# EIP-8025 -- Proof Engine

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Proof engine](#proof-engine)
  - [New `verify_execution_proof`](#new-verify_execution_proof)
  - [New `ProofAttributes`](#new-proofattributes)
  - [New `request_proofs`](#new-request_proofs)
  - [New `get_proof`](#new-get_proof)

<!-- mdformat-toc end -->

## Introduction

This document contains the Proof Engine specification. The Proof Engine enables
stateless validation of execution payloads through execution proofs.

## Proof engine

Proof generation and retrieval are only required for the prover role. Proof
verification remains part of the baseline EIP-8025 specification.

The implementation-dependent `ProofEngine` protocol encapsulates proof
verification and asynchronous proof generation via:

- a verification function `self.verify_execution_proof` to verify individual
  proofs;
- a generation function `self.request_proofs` to initiate proof generation for
  one or more requested proof types; and
- a retrieval function `self.get_proof` to wait for and return a generated
  proof.

Implementations that do not support proof generation may reject generation and
retrieval requests.

### New `verify_execution_proof`

```python
def verify_execution_proof(
    self: ProofEngine,
    execution_proof: ExecutionProof,
) -> bool:
    """
    Verify an execution proof.
    Return ``True`` if the proof is valid.

    Use ``execution_proof.public_input.new_payload_request_root`` as the
    proof-system public input.
    """
```

### New `ProofAttributes`

```python
@dataclass
class ProofAttributes:
    proof_types: Sequence[ProofType]
```

### New `request_proofs`

```python
# Only required for clients performing the prover role
def request_proofs(
    self: ProofEngine,
    new_payload_request: NewPayloadRequest,
    proof_attributes: ProofAttributes,
) -> None:
    """
    Request asynchronous proof generation for ``new_payload_request`` using
    ``proof_attributes``.

    Internally associate generated proofs with
    ``hash_tree_root(new_payload_request)``.
    """
```

### New `get_proof`

```python
# Only required for clients performing the prover role
def get_proof(
    self: ProofEngine,
    new_payload_request_root: Root,
    proof_type: ProofType,
) -> ProofData:
    """
    Wait for the generation request identified by ``new_payload_request_root``
    and ``proof_type`` to complete, then return its proof data.

    If generation fails or is abandoned, this function MUST NOT return a
    ``ProofData``.
    """
```
