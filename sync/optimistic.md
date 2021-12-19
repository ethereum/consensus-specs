# Optimistic Sync

## Introduction

In order to provide a syncing execution engine with a partial view of the head
of the chain, it may be desirable for a consensus engine to import beacon
blocks without verifying the execution payloads. This partial sync is called an
*optimistic sync*.

## Constants

|Name|Value|Unit
|---|---|---|
|`SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY`| `96` | slots

*Note: the `SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY` must be user-configurable. See
[Failure Recovery](#failure-recovery).

## Helpers

Let `head_block: BeaconBlock` be the result of calling of the fork choice
algorithm at the time of block production. Let `justified_block: BeaconBlock`
be the latest current justified ancestor ancestor of the `head_block`.

```python
def is_optimistic(block: BeaconBlock) -> bool:
    hash_tree_root(block) in optimistic_roots
```

```python
def latest_valid_ancestor(block: BeaconBlock) -> BeaconBlock:
    while True:
        if not is_optimistic(block) or block.parent_root == Root():
	        return block
        block = get_block(block.parent_root)
```

```python
def is_execution_block(block: BeaconBlock) -> BeaconBlock:
	block.execution_payload != ExecutionPayload()
```

```python
def should_optimistically_import_block(current_slot: Slot, block: BeaconBlock) -> bool:
	block.slot + SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY <= current_slot
```

Let only a node which returns `is_optimistic(head) == True` be an *optimistic
node*. Let only a validator on an optimistic node be an *optimistic validator*.

When this specification only defines behaviour for an optimistic
node/validator, but *not* for the non-optimistic case, assume default
behaviours without regard for optimistic sync.

## Mechanisms

## When to optimistically import blocks

A block MUST NOT be optimistically imported, unless either of the following
conditions are met:

1. The justified checkpoint has execution enabled. I.e.,
   `is_execution_block(get_block(get_state(head_block).finalized_checkpoint.root))`
1. The current slot (as per the system clock) is at least `SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY` ahead of
   the slot of the block being imported. I.e., `should_optimistically_import_block(current_slot) == True`.

## How to optimistically import blocks

To optimistically import a block:

- The `execute_payload` function MUST return `True` if the execution
	engine returns `SYNCING` or `VALID`. An `INVALID` response MUST return `False`.

In addition to this change to validation, the consensus engine MUST be able
to ascertain, after import, which blocks returned `SYNCING` and which returned
`VALID`. This document will assume that consensus engines store the following
set:

- `optimistic_roots: Set[Root]`: `hash_tree_root(block)` where
	`block.body.execution_payload` is known to be `SYNCING`.

Notably, blocks included in `optimistic_roots` have passed all verifications
included in `process_block` (noting the modifications to the
`execute_payload`). I.e., the blocks are fully verified but awaiting execution
of the `ExecutionPayload`.

A consensus engine MUST be able to retrospectively (i.e., after import) modify
the status of `SYNCING` blocks to be either `VALID` or `INVALID` based upon responses
from an execution engine. I.e., perform the following transitions:

- `SYNCING` -> `VALID`
- `SYNCING` -> `INVALID`

When a block transitions from `SYNCING` -> `VALID`, all *ancestors* of the block MUST
also transition from `SYNCING` -> `VALID`.

When a block transitions from `SYNCING` -> `INVALID`, all *descendants* of the
block MUST also transition from `SYNCING` -> `INVALID`.

When a node transitions from the `SYNCING` state it is removed from the set of
`optimistic_roots`.

### Execution Engine Errors

A consensus engine MUST NOT interpret an error or failure to respond to a
message as a `SYNCING`, `VALID` or `INVALID` response. A message which receives
and error or no response MUST NOT be permitted to modify the fork choice
`Store`. A consensus engine MAY queue such a message for later processing.

### Assumptions about Execution Engine Behaviour

This specification assumes execution engines will only return `SYNCING` when
there is insufficient information available to make a `VALID` or `INVALID`
determination on the given `ExecutionPayload` (e.g., the parent payload is
unknown). Specifically, `SYNCING` responses should be fork-specific; the search
for a block on one chain MUST NOT trigger a `SYNCING` response for another
chain.

### Re-Orgs

The consensus engine MUST support any chain reorganisation which does *not*
affect the justified checkpoint. The consensus engine MAY support re-orgs
beyond the justified checkpoint.

If the justified checkpoint transitions from `SYNCING` -> `INVALID`, a
consensus engine MAY choose to alert the user and force the application to
exit.

## Failure Recovery

During the merge transition it is possible for an attacker to craft a
`BeaconBlock` with an execution payload that references an
eternally-unavailable `body.execution_payload.parent_hash` value. In some rare
circumstances, it is possible that an attacker can build atop such a block to
trigger justification. If an optimistic node imports this malicious chain, that
node will have a "poisoned" fork choice store, such that the node is unable to
produce a child of the head (due to the invalid chain of payloads) and the node
is unable to fork around the head (due to the justification of the malicious
chain).

The fork choice poisoning attack is temporary for an individual node, assuming
there exists an honest chain. An honest chain which justifies a higher epoch
than the malicious chain will take precedence and revive any poisoned store
once imported.

The `SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY` parameter assumes that the network
will justify a honest chain within some number of slots. With this assumption,
it is therefore "safe" to optimistically import transition blocks during the
sync process. Since there is an assumption that an honest chain with a higher
justified checkpoint exists, any fork choice poisoning will be short-lived and
resolved before that node is required to produce a block.

However, the assumption that the honest, canonical chain will always justify
within `SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY` slots is dubious. Therefore,
clients MUST provide the following command line flag to assist with manual
disaster recovery:

- `--safe_slots_to_import_optimistically`: modifies the
	`SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY`.

## Fork Choice

Consensus engines MUST support removing from fork choice blocks that transition
from `SYNCING` to `INVALID`. Specifically, a block deemed `INVALID` at any
point MUST NOT be included in the canonical chain and the weights from those
`INVALID` blocks MUST NOT be applied to any `VALID` or `SYNCING` ancestors.

## Checkpoint Sync (Weak Subjectivity Sync)

A consensus engine MAY assume that the `ExecutionPayload` of a block used for
checkpoint sync is `VALID`.

## Validator assignments

An entirely optimistically synced node is *not* a full node. It is unable to
produce blocks, since an execution engine cannot produce a payload upon an
unknown parent. It cannot faithfully attest to the head block of the chain,
since it has not fully verified that block.

### Block Production

A optimistic validator MUST NOT produce a block (i.e., sign across the
`DOMAIN_BEACON_PROPOSER` domain), unless one of the following exceptions are
met:

#### Block Production Exception 1.

If the justified block is fully verified (i.e., `not
is_optimistic(justified_block)`, the validator MAY produce a block upon
`latest_valid_ancestor(head)`.

### Attesting

An optimistic validator MUST NOT participate in attestation (i.e., sign across the
`DOMAIN_BEACON_ATTESTER`, `DOMAIN_SELECTION_PROOF` or
`DOMAIN_AGGREGATE_AND_PROOF` domains).

### Participating in Sync Committees

An optimistic validator MUST NOT participate in sync committees (i.e., sign across the
`DOMAIN_SYNC_COMMITTEE`, `DOMAIN_SYNC_COMMITTEE_SELECTION_PROOF` or
`DOMAIN_CONTRIBUTION_AND_PROOF` domains).

## P2P Networking

### The Gossip Domain (gossipsub)

#### `beacon_block`

An optimistic validator MAY subscribe to the `beacon_block` topic. Propagation
validation conditions are modified as such:

Do not apply the existing condition:

- [REJECT] The block's parent (defined by block.parent_root) passes validation.

Instead, apply the new condition:

- [REJECT] The block's parent (defined by block.parent_root) passes validation,
	*and* `block.parent root not in optimistic_roots`.

#### Other Topics

An optimistic node MUST NOT subscribe to the following topics:

-  `beacon_aggregate_and_proof`
-  `voluntary_exit`
-  `proposer_slashing`
-  `attester_slashing`
-  `beacon_attestation_{subnet_id}`
-  `sync_committee_contribution_and_proof`
-  `sync_committee_{subnet_id}`

Once the node ceases to be optimistic, it MAY re-subscribe to the aformentioned
topics.

### The Req/Resp Domain

#### BeaconBlocksByRange (v1, v2)

Consensus engines MUST NOT include any block in a response where
`is_optimistic(block) == True`.

#### BeaconBlocksByRoot (v1, v2)

Consensus engines MUST NOT include any block in a response where
`is_optimistic(block) == True`.

#### Status

An optimistic node MUST use the `latest_valid_ancestor(head)` block to form
responses, rather than the head block. Specifically, an optimistic node must
form a `Status` message as so:

The fields are, as seen by the client at the time of sending the message:

- `fork_digest`: As previously defined.
- `finalized_root`: `state.finalized_checkpoint.root` for the state corresponding to the latest valid ancestor block
  (Note this defaults to `Root(b'\x00' * 32)` for the genesis finalized checkpoint).
- `finalized_epoch`: `state.finalized_checkpoint.epoch` for the state corresponding to the latest valid ancestor block.
- `head_root`: The `hash_tree_root` root of the current latest valid ancestor block (`BeaconBlock`).
- `head_slot`: The slot of the block corresponding to `latest_valid_ancestor(head)`.

## Ethereum Beacon APIs

Consensus engines which provide an implementation of the [Ethereum Beacon
APIs](https://github.com/ethereum/beacon-APIs) must take care to avoid
presenting optimistic blocks as fully-verified blocks.

When information about an optimistic block is requested, the consensus engine:

- MUST NOT return a "success"-type response (e.g., 2xx).
- MAY return an "empty"-type response (e.g., 404).
- MAY return a "beacon node is currently syncing"-type response (e.g., 503).

When `is_optimistic(head) == True`, the consensus engine:

- MAY substitute the head block with `latest_valid_ancestor(block)`.
- MAY return a "beacon node is currently syncing"-type response (e.g., 503).
