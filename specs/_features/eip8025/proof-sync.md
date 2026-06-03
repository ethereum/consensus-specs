# EIP-8025 -- Proof Sync

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Beacon chain proof guest](#beacon-chain-proof-guest)
  - [New `extend_chain`](#new-extend_chain)
- [Binding the beacon header to the execution proof](#binding-the-beacon-header-to-the-execution-proof)
- [Updating the weak-subjectivity checkpoint](#updating-the-weak-subjectivity-checkpoint)
  - [New `is_checkpoint_in_beacon_chain_proof_range`](#new-is_checkpoint_in_beacon_chain_proof_range)
  - [New `update_checkpoint`](#new-update_checkpoint)

<!-- mdformat-toc end -->

## Introduction

This document contains the proof-sync specifications for EIP-8025. Proof sync
allows a node that starts from a weak-subjectivity checkpoint to verify
execution validity for a beacon chain without downloading all historical
execution payloads. This is achieved by composing recursive proofs over the beacon
chain.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md),
imports execution proof types from [beacon-chain.md](./beacon-chain.md), and
uses the proof engine interface from [proof-engine.md](./proof-engine.md).

The base EIP-8025 `ExecutionProof` remains an Engine API proof over
`new_payload_request_root`. A `BeaconChainProof` is a layer above that proof. A
beacon chain proof verifies:

- one parent `BeaconChainProof`;
- one execution proof;
- execution payload binding.

## Beacon chain proof guest

The beacon chain proof guest is the zkvm program that produces the beacon chain proofs.
It consists of two methods:
- `extend_chain` for extending the beacon chain proof by one block; and
- `update_checkpoint` for moving the weak-subjectivity checkpoint forward.

### New `extend_chain`

Extend chain is used to extend the beacon chain proof by one block.

```python
def extend_chain(
    parent_beacon_chain_proof: BeaconChainProof,
    execution_proof: ExecutionProof,
    execution_binding: BeaconBlockExecutionBinding,
    proof_engine: ProofEngine,
) -> BeaconChainProofPublicInput:
    parent = parent_beacon_chain_proof.public_input
    header = execution_binding.beacon_header
    bid = execution_binding.signed_execution_payload_bid.message
    header_root = hash_tree_root(header)

    # Verify both input proofs.
    assert proof_engine.verify_beacon_chain_proof(parent_beacon_chain_proof)
    assert proof_engine.verify_execution_proof(execution_proof)
    assert parent_beacon_chain_proof.proof_type == execution_proof.proof_type

    # Open the header body root to the compact execution binding.
    assert hash_tree_root(execution_binding) == header.body_root

    # TODO: Refine this binding before treating it as normative. This sketch
    # shows the intended relationship: the recursive guest rebuilds the
    # execution proof's public input from beacon-committed execution data.
    new_payload_request_header = NewPayloadRequestHeader(
        execution_payload_header=execution_binding.execution_payload_header,
        versioned_hashes=[
            kzg_commitment_to_versioned_hash(commitment) for commitment in bid.blob_kzg_commitments
        ],
        parent_beacon_block_root=header.parent_root,
        execution_requests_root=bid.execution_requests_root,
    )

    # Bind the execution proof public input to the constructed request header.
    assert hash_tree_root(new_payload_request_header) == (
        execution_proof.public_input.new_payload_request_root
    )

    # Check that the header extends the proven chain head.
    assert header.parent_root == parent.head_root
    assert header.slot > parent.head_slot

    return BeaconChainProofPublicInput(
        ws_checkpoint_root=parent.ws_checkpoint_root,
        ws_checkpoint_slot=parent.ws_checkpoint_slot,
        head_root=header_root,
        head_slot=header.slot,
    )
```

## Updating the weak-subjectivity checkpoint

The `update_checkpoint` operation moves the public weak-subjectivity checkpoint
forward.

### New `is_checkpoint_in_beacon_chain_proof_range`

```python
def is_checkpoint_in_beacon_chain_proof_range(
    beacon_chain_proof: BeaconChainProof,
    checkpoint_root: Root,
    checkpoint_slot: Slot,
) -> bool:
    """
    Return ``True`` if the checkpoint is inside the beacon chain proof range.
    """
    # TODO: Consider using an MMR over proven beacon roots to make this
    # membership check efficient.
    raise NotImplementedError
```

### New `update_checkpoint`

```python
def update_checkpoint(
    beacon_chain_proof: BeaconChainProof,
    checkpoint_root: Root,
    checkpoint_slot: Slot,
    proof_engine: ProofEngine,
) -> BeaconChainProofPublicInput:
    public_input = beacon_chain_proof.public_input

    assert proof_engine.verify_beacon_chain_proof(beacon_chain_proof)
    assert is_checkpoint_in_beacon_chain_proof_range(
        beacon_chain_proof,
        checkpoint_root,
        checkpoint_slot,
    )
    assert checkpoint_slot >= public_input.ws_checkpoint_slot
    assert checkpoint_slot <= public_input.head_slot

    return BeaconChainProofPublicInput(
        ws_checkpoint_root=checkpoint_root,
        ws_checkpoint_slot=checkpoint_slot,
        head_root=public_input.head_root,
        head_slot=public_input.head_slot,
    )
```

The membership proof used by `is_checkpoint_in_beacon_chain_proof_range` is
implementation-dependent. It may be supplied as a private witness to the guest.
