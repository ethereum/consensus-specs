# EIP-8198 -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Slot timing](#slot-timing)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Sidecar retention](#sidecar-retention)

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

### Block and sidecar proposal

#### Sidecar retention

The data column sidecar retention period is modified to
`MIN_BLOB_DATA_RETENTION_MS` milliseconds.
