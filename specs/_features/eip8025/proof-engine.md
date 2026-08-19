# EIP-8025 -- Proof Engine

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Proof engine](#proof-engine)
  - [New `verify_execution_proof`](#new-verify_execution_proof)
  - [New `request_proof`](#new-request_proof)
  - [New `get_proof`](#new-get_proof)

<!-- mdformat-toc end -->

## Introduction

This document contains the host-side Proof Engine specification. The recursive
guest interface and transition logic are defined separately in
[guest-program.md](./guest-program.md).

## Proof engine

The implementation-dependent `ProofEngine` protocol encapsulates proof
verification and asynchronous proof generation via:

- a verification function `self.verify_execution_proof` to verify recursive
  execution proofs; and
- a generation function `self.request_proof` to generate a proof from a
  `PrivateInput` containing the beacon-chain and execution witness material for
  one `ProofType`; and
- a retrieval function `self.get_proof` to wait for and return a generated
  proof.

Proof verification is part of the baseline EIP-8025 profile. Proof generation is
part of the optional `prover` feature, identified by the `eip8025-prover` tag.
Implementations that do not support this feature may reject generation requests.

### New `verify_execution_proof`

```python
def verify_execution_proof(
    self: ProofEngine,
    execution_proof: ExecutionProof,
    chain_config_root: Root,
) -> bool:
    """
    Verify ``execution_proof`` against the locally trusted
    ``chain_config_root``. Return ``True`` if the proof is valid.
    """
```

### New `request_proof`

```python
def request_proof(
    self: ProofEngine,
    private_input: PrivateInput,
    proof_type: ProofType,
) -> Root:
    """
    Request asynchronous proof generation for ``private_input`` using
    ``proof_type`` and local chain configuration. Return the target beacon block
    root from ``private_input`` to track the generation request.

    Requests are singular because the recursive predecessor in
    ``private_input.beacon_chain_witness.previous_proof`` is specific to
    ``proof_type``.
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
