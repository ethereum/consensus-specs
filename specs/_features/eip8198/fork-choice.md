# EIP-8198 -- Beacon Chain Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `get_slot_component_duration_ms`](#modified-get_slot_component_duration_ms)

<!-- mdformat-toc end -->

## Introduction

EIP-8198 uses `get_slot_schedule` to map wall-clock time to slots across
historical slot durations. Deadline helpers convert the inherited basis-point
configuration into millisecond offsets using `SLOT_DURATION_MS_EIP8198`. Later
forks that change slot duration or duty timing MUST define their own deadline
rules.

*Note*: This specification is built upon [Heze](../../heze/fork-choice.md).

## Helpers

### Modified `get_slot_component_duration_ms`

```python
def get_slot_component_duration_ms(basis_points: Uint64) -> Uint64:
    """
    Calculate a slot component's duration using this fork's slot duration.
    """
    # [Modified in EIP8198]
    return basis_points * SLOT_DURATION_MS_EIP8198 // BASIS_POINTS
```
