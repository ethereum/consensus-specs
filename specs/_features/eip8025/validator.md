# EIP-8025 -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Attestation execution-validity gating](#attestation-execution-validity-gating)

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

### Attestation execution-validity gating

*[New in EIP8025]*

With `process_execution_payload` no longer gating consensus on execution
validity, an honest validator SHOULD NOT attest to a block whose
`execution_payload` has not been independently validated. Specifically, a
validator SHOULD withhold its attestation for a block until at least one of the
following conditions holds by the attestation deadline:

1. A locally-run `ExecutionEngine` has returned `VALID` for the block's
   corresponding `NewPayloadRequest` (i.e.
   `execution_engine.verify_and_notify_new_payload(new_payload_request)`
   returned `True`).
2. A `SignedExecutionProof` has been received on the `execution_proof` gossip
   topic for the block, and:
   - `proof.public_input.new_payload_request_root` equals
     `hash_tree_root(new_payload_request)` for the block's `NewPayloadRequest`,
     and
   - `proof_engine.verify_execution_proof(proof)` returned `True` (i.e. the
     proof passed `process_execution_proof`).

If neither signal is available by the attestation deadline, the validator SHOULD
withhold its attestation for that block. This restores a defense-in-depth
penalty signal against attesting to blocks with invalid execution payloads after
the removal of the consensus-level assert on the execution engine: validators
that opt out of both running a local execution engine and subscribing to
execution proofs will miss attestations for blocks whose validity they cannot
independently establish, and will therefore incur the standard
missed-attestation penalty.

*Note*: This guidance applies only to validators performing attestation duties.
Follower or non-attesting nodes MAY accept blocks through state-transition
without any execution-validity signal; they do not put network safety at risk by
doing so.

*Note*: Validators running a local execution engine are unaffected in practice —
condition (1) will be satisfied via the existing `verify_and_notify_new_payload`
call in `process_execution_payload`. This rule only changes behavior for
validators that have opted out of running an execution engine.
