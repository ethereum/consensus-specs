# EIP-8025 -- Honest Prover

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Helpers](#helpers)
  - [New `get_execution_proof_signature`](#new-get_execution_proof_signature)
- [Execution proof](#execution-proof)
  - [Requesting proof generation](#requesting-proof-generation)
  - [Signing and publishing a proof](#signing-and-publishing-a-proof)

<!-- mdformat-toc end -->

## Introduction

This document represents the prover guide accompanying EIP-8025. Provers are
active validators who voluntarily generate and submit execution proofs without
direct protocol-level compensation. They provide a public good by producing
independently verifiable execution proofs during the optional proof phase.

*Note*: Provers are a transitional mechanism. In future mandatory proof forks,
builders will be required to produce and gossip execution proofs as part of
their block production duties, and the prover role will be deprecated.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md)
and imports proof types from [proof-engine.md](./proof-engine.md).

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

### Requesting proof generation

An honest prover performs the following steps for a received
`SignedExecutionPayloadEnvelope` and a set of supported proof types:

1. Let `beacon_block_root = signed_envelope.message.beacon_block_root`.
2. Construct `ProofAttributes` containing the desired proof types.
3. Call
   `requested_root = proof_engine.request_proofs(beacon_block_root, proof_attributes)`
   and check that `requested_root == beacon_block_root`.
4. For each requested `proof_type`, subsequently call
   `proof = proof_engine.get_proof(beacon_block_root, proof_type)`.

### Signing and publishing a proof

For each returned proof, the prover performs the following steps:

1. Check that `proof.public_input.beacon_block_root` equals the tracked
   `beacon_block_root` and that `proof.proof_type` is the requested type.
2. Let `validator_index` be the prover's validator index and let
   `signature = get_execution_proof_signature(state, proof, prover_privkey)`.
3. Construct
   `SignedExecutionProof(message=proof, validator_index=validator_index, signature=signature)`
   and broadcast it on the `execution_proof` topic.
