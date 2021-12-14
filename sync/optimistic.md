# Optimistic Sync

## Introduction

In order to provide a syncing execution engine with a partial view of the head
of the chain, it may be desirable for a consensus engine to import beacon
blocks without verifying the execution payloads. This partial sync is called an
*optimistic sync*.

## Mechanisms

To perform an optimistic sync:

- The `execute_payload` function MUST return `True` if the execution
	engine returns `SYNCING` or `VALID`. An `INVALID` response MUST return `False`.
- The `validate_merge_block` function MUST NOT raise an assertion if both the
	`pow_block` and `pow_parent` are unknown to the execution engine.

In addition to these changes to validation, the consensus engine MUST be able
to ascertain, after import, which blocks returned `SYNCING` and which returned
`VALID`. This document will assume that consensus engines store the following
sets:

- `valid_roots: Set[Root]`: `hash_tree_root(block)` where
	`block.body.execution_payload` is known to be `VALID`.
- `optimistic_roots: Set[Root]`: `hash_tree_root(block)` where
	`block.body.execution_payload` is known to be `SYNCING`.

Notably, `optimistic_roots` only includes blocks which have execution enabled.
On the other hand, `valid_roots` contains blocks *with or without* execution
enabled (i.e., all blocks).

A consensus engine MUST be able to retrospectively (i.e., after import) modify
the status of `SYNCING` blocks to be either `VALID` or `INVALID` based upon responses
from an execution engine. I.e., perform the following transitions:

- `SYNCING` -> `VALID`
- `SYNCING` -> `INVALID`

When a block transitions from `SYNCING` -> `VALID`, all *ancestors* of the block MUST
also transition from `SYNCING` -> `VALID`.

When a block transitions from `SYNCING` -> `INVALID`, all *descendants* of the
block MUST also transition from `SYNCING` -> `INVALID`.

### Execution Engine Errors

A consensus engine MUST NOT interpret an error or failure to respond to a
message as a `SYNCING`, `VALID` or `INVALID` response. A consensus engine MAY
queue such a message for later processing.

## Merge Transition

To protect against attacks during the transition from empty `ExecutionPayload`
values to those which include the terminal PoW block, a consensus engine MUST
NOT perform an optimistic sync unless the `finalized_checkpoint.root` of the head
block references a block for which
`is_execution_enabled(head_state, head_block.body) == True`.

TODO: this restriction is very onerous, however it is the best known remedy for
the attack described in https://hackmd.io/S5ZEVhsNTqqfJirTAkBPlg I hope we can
do better.

## Fork Choice

Consensus engines MUST support removing from fork choice blocks that transition
from `SYNCING` to `INVALID`. Specifically, a block deemed `INVALID` at any
point MUST NOT be included in the canonical chain and the weights from those
`INVALID` blocks MUST NOT be applied to any `VALID` or `SYNCING` ancestors.

### Helpers

Let `head_block: BeaconBlock` be the result of calling of the fork choice
algorithm at the time of block production. Let `justified_block: BeaconBlock`
be the latest current justified ancestor ancestor of the `head_block`.

```python
def is_optimistic(block: BeaconBlock) -> bool:
    hash_tree_root(block) in optimistic_roots
```

```python
def latest_valid_ancestor(block: BeaconBlock) -> BeaconBlock:
    while block.parent_root != Root():
	    if not is_optimistic(block) or block.parent_root == Root():
		    return block
        block = get_block(block.parent_root)
```

Let only a node which returns `is_optimistic(head) == True` be an *optimistic
node*. Let only a validator on an optimistic node be an *optimistic validator*.

When this specification only defines behaviour for an optimistic
node/validator, but *not* for the non-optimistic case, assume default
behaviours without regard for optimistic sync.

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

#### `beacon_aggregate_and_proof`

An optimistic validator MUST NOT subscribe to the `beacon_aggregate_and_proof`
topic.

#### `voluntary_exit`

An optimistic validator MUST NOT subscribe to the `voluntary_exit` topic.

#### `proposer_slashing`

An optimistic validator MUST NOT subscribe to the `proposer_slashing` topic.

#### `attester_slashing`

An optimistic validator MUST NOT subscribe to the `attester_slashing` topic.

#### `beacon_attestation_{subnet_id}`

An optimistic validator MUST NOT subscribe to the
`beacon_attestation_{subnet_id}` (attestation subnets) topics.

#### `sync_committee_contribution_and_proof`

An optimistic validator MUST NOT subscribe to the
`sync_committee_contribution_and_proof` topic.

#### `sync_committee_{subnet_id}`

An optimistic validator MUST NOT subscribe to the `sync_committee_{subnet_id}`
(sync committee subnets) topics.

### The Req/Resp Domain

#### BeaconBlocksByRange (v1, v2)

Consensus engines MUST NOT include any block in a response where
`is_optimistic(block) == False`.

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
