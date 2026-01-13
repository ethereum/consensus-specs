# EIP-8025 (Gloas) -- Honest Prover

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Execution proof signature](#execution-proof-signature)
- [Constructing the `ProverSignedExecutionProof`](#constructing-the-proversignedexecutionproof)
- [Honest Prover Relay](#honest-prover-relay)
  - [Accepting proofs](#accepting-proofs)
  - [Signing and broadcasting](#signing-and-broadcasting)

<!-- mdformat-toc end -->

## Introduction

This document represents the prover guide accompanying EIP-8025 on Gloas.
Provers are whitelisted network operators who generate execution proofs during
the optional proof phase.

*Note*: This specification imports proof types from
[eip8025_fulu/proof-engine.md](../eip8025_fulu/proof-engine.md).

## Prerequisites

All terminology, constants, functions, and protocol mechanics defined in the
[EIP-8025 (Gloas) -- Beacon Chain](./beacon-chain.md) document are requisite for
this document.

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

## Constructing the `ProverSignedExecutionProof`

Provers subscribe to the `signed_execution_payload_envelope` gossip topic
(defined in [Gloas](../../gloas/p2p-interface.md)) to receive execution payloads
for which they can generate execution proofs.

To construct a `ProverSignedExecutionProof`:

1. Extract the `NewPayloadRequest` from the `SignedExecutionPayloadEnvelope`.
2. Select proof types and create `ProofAttributes`.
3. Call
   `proof_gen_id = proof_engine.request_proofs(new_payload_request, proof_attributes)`
   to initiate proof generation.
4. Call `proofs = proof_engine.get_proofs(proof_gen_id)` to retrieve generated
   proofs.
5. For each `ExecutionProof` in `proofs`:
   - Set `signed_proof.message` to the `ExecutionProof`.
   - Set `signed_proof.prover_pubkey` to the prover's public key.
   - Set `signed_proof.signature` to the result of
     `get_execution_proof_signature(state, proof, privkey)`.
   - Broadcast the `ProverSignedExecutionProof` on the `execution_proof` gossip
     topic.

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
2. Set `signed_proof.prover_pubkey` to the relay's whitelisted public key.
3. Set `signed_proof.signature` to the result of
   `get_execution_proof_signature(state, proof, relay_privkey)`.
4. Broadcast the `ProverSignedExecutionProof` on the `execution_proof` gossip
   topic.

*Note*: The relay's public key MUST be included in `WHITELISTED_PROVERS`. The
relay takes responsibility for the validity of proofs it signs.
