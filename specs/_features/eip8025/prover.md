# EIP-8025 -- Honest Prover

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Helpers](#helpers)
  - [`get_execution_proof_signature`](#get_execution_proof_signature)
- [Constructing `ProverSignedExecutionProof`](#constructing-proversignedexecutionproof)
- [Honest prover relay](#honest-prover-relay)

<!-- mdformat-toc end -->

## Introduction

This document represents the prover guide accompanying EIP-8025. Provers are
whitelisted network participants who voluntarily generate and submit execution
proofs without direct protocol-level compensation. They provide a public good by
enabling stateless validation during the optional proof phase.

*Note*: Provers are a transitional mechanism. In future mandatory proof forks,
builders will be required to produce and gossip execution proofs as part of
their block production duties, and the prover role will be deprecated.

*Note*: This specification is built upon [Fulu](../../fulu/beacon-chain.md) and
imports proof types from [proof-engine.md](./proof-engine.md).

## Helpers

### `get_execution_proof_signature`

```python
def get_execution_proof_signature(
    state: BeaconState, proof: ExecutionProof, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof, domain)
    return bls.Sign(privkey, signing_root)
```

## Constructing `ProverSignedExecutionProof`

An honest prover who has been whitelisted and wants to generate execution proofs
for a `BeaconBlockBody` performs the following steps:

1. Extract `NewPayloadRequest` from `BeaconBlockBody`:
   - `execution_payload = body.execution_payload`
   - `versioned_hashes = [kzg_commitment_to_versioned_hash(c) for c in body.blob_kzg_commitments]`
   - `parent_beacon_block_root = state.latest_block_header.parent_root`
   - `execution_requests = body.execution_requests`
2. Create `ProofAttributes` with desired proof types.
3. Call
   `proof_gen_id = proof_engine.request_proofs(new_payload_request, proof_attributes)`
   to initiate proof generation.
4. Call `proof_engine.get_proofs(proof_gen_id)` to retrieve the generated
   proofs.
5. For each `ExecutionProof` in the returned list:
   - Set `message` to the `ExecutionProof`.
   - Set `prover_pubkey` to the prover's public key.
   - Sign the proof using
     `get_execution_proof_signature(state, proof, prover_privkey)`.
   - Broadcast the `ProverSignedExecutionProof` on the `execution_proof` gossip
     topic.

## Honest prover relay

A prover relay is a trusted intermediary that accepts unsigned execution proofs
from community provers and signs them for broadcast. The relay's public key MUST
be in the prover whitelist.

When a prover relay receives an unsigned `ExecutionProof`:

1. Validate that `proof_data` is non-empty.
2. Verify the execution proof is valid using
   `proof_engine.verify_execution_proof(proof)`.
3. Check the proof is not a duplicate (same `new_payload_request_root`,
   `proof_type`).
4. If valid and not a duplicate:
   - Create a `ProverSignedExecutionProof` with the relay's public key and
     signature.
   - Broadcast on the `execution_proof` gossip topic.
