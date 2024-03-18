# EIP-7547 -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [New `verify_inclusion_list`](#new-verify_inclusion_list)
  - [New `is_inclusion_list_available`](#new-is_inclusion_list_available)
- [New fork-choice handlers](#new-fork-choice-handlers)
  - [New `on_inclusion_list`](#new-on_inclusion_list)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice accompanying EIP-7547.

## Helpers

### New `verify_inclusion_list`

```python
def verify_inclusion_list(state: BeaconState, block: BeaconBlock, inclusion_list: InclusionList,
                          execution_engine: ExecutionEngine) -> bool:
    """
    returns true if the inclusion list is valid. 
    """
    # Check that the inclusion list corresponds to the block proposer
    signed_summary = inclusion_list.signed_summary
    proposer_index = signed_summary.message.proposer_index
    assert block.proposer_index == proposer_index

    # Check that the signature is correct
    assert verify_inclusion_list_summary_signature(state, signed_summary)

    # Check that the inclusion list is valid
    return execution_engine.verify_and_notify_new_inclusion_list(NewInclusionListRequest(
        inclusion_list=inclusion_list.transactions, 
        summary=inclusion_list.signed_summary.message.summary,
        parent_block_hash=state.latest_execution_payload_header.block_hash,
    ))
```

### New `is_inclusion_list_available`

```python
def is_inclusion_list_available(self: ExecutionEngine, new_payload_request: NewPayloadRequest) -> bool:
    """
    Return ``True`` if and only if the payload has a corresponding inclusion list.
    """
    ...
```

## New fork-choice handlers

### New `on_inclusion_list`

A new handler to be called when a new inclusion list is received.

```python
def on_inclusion_list(store: Store, signed_block_and_inclusion_list: InclusionList) -> None:
    """
    Run ``on_inclusion_list`` upon receiving a new inclusion lit.
    """
    # [New in EIP-7547] Get block and inclusion list from the gossip message.
    signed_block = signed_block_and_inclusion_list.signed_block
    signed_inclusion_list = signed_block_and_inclusion_list.signed_inclusion_list
    block = signed_block.message
    
    # [New in EIP-7547] Check if the inclusion list is valid.
    state = pre_state.copy()
    assert verify_inclusion_list(state, block, signed_inclusion_list.signed_summary, block.parent_root)
```