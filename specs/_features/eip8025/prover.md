# EIP-8025 -- Honest Prover

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Helpers](#helpers)
  - [New `get_execution_proof_signature`](#new-get_execution_proof_signature)
- [Execution proof](#execution-proof)
  - [Constructing the `SignedExecutionProof`](#constructing-the-signedexecutionproof)

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

## Execution proof

### Constructing the `SignedExecutionProof`

An honest prover who is an active validator and wants to generate execution
proofs for a `BeaconBlock` performs the following steps:

1. Subscribe to `Block` events from the beacon node via SSE.
2. Upon receiving a `Block` event:
   - Fetch the full `BeaconBlock` via RPC.
   - Construct `NewPayloadRequest` from the block.
   - Create `ProofAttributes` with desired proof types.
   - Call
     `new_payload_request_root = proof_engine.request_proofs(new_payload_request, proof_attributes)`
     to initiate proof generation, tracking the request by
     `new_payload_request_root`.
3. Subscribe to proof completion events from the proof engine via SSE.
4. Upon receiving a proof completion event for a tracked
   `new_payload_request_root`:
   - Fetch the completed `ExecutionProof` from the proof engine.
   - Let `validator_index` be the prover's validator index.
   - Let
     `signature = get_execution_proof_signature(state, proof, prover_privkey)`.
   - Let
     `signed_proof = SignedExecutionProof(message=proof, validator_index=validator_index, signature=signature)`.
   - Broadcast `signed_proof` on the `execution_proof` gossip topic.
