# EIP-6914 -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Fork choice](#fork-choice)
  - [Handlers](#handlers)
    - [`on_reused_index`](#on_reused_index)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork choice according to EIP-6914.

## Fork choice

A new handler is added with this upgrade:

- `on_reused_index(store, index)` whenever a validator index
  `index: ValidatorIndex` is reused. That is,
  [`get_index_for_new_validator()`](./beacon-chain.md#get_index_for_new_validator)
  provides an index due to a return value of `True` from
  [`is_reusable_validator()`](./beacon-chain.md#is_reusable_validator).

This new handler is used to update the list of equivocating indices to be
synchronized with the canonical chain.

### Handlers

#### `on_reused_index`

```python
def on_reused_index(store: Store, index: ValidatorIndex) -> None:
    store.equivocating_indices.discard(index)
```
