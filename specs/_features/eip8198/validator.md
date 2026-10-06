# EIP-8198 -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Sidecar retention](#sidecar-retention)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement EIP-8198.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

*Note*: Validators MUST schedule duties through the updated
`get_slot_component_duration_ms`.

### Block and sidecar proposal

#### Sidecar retention

The data column sidecar retention period is modified to
`MIN_BLOB_DATA_RETENTION_MS` milliseconds.
