# Altair -- Beacon Chain Fork Choice

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Fork choice](#fork-choice)
  - [Constants](#constants)
    - [Duration identifiers](#duration-identifiers)
  - [Helpers](#helpers)
    - [Modified `get_duration_ms`](#modified-get_duration_ms)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork choice according to the Altair upgrade.

Unless stated explicitly, all prior functionality from
[Phase 0](../phase0/fork-choice.md) is inherited.

## Fork choice

### Constants

#### Duration identifiers

| Name                           | Value           |
| ------------------------------ | --------------- |
| `DURATION_ID_SYNC_MESSAGE_DUE` | `DurationId(4)` |
| `DURATION_ID_CONTRIBUTION_DUE` | `DurationId(5)` |

### Helpers

#### Modified `get_duration_ms`

```python
def get_duration_ms(duration_id: DurationId) -> uint64:
    if duration_id == DURATION_ID_SLOT:
        return SLOT_DURATION_MS
    elif duration_id == DURATION_ID_PROPOSER_REORG_CUTOFF:
        return get_slot_component_duration_ms(PROPOSER_REORG_CUTOFF_BPS)
    elif duration_id == DURATION_ID_ATTESTATION_DUE:
        return get_slot_component_duration_ms(ATTESTATION_DUE_BPS)
    elif duration_id == DURATION_ID_AGGREGATE_DUE:
        return get_slot_component_duration_ms(AGGREGATE_DUE_BPS)
    # [New in Altair]
    elif duration_id == DURATION_ID_SYNC_MESSAGE_DUE:
        return get_slot_component_duration_ms(SYNC_MESSAGE_DUE_BPS)
    # [New in Altair]
    elif duration_id == DURATION_ID_CONTRIBUTION_DUE:
        return get_slot_component_duration_ms(CONTRIBUTION_DUE_BPS)
```
