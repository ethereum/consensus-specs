# EIP-8198 -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Slot timing](#slot-timing)
  - [Data availability retention](#data-availability-retention)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement EIP-8198.

*Note*: This specification is built upon [Heze](../../heze/validator.md).

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Slot timing

Validators MUST schedule duties against the piecewise timeline given by
`compute_time_at_slot_ms`: each era of `SLOT_DURATION_SCHEDULE` runs at its own
slot duration, starting from the end of the previous era. Intra-slot deadlines
rescale automatically through the modified `get_slot_component_duration_ms`, so
each duty keeps its relative position in the slot. Duty schedulers MUST keep
millisecond precision, since deadlines are not generally whole seconds.

### Data availability retention

The lower bounds of the blob and data-column sidecar retention windows in the
inherited retention guidance are
`get_blob_sidecars_retention_start(current_epoch)` and
`get_data_column_sidecars_retention_start(current_epoch)`, respectively (see the
EIP-8198 networking document).
