# Heze -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Presets](#presets)
  - [Type-specific SSZ bounds](#type-specific-ssz-bounds)
- [Configs](#configs)
- [Types](#types)
  - [New `SignedInclusionLists`](#new-signedinclusionlists)
- [Helpers](#helpers)
  - [Modified `Seen`](#modified-seen)
  - [Modified `compute_fork_version`](#modified-compute_fork_version)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [Modified `execution_payload_bid`](#modified-execution_payload_bid)
      - [New `inclusion_list`](#new-inclusion_list)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [BeaconBlocksByRange v2](#beaconblocksbyrange-v2)
    - [BeaconBlocksByRoot v2](#beaconblocksbyroot-v2)
    - [InclusionListsByIndices v1](#inclusionlistsbyindices-v1)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for Heze.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Presets

### Type-specific SSZ bounds

| Name                                         | Value                         |
| -------------------------------------------- | ----------------------------- |
| `MAX_SIGNED_EXECUTION_PAYLOAD_BID_SIZE_HEZE` | `Uint64(196934)` (= ~192 KiB) |
| `MAX_SIGNED_INCLUSION_LIST_SIZE`             | `Uint64(41112)` (= ~40 KiB)   |

## Configs

| Name                                        | Value                     | Description                                                     |
| ------------------------------------------- | ------------------------- | --------------------------------------------------------------- |
| `MAX_REQUEST_INCLUSION_LIST`                | `Uint64(2**4)` (= 16)     | Maximum number of inclusion lists in a single request           |
| `MIN_SLOTS_FOR_INCLUSION_LISTS_REQUESTS`    | `Slot(1)`                 | Minimum slot range over which a node must serve inclusion lists |
| `MAX_TRANSACTIONS_BYTES_PER_INCLUSION_LIST` | `Uint64(2**13)` (= 8,192) | Maximum size of the inclusion list's transactions in bytes      |

## Types

### New `SignedInclusionLists`

```python
class SignedInclusionLists(List[SignedInclusionList]):
    """
    Signed inclusion lists returned in an ``InclusionListsByIndices``
    response.
    """

    LIMIT = MAX_REQUEST_INCLUSION_LIST
```

## Helpers

### Modified `Seen`

```python
@dataclass
class Seen:
    proposer_slots: Set[Tuple[Slot, ValidatorIndex]]
    aggregator_epochs: Set[Tuple[Epoch, ValidatorIndex]]
    aggregate_data_roots: Dict[Tuple[Root, CommitteeIndex], Set[Tuple[bool, ...]]]
    voluntary_exit_indices: Set[ValidatorIndex]
    proposer_slashing_indices: Set[ValidatorIndex]
    attester_slashing_indices: Set[ValidatorIndex]
    attestation_validator_epochs: Set[Tuple[Epoch, ValidatorIndex]]
    sync_contribution_aggregator_slots: Set[Tuple[Slot, ValidatorIndex, Uint64]]
    sync_contribution_data: Dict[Tuple[Slot, Root, Uint64], Set[Tuple[bool, ...]]]
    sync_message_validator_slots: Set[Tuple[Slot, ValidatorIndex, Uint64]]
    bls_to_execution_change_indices: Set[ValidatorIndex]
    data_column_sidecar_tuples: Set[Tuple[Root, ColumnIndex]]
    execution_payloads: Dict[Hash32, ExecutionPayload]
    execution_payload_envelopes: Set[Tuple[Root, BuilderIndex]]
    payload_attestation_validators: Set[Tuple[Slot, ValidatorIndex]]
    execution_payload_bids: Set[Tuple[Slot, Hash32, Root, BuilderIndex]]
    best_execution_payload_bid: Dict[Tuple[Slot, Hash32, Root], Gwei]
    proposer_preferences: Dict[Tuple[Slot, Root], ProposerPreferences]
    # [New in Heze:EIP7805]
    inclusion_list_counts: Counter[Tuple[Slot, Root, ValidatorIndex]]
```

### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
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

## The gossip domain: gossipsub

### Topics and messages

The `execution_payload_bid` topic is modified to support Heze bids.

The new topics along with the type of the `data` field of a gossipsub message
are given in this table:

| Name             | Message Type          |
| ---------------- | --------------------- |
| `inclusion_list` | `SignedInclusionList` |

#### Global topics

##### Modified `execution_payload_bid`

```python
def validate_execution_payload_bid_gossip(
    seen: Seen,
    store: Store,
    signed_execution_payload_bid: SignedExecutionPayloadBid,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a SignedExecutionPayloadBid for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    bid = signed_execution_payload_bid.message

    # [IGNORE] This is the first bid for this slot, parent, and builder
    bid_key = (bid.slot, bid.parent_block_hash, bid.parent_block_root, bid.builder_index)
    if bid_key in seen.execution_payload_bids:
        raise GossipIgnore("already seen valid bid for this slot, parent, and builder")

    # [IGNORE] This is the highest value bid seen for the slot and parent
    best_bid_key = (bid.slot, bid.parent_block_hash, bid.parent_block_root)
    if best_bid_key in seen.best_execution_payload_bid:
        if bid.value <= seen.best_execution_payload_bid[best_bid_key]:
            raise GossipIgnore("bid is not the highest value bid seen for this slot and parent")

    # [IGNORE] The bid's slot is the current slot or the next slot
    if not is_current_or_next_slot(store, bid.slot, current_time_ms):
        raise GossipIgnore("bid's slot is not the current or next slot")

    # [REJECT] The bid's execution payment is zero
    if bid.execution_payment != 0:
        raise GossipReject("bid's execution payment must be zero")

    # [REJECT] The bid's block hash is not equal to its parent block hash
    if bid.block_hash == bid.parent_block_hash:
        raise GossipReject("bid's block hash equals its parent block hash")

    # [REJECT] The bid's blob KZG commitment count is within the per-epoch limit
    proposal_epoch = compute_epoch_at_slot(bid.slot)
    max_blobs = get_blob_parameters(proposal_epoch).max_blobs_per_block
    if len(bid.blob_kzg_commitments) > max_blobs:
        raise GossipReject("too many blob kzg commitments")

    # [IGNORE] The bid's parent block root is a known beacon block
    # (MAY be queued until parent is retrieved)
    if bid.parent_block_root not in store.blocks:
        raise GossipIgnore("bid's parent block root is not a known beacon block")

    # [REJECT] The bid is for a higher slot than its parent block
    if bid.slot <= store.blocks[bid.parent_block_root].slot:
        raise GossipReject("bid's slot is not higher than its parent's slot")

    # [IGNORE] The bid's parent block has been imported
    # (MAY be queued until parent is imported)
    if bid.parent_block_root not in store.block_states:
        raise GossipIgnore("bid's parent block post-state is unavailable")

    state = store.block_states[bid.parent_block_root]

    # [IGNORE] The bid's slot is within the parent's proposer lookahead
    if proposal_epoch > get_current_epoch(state) + MIN_SEED_LOOKAHEAD:
        raise GossipIgnore("bid's slot is past the parent's proposer lookahead")

    # [IGNORE] The matching proposer preferences have been seen
    dependent_root = get_shuffling_dependent_root(store, bid.parent_block_root, proposal_epoch)
    prefs_key = (bid.slot, dependent_root)
    if prefs_key not in seen.proposer_preferences:
        raise GossipIgnore("matching proposer preferences have not been seen")

    proposer_preferences = seen.proposer_preferences[prefs_key]

    # [IGNORE] The bid's fee recipient matches the proposer's preference
    if bid.fee_recipient != proposer_preferences.fee_recipient:
        raise GossipIgnore("bid's fee recipient does not match the proposer's preference")

    # [IGNORE] The bid's parent block hash is the hash of a known execution payload
    if bid.parent_block_hash not in seen.execution_payloads:
        raise GossipIgnore("bid's parent block hash is not a known execution payload")

    # [IGNORE] The bid's gas limit is compatible with the proposer's target gas limit
    parent_gas_limit = seen.execution_payloads[bid.parent_block_hash].gas_limit
    if not is_gas_limit_target_compatible(
        parent_gas_limit, bid.gas_limit, proposer_preferences.target_gas_limit
    ):
        raise GossipIgnore("bid's gas limit is not compatible with the proposer's target")

    # [IGNORE] The bid is compatible with the current head branch
    if not is_bid_compatible_with_head(store, bid):
        raise GossipIgnore("bid is not compatible with the current head branch")

    # [REJECT] The bid's previous randao is correct
    if bid.prev_randao != get_randao_mix(state, get_current_epoch(state)):
        raise GossipReject("bid's previous randao is incorrect")

    state = state.copy()
    process_slots(state, bid.slot)

    # [REJECT] The builder index is valid
    if bid.builder_index >= len(state.builders):
        raise GossipReject("builder index out of range")

    builder = state.builders[bid.builder_index]

    # [REJECT] The builder is a payload builder
    if builder.version != PAYLOAD_BUILDER_VERSION:
        raise GossipReject("builder is not a payload builder")

    # [REJECT] The builder is active
    if not is_active_builder(state, bid.builder_index):
        raise GossipReject("builder is not active")

    # [IGNORE] The builder can cover the bid
    if not can_builder_cover_bid(state, bid.builder_index, bid.value):
        raise GossipIgnore("builder cannot cover bid value")

    # [IGNORE] The parent's payload does not try to exit the builder
    if bid.parent_block_hash == state.latest_execution_payload_bid.block_hash:
        envelope = store.payloads[bid.parent_block_root]
        for request in envelope.execution_requests.builder_exits:
            if request.pubkey == builder.pubkey:
                if request.source_address == builder.execution_address:
                    raise GossipIgnore("builder may exit")

    # [IGNORE] The bid's inclusion list bits is inclusive
    inclusion_list_slot = bid.slot - Slot(1)
    inclusion_list_committee = get_inclusion_list_committee(state, inclusion_list_slot)
    inclusion_list_dependent_root = get_shuffling_dependent_root(
        store, bid.parent_block_root, compute_epoch_at_slot(inclusion_list_slot)
    )
    if not is_inclusion_list_bits_inclusive(
        get_inclusion_list_store(),
        inclusion_list_committee,
        inclusion_list_slot,
        inclusion_list_dependent_root,
        bid.inclusion_list_bits,
        only_timely=True,
    ):
        raise GossipIgnore("bid's inclusion list bits is not inclusive")

    # [REJECT] The bid signature is valid
    if not verify_execution_payload_bid_signature(state, signed_execution_payload_bid):
        raise GossipReject("invalid bid signature")

    # Mark this bid as seen and update the highest-value bid for this slot/parent
    seen.execution_payload_bids.add(bid_key)
    seen.best_execution_payload_bid[best_bid_key] = bid.value
```

*Note*: Implementations SHOULD include DoS prevention measures to mitigate spam
from malicious builders submitting numerous bids with minimal value increments.
Possible strategies include: (1) only forwarding bids that exceed the current
highest bid by a minimum threshold, or (2) forwarding only the highest observed
bid at regular time intervals.

##### New `inclusion_list`

This topic is used to propagate signed inclusion list.

```python
def validate_inclusion_list_gossip(
    seen: Seen,
    store: Store,
    signed_inclusion_list: SignedInclusionList,
    current_time_ms: Uint64,
) -> None:
    """
    Validate a SignedInclusionList for gossip propagation.
    Raises GossipIgnore or GossipReject on validation failure.
    """
    inclusion_list = signed_inclusion_list.message

    # [IGNORE] This is the first or second valid message from this validator
    includer_index = inclusion_list.validator_index
    inclusion_list_key = (inclusion_list.slot, inclusion_list.dependent_root, includer_index)
    if seen.inclusion_list_counts[inclusion_list_key] >= 2:
        raise GossipIgnore("already seen two valid inclusion lists from this validator")

    # [IGNORE] The inclusion list's slot is for the current slot
    if not is_current_slot(store, inclusion_list.slot, current_time_ms):
        raise GossipIgnore("inclusion list is not for the current slot")

    # [IGNORE] The size of inclusion list transactions must be non-empty
    transactions_size = sum(len(transaction) for transaction in inclusion_list.transactions)
    if transactions_size == 0:
        raise GossipIgnore("inclusion list contains no transactions")

    # [REJECT] The size of inclusion list transactions must not exceed the maximum size
    if transactions_size > MAX_TRANSACTIONS_BYTES_PER_INCLUSION_LIST:
        raise GossipReject("inclusion list transactions exceed the maximum size")

    # [REJECT] Every transaction must be non-empty
    if not all(len(transaction) > 0 for transaction in inclusion_list.transactions):
        raise GossipReject("inclusion list contains an empty transaction")

    # [IGNORE] The dependent block has been seen (via gossip or non-gossip sources)
    # (MAY be queued until block is retrieved)
    if inclusion_list.dependent_root not in store.blocks:
        raise GossipIgnore("dependent block has not been seen")

    # [IGNORE] The dependent block passes validation
    if inclusion_list.dependent_root not in store.block_states:
        raise GossipIgnore("dependent block failed validation")

    # [REJECT] The dependent block's slot is not after the shuffling dependent slot
    epoch = compute_epoch_at_slot(inclusion_list.slot)
    dependent_slot = compute_shuffling_dependent_slot(epoch)
    if store.blocks[inclusion_list.dependent_root].slot > dependent_slot:
        raise GossipReject("dependent block is after the shuffling dependent slot")

    # [IGNORE] The dependent block is a possible dependent block for the inclusion list committee lookahead
    if not is_valid_dependent_root(store, inclusion_list.dependent_root, dependent_slot):
        raise GossipIgnore("dependent block is not a possible dependent block")

    # [REJECT] The includer is a member of the committee
    state = store.block_states[inclusion_list.dependent_root].copy()
    lookahead_start_slot = compute_shuffling_lookahead_start_slot(epoch)
    if state.slot < lookahead_start_slot:
        process_slots(state, lookahead_start_slot)
    committee = get_inclusion_list_committee(state, inclusion_list.slot)
    if includer_index not in committee:
        raise GossipReject("includer is not a member of the committee")

    # [REJECT] The signature is valid
    if not is_valid_inclusion_list_signature(state, signed_inclusion_list):
        raise GossipReject("invalid inclusion list signature")

    # Mark this inclusion list as seen
    seen.inclusion_list_counts[inclusion_list_key] += 1
```

## The Req/Resp domain

### Messages

#### BeaconBlocksByRange v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_range/2/`

The Heze fork-digest is introduced to the `context` enum to specify Heze beacon
block type.

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `ELECTRA_FORK_VERSION`   | `electra.SignedBeaconBlock`   |
| `FULU_FORK_VERSION`      | `fulu.SignedBeaconBlock`      |
| `GLOAS_FORK_VERSION`     | `gloas.SignedBeaconBlock`     |
| `HEZE_FORK_VERSION`      | `heze.SignedBeaconBlock`      |

#### BeaconBlocksByRoot v2

**Protocol ID:** `/eth2/beacon_chain/req/beacon_blocks_by_root/2/`

The Heze fork-digest is introduced to the `context` enum to specify Heze beacon
block type.

<!-- eth_consensus_specs: skip -->

| `fork_version`           | Chunk SSZ type                |
| ------------------------ | ----------------------------- |
| `GENESIS_FORK_VERSION`   | `phase0.SignedBeaconBlock`    |
| `ALTAIR_FORK_VERSION`    | `altair.SignedBeaconBlock`    |
| `BELLATRIX_FORK_VERSION` | `bellatrix.SignedBeaconBlock` |
| `CAPELLA_FORK_VERSION`   | `capella.SignedBeaconBlock`   |
| `DENEB_FORK_VERSION`     | `deneb.SignedBeaconBlock`     |
| `ELECTRA_FORK_VERSION`   | `electra.SignedBeaconBlock`   |
| `FULU_FORK_VERSION`      | `fulu.SignedBeaconBlock`      |
| `GLOAS_FORK_VERSION`     | `gloas.SignedBeaconBlock`     |
| `HEZE_FORK_VERSION`      | `heze.SignedBeaconBlock`      |

#### InclusionListsByIndices v1

**Protocol ID:** `/eth2/beacon_chain/req/inclusion_lists_by_indices/1/`

*[New in Heze:EIP7805]*

Request Content:

```
(
  slot: Slot
  dependent_root: Root
  indices: InclusionListBits
)
```

Response Content:

```
(
  SignedInclusionLists
)
```

Requests inclusion lists by `slot`, `dependent_root`, and inclusion list
committee `indices`. The `indices` field is interpreted with respect to
`get_inclusion_list_committee(state, slot)`, where `state` is the state
corresponding to processing the block with root `dependent_root` up to the slot
`slot`. The response is a list of `SignedInclusionList` whose length is less
than or equal to the number of requested inclusion lists. It may be less in the
case that the responding peer is missing inclusion lists.

No more than `MAX_REQUEST_INCLUSION_LIST` may be requested at a time.

`InclusionListsByIndices` is primarily used to fetch inclusion lists that may
have been missed on gossip (e.g. when producing an execution payload for a slot
for which some inclusion lists are missing).

The request MUST be encoded as an SSZ-container.

The response MUST consist of zero or more `response_chunk`. Each successful
`response_chunk` MUST contain a single `SignedInclusionList` payload.

Clients MUST support requesting inclusion lists since `minimum_request_slot`,
where
`minimum_request_slot = max(current_slot - MIN_SLOTS_FOR_INCLUSION_LISTS_REQUESTS, compute_start_slot_at_epoch(HEZE_FORK_EPOCH))`.
If `slot` in the request content references a slot earlier than
`minimum_request_slot`, peers MAY respond with error code
`3: ResourceUnavailable` or not include the inclusion lists in the response.

Clients MUST respond with at least one inclusion list, if they have it. Clients
MAY limit the number of inclusion lists in the response.

Clients SHOULD include an inclusion list in the response as soon as it passes
the gossip validation rules. Clients SHOULD NOT respond with inclusion lists
that fail the gossip validation rules. Clients SHOULD NOT respond with inclusion
lists from equivocators for the requested `slot` and `dependent_root`.

For each successful `response_chunk`, the `ForkDigest` context epoch is
determined by `compute_epoch_at_slot(signed_inclusion_list.message.slot)`.

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth_consensus_specs: skip -->

| `fork_version`      | Chunk SSZ type             |
| ------------------- | -------------------------- |
| `HEZE_FORK_VERSION` | `heze.SignedInclusionList` |
