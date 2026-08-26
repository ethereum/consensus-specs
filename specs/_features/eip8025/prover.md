# EIP-8025 -- Honest Prover

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Helpers](#helpers)
  - [New `get_execution_proof_envelope_signature`](#new-get_execution_proof_envelope_signature)
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

### New `get_execution_proof_envelope_signature`

```python
def get_execution_proof_envelope_signature(
    state: BeaconState, proof_envelope: ExecutionProofEnvelope, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof_envelope, domain)
    return bls.Sign(privkey, signing_root)
```

## Execution proof

### Requesting proof generation

An honest prover performs the following steps for a received
`SignedExecutionPayloadEnvelope` and a set of supported proof types:

1. Let `beacon_block_root = signed_payload_envelope.message.beacon_block_root`.
2. Construct the corresponding `NewPayloadRequest` from the beacon block and
   `signed_payload_envelope`.
3. Construct `ProofAttributes` containing the desired proof types.
4. Let
   `new_payload_request_root = proof_engine.request_proofs(new_payload_request, proof_attributes)`.
5. For each requested `proof_type`, subsequently call
   `proof = proof_engine.get_proof(new_payload_request_root, proof_type)`.
6. Verify that `proof.public_input.new_payload_request_root` equals
   `new_payload_request_root` and that `proof.proof_type` equals `proof_type`.

### Signing and publishing a proof

For each returned `proof`, the prover performs the following steps:

1. Construct `ExecutionProofEnvelope` from `proof.proof_data`,
   `proof.proof_type`, and `beacon_block_root`.
2. Let `validator_index` be the prover's validator index and let
   `signature = get_execution_proof_envelope_signature(state, proof_envelope, prover_privkey)`.
3. Construct
   `SignedExecutionProofEnvelope(message=proof_envelope, validator_index=validator_index, signature=signature)`
   and broadcast it on the `execution_proof` topic.
