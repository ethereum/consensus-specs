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

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Slot timing

Validators MUST schedule duties against the piecewise timeline given by
`compute_time_at_slot_ms`, and use the deadline configuration of the fork
governing each duty. The duration history does not define historical deadlines.
Duty schedulers MUST keep millisecond precision, since deadlines are not
generally whole seconds.

### Data availability retention

The data-column sidecar retention window is defined by
`MIN_BLOB_DATA_RETENTION_MS`. Validators MUST retain and serve sidecars from
`max(get_blob_data_retention_start(current_epoch), FULU_FORK_EPOCH)` through the
current epoch. They MAY prune sidecars from earlier epochs. This replaces the
inherited epoch-count retention and pruning guidance; see the EIP-8198
networking document for the time-based cutoff.
