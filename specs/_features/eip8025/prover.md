# EIP-8025 -- Honest Prover

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Helpers](#helpers)
  - [New `get_execution_proof_signature`](#new-get_execution_proof_signature)
- [Constructing `SignedExecutionProof`](#constructing-signedexecutionproof)
- [Honest prover relay](#honest-prover-relay)

<!-- mdformat-toc end -->

## Introduction

This document represents the prover guide accompanying EIP-8025. Provers are
active validators who voluntarily generate and submit execution proofs without
direct protocol-level compensation. They provide a public good by enabling
stateless validation during the optional proof phase.

*Note*: Provers are a transitional mechanism. In future mandatory proof forks,
builders will be required to produce and gossip execution proofs as part of
their block production duties, and the prover role will be deprecated.

*Note*: This specification is built upon [Fulu](../../fulu/beacon-chain.md) and
imports proof types from [proof-engine.md](./proof-engine.md).

## Helpers

### New `get_execution_proof_signature`

```python
def get_execution_proof_signature(
    state: BeaconState, proof: ExecutionProof, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof, domain)
    return bls.Sign(privkey, signing_root)
```

## Constructing `SignedExecutionProof`

An honest prover who is an active validator and wants to generate execution
proofs for a `BeaconBlock` performs the following steps:

1. Extract `NewPayloadRequest` from `BeaconBlock`:
   - `execution_payload = block.body.execution_payload`
   - `versioned_hashes = [kzg_commitment_to_versioned_hash(c) for c in block.body.blob_kzg_commitments]`
   - `parent_beacon_block_root = block.parent_root`
   - `execution_requests = block.body.execution_requests`
2. Create `ProofAttributes` with desired proof types.
3. Call
   `proof_gen_id = proof_engine.request_proofs(new_payload_request, proof_attributes)`
   to initiate proof generation.
4. The proof engine generates proofs asynchronously and delivers them to the
   prover via `POST /eth/v1/prover/execution_proofs`. Each proof is delivered
   with its associated `proof_gen_id` to link it to the original request.
5. Upon receiving each `ExecutionProof` with its `proof_gen_id`:
   - Validate the proof matches a pending `proof_gen_id`.
   - Set `message` to the `ExecutionProof`.
   - Set `validator_index` to the prover's validator index.
   - Sign the proof using
     `get_execution_proof_signature(state, proof, prover_privkey)`.
   - Broadcast the `SignedExecutionProof` on the `execution_proof` gossip topic.

## Honest prover relay

A prover relay is a trusted intermediary that accepts unsigned execution proofs
from proof engines and signs them for broadcast. The relay MUST be an active
validator.

When a prover relay receives an unsigned `ExecutionProof` via
`POST /eth/v1/prover/execution_proofs`:

1. Validate that `proof_data` is non-empty.
2. Verify the execution proof is valid using
   `proof_engine.verify_execution_proof(proof)`.
3. Check the proof is not a duplicate (same `new_payload_request_root`,
   `proof_type`).
4. If valid and not a duplicate:
   - Create a `SignedExecutionProof` with the relay's validator index and
     signature.
   - Broadcast on the `execution_proof` gossip topic.
