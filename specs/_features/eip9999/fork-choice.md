# EIP-9999 -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `verify_execution_payload_envelope`](#modified-verify_execution_payload_envelope)

<!-- mdformat-toc end -->

## Introduction

`verify_and_notify_new_payload` gains a required `payload_request_chain_root`
argument, so its existing call site supplies one. At this point
`state.payload_request_chain_root` covers every full payload up to and including
the parent, so extending it with this payload's commitment yields the chain
through this payload.

The per-field checks against the committed bid are retained. They are redundant
with the chain assertion whenever the payload is in hand, and they localise a
failure to a specific field, which the chain cannot.

## Helpers

### Modified `verify_execution_payload_envelope`

```python
def verify_execution_payload_envelope(
    state: BeaconState,
    signed_envelope: SignedExecutionPayloadEnvelope,
    execution_engine: ExecutionEngine,
) -> None:
    envelope = signed_envelope.message
    payload = envelope.payload

    # Verify signature
    assert verify_execution_payload_envelope_signature(state, signed_envelope)

    # Verify consistency with the beacon block
    header = state.latest_block_header.copy()
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

    # Compute versioned hashes
    versioned_hashes = VersionedHashes()
    for commitment in bid.blob_kzg_commitments:
        versioned_hashes.append(kzg_commitment_to_versioned_hash(commitment))

    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=envelope.parent_beacon_block_root,
            execution_requests=envelope.execution_requests,
        ),
        # [New in EIP9999]
        compute_payload_request_chain_root(state, bid, envelope.execution_requests),
    )
```
