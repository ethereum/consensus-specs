# EIP-6110 -- Honest Validator

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Block proposal](#block-proposal)
  - [Deposits](#deposits)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement EIP-6110.

## Prerequisites

This document is an extension of the [Deneb -- Honest Validator](../../deneb/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [EIP-6110](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Block proposal

### Deposits

The expected number of deposits MUST be changed from `min(MAX_DEPOSITS, eth1_data.deposit_count - state.eth1_deposit_index)` to the result of the following function:

```python
def get_eth1_deposit_count(state: BeaconState) -> uint64:
    eth1_deposit_index_limit = min(state.eth1_data.deposit_count, state.deposit_receipts_start_index)
    if state.eth1_deposit_index < eth1_deposit_index_limit:
        return min(MAX_DEPOSITS, eth1_deposit_index_limit - state.eth1_deposit_index)
    else:
        return uint64(0)
```
