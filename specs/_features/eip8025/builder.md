# EIP-8025 -- Honest Builder

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Constructing the `SignedExecutionPayloadHeaderEnvelope`](#constructing-the-signedexecutionpayloadheaderenvelope)
- [Execution proof signature](#execution-proof-signature)
- [Constructing the `SignedExecutionProof`](#constructing-the-signedexecutionproof)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to the builder guide accompanying EIP-8025.

## Prerequisites

This document is an extension of the
[Gloas -- Honest Builder](../../gloas/builder.md) guide. All behaviors and
definitions defined in this document, and documents it extends, carry over
unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the
[EIP-8025 -- Beacon Chain](./beacon-chain.md) and
[EIP-8025 -- zkEVM](./zkevm.md) documents are requisite for this document.

## Configuration

| Name                                 | Value   |
| ------------------------------------ | ------- |
| `EXECUTION_PROOF_GENERATION_ENABLED` | `False` |

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
`signed_execution_payload_envelope_header` global gossip topic.

## Execution proof signature

```python
def get_execution_proof_signature(
    state: BeaconState, proof: ExecutionProof, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof, domain)
    return bls.Sign(privkey, signing_root)
```

## Constructing the `SignedExecutionProof`

After producing an `ExecutionPayloadEnvelope` the builder constructs a set of
`SignedExecutionProof` as follows:

1. Extract the `NewPayloadRequest` from the envelope.
2. Obtain the `ZKExecutionWitness` from the execution layer.
3. Select a `proof_id` corresponding to the proof system being used.
4. Call
   `generate_execution_proof(new_payload_request, execution_witness, PROGRAM, proof_id)`
   to produce the `ExecutionProof`.
5. Set `signed_proof.message` to the generated `ExecutionProof`.
6. Set `signed_proof.prover_id` to the builder's `BuilderIndex`.
7. Set `signed_proof.signature` to the result of
   `get_execution_proof_signature(state, proof, privkey)`.

Then the builder assembles
`signed_execution_proof = SignedExecutionProof(message=proof, prover_id=builder_index, signature=signature)`
and broadcasts it on the `execution_proof_{subnet_id}` gossip topic, where
`subnet_id = proof.proof_type`.

*Note*: The `proof_id` determines which subnet the proof is broadcast on. Each
proof system has a dedicated subnet to allow validators to subscribe to proofs
from specific proof systems.
