# EIP-8198 -- Beacon Chain Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `get_slot_component_duration_ms`](#modified-get_slot_component_duration_ms)

<!-- mdformat-toc end -->

## Introduction

EIP-8198 uses `SLOT_DURATION_SCHEDULE` to map wall-clock time to slots across
historical slot durations. Deadline helpers convert the inherited basis-point
configuration into millisecond offsets using the slot duration at
`EIP8198_FORK_EPOCH`. Later forks that change slot duration or duty timing MUST
define their own deadline rules.

*Note*: This specification is built upon [Heze](../../heze/fork-choice.md).

## Helpers

### Modified `get_slot_component_duration_ms`

```python
def get_slot_component_duration_ms(basis_points: Uint64) -> Uint64:
    """
    Calculate a slot component's duration using this fork's slot duration.
    """
    # [Modified in EIP8198]
    return basis_points * get_slot_duration_ms(EIP8198_FORK_EPOCH) // BASIS_POINTS
```
