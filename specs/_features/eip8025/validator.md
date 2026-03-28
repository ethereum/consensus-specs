# EIP-8025 -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Proof re-signing](#proof-re-signing)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement EIP-8025.

## Prerequisites

This document is an extension of the
[Fulu -- Honest Validator](../../fulu/validator.md) guide. All behaviors and
definitions defined in this document, and documents it extends, carry over
unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in
[EIP-8025 -- The Beacon Chain](./beacon-chain.md),
[EIP-8025 -- Proof Engine](./proof-engine.md), and
[EIP-8025 -- Honest Prover](./prover.md) are requisite for this document and
used throughout.

## Beacon chain responsibilities

### Proof re-signing

*[New in EIP8025]*

Upon receiving a valid `SignedExecutionProof` on the `execution_proof` gossip
topic, an honest validator MAY re-sign and re-broadcast it to ensure proof
availability for peers that may have discarded proofs from the original signer
due to a prior invalid submission.

*Note*: Gossip validation of `execution_proof` already calls
`proof_engine.verify_execution_proof` via `process_execution_proof`, so a proof
reaching this point has already been verified by the local node.

1. Let `validator_index` be the validator index of the re-signing validator.
2. Let `signature = get_execution_proof_signature(state, proof.message, privkey)`.
3. Let `resigned_proof = SignedExecutionProof(message=proof.message, validator_index=validator_index, signature=signature)`.
4. Broadcast `resigned_proof` on the `execution_proof` gossip topic.
