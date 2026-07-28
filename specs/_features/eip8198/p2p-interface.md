# EIP-8198 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in EIP-8198](#modifications-in-eip-8198)
  - [Helpers](#helpers)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
    - [Modified `compute_time_at_slot_ms`](#modified-compute_time_at_slot_ms)
  - [Time-sensitive parameters](#time-sensitive-parameters)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [The Req/Resp domain](#the-reqresp-domain)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-8198.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

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

#### Modified `compute_time_at_slot_ms`

*Note*: This is the millisecond counterpart of the modified
`compute_time_at_slot` (see the beacon chain document): slots after
`EIP8198_FORK_EPOCH` start at `SLOT_DURATION_MS_EIP8198` intervals from the fork
time, not at `SLOT_DURATION_MS` intervals from genesis. The gossip validation
gates `is_not_from_future_slot` and `is_within_slot_range` are defined in terms
of this function and inherit the corrected timeline without further changes.
Without this override, honest messages would be rejected as coming from the
future by an ever-growing margin after the fork.

```python
def compute_time_at_slot_ms(state: BeaconState, slot: Slot) -> Uint64:
    """
    Return the time in milliseconds at the start of the given slot.
    """
    slots_since_genesis = slot - GENESIS_SLOT
    if EIP8198_FORK_EPOCH == FAR_FUTURE_EPOCH:
        return Uint64(state.genesis_time * 1000 + slots_since_genesis * SLOT_DURATION_MS)
    fork_slot = EIP8198_FORK_EPOCH * SLOTS_PER_EPOCH
    if slot < fork_slot:
        return Uint64(state.genesis_time * 1000 + slots_since_genesis * SLOT_DURATION_MS)
    time_before_fork_ms = fork_slot * SLOT_DURATION_MS
    time_after_fork_ms = (slots_since_genesis - fork_slot) * SLOT_DURATION_MS_EIP8198
    return Uint64(state.genesis_time * 1000 + time_before_fork_ms + time_after_fork_ms)
```

### Time-sensitive parameters

EIP-8198 changes no networking constant values. The following notes fix how the
existing constants are to be interpreted under the shorter slot:

- `ATTESTATION_PROPAGATION_SLOT_RANGE` remains `32` slots. It is kept
  slot-denominated because it is aligned with the consensus structure (one epoch
  plus margin); its wall-clock duration therefore shrinks from 384 to 320
  seconds on mainnet. This is a deliberate choice, not an omission.
- `MAXIMUM_GOSSIP_CLOCK_DISPARITY` and the Req/Resp timeouts (`TTFB_TIMEOUT`,
  `RESP_TIMEOUT`) are absolute wall-clock allowances and MUST NOT be rescaled.
- The gossipsub `seen_ttl` parameter is defined by the formula
  `SLOTS_PER_EPOCH * SLOT_DURATION_MS / 1000 / heartbeat_interval`; after the
  fork, `SLOT_DURATION_MS_EIP8198` replaces `SLOT_DURATION_MS` in this formula
  so that the cache keeps covering two epochs.

### The gossip domain: gossipsub

EIP-8198 adds no message types and modifies no gossip validation conditions
beyond the timeline change in `compute_time_at_slot_ms` above. All topics carry
over from Heze, re-keyed under the EIP-8198 fork digest (derived from
`EIP8198_FORK_VERSION` via the modified `compute_fork_version`). As with
previous upgrades, clients SHOULD subscribe to the new-digest topics ahead of
the fork epoch and unsubscribe from the old-digest topics after it, following
the usual fork transition practice.

### The Req/Resp domain

Request and response message types are unchanged from Heze. The blob and
data-column sidecar retention windows used by the sidecar request validations
(`MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS` and
`MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS`) are rescaled together with the
fork epoch as described in the Data availability section of the beacon chain
document.
