# Altair -- Fork Choice

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [New fork-choice helpers](#new-fork-choice-helpers)
  - [New `get_sync_message_due_ms`](#new-get_sync_message_due_ms)
  - [New `get_contribution_due_ms`](#new-get_contribution_due_ms)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork choice according to the Altair upgrade.

Unless stated explicitly, all prior functionality from
[Phase0](../phase0/fork-choice.md) is inherited.

## New fork-choice helpers

#### New `get_sync_message_due_ms`

```python
def get_sync_message_due_ms(epoch: Epoch) -> uint64:
    return get_slot_component_duration_ms(SYNC_MESSAGE_DUE_BPS)
```

#### New `get_contribution_due_ms`

```python
def get_contribution_due_ms(epoch: Epoch) -> uint64:
    return get_slot_component_duration_ms(CONTRIBUTION_DUE_BPS)
```
