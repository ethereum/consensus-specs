# EIP-8025 (Gloas) -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Handlers](#handlers)
  - [Modified `on_execution_payload`](#modified-on_execution_payload)
  - [New `on_execution_payload_header`](#new-on_execution_payload_header)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork choice accompanying the EIP-8025 upgrade
for Gloas, enabling stateless validation of execution payloads through
cryptographic proofs.

*Note*: This specification is built upon [Gloas](../../gloas/fork-choice.md) and
imports proof types from
[eip8025_fulu/proof-engine.md](../eip8025_fulu/proof-engine.md).

## Handlers

### Modified `on_execution_payload`

*Note*: `on_execution_payload` is modified in EIP-8025 to include `PROOF_ENGINE`
in the call to `process_execution_payload`.

```python
def on_execution_payload(store: Store, signed_envelope: SignedExecutionPayloadEnvelope) -> None:
    """
    Run ``on_execution_payload`` upon receiving a new execution payload.
    """
    envelope = signed_envelope.message
    # The corresponding beacon block root needs to be known
    assert envelope.beacon_block_root in store.block_states

    # Check if blob data is available
    # If not, this payload MAY be queued and subsequently considered when blob data becomes available
    assert is_data_available(envelope.beacon_block_root)

    # Make a copy of the state to avoid mutability issues
    state = copy(store.block_states[envelope.beacon_block_root])

    # Process the execution payload
    # [Modified in EIP-8025] Added PROOF_ENGINE parameter
    process_execution_payload(state, signed_envelope, EXECUTION_ENGINE, PROOF_ENGINE)

    # Add new state for this payload to the store
    store.execution_payload_states[envelope.beacon_block_root] = state
```

### New `on_execution_payload_header`

```python
def on_execution_payload_header(
    store: Store, signed_envelope: SignedExecutionPayloadHeaderEnvelope
) -> None:
    """
    Run ``on_execution_payload_header`` upon receiving a new execution payload header.
    """
    envelope = signed_envelope.message
    # The corresponding beacon block root needs to be known
    assert envelope.beacon_block_root in store.block_states

    # Check if blob data is available
    # If not, this payload MAY be queued and subsequently considered when blob data becomes available
    assert is_data_available(envelope.beacon_block_root)

    # Make a copy of the state to avoid mutability issues
    state = copy(store.block_states[envelope.beacon_block_root])

    # Process the execution payload header
    process_execution_payload_header(state, signed_envelope, PROOF_ENGINE)

    # Add new state for this payload to the store
    store.execution_payload_states[envelope.beacon_block_root] = state
```
