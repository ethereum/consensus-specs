# EIP-8025 -- Honest Prover

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Helpers](#helpers)
  - [New `get_execution_proof_envelope_signature`](#new-get_execution_proof_envelope_signature)
  - [New `request_execution_proofs`](#new-request_execution_proofs)
  - [New `get_signed_execution_proof_envelope`](#new-get_signed_execution_proof_envelope)

<!-- mdformat-toc end -->

## Introduction

This document represents the prover guide accompanying EIP-8025. Provers are
active validators who voluntarily generate and submit execution proofs without
direct protocol-level compensation. They provide a public good by producing
independently verifiable execution proofs during the optional proof phase.

*Note*: The prover role is optional for clients to implement.

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
    """
    Return the prover signature for an execution proof envelope.
    """
    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof_envelope, domain)
    return bls.Sign(privkey, signing_root)
```

### New `request_execution_proofs`

```python
def request_execution_proofs(
    block: BeaconBlock,
    signed_payload_envelope: SignedExecutionPayloadEnvelope,
    proof_types: Sequence[ProofType],
    proof_engine: ProofEngine,
) -> Root:
    """
    Request execution proofs for an accepted execution payload.
    """
    payload_envelope = signed_payload_envelope.message
    assert payload_envelope.beacon_block_root == hash_tree_root(block)

    bid = block.body.signed_execution_payload_bid.message
    new_payload_request = SSZNewPayloadRequest(
        execution_payload=payload_envelope.payload,
        versioned_hashes=VersionedHashes(
            data=[
                kzg_commitment_to_versioned_hash(commitment)
                for commitment in bid.blob_kzg_commitments
            ]
        ),
        parent_beacon_block_root=payload_envelope.parent_beacon_block_root,
        execution_requests=payload_envelope.execution_requests,
    )
    proof_attributes = ProofAttributes(proof_types=proof_types)
    return proof_engine.request_proofs(
        new_payload_request,
        DEPOSIT_CHAIN_ID,
        STATELESS_INPUT_SCHEMA_ID,
        proof_attributes,
    )
```

### New `get_signed_execution_proof_envelope`

```python
def get_signed_execution_proof_envelope(
    state: BeaconState,
    beacon_block_root: Root,
    new_payload_request_root: Root,
    proof_type: ProofType,
    validator_index: ValidatorIndex,
    prover_privkey: int,
    proof_engine: ProofEngine,
) -> SignedExecutionProofEnvelope:
    """
    Retrieve and validate a generated proof, then sign its execution proof envelope.
    """
    proof = proof_engine.get_proof(new_payload_request_root, proof_type)
    assert proof.public_input.new_payload_request_root == new_payload_request_root
    assert proof.public_input.successful_validation
    assert proof.public_input.chain_id == DEPOSIT_CHAIN_ID
    assert proof.public_input.schema_id == STATELESS_INPUT_SCHEMA_ID
    assert proof.proof_type == proof_type

    proof_envelope = ExecutionProofEnvelope(
        proof_data=proof.proof_data,
        proof_type=proof.proof_type,
        beacon_block_root=beacon_block_root,
    )
    signature = get_execution_proof_envelope_signature(
        state,
        proof_envelope,
        prover_privkey,
    )
    return SignedExecutionProofEnvelope(
        message=proof_envelope,
        validator_index=validator_index,
        signature=signature,
    )
```

The prover broadcasts the returned `SignedExecutionProofEnvelope` on the
`execution_proof` topic.
