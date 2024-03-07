# EIP-7547 -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Preset](#preset)
  - [Execution](#execution)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [Request data](#request-data)
      - [Extended `PayloadAttributes`](#extended-payloadattributes)
    - [Engine APIs](#engine-apis)
      - [Extended `notify_forkchoice_updated`](#extended-notify_forkchoice_updated)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice accompanying the EIP7547 upgrade.

## Preset

### Execution

| Name | Value |
| - | - |
| `MAX_TRANSACTIONS_PER_INCLUSION_LIST` |  `uint64(2**4)` (= 16) |

## Protocols

### `ExecutionEngine`

#### Request data

##### Extended `PayloadAttributes`

`PayloadAttributes` is extended with the inclusion list transactions that are passed from the CL to the EL when requesting block construction. We change the content of `notify_forkchoice_updated` accordingly.

```python
@dataclass
class PayloadAttributes(object):
    timestamp: uint64
    prev_randao: Bytes32
    suggested_fee_recipient: ExecutionAddress
    withdrawals: Sequence[Withdrawal]
    parent_beacon_block_root: Root
    inclusion_list_transactions: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST]  # [New in EIP7547]
```

#### Engine APIs

##### Extended `notify_forkchoice_updated`

The only change made is to the `PayloadAttributes` container with the extended `PayloadAttributes`.
Otherwise, `notify_forkchoice_updated` inherits all prior functionality.