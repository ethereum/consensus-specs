# Optimistic Sync

## Introduction

In order to provide a syncing execution engine with a partial view of the head
of the chain, it may be desirable for a consensus engine to import beacon
blocks without verifying the execution payloads. This partial sync is called an
*optimistic sync*.

Optimistic sync is designed to be opt-in and backwards compatible (i.e.,
non-optimistic nodes can tolerate optimistic nodes on the network and vice
versa). Optimistic sync is not a fundamental requirement for consensus nodes.
Rather, it's a stop-gap measure to allow execution nodes to sync via
established methods until future Ethereum roadmap items are implemented (e.g.,
statelessness).

## Constants

|Name|Value|Unit
|---|---|---|
|`SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY`| `128` | slots

*Note: the `SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY` must be user-configurable. See
[Fork Choice Poisoning](#fork-choice-poisoning).*

## Helpers

For brevity, we define two aliases for values of the `status` field on
`PayloadStatusV1`:

- Alias `NOT_VALIDATED` to:
    - `SYNCING`
    - `ACCEPTED`
- Alias `INVALIDATED` to:
    - `INVALID`
    - `INVALID_BLOCK_HASH`

Let `head: BeaconBlock` be the result of calling of the fork choice
algorithm at the time of block production. Let `head_block_root: Root` be the
root of that block.

Let `blocks: Dict[Root, BeaconBlock]` and `block_states: Dict[Root,
BeaconState]` be the blocks (and accompanying states) that have been verified
either completely or optimistically.

Let `optimistic_roots: Set[Root]` be the set of `hash_tree_root(block)` for all
optimistically imported blocks which have only received a `NOT_VALIDATED` designation
from an execution engine (i.e., they are not known to be `INVALIDATED` or `VALID`).

Let `current_slot: Slot` be `(time - genesis_time) // SECONDS_PER_SLOT` where
`time` is the UNIX time according to the local system clock.

```python
@dataclass
class OptimisticStore(object):
    optimistic_roots: Set[Root]
    head_block_root: Root
    blocks: Dict[Root, BeaconBlock]
    block_states: Dict[Root, BeaconState]
```

```python
def is_optimistic(opt_store: OptimisticStore, block: BeaconBlock) -> bool:
    return hash_tree_root(block) in opt_store.optimistic_roots
```

```python
def latest_verified_ancestor(opt_store: OptimisticStore, block: BeaconBlock) -> BeaconBlock:
    # It is assumed that the `block` parameter is never an INVALIDATED block.
    while True:
        if not is_optimistic(opt_store, block) or block.parent_root == Root():
            return block
        block = opt_store.blocks[block.parent_root]
```

```python
def is_execution_block(block: BeaconBlock) -> bool:
    return block.body.execution_payload != ExecutionPayload()
```

```python
def is_optimistic_candidate_block(opt_store: OptimisticStore, current_slot: Slot, block: BeaconBlock) -> bool:
    if is_execution_block(opt_store.blocks[block.parent_root]):
        return True

    if block.slot + SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY <= current_slot:
        return True

    return False
```

Let only a node which returns `is_optimistic(opt_store, head) is True` be an *optimistic
node*. Let only a validator on an optimistic node be an *optimistic validator*.

When this specification only defines behaviour for an optimistic
node/validator, but *not* for the non-optimistic case, assume default
behaviours without regard for optimistic sync.

## Mechanisms

### When to optimistically import blocks

A block MAY be optimistically imported when
`is_optimistic_candidate_block(opt_store, current_slot, block)` returns `True`.
This ensures that blocks are only optimistically imported if one or more of the
following are true:

1. The parent of the block has execution enabled.
1. The current slot (as per the system clock) is at least
   `SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY` ahead of the slot of the block being
   imported.

In effect, there are restrictions on when a *merge block* can be optimistically
imported. The merge block is the first block in any chain where
`is_execution_block(block) == True`. Any descendant of a merge block may be
imported optimistically at any time.

*See [Fork Choice Poisoning](#fork-choice-poisoning) for the motivations behind
these conditions.*

### How to optimistically import blocks

To optimistically import a block:

- The [`notify_new_payload`](../specs/bellatrix/beacon-chain.md#notify_new_payload) function MUST return `True` if the execution
  engine returns `NOT_VALIDATED` or `VALID`. An `INVALIDATED` response MUST return `False`.
- The [`validate_merge_block`](../specs/bellatrix/fork-choice.md#validate_merge_block)
 function MUST NOT raise an assertion if both the
`pow_block` and `pow_parent` are unknown to the execution engine.
  - All other assertions in [`validate_merge_block`](../specs/bellatrix/fork-choice.md#validate_merge_block)
   (e.g., `TERMINAL_BLOCK_HASH`) MUST prevent an optimistic import.
- The parent of the block MUST NOT have an `INVALIDATED` execution payload.

In addition to this change in validation, the consensus engine MUST track which
blocks returned `NOT_VALIDATED` and which returned `VALID` for subsequent processing.

Optimistically imported blocks MUST pass all verifications included in
`process_block` (withstanding the modifications to `notify_new_payload`).

A consensus engine MUST be able to retrospectively (i.e., after import) modify
the status of `NOT_VALIDATED` blocks to be either `VALID` or `INVALIDATED` based upon responses
from an execution engine. I.e., perform the following transitions:

- `NOT_VALIDATED` -> `VALID`
- `NOT_VALIDATED` -> `INVALIDATED`

When a block transitions from `NOT_VALIDATED` -> `VALID`, all *ancestors* of the
block MUST also transition from `NOT_VALIDATED` -> `VALID`. Such a block and any previously `NOT_VALIDATED` ancestors are no longer
considered "optimistically imported".

When a block transitions from `NOT_VALIDATED` -> `INVALIDATED`, all *descendants* of the
block MUST also transition from `NOT_VALIDATED` -> `INVALIDATED`.

When a block transitions from the `NOT_VALIDATED` state, it is removed from the set of
`opt_store.optimistic_roots`.

When a "merge block" (i.e. the first block which enables execution in a chain) is declared to be
`VALID` by an execution engine (either directly or indirectly), the full
[`validate_merge_block`](../specs/bellatrix/fork-choice.md#validate_merge_block)
MUST be run against the merge block. If the block
fails [`validate_merge_block`](../specs/bellatrix/fork-choice.md#validate_merge_block),
the merge block MUST be treated the same as
an `INVALIDATED` block (i.e., it and all its descendants are invalidated and
removed from the block tree).

### Execution Engine Errors

When an execution engine returns an error or fails to respond to a payload
validity request for some block, a consensus engine:

- MUST NOT optimistically import the block.
- MUST NOT apply the block to the fork choice store.
- MAY queue the block for later processing.

### Assumptions about Execution Engine Behaviour

This specification assumes execution engines will only return `NOT_VALIDATED` when
there is insufficient information available to make a `VALID` or `INVALIDATED`
determination on the given `ExecutionPayload` (e.g., the parent payload is
unknown). Specifically, `NOT_VALIDATED` responses should be fork-specific, in that
the search for a block on one chain MUST NOT trigger a `NOT_VALIDATED` response for
another chain.

### Re-Orgs

The consensus engine MUST support any chain reorganisation which does *not*
affect the justified checkpoint.

If the justified checkpoint transitions from `NOT_VALIDATED` -> `INVALIDATED`, a
consensus engine MAY choose to alert the user and force the application to
exit.

## Fork Choice

Consensus engines MUST support removing blocks from fork choice that transition
from `NOT_VALIDATED` to `INVALIDATED`. Specifically, a block deemed `INVALIDATED` at any
point MUST NOT be included in the canonical chain and the weights from those
`INVALIDATED` blocks MUST NOT be applied to any `VALID` or `NOT_VALIDATED` ancestors.

### Fork Choice Poisoning

During the merge transition it is possible for an attacker to craft a
`BeaconBlock` with an execution payload that references an
eternally-unavailable `body.execution_payload.parent_hash` (i.e., the parent
hash is random bytes). In rare circumstances, it is possible that an attacker
can build atop such a block to trigger justification. If an optimistic node
imports this malicious chain, that node will have a "poisoned" fork choice
store, such that the node is unable to produce a block that descends from the
head (due to the invalid chain of payloads) and the node is unable to produce a
block that forks around the head (due to the justification of the malicious
chain).

If an honest chain exists which justifies a higher epoch than the malicious
chain, that chain will take precedence and revive any poisoned store. Such a
chain, if imported before the malicious chain, will prevent the store from
being poisoned. Therefore, the poisoning attack is temporary if >= 2/3rds of
the network is honest and non-faulty.

The `SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY` parameter assumes that the network
will justify a honest chain within some number of slots. With this assumption,
it is acceptable to optimistically import transition blocks during the sync
process. Since there is an assumption that an honest chain with a higher
justified checkpoint exists, any fork choice poisoning will be short-lived and
resolved before that node is required to produce a block.

However, the assumption that the honest, canonical chain will always justify
within `SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY` slots is dubious. Therefore,
clients MUST provide the following command line flag to assist with manual
disaster recovery:

- `--safe-slots-to-import-optimistically`: modifies the
	`SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY`.

## Checkpoint Sync (Weak Subjectivity Sync)

A consensus engine MAY assume that the `ExecutionPayload` of a block used as an
anchor for checkpoint sync is `VALID` without necessarily providing that
payload to an execution engine.

## Validator assignments

An optimistic node is *not* a full node. It is unable to produce blocks, since
an execution engine cannot produce a payload upon an unknown parent. It cannot
faithfully attest to the head block of the chain, since it has not fully
verified that block.

### Block Production

An optimistic validator MUST NOT produce a block (i.e., sign across the
`DOMAIN_BEACON_PROPOSER` domain).

### Attesting

An optimistic validator MUST NOT participate in attestation (i.e., sign across the
`DOMAIN_BEACON_ATTESTER`, `DOMAIN_SELECTION_PROOF` or
`DOMAIN_AGGREGATE_AND_PROOF` domains).

### Participating in Sync Committees

An optimistic validator MUST NOT participate in sync committees (i.e., sign across the
`DOMAIN_SYNC_COMMITTEE`, `DOMAIN_SYNC_COMMITTEE_SELECTION_PROOF` or
`DOMAIN_CONTRIBUTION_AND_PROOF` domains).

## Ethereum Beacon APIs

Consensus engines which provide an implementation of the [Ethereum Beacon
APIs](https://github.com/ethereum/beacon-APIs) must take care to ensure the
`execution_optimistic` value is set to `True` whenever the request references
optimistic blocks (and vice-versa).

## Design Decision Rationale

### Why `SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY`?

Nodes can only import an optimistic block if their justified checkpoint is
verified or the block is older than `SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY`.

These restraints are applied in order to mitigate an attack where a block which
enables execution (a *transition block*) can reference a junk parent hash. This
makes it impossible for honest nodes to build atop that block. If an attacker
exploits a nuance in fork choice `filter_block_tree`, they can, in some rare
cases, produce a junk block that out-competes all locally produced blocks for
the head. This prevents a node from producing a chain of blocks, therefore
breaking liveness.

Thankfully, if 2/3rds of validators are not poisoned, they can justify an
honest chain which will un-poison all other nodes.

Notably, this attack only exists for optimistic nodes. Nodes which fully verify
the transition block will reject a block with a junk parent hash. Therefore,
liveness is unaffected if a vast majority of nodes have fully synced execution
and consensus clients before and during the transition.

Given all of this, we can say two things:

1. **BNs which are following the head during the transition shouldn't
   optimistically import the transition block.** If 1/3rd of validators
   optimistically import the poison block, there will be no remaining nodes to
   justify an honest chain.
2. **BNs which are syncing can optimistically import transition blocks.** In
   this case a justified chain already exists blocks. The poison block would be
   quickly reverted and would have no affect on liveness.

Astute readers will notice that (2) contains a glaring assumption about network
liveness. This is necessary because a node cannot feasibly ascertain that the
transition block is justified without importing that block and risking
poisoning. Therefore, we use `SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY` to say
something along the lines of: *"if the transition block is sufficiently old
enough, then we can just assume that block is honest or there exists an honest
justified chain to out-compete it."*

Note the use of "feasibly" in the previous paragraph. One can imagine
mechanisms to check that a block is justified before importing it. For example,
just keep processing blocks without adding them to fork choice.  However, there
are still edge-cases here (e.g., when to halt and declare there was no
justification?) and how to mitigate implementation complexity.  At this point,
it's important to reflect on the attack and how likely it is to happen. It
requires some rather contrived circumstances and it seems very unlikely to
occur.  Therefore, we need to consider if adding complexity to avoid an
unlikely attack increases or decreases our total risk. Presently, it appears
that `SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY` sits in a sweet spot for this
trade-off.

### Transitioning from VALID -> INVALIDATED or INVALIDATED -> VALID

These operations are purposefully omitted. It is outside of the scope of the
specification since it's only possible with a faulty EE.

Such a scenario requires manual intervention.

## What about Light Clients?

An alternative to optimistic sync is to run a light client inside/alongside
beacon nodes that mitigates the need for optimistic sync by providing
tip-of-chain blocks to the execution engine. However, light clients comes with
their own set of complexities. Relying on light clients may also restrict nodes
from syncing from genesis, if they so desire.

A notable thing about optimistic sync is that it's *optional*. Should an
implementation decide to go the light-client route, then they can just ignore
optimistic sync all together.

## What if `TERMINAL_BLOCK_HASH` is used?

If the terminal block hash override is used (i.e., `TERMINAL_BLOCK_HASH !=
Hash32()`), the [`validate_merge_block`](../specs/bellatrix/fork-choice.md#validate_merge_block)
function will deterministically
return `True` or `False`. Whilst it's not *technically* required
retrospectively call [`validate_merge_block`](../specs/bellatrix/fork-choice.md#validate_merge_block)
on a transition block that
matches `TERMINAL_BLOCK_HASH` after an optimistic sync, doing so will have no
effect. For simplicity, the optimistic sync specification does not define
edge-case behaviour for when `TERMINAL_BLOCK_HASH` is used.
