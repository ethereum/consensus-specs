# EIP-7547 -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Presets](#presets)
  - [Time parameters](#time-parameters)
- [Containers](#containers)
    - [`InclusionList`](#inclusionlist)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [Request data](#request-data)
      - [Extended `PayloadAttributes`](#extended-payloadattributes)
      - [New `NewInclusionListRequest`](#new-newinclusionlistrequest)
    - [Engine APIs](#engine-apis)
      - [Extended `notify_forkchoice_updated`](#extended-notify_forkchoice_updated)
      - [New `notify_new_inclusion_list`](#new-notify_new_inclusion_list)
- [Helpers](#helpers)
  - [`verify_inclusion_list_summary_signature`](#verify_inclusion_list_summary_signature)
  - [`verify_inclusion_list`](#verify_inclusion_list)
  - [`is_inclusion_list_available`](#is_inclusion_list_available)
- [Updated fork-choice handlers](#updated-fork-choice-handlers)
  - [`on_block`](#on_block)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice accompanying the EIP7547 upgrade.

## Presets

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `MIN_SLOTS_FOR_INCLUSION_LISTS_REQUESTS` | `uint64(2)` | slots | 24 seconds |

## Containers

#### `InclusionList`

```python
class InclusionList(Container):
    summary: SignedInclusionListSummary
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST]
```

## Protocols

### `ExecutionEngine`

#### Request data

##### Extended `PayloadAttributes`

`PayloadAttributes` is extended with the parent beacon block root for EIP7547. It changes the content of `notify_forkchoice_updated` accordingly.

```python
@dataclass
class PayloadAttributes(object):
    timestamp: uint64
    prev_randao: Bytes32
    suggested_fee_recipient: ExecutionAddress
    withdrawals: Sequence[Withdrawal]
    parent_beacon_block_root: Root
    inclusion_list_summary: List[InclusionListSummaryEntry, MAX_TRANSACTIONS_PER_INCLUSION_LIST]  # [New in EIP7547]
```

##### New `NewInclusionListRequest`

```python
@dataclass
class NewInclusionListRequest(object):
    inclusion_list: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST]
    summary: List[InclusionListSummaryEntry, MAX_TRANSACTIONS_PER_INCLUSION_LIST]
    parent_block_hash: Hash32
```

#### Engine APIs

##### Extended `notify_forkchoice_updated`

The only change made is to the `PayloadAttributes` container with the extended `PayloadAttributes`.
Otherwise, `notify_forkchoice_updated` inherits all prior functionality.

##### New `notify_new_inclusion_list`

```python
def notify_new_inclusion_list(self: ExecutionEngine,
                              inclusion_list_request: NewInclusionListRequest) -> bool:
    """
    Return ``True`` if and only if the transactions in the inclusion list can be successfully executed
    starting from the execution state corresponding to the `parent_block_hash` in the inclusion list
    summary. The execution engine also checks that the total gas limit is less or equal that
    ``MAX_GAS_PER_INCLUSION_LIST``, and the transactions in the list of transactions correspond
    to the signed summary
    """
    ...
```

## Helpers

### `verify_inclusion_list_summary_signature`

```python
def verify_inclusion_list_summary_signature(state: BeaconState, signed_summary: SignedInclusionListSummary) -> bool:
    # TODO: do we need a new domain?
    summary = signed_summary.message
    signing_root = compute_signing_root(summary, get_domain(state, DOMAIN_BEACON_PROPOSER))
    proposer = state.validators[summary.proposer_index]
    return bls.Verify(proposer.pubkey, signing_root, signed_summary.signature)
```

### `verify_inclusion_list`

```python
def verify_inclusion_list(state: BeaconState, block: BeaconBlock,
                          inclusion_list: InclusionList, execution_engine: ExecutionEngine) -> bool:
    """
    Returns true if the inclusion list is valid. 
    """
    # Check that the inclusion list corresponds to the block proposer
    signed_summary = inclusion_list.summary
    proposer_index = signed_summary.message.proposer_index
    assert block.proposer_index == proposer_index

    # Check that the signature is correct
    assert verify_inclusion_list_summary_signature(state, signed_summary)

    # TODO: These checks will also be performed by the EL surely so we can probably remove them from here.
    # Check the summary and transaction list lengths
    summary = signed_summary.message.summary
    assert len(summary) <= MAX_TRANSACTIONS_PER_INCLUSION_LIST
    assert len(inclusion_list.transactions) == len(summary)

    # TODO: These checks will also be performed by the EL surely so we can probably remove them from here.
    # Check that the total gas limit is bounded
    total_gas_limit = sum(entry.gas_limit for entry in summary)
    assert total_gas_limit <= MAX_GAS_PER_INCLUSION_LIST

    # Check that the inclusion list is valid
    return execution_engine.notify_new_inclusion_list(NewInclusionListRequest(
        inclusion_list=inclusion_list.transactions, 
        summary=inclusion_list.summary.message.summary,
        parent_block_hash=state.latest_execution_payload_header.block_hash,
    ))
```

### `is_inclusion_list_available`

```python
def is_inclusion_list_available(state: BeaconState, block: BeaconBlock) -> bool:
    """
    Returns whether one inclusion list for the corresponding block was seen in full and has been validated. 
    `retrieve_inclusion_list` is implementation and context dependent
    It returns one inclusion list that was broadcasted during the given slot by the given proposer. 

    Note: the p2p network does not guarantee sidecar retrieval outside of
    `MIN_SLOTS_FOR_INCLUSION_LISTS_REQUESTS`
    """
    # Verify the inclusion list
    inclusion_list = retrieve_inclusion_list(block.slot, block.proposer_index)
    return verify_inclusion_list(state, block, inclusion_list, EXECUTION_ENGINE)
```

## Updated fork-choice handlers

### `on_block`

*Note*: The only modification is the addition of the inclusion list availability check.

```python
def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    """
    Run ``on_block`` upon receiving a new block.
    """
    block = signed_block.message
    # Parent block must be known
    assert block.parent_root in store.block_states
    # Make a copy of the state to avoid mutability issues
    pre_state = copy(store.block_states[block.parent_root])
    # Blocks cannot be in the future. If they are, their consideration must be delayed until they are in the past.
    assert get_current_slot(store) >= block.slot

    # Check that block is later than the finalized epoch slot (optimization to reduce calls to get_ancestor)
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    assert block.slot > finalized_slot
    # Check block is a descendant of the finalized block at the checkpoint finalized slot
    finalized_checkpoint_block = get_checkpoint_block(
        store,
        block.parent_root,
        store.finalized_checkpoint.epoch,
    )
    assert store.finalized_checkpoint.root == finalized_checkpoint_block

    # Check if blob data is available
    # If not, this block MAY be queued and subsequently considered when blob data becomes available
    # *Note*: Extraneous or invalid Blobs (in addition to the expected/referenced valid blobs)
    # received on the p2p network MUST NOT invalidate a block that is otherwise valid and available
    assert is_data_available(hash_tree_root(block), block.body.blob_kzg_commitments)

    # Check the block is valid and compute the post-state
    state = pre_state.copy()

    # [New in EIP7547]
    # Check if there is a valid inclusion list. 
    # This check is performed only if the block's slot is within the visibility window
    # If not, this block MAY be queued and subsequently considered when a valid inclusion list becomes available
    if block.slot + MIN_SLOTS_FOR_INCLUSION_LISTS_REQUESTS >= get_current_slot(store):
        assert is_inclusion_list_available(state, block)

    block_root = hash_tree_root(block)
    state_transition(state, signed_block, True)

    # Add new block to the store
    store.blocks[block_root] = block
    # Add new state for this block to the store
    store.block_states[block_root] = state

    # Add block timeliness to the store
    time_into_slot = (store.time - store.genesis_time) % SECONDS_PER_SLOT
    is_before_attesting_interval = time_into_slot < SECONDS_PER_SLOT // INTERVALS_PER_SLOT
    is_timely = get_current_slot(store) == block.slot and is_before_attesting_interval
    store.block_timeliness[hash_tree_root(block)] = is_timely

    # Add proposer score boost if the block is timely and not conflicting with an existing block
    is_first_block = store.proposer_boost_root == Root()
    if is_timely and is_first_block:
        store.proposer_boost_root = hash_tree_root(block)

    # Update checkpoints in store if necessary
    update_checkpoints(store, state.current_justified_checkpoint, state.finalized_checkpoint)

    # Eagerly compute unrealized justification and finality.
    compute_pulled_up_tip(store, block_root)
```
