# EIP-8025 -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Execution payload envelope](#execution-payload-envelope)
  - [Modified `verify_execution_payload_envelope`](#modified-verify_execution_payload_envelope)
  - [Modified `on_execution_payload_envelope`](#modified-on_execution_payload_envelope)

<!-- mdformat-toc end -->

## Introduction

This document contains the fork-choice modifications for EIP-8025.

*Note*: This specification is built upon [Gloas](../../gloas/fork-choice.md) and
imports proof types from [proof-engine.md](./proof-engine.md).

## Execution payload envelope

### Modified `verify_execution_payload_envelope`

*Note*: `verify_execution_payload_envelope` is modified in EIP-8025 to require
both `ExecutionEngine` and `ProofEngine`, and to notify the `ProofEngine` of the
new payload alongside the `ExecutionEngine`.

```python
def verify_execution_payload_envelope(
    state: BeaconState,
    signed_envelope: SignedExecutionPayloadEnvelope,
    execution_engine: ExecutionEngine,
    proof_engine: ProofEngine,
) -> None:
    envelope = signed_envelope.message
    payload = envelope.payload

    # Verify signature
    assert verify_execution_payload_envelope_signature(state, signed_envelope)

    # Verify consistency with the beacon block
    header = copy(state.latest_block_header)
    header.state_root = hash_tree_root(state)
    assert envelope.beacon_block_root == hash_tree_root(header)
    assert envelope.parent_beacon_block_root == state.latest_block_header.parent_root

    # Verify consistency with the committed bid
    bid = state.latest_execution_payload_bid
    assert envelope.builder_index == bid.builder_index
    assert payload.prev_randao == bid.prev_randao
    assert payload.gas_limit == bid.gas_limit
    assert payload.block_hash == bid.block_hash
    assert hash_tree_root(envelope.execution_requests) == bid.execution_requests_root

    # Verify the execution payload is valid
    assert payload.slot_number == state.slot
    assert payload.parent_hash == state.latest_block_hash
    assert payload.timestamp == compute_time_at_slot(state, state.slot)
    assert hash_tree_root(payload.withdrawals) == hash_tree_root(state.payload_expected_withdrawals)

    new_payload_request = NewPayloadRequest(
        execution_payload=payload,
        versioned_hashes=[
            kzg_commitment_to_versioned_hash(commitment) for commitment in bid.blob_kzg_commitments
        ],
        parent_beacon_block_root=envelope.parent_beacon_block_root,
        execution_requests=envelope.execution_requests,
    )

    # Verify the execution payload is valid via ExecutionEngine
    assert execution_engine.verify_and_notify_new_payload(new_payload_request)

    # [New in EIP8025]
    # Notify ProofEngine of the new execution payload
    proof_engine.notify_new_payload(new_payload_request)
```

### Modified `on_execution_payload_envelope`

*Note*: `on_execution_payload_envelope` is modified in EIP-8025 to pass
`PROOF_ENGINE` alongside `EXECUTION_ENGINE` to
`verify_execution_payload_envelope`.

```python
def on_execution_payload_envelope(
    store: Store, signed_envelope: SignedExecutionPayloadEnvelope
) -> None:
    """
    Run ``on_execution_payload_envelope`` upon receiving a new execution payload envelope.
    """
    envelope = signed_envelope.message
    # The corresponding beacon block root needs to be known
    assert envelope.beacon_block_root in store.block_states

    # Check if blob data is available
    # If not, this payload MAY be queued and subsequently considered when blob data becomes available
    assert is_data_available(envelope.beacon_block_root)

    state = store.block_states[envelope.beacon_block_root]

    # Verify the execution payload envelope
    # [Modified in EIP8025]
    verify_execution_payload_envelope(state, signed_envelope, EXECUTION_ENGINE, PROOF_ENGINE)

    # Add execution payload envelope to the store
    store.payloads[envelope.beacon_block_root] = envelope
```
