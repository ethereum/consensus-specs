# Fork Choice -- Safe Block

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [`get_safe_beacon_block`](#get_safe_beacon_block)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

Under honest majority and certain network synchronicity assumptions
there exist a block that is safe from re-orgs. Normally this block is
pretty close to the head of canonical chain which makes it valuable
to expose a safe block to users.

This section describes an algorithm to find a safe block.

## `get_safe_beacon_block`

```python
def get_safe_beacon_block(store: Store) -> Root:
    # Use most recent justified block as a stopgap
    return store.justified_checkpoint.root
```
*Note*: Currently safe block algorithm simply returns `store.justified_checkpoint.root`
and is meant to be improved in the future.
