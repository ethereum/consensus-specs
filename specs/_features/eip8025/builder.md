# EIP-8025 -- Honest Builder

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Constructing the `SignedExecutionPayloadHeaderEnvelope`](#constructing-the-signedexecutionpayloadheaderenvelope)
- [Execution proof signature](#execution-proof-signature)
- [Constructing the `BuilderSignedExecutionProof`](#constructing-the-buildersignedexecutionproof)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to the builder guide accompanying EIP-8025.

## Prerequisites

This document is an extension of the
[Gloas -- Honest Builder](../../gloas/builder.md) guide. All behaviors and
definitions defined in this document, and documents it extends, carry over
unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the
[EIP-8025 -- Beacon Chain](./beacon-chain.md) document are requisite for this
document.

## Constructing the `SignedExecutionPayloadHeaderEnvelope`

Builders MUST broadcast `SignedExecutionPayloadHeaderEnvelope` messages to allow
ZK attesters to perform proof verification.

To construct the `SignedExecutionPayloadHeaderEnvelope` from an existing
`SignedExecutionPayloadEnvelope`:

1. Set `header_envelope.payload` to the `ExecutionPayloadHeader` derived from
   `envelope.payload`.
2. Copy all other fields from the original envelope:
   - `header_envelope.execution_requests = envelope.execution_requests`
   - `header_envelope.builder_index = envelope.builder_index`
   - `header_envelope.beacon_block_root = envelope.beacon_block_root`
   - `header_envelope.slot = envelope.slot`
   - `header_envelope.blob_kzg_commitments = envelope.blob_kzg_commitments`
   - `header_envelope.state_root = envelope.state_root`
3. Set `signed_header_envelope.message = header_envelope`.
4. Set `signed_header_envelope.signature = signed_envelope.signature`.

Then the builder broadcasts `signed_header_envelope` on the
`signed_execution_payload_header_envelope` global gossip topic.

## Execution proof signature

```python
def get_execution_proof_signature(
    state: BeaconState, proof: ExecutionProof, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof, domain)
    return bls.Sign(privkey, signing_root)
```

## Constructing the `BuilderSignedExecutionProof`

After producing an `ExecutionPayloadEnvelope` the builder constructs a set of
`BuilderSignedExecutionProof` as follows:

1. Extract the `NewPayloadRequest` from the envelope.
2. Select proof types and create `ProofAttributes`.
3. Call
   `proof_gen_id = proof_engine.request_proofs(new_payload_request, proof_attributes)`
   to initiate proof generation.
4. Call `proofs = proof_engine.get_proofs(proof_gen_id)` to retrieve generated
   proofs.
5. For each `ExecutionProof` in `proofs`:
   - Set `signed_proof.message` to the `ExecutionProof`.
   - Set `signed_proof.builder_index` to the builder's `BuilderIndex`.
   - Set `signed_proof.signature` to the result of
     `get_execution_proof_signature(state, proof, privkey)`.
   - Broadcast the `BuilderSignedExecutionProof` on the `execution_proof` gossip
     topic.
