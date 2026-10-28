# Gloas -- Optimistic Sync

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `OptimisticStore`](#modified-optimisticstore)
  - [Modified `is_optimistic`](#modified-is_optimistic)
  - [Modified `latest_verified_ancestor`](#modified-latest_verified_ancestor)
- [Mechanisms](#mechanisms)
  - [How to optimistically import payloads](#how-to-optimistically-import-payloads)
  - [How to apply `latestValidHash` when payload status is `INVALID`](#how-to-apply-latestvalidhash-when-payload-status-is-invalid)
- [Checkpoint Sync (Weak Subjectivity Sync)](#checkpoint-sync-weak-subjectivity-sync)
- [Validator assignments](#validator-assignments)
  - [Payload attestations](#payload-attestations)
  - [Builder duties](#builder-duties)
- [Ethereum Beacon APIs](#ethereum-beacon-apis)

<!-- mdformat-toc end -->

## Introduction

This document extends the
[Bellatrix optimistic sync specification](../bellatrix/optimistic-sync.md) for
Gloas. A beacon block no longer carries its execution payload: it commits to the
payload it builds on through `bid.parent_block_hash`, and its own payload
arrives separately in an `ExecutionPayloadEnvelope`. A block therefore has an
`empty` and a `full` fork choice node, and a block root no longer identifies a
payload. Optimistic status is tracked per payload.

## Helpers

### Modified `OptimisticStore`

Let `optimistic_payloads: set[Hash32]` be the set of `block_hash` for all
optimistically imported execution payloads which have only received a
`NOT_VALIDATED` designation from an execution engine.

```python
@dataclass
class OptimisticStore:
    # [Modified in Gloas:EIP7732]
    optimistic_payloads: set[Hash32]
    head_block_root: Root
    blocks: dict[Root, BeaconBlock]
    block_states: dict[Root, BeaconState]
```

At the Gloas fork, `optimistic_payloads` is initialized with
`body.execution_payload.block_hash` of every block in `optimistic_roots`.

### Modified `is_optimistic`

*Note*: `is_optimistic` is modified to take a `ForkChoiceNode`. A `full` node
references the block's own payload, a `pending` or `empty` node references the
payload the block builds on.

```python
def is_optimistic(opt_store: OptimisticStore, node: ForkChoiceNode) -> bool:
    bid = opt_store.blocks[node.root].body.signed_execution_payload_bid.message
    if node.payload_status == PAYLOAD_STATUS_FULL:
        return bid.block_hash in opt_store.optimistic_payloads
    return bid.parent_block_hash in opt_store.optimistic_payloads
```

### Modified `latest_verified_ancestor`

```python
def latest_verified_ancestor(opt_store: OptimisticStore, node: ForkChoiceNode) -> ForkChoiceNode:
    # It is assumed that the `node` parameter is never an INVALIDATED node.
    while True:
        if not is_optimistic(opt_store, node):
            return node
        block = opt_store.blocks[node.root]
        if node.payload_status != PAYLOAD_STATUS_PENDING:
            node = ForkChoiceNode(root=node.root, payload_status=PAYLOAD_STATUS_PENDING)
        elif block.parent_root == Root():
            return node
        else:
            parent = opt_store.blocks[block.parent_root]
            parent_block_hash = block.body.signed_execution_payload_bid.message.parent_block_hash
            message_block_hash = parent.body.signed_execution_payload_bid.message.block_hash
            parent_status = (
                PAYLOAD_STATUS_FULL
                if parent_block_hash == message_block_hash
                else PAYLOAD_STATUS_EMPTY
            )
            node = ForkChoiceNode(root=block.parent_root, payload_status=parent_status)
```

Let a node be an *optimistic node* if
`is_optimistic(opt_store, get_head(store))` is `True`. Invalidating payloads
leaves every block's `empty` node viable, so the block tree cannot be left
without viable branches.

## Mechanisms

### How to optimistically import payloads

Blocks are imported without consulting an execution engine. The optimistically
imported unit is the execution payload envelope. To optimistically import an
envelope:

- [`verify_and_notify_new_payload`](../electra/beacon-chain.md#modified-verify_and_notify_new_payload)
  MUST return `True` if the execution engine returns `NOT_VALIDATED` or `VALID`.
  An `INVALIDATED` response MUST return `False`.
- The payload the block builds on, `bid.parent_block_hash`, MUST NOT be
  `INVALIDATED`.

On an execution engine error, the envelope MUST NOT be imported or applied to
fork choice and MAY be queued for later processing.

The consensus engine MUST track which payloads returned `NOT_VALIDATED` and
which returned `VALID` for subsequent processing, and MUST be able to
retrospectively modify the status of `NOT_VALIDATED` payloads to `VALID` or
`INVALIDATED` based upon responses from an execution engine.

When a payload transitions from `NOT_VALIDATED` -> `VALID`, all *ancestor*
payloads MUST also transition from `NOT_VALIDATED` -> `VALID`.

When a payload transitions from `NOT_VALIDATED` -> `INVALIDATED`, all
*descendant* payloads MUST also transition from `NOT_VALIDATED` ->
`INVALIDATED`. The `full` node of each such payload and every node descending
from it MUST be removed from fork choice. The block's `empty` node is not
affected.

When a payload transitions from the `NOT_VALIDATED` state, it is removed from
the set of `opt_store.optimistic_payloads`.

### How to apply `latestValidHash` when payload status is `INVALID`

The Bellatrix rules apply to the payload chain, linked by `parent_hash`, with
"block" read as "payload": `invalidPayload` is the child of the payload with
`block_hash == latestValidHash` in the chain containing the payload in question,
the first payload of that chain if `latestValidHash` is `0x00..00` (all zeroes),
or the payload in question itself if `latestValidHash` is `null` or unknown.
`invalidPayload` and all its descendant payloads MUST be transitioned from
`NOT_VALIDATED` to `INVALIDATED`.

## Checkpoint Sync (Weak Subjectivity Sync)

A consensus engine MAY assume that the payload referenced by `latest_block_hash`
of a state used as an anchor for checkpoint sync is `VALID` without necessarily
providing that payload to an execution engine.

## Validator assignments

Let only a builder on an optimistic node be an *optimistic builder*.

### Payload attestations

An optimistic validator MUST NOT produce payload attestations (i.e., sign across
the `DOMAIN_PTC_ATTESTER` domain).

### Builder duties

An optimistic builder MUST NOT submit execution payload bids or envelopes (i.e.,
sign across the `DOMAIN_BEACON_BUILDER` domain).

## Ethereum Beacon APIs

Consensus engines which provide an implementation of the
[Ethereum Beacon APIs](https://github.com/ethereum/beacon-APIs) must set
`execution_optimistic` to `is_optimistic(opt_store, node)` for the fork choice
node a request resolves to. The Beacon APIs define which node each request
resolves to.
