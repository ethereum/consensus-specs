# Optimistic Sync

## Introduction

In order to provide a syncing execution engine with a (partially-verified) view
of the head of the chain, it may be desirable for a consensus engine to import
beacon blocks without verifying the execution payloads. This partial sync is
called an *optimistic sync*.

## Mechanisms

To perform an optimistic sync:

- The `execute_payload` function MUST return `True` if the execution
	engine returns SYNCING or VALID. An INVALID response MUST return `False`.
- The `validate_merge_block` function MUST NOT raise an assertion if both the
	`pow_block` and `pow_parent` are unknown to the execution engine.

In addition to these changes to validation, the consensus engine MUST be able
to ascertain, after import, which blocks returned SYNCING and which returned
VALID. This document will assume consensus engines store the following sets:

- `valid_roots: Set[Root]`: `hash_tree_root(block)` where
	`block.body.execution_payload` is known to be VALID.
- `optimistic_roots: Set[Root]`: `hash_tree_root(block)` where
	`block.body.execution_payload` is known to be SYNCING.

Notably, `optimistic_roots` only includes blocks which have execution enabled
whilst `valid_roots` contains blocks *with or without* execution enabled (i.e.,
all blocks).

A consensus engine MUST be able to retrospectively (i.e., after import) modify
the status of SYNCING blocks to be either VALID or INVALID based upon responses
from an execution engine. I.e., perform the following transitions:

- SYNCING -> VALID
- SYNCING -> INVALID

When a block transitions from SYNCING -> VALID, all *ancestors* of the block MUST
also transition from SYNCING -> VALID.

When a block transitions from SYNCING -> INVALID, all *descendants* of the
block MUST also transition from SYNCING -> INVALID.

## Fork Choice

Consensus engines MUST support removing blocks that transition from SYNCING to
INVALID. Specifically, an INVALID block MUST NOT be included in the canonical
chain and the weights from INVALID blocks MUST NOT be applied to any VALID or
SYNCING ancestors.

## Validator assignments

An entirely optimistically synced node is *not* a full node. It is unable to
produce blocks, since an execution engine cannot produce a payload upon an
unknown parent. It cannot faithfully attest to the head block of the chain,
since it has not fully verified that block.

Let `head_block: BeaconBlock` be the result of calling of the fork choice
algorithm at the time of block production. Let `justified_block: BeaconBlock`
be the latest current justified ancestor ancestor of the `head_block`.

```python
def is_optimistic(block: BeaconBlock) -> bool:
	hash_tree_root(block) in optimistic_roots
```

```python
def latest_valid_ancestor(block: BeaconBlock) -> Optional[BeaconBlock]:
	while block.parent_root != Root():
		if not is_optimistic(block):
			return block
		block = get_block(block.parent_root)

	return None
```

Let a node which returns `is_optimistic(head) == True` be an *optimistic
node*. Let a validator on an optimistic node be an *optimistic validator*.

### Block production

A optimistic validator MUST NOT produce a block (i.e., sign across the
`DOMAIN_BEACON_PROPOSER` domain), unless one of the follow exceptions are met:

#### Exception 1.

If the justified block is fully verified (i.e., `not
is_optimistic(justified_block)`, the validator MUST produce a block upon
`latest_valid_ancestor(head)`.

### Attesting

An optimistic validator MUST NOT participate in attestation (i.e., sign across the
`DOMAIN_BEACON_ATTESTER`, `DOMAIN_SELECTION_PROOF` or
`DOMAIN_AGGREGATE_AND_PROOF` domains), unless one of the follow exceptions are
met:

#### Exception

#### Exception 1.

If a validator *does not* have an optimistic head (i.e., `not
is_optimistic(head_block)`), the node is *fully synced*.
The validator may produce an attestation.
