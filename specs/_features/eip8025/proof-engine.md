# EIP-8025 -- Proof Engine

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Proof engine](#proof-engine)
  - [New `verify_execution_proof`](#new-verify_execution_proof)
  - [New `request_proof`](#new-request_proof)

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
  one `ProofType`.

The Proof Engine does not receive payload or fork-choice notifications. The
prover is responsible for assembling `PrivateInput` and for checking that the
target remains canonical before broadcasting a completed proof.

The bodies of these functions are implementation dependent. The Engine API may
be extended to expose equivalent functions when the proof engine is an external
process.

### New `verify_execution_proof`

```python
def verify_execution_proof(
    self: ProofEngine,
    execution_proof: ExecutionProof,
    trusted_chain_config_root: Root,
) -> bool:
    """
    Reconstruct ``GuestPublicInput`` from the gossiped claim and locally trusted
    ``chain_config_root``, then verify the proof against that public input.
    Return ``True`` if the proof is valid.
    """
```

### New `request_proof`

```python
def request_proof(
    self: ProofEngine,
    private_input: PrivateInput,
    proof_type: ProofType,
    trusted_chain_config_root: Root,
) -> Root:
    """
    Request asynchronous proof generation for ``private_input`` using
    ``proof_type`` and locally trusted chain configuration. Returns the target beacon block root
    ``private_input.beacon_chain_witness.signed_envelope.message.beacon_block_root``
    to track the generation request.

    Requests are singular because the recursive predecessor in
    ``private_input.beacon_chain_witness.previous_proof`` is specific to
    ``proof_type``.

    The proof engine MUST reject the completed guest output unless its
    ``chain_config_root`` equals ``trusted_chain_config_root``.
    """
```
