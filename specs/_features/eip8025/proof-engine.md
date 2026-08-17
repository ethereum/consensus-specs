# EIP-8025 -- Proof Engine

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Proof interfaces](#proof-interfaces)
  - [Proof verifier](#proof-verifier)
    - [New `verify_execution_proof`](#new-verify_execution_proof)
  - [Proof generator](#proof-generator)
    - [New `request_proof`](#new-request_proof)
  - [Composite proof engine](#composite-proof-engine)

<!-- mdformat-toc end -->

## Introduction

This document contains the host-side Proof Engine specification. The recursive
guest interface and transition logic are defined separately in
[guest-program.md](./guest-program.md).

## Proof interfaces

Proof verification is part of the baseline EIP-8025 profile. Proof generation is
part of the optional `prover` feature, identified by the `eip8025-prover` tag.

### Proof verifier

The implementation-dependent `ProofVerifier` protocol encapsulates recursive
execution-proof verification. It does not receive payload or fork-choice
notifications.

The body of this function is implementation dependent. The Engine API may be
extended to expose an equivalent function when the verifier is an external
process.

#### New `verify_execution_proof`

```python
def verify_execution_proof(
    self: ProofVerifier,
    execution_proof: ExecutionProof,
    chain_config_root: Root,
) -> bool:
    """
    Reconstruct ``GuestPublicInput`` from the gossiped claim and locally trusted
    ``chain_config_root``, then verify the proof against that public input.
    Return ``True`` if the proof is valid.
    """
```

### Proof generator

The implementation-dependent `ProofGenerator` protocol encapsulates asynchronous
proof generation. A prover is responsible for assembling `PrivateInput` and
checking that the target remains canonical before broadcasting a completed
proof.

The body of this function is implementation dependent. The Engine API may be
extended to expose an equivalent function when the generator is an external
process.

#### New `request_proof`

```python
def request_proof(
    self: ProofGenerator,
    private_input: PrivateInput,
    proof_type: ProofType,
    chain_config_root: Root,
) -> Root:
    """
    Request asynchronous proof generation for ``private_input`` using
    ``proof_type`` and local chain configuration. Returns the target beacon block root
    ``private_input.beacon_chain_witness.signed_envelope.message.beacon_block_root``
    to track the generation request.

    Requests are singular because the recursive predecessor in
    ``private_input.beacon_chain_witness.previous_proof`` is specific to
    ``proof_type``.

    The proof engine MUST reject the completed guest output unless its
    ``chain_config_root`` equals ``chain_config_root``.
    """
```

### Composite proof engine

An implementation may expose one object implementing both interfaces. The
executable specification defines `ProofEngine` as the composition of
`ProofVerifier` and `ProofGenerator`. Baseline consumers depend only on
`ProofVerifier`; prover consumers may depend on `ProofGenerator` or the
composite `ProofEngine`.
