# FOCIL -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [New `evaluate_inclusion_summary_aggregates`](#new-evaluate_inclusion_summary_aggregates)
  - [Modified `Store`](#modified-store)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice accompanying the FOCIL upgrade.

## Helpers

### New `evaluate_inclusion_summary_aggregates`

```python
def evaluate_inclusion_summary_aggregates(store: Store, inclusion_summary_aggregates: InclusionSummaryAggregates) -> bool:
    """
    Return ``True`` if and only if the input ``inclusion_summary_aggregates`` satifies evaluation.
    """
    ...
```

TODO: Apply `evaluate_inclusion_summary_aggregates`, which can be part of the import rule for head filtering. Where it should be applied requires further analysis, and we won't specify the design at this moment.

### Modified `Store` 
**Note:** `Store` is modified to track the seen local inclusion lists before inclusion list aggregate cutoff interval.

```python
@dataclass
class Store(object):
    time: uint64
    genesis_time: uint64
    justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    unrealized_justified_checkpoint: Checkpoint
    unrealized_finalized_checkpoint: Checkpoint
    proposer_boost_root: Root
    equivocating_indices: Set[ValidatorIndex]
    blocks: Dict[Root, BeaconBlock] = field(default_factory=dict)
    block_states: Dict[Root, BeaconState] = field(default_factory=dict)
    block_timeliness: Dict[Root, boolean] = field(default_factory=dict)
    checkpoint_states: Dict[Checkpoint, BeaconState] = field(default_factory=dict)
    latest_messages: Dict[ValidatorIndex, LatestMessage] = field(default_factory=dict)
    unrealized_justifications: Dict[Root, Checkpoint] = field(default_factory=dict)
    inclusion_summary_aggregates: Dict[Root, InclusionSummaryAggregates] = field(default_factory=dict)  # [New in FOCIL]
    

### New `on_local_inclusion_list`

`on_local_inclusion_list` is called to import `signed_local_inclusion_list` to the fork choice store.

```python
def on_local_inclusion_list(
        store: Store, signed_inclusion_list: SignedLocalInclusionList) -> None:
    """
    ``on_local_inclusion_list`` verify the inclusion list before import it to fork choice store.
    """
    message = signed_inclusion_list.message
    # Verify inclusion list slot is bouded to the current slot
    assert get_current_slot(store) != message.slot

    state = store.block_states[message.beacon_block_root]
    ilc = get_inclusion_list_committee(state, message.slot)
    # Verify inclusion list validator is part of the committee
    assert message.validator_index in ilc
   
    # Verify inclusion list signature
    assert is_valid_local_inclusion_list_signature(state, signed_inclusion_list) 

    parent_hash = message.parent_hash

    aggregates = InclusionSummaryAggregate()
    store.inclusion_summary_aggregates[parent_hash] = aggregate
```