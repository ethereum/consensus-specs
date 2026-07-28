# EIP-8198 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in EIP-8198](#modifications-in-eip-8198)
  - [Configuration](#configuration)
  - [Helpers](#helpers)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
    - [New `compute_seen_ttl`](#new-compute_seen_ttl)
    - [New `get_min_epochs_for_blob_sidecars_requests`](#new-get_min_epochs_for_blob_sidecars_requests)
    - [New `get_min_epochs_for_data_column_sidecars_requests`](#new-get_min_epochs_for_data_column_sidecars_requests)
    - [New `is_gas_limit_target_compatible_eip8198`](#new-is_gas_limit_target_compatible_eip8198)
  - [Time-sensitive parameters](#time-sensitive-parameters)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Modified `validate_bls_to_execution_change_gossip`](#modified-validate_bls_to_execution_change_gossip)
    - [Modified `execution_payload_bid`](#modified-execution_payload_bid)
  - [The Req/Resp domain](#the-reqresp-domain)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-8198.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Modifications in EIP-8198

### Configuration

| Name                                                   | Value          | Description                                                       |
| ------------------------------------------------------ | -------------- | ----------------------------------------------------------------- |
| `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS_EIP8198`        | `Uint64(6144)` | Steady-state minimum epoch range for serving blob sidecars        |
| `MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS_EIP8198` | `Uint64(6144)` | Steady-state minimum epoch range for serving data-column sidecars |

### Helpers

#### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    # [New in EIP8198]
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

#### New `compute_seen_ttl`

```python
def compute_seen_ttl(current_slot: Slot) -> Uint64:
    """
    Return the gossipsub seen-message cache duration in seconds.
    """
    end_slot = Slot(current_slot + 2 * SLOTS_PER_EPOCH)
    return compute_slot_range_duration_ms(current_slot, end_slot) // 1000
```

#### New `get_min_epochs_for_blob_sidecars_requests`

```python
def get_min_epochs_for_blob_sidecars_requests(epoch: Epoch) -> Uint64:
    if EIP8198_FORK_EPOCH == FAR_FUTURE_EPOCH:
        return MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS
    additional_epochs = (
        MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS_EIP8198 - MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS
    )
    transition_start = (
        EIP8198_FORK_EPOCH - additional_epochs
        if additional_epochs <= EIP8198_FORK_EPOCH
        else GENESIS_EPOCH
    )
    if epoch < transition_start:
        return MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS
    if epoch < EIP8198_FORK_EPOCH:
        return Uint64(MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS + epoch - transition_start)
    return MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS_EIP8198
```

#### New `get_min_epochs_for_data_column_sidecars_requests`

```python
def get_min_epochs_for_data_column_sidecars_requests(epoch: Epoch) -> Uint64:
    if EIP8198_FORK_EPOCH == FAR_FUTURE_EPOCH:
        return MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS
    additional_epochs = (
        MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS_EIP8198
        - MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS
    )
    transition_start = (
        EIP8198_FORK_EPOCH - additional_epochs
        if additional_epochs <= EIP8198_FORK_EPOCH
        else GENESIS_EPOCH
    )
    if epoch < transition_start:
        return MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS
    if epoch < EIP8198_FORK_EPOCH:
        return Uint64(MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS + epoch - transition_start)
    return MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS_EIP8198
```

#### New `is_gas_limit_target_compatible_eip8198`

```python
def is_gas_limit_target_compatible_eip8198(
    parent_gas_limit: Uint64,
    gas_limit: Uint64,
    target_gas_limit: Uint64,
    parent_execution_payload_slot: Slot,
    bid_slot: Slot,
) -> bool:
    """
    Check the bid gas limit, including the one-time EIP-8198 transition.
    """
    if EIP8198_FORK_EPOCH != FAR_FUTURE_EPOCH:
        fork_slot = compute_start_slot_at_epoch(EIP8198_FORK_EPOCH)
        if parent_execution_payload_slot < fork_slot <= bid_slot:
            expected_gas_limit = parent_gas_limit * SLOT_DURATION_MS_EIP8198 // SLOT_DURATION_MS
            return gas_limit == expected_gas_limit
    return is_gas_limit_target_compatible(parent_gas_limit, gas_limit, target_gas_limit)
```

### Time-sensitive parameters

The following rules define how time-sensitive networking parameters are
interpreted under the shorter slot:

- `ATTESTATION_PROPAGATION_SLOT_RANGE` remains `32` slots. It is kept
  slot-denominated because it is aligned with the consensus structure (one epoch
  plus margin); its wall-clock duration therefore shrinks from 384 to 256
  seconds on mainnet. This is a deliberate choice, not an omission.
- `MAXIMUM_GOSSIP_CLOCK_DISPARITY` and the Req/Resp timeouts (`TTFB_TIMEOUT`,
  `RESP_TIMEOUT`) are absolute wall-clock allowances and MUST NOT be rescaled.
- The gossipsub `seen_ttl` parameter is `compute_seen_ttl(current_slot)`. This
  covers exactly two epochs and correctly sums old- and new-duration slots when
  the window crosses the fork.
- All slot-derived schedulers, expiry windows, and gossip-scoring durations MUST
  use `compute_slot_start_time_ms` or `compute_slot_range_duration_ms`.
  Replacing `SLOT_DURATION_MS` with the post-fork value in a genesis-anchored
  formula is incorrect.

### The gossip domain: gossipsub

EIP-8198 adds no message types. The inherited gossip slot gates use the
beacon-chain document's modified `compute_time_at_slot_ms`. All topics carry
over from Heze, re-keyed under the EIP-8198 fork digest (derived from
`EIP8198_FORK_VERSION` via the modified `compute_fork_version`). As with
previous upgrades, clients SHOULD subscribe to the new-digest topics ahead of
the fork epoch and unsubscribe from the old-digest topics after it, following
the usual fork transition practice.

#### Modified `validate_bls_to_execution_change_gossip`

*Note*: The Capella definition is modified only in its wall-clock-to-slot
conversion. Although the Capella epoch gate is already satisfied by the time
EIP-8198 activates, using the canonical inverse timeline removes the final
inherited fixed-duration derivation.

```python
def validate_bls_to_execution_change_gossip(
    seen: Seen,
    state: BeaconState,
    signed_bls_to_execution_change: SignedBLSToExecutionChange,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a SignedBLSToExecutionChange for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    bls_to_execution_change = signed_bls_to_execution_change.message
    validator_index = bls_to_execution_change.validator_index

    # [IGNORE] The current epoch is at or after the Capella fork epoch
    # (where current_epoch is defined by the current wall-clock time)
    # [Modified in EIP8198]
    current_slot = compute_slot_at_time_ms(state.genesis_time, current_time_ms)
    current_epoch = compute_epoch_at_slot(current_slot)
    if current_epoch < CAPELLA_FORK_EPOCH:
        raise GossipIgnore("current epoch is pre-capella")

    # [IGNORE] This is the first valid bls_to_execution_change received for the validator
    if validator_index in seen.bls_to_execution_change_indices:
        raise GossipIgnore("already seen BLS to execution change for this validator")

    # [REJECT] The validator index is valid
    if validator_index >= len(state.validators):
        raise GossipReject("validator index out of range")

    validator = state.validators[validator_index]

    # [REJECT] The validator has BLS withdrawal credentials
    if validator.withdrawal_credentials[:1] != BLS_WITHDRAWAL_PREFIX:
        raise GossipReject("validator does not have BLS withdrawal credentials")

    # [REJECT] The bls_to_execution_change is for the validator's withdrawal pubkey
    if validator.withdrawal_credentials[1:] != hash(bls_to_execution_change.from_bls_pubkey)[1:]:
        raise GossipReject("pubkey does not match validator withdrawal credentials")

    # [REJECT] The signature is valid
    domain = compute_domain(
        DOMAIN_BLS_TO_EXECUTION_CHANGE, genesis_validators_root=state.genesis_validators_root
    )
    signing_root = compute_signing_root(bls_to_execution_change, domain)
    if not bls.Verify(
        bls_to_execution_change.from_bls_pubkey,
        signing_root,
        signed_bls_to_execution_change.signature,
    ):
        raise GossipReject("invalid BLS to execution change signature")

    # Mark this bls_to_execution_change as seen
    seen.bls_to_execution_change_indices.add(validator_index)
```

#### Modified `execution_payload_bid`

Replace the inherited gas-limit _[IGNORE]_ condition for `execution_payload_bid`
with the following:

- _[IGNORE]_ `bid.parent_block_hash` is the block hash of a known execution
  payload in fork choice and
  `is_gas_limit_target_compatible_eip8198(parent_gas_limit, bid.gas_limit, proposer_preferences.target_gas_limit, parent_execution_payload_slot, bid.slot)`
  is `True`, where `parent_gas_limit` is obtained from that execution payload
  and `parent_execution_payload_slot` is the slot of the associated beacon
  block. Resolve the association through
  `signed_execution_payload_envelope.message.beacon_block_root` and the
  corresponding `store.blocks[beacon_block_root].slot`.

Using the execution payload's slot ensures that a missed slot or a post-fork
beacon block without the first post-fork execution payload cannot bypass the
one-time gas-limit scaling.

### The Req/Resp domain

Request and response message types are unchanged from Heze. The blob and
data-column sidecar retention windows used by the sidecar request validations
and pruning guidance MUST use
`get_min_epochs_for_blob_sidecars_requests(current_epoch)` and
`get_min_epochs_for_data_column_sidecars_requests(current_epoch)`, respectively.

The `6144`-epoch values preserve the old wall-clock retention duration only
after the entire window is post-fork. A window crossing the fork is longer
because it contains 12-second epochs. To avoid an availability gap at
activation, a node configured for EIP-8198 MUST begin increasing its retained
history one epoch at a time at `EIP8198_FORK_EPOCH - (6144 - 4096)` (or at
genesis if that expression would be negative), as encoded by the selectors
above. A deployment announced with less than `2048` epochs of lead time MUST
backfill the missing pre-fork sidecars before activation. This temporary
over-retention converges to the steady-state wall-clock window after `6144`
post-fork epochs.
