# EIP-8025 -- Honest Prover

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Execution proof signature](#execution-proof-signature)
- [Constructing the `SignedExecutionProof`](#constructing-the-signedexecutionproof)
- [Honest Prover Relay](#honest-prover-relay)
  - [Accepting proofs](#accepting-proofs)
  - [Signing and broadcasting](#signing-and-broadcasting)

<!-- mdformat-toc end -->

## Introduction

This document represents the prover guide accompanying EIP-8025. Provers are
whitelisted network operators who generate execution proofs during the optional
proof phase.

## Prerequisites

All terminology, constants, functions, and protocol mechanics defined in the
[EIP-8025 -- Beacon Chain](./beacon-chain.md) and
[EIP-8025 -- zkEVM](./zkevm.md) documents are requisite for this document.

The prover MUST have their public key included in `WHITELISTED_PROVERS` or
alternatively use a whitelisted community proof relay.

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

Provers subscribe to the `signed_execution_payload_envelope` gossip topic to
receive execution payloads for which they can generate execution proofs.

To construct a `SignedExecutionProof`:

1. Extract the `NewPayloadRequest` from the `SignedExecutionPayloadEnvelope`.
2. Obtain the `ZKExecutionWitness` from the execution layer.
3. Select a `proof_id` corresponding to the proof system being used.
4. Call
   `generate_execution_proof(new_payload_request, execution_witness, PROGRAM, proof_id)`
   to produce the `ExecutionProof`.
5. Set `signed_proof.message` to the generated `ExecutionProof`.
6. Set `signed_proof.prover_id` to the prover's public key.
7. Set `signed_proof.signature` to the result of
   `get_execution_proof_signature(state, proof, privkey)`.

Then the prover assembles
`signed_execution_proof = SignedExecutionProof(message=proof, prover_id=pubkey, signature=signature)`
and broadcasts it on the `execution_proof_{subnet_id}` gossip topic, where
`subnet_id = proof.proof_type`.

*Note*: The `proof_id` determines which subnet the proof is broadcast on. Each
proof system has a dedicated subnet to allow validators to subscribe to proofs
from specific proof systems.

## Honest Prover Relay

A prover relay is a whitelisted service that accepts execution proofs from
community provers, validates them, signs them, and broadcasts them to the
network. This allows any prover to contribute proofs without needing to be
individually whitelisted.

### Accepting proofs

The relay exposes an API endpoint that accepts unsigned `ExecutionProof`
submissions from community provers. Upon receiving a proof, the relay MUST:

1. Verify the `proof.proof_data` is non-empty.
2. Verify the execution proof is valid using
   `verify_execution_proof(proof, program_bytecode)`.
3. Verify a proof for the same `(new_payload_request_root, proof_type)` has not
   already been signed and broadcast.

If any validation fails, the relay SHOULD reject the submission.

### Signing and broadcasting

After successful validation, the relay signs and broadcasts the proof:

1. Set `signed_proof.message` to the validated `proof`.
2. Set `signed_proof.prover_id` to the relay's whitelisted public key.
3. Set `signed_proof.signature` to the result of
   `get_execution_proof_signature(state, proof, relay_privkey)`.
4. Broadcast the `SignedExecutionProof` on the `execution_proof_{subnet_id}`
   gossip topic, where `subnet_id = proof.proof_type`.

*Note*: The relay's public key MUST be included in `WHITELISTED_PROVERS`. The
relay takes responsibility for the validity of proofs it signs.
