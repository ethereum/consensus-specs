# Capella -- Fork Choice

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [`notify_forkchoice_updated`](#notify_forkchoice_updated)
- [Helpers](#helpers)
  - [Extended `PayloadAttributes`](#extended-payloadattributes)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice according to the Capella upgrade.

Unless stated explicitly, all prior functionality from [Bellatrix](../bellatrix/fork-choice.md) is inherited.

## Custom types

## Protocols

### `ExecutionEngine`

*Note*: The `notify_forkchoice_updated` function is modified in the `ExecutionEngine` protocol at the Capella upgrade.

#### `notify_forkchoice_updated`

The only change made is to the `PayloadAttributes` container through the addition of `withdrawals`.
Otherwise, `notify_forkchoice_updated` inherits all prior functionality.

```python
def notify_forkchoice_updated(self: ExecutionEngine,
                              head_block_hash: Hash32,
                              safe_block_hash: Hash32,
                              finalized_block_hash: Hash32,
                              payload_attributes: Optional[PayloadAttributes]) -> Optional[PayloadId]:
    ...
```

## Helpers

### Extended `PayloadAttributes`

`PayloadAttributes` is extended with the `withdrawals` field.

```python
@dataclass
class PayloadAttributes(object):
    timestamp: uint64
    prev_randao: Bytes32
    suggested_fee_recipient: ExecutionAddress
    withdrawals: Sequence[Withdrawal]  # [New in Capella]
```
