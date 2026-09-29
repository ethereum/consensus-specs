# EIP-8369 -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [Modified `is_inclusion_list_satisfied`](#modified-is_inclusion_list_satisfied)
- [Helpers](#helpers)
  - [Modified `PayloadAttributes`](#modified-payloadattributes)
  - [Modified `record_payload_inclusion_list_satisfaction`](#modified-record_payload_inclusion_list_satisfaction)
  - [Modified `verify_execution_payload_envelope`](#modified-verify_execution_payload_envelope)
- [Handlers](#handlers)
  - [Modified `on_execution_payload_envelope`](#modified-on_execution_payload_envelope)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork choice accompanying EIP-8369. The execution
engine receives the inclusion lists grouped per committee member, together with
the inclusion list claims revealed in the payload envelope.

*Note*: This specification is built upon [Heze](../../heze/fork-choice.md).

## Protocols

### `ExecutionEngine`

#### Modified `is_inclusion_list_satisfied`

*Note*: `inclusion_lists` holds one list of transactions per inclusion list, and
`inclusion_list_claims` is passed unchanged from the payload envelope. The
execution engine resolves the claims as specified in EIP-7805.

```python
def is_inclusion_list_satisfied(
    self: ExecutionEngine,
    execution_payload: ExecutionPayload,
    # [Modified in EIP8369]
    inclusion_lists: Sequence[Sequence[Transaction]],
    # [New in EIP8369]
    inclusion_list_claims: Sequence[InclusionListClaim],
) -> bool:
    """
    Return ``True`` if and only if ``execution_payload`` satisfies the inclusion
    list constraints with respect to ``inclusion_lists`` and
    ``inclusion_list_claims``.
    """
```

## Helpers

### Modified `PayloadAttributes`

*Note*: `inclusion_list_transactions` is replaced by `inclusion_lists`, which
holds one list of transactions per inclusion list.

```python
@dataclass
class PayloadAttributes:
    timestamp: Uint64
    prev_randao: Bytes32
    suggested_fee_recipient: ExecutionAddress
    withdrawals: Sequence[Withdrawal]
    parent_beacon_block_root: Root
    slot_number: Uint64
    target_gas_limit: Uint64
    # [Modified in EIP8369]
    inclusion_lists: Sequence[Sequence[Transaction]]
```

### Modified `record_payload_inclusion_list_satisfaction`

```python
def record_payload_inclusion_list_satisfaction(
    store: Store,
    root: Root,
    payload: ExecutionPayload,
    # [New in EIP8369]
    inclusion_list_claims: Sequence[InclusionListClaim],
    execution_engine: ExecutionEngine,
) -> None:
    slot = store.blocks[root].slot - 1
    dependent_root = get_shuffling_dependent_root(store, root, compute_epoch_at_slot(slot))
    # [Modified in EIP8369]
    inclusion_lists = get_inclusion_list_transactions_by_member(
        get_inclusion_list_store(), slot, dependent_root, only_timely=True
    )
    is_inclusion_list_satisfied = execution_engine.is_inclusion_list_satisfied(
        payload,
        inclusion_lists,
        # [New in EIP8369]
        inclusion_list_claims,
    )
    store.payload_inclusion_list_satisfaction[root] = is_inclusion_list_satisfied
```

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
    # [New in EIP8369]
    assert hash_tree_root(envelope.inclusion_claims) == bid.inclusion_claims_root

    # Verify the execution payload is valid
    assert payload.slot_number == state.slot
    assert payload.parent_hash == state.latest_block_hash
    assert payload.timestamp == compute_time_at_slot(state.genesis_time, state.slot)
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
        )
    )
```

## Handlers

### Modified `on_execution_payload_envelope`

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
    verify_execution_payload_envelope(state, signed_envelope, EXECUTION_ENGINE)

    # Check if this payload satisfies the inclusion list constraints
    # If not, add this payload to the store as inclusion list constraints unsatisfied
    record_payload_inclusion_list_satisfaction(
        store,
        envelope.beacon_block_root,
        envelope.payload,
        # [New in EIP8369]
        envelope.inclusion_claims,
        EXECUTION_ENGINE,
    )

    # Add execution payload envelope to the store
    store.payloads[envelope.beacon_block_root] = envelope
```
