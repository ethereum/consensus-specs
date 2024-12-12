# Electra -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Containers](#containers)
- [Helpers](#helpers)
  - [Extended `PayloadAttributes`](#extended-payloadattributes)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice accompanying the Electra upgrade.

## Containers

## Helpers

### Extended `PayloadAttributes`

*Note*: `PayloadAttributes` is extended with the target/maximum number of blobs per block.

```python
@dataclass
class PayloadAttributes(object):
    timestamp: uint64
    prev_randao: Bytes32
    suggested_fee_recipient: ExecutionAddress
    withdrawals: Sequence[Withdrawal]
    parent_beacon_block_root: Root
```
