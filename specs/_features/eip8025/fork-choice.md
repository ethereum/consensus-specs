# EIP-8025 -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Handlers](#handlers)
  - [Modified `on_execution_payload`](#modified-on_execution_payload)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork choice accompanying the EIP-8025 upgrade,
enabling stateless validation of execution payloads through cryptographic
proofs.

*Note*: This specification is built upon [Gloas](../../gloas/fork-choice.md).

## Handlers

### Modified `on_execution_payload`

The handler `on_execution_payload` is modified to accept either a full
`SignedExecutionPayloadEnvelope` or a `SignedExecutionPayloadHeaderEnvelope`.

```python
def on_execution_payload(
    store: Store,
    # [Modified in EIP-8025]
    # Accept either full envelope or header-only envelope
    signed_envelope: SignedExecutionPayloadEnvelope | SignedExecutionPayloadHeaderEnvelope,
) -> None:
    """
    Run ``on_execution_payload`` upon receiving a new execution payload or header.
    """
    envelope = signed_envelope.message
    # The corresponding beacon block root needs to be known
    assert envelope.beacon_block_root in store.block_states

    # Check if blob data is available
    # If not, this payload MAY be queued and subsequently considered when blob data becomes available
    assert is_data_available(envelope.beacon_block_root)

    # Make a copy of the state to avoid mutability issues
    state = copy(store.block_states[envelope.beacon_block_root])

    # Process the execution payload (handles both full envelope and header)
    process_execution_payload(state, signed_envelope, EXECUTION_ENGINE)

    # Add new state for this payload to the store
    store.execution_payload_states[envelope.beacon_block_root] = state
```
