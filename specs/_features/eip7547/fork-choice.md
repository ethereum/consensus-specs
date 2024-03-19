# EIP-7547 -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [New `is_inclusion_list_available`](#new-is_inclusion_list_available)
- [New fork-choice handlers](#new-fork-choice-handlers)
  - [New `on_inclusion_list`](#new-on_inclusion_list)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice accompanying EIP-7547.

## Helpers

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
def on_inclusion_list(store: Store, inclusion_list: InclusionList) -> None:
    """
    Run ``on_inclusion_list`` upon receiving a new inclusion lit.
    """

    # [New in EIP-7547] Check if the inclusion list is valid.
    state = pre_state.copy()
    assert execution_engine.verify_and_notify_new_inclusion_list(inclusion_list)
```