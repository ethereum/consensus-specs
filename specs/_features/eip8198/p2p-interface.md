# EIP-8198 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configs](#configs)
- [Modifications in EIP-8198](#modifications-in-eip-8198)
  - [Helpers](#helpers)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
    - [New `compute_blob_data_retention_start_epoch`](#new-compute_blob_data_retention_start_epoch)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Status v2](#status-v2)
    - [DataColumnSidecarsByRange v1](#datacolumnsidecarsbyrange-v1)
    - [DataColumnSidecarsByRoot v1](#datacolumnsidecarsbyroot-v1)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-8198.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

*Note*: This specification is built upon [Heze](../../heze/p2p-interface.md).

## Configs

| Name                         |                Value |
| ---------------------------- | -------------------: |
| `MIN_BLOB_DATA_RETENTION_MS` | `Uint64(1572864000)` |

*Note*: `MIN_BLOB_DATA_RETENTION_MS` replaces
`MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS` with the same duration, defined
in wall-clock time rather than epochs.

## Modifications in EIP-8198

### Helpers

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIP8198_FORK_EPOCH:
        return EIP8198_FORK_VERSION
    if epoch >= HEZE_FORK_EPOCH:
        return HEZE_FORK_VERSION
    if epoch >= GLOAS_FORK_EPOCH:
        return GLOAS_FORK_VERSION
    if epoch >= FULU_FORK_EPOCH:
        return FULU_FORK_VERSION
    if epoch >= ELECTRA_FORK_EPOCH:
        return ELECTRA_FORK_VERSION
    if epoch >= DENEB_FORK_EPOCH:
        return DENEB_FORK_VERSION
    if epoch >= CAPELLA_FORK_EPOCH:
        return CAPELLA_FORK_VERSION
    if epoch >= BELLATRIX_FORK_EPOCH:
        return BELLATRIX_FORK_VERSION
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

#### New `compute_blob_data_retention_start_epoch`

```python
def compute_blob_data_retention_start_epoch(epoch: Epoch) -> Epoch:
    """
    Return the start epoch of the blob data retention window,
    preserving its wall-clock length across slot duration changes.
    """
    window_ms = MIN_BLOB_DATA_RETENTION_MS
    current_start_slot = compute_start_slot_at_epoch(epoch)
    current_start_ms = compute_time_at_slot_ms(Uint64(0), current_start_slot)
    if current_start_ms < window_ms:
        return GENESIS_EPOCH
    window_start_ms = Uint64(current_start_ms - window_ms)
    return compute_epoch_at_slot(compute_slot_at_time_ms(Uint64(0), window_start_ms))
```

### The gossip domain: gossipsub

Each duration schedule entry after genesis MUST coincide with a network upgrade
at or after `EIP8198_FORK_EPOCH`. Clients SHOULD subscribe to the new
fork-digest topics ahead of the upgrade epoch and unsubscribe from the old
topics after it.

Durations defined in slots or epochs MUST use the piecewise timeline
(`compute_time_at_slot_ms` / `compute_slot_at_time_ms`). For example, the
gossipsub `seen_ttl` is the difference between the start times of
`current_slot + 2 * SLOTS_PER_EPOCH` and `current_slot`, converted to seconds
with `milliseconds_to_seconds`. Duty schedulers and the light-client local-clock
`current_slot` MUST also use this timeline. Durations configured in
milliseconds, including data column sidecar retention, remain fixed in
wall-clock time.

### The Req/Resp domain

#### Status v2

**Protocol ID:** `/eth2/beacon_chain/req/status/2/`

*[Modified in EIP8198]* The data column sidecar retention period used to
determine `earliest_available_slot` begins at epoch
`max(compute_blob_data_retention_start_epoch(current_epoch), FULU_FORK_EPOCH)`.

#### DataColumnSidecarsByRange v1

**Protocol ID:** `/eth2/beacon_chain/req/data_column_sidecars_by_range/1/`

*[Modified in EIP8198]* The `data_column_serve_range` is modified to
`[max(compute_blob_data_retention_start_epoch(current_epoch), FULU_FORK_EPOCH), current_epoch]`.

#### DataColumnSidecarsByRoot v1

**Protocol ID:** `/eth2/beacon_chain/req/data_column_sidecars_by_root/1/`

*[Modified in EIP8198]* The `data_column_serve_range` is modified to
`[max(compute_blob_data_retention_start_epoch(current_epoch), FULU_FORK_EPOCH), current_epoch]`.
