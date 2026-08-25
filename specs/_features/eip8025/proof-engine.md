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

> **EIP-8025 feature:** `prover` (`eip8025-prover`). This feature is optional;
> proof verification remains part of the baseline profile.

The implementation-dependent `ProofEngine` protocol encapsulates proof
verification and asynchronous proof generation via:

- a verification function `self.verify_execution_proof` to verify individual
  proofs;
- a generation function `self.request_proofs` to initiate proof generation for
  one or more requested proof types; and
- a retrieval function `self.get_proof` to wait for and return a generated
  proof.

Implementations that do not support the `prover` feature may reject generation
and retrieval requests.

### New `verify_execution_proof`

```python
def verify_execution_proof(
    self: ProofEngine,
    execution_proof: ExecutionProof,
) -> bool:
    """
    Verify an execution proof.
    Return ``True`` if proof is valid.

    Internally resolve the beacon block and verified execution payload envelope
    identified by ``execution_proof.public_input.beacon_block_root``. Construct
    the corresponding ``NewPayloadRequest`` and use its root as the proof-system
    public input.
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
def request_proofs(
    self: ProofEngine,
    beacon_block_root: Root,
    proof_attributes: ProofAttributes,
) -> Root:
    """
    Request asynchronous proof generation for ``beacon_block_root`` using
    ``proof_attributes``. Return ``beacon_block_root`` to track the generation
    request.
    """
```

### New `get_proof`

```python
def get_proof(
    self: ProofEngine,
    beacon_block_root: Root,
    proof_type: ProofType,
) -> ExecutionProof:
    """
    Wait for the generation request identified by ``beacon_block_root`` and
    ``proof_type`` to complete, then return its proof.

    If generation fails or is abandoned, this function MUST NOT return an
    ``ExecutionProof``.
    """
```
