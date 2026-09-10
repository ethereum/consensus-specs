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
`compute_time_at_slot_ms`, and MUST call the deadline helpers with the duty's
slot, whose schedule entry determines its deadlines. Duty schedulers MUST keep
millisecond precision, since deadlines are not generally whole seconds.

### Data availability retention

The lower bound of the data-column sidecar retention window in the inherited
retention guidance is
`max(get_data_column_sidecars_retention_start(current_epoch), FULU_FORK_EPOCH)`
(see the EIP-8198 networking document).
