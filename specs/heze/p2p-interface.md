# Heze -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in Heze](#modifications-in-heze)
  - [Preset](#preset)
    - [Type-specific SSZ bounds](#type-specific-ssz-bounds)
  - [Configuration](#configuration)
  - [Helpers](#helpers)
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
      - [InclusionListByCommitteeIndices v1](#inclusionlistbycommitteeindices-v1)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for Heze.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Modifications in Heze

### Preset

#### Type-specific SSZ bounds

| Name                                         | Value                         |
| -------------------------------------------- | ----------------------------- |
| `MAX_SIGNED_EXECUTION_PAYLOAD_BID_SIZE_HEZE` | `uint64(196934)` (= ~192 KiB) |
| `MAX_SIGNED_INCLUSION_LIST_SIZE`             | `uint64(8348)` (= ~8 KiB)     |

### Configuration

| Name                           | Value             | Description                                                |
| ------------------------------ | ----------------- | ---------------------------------------------------------- |
| `MAX_REQUEST_INCLUSION_LIST`   | `2**4` (= 16)     | Maximum number of inclusion list in a single request       |
| `MAX_BYTES_PER_INCLUSION_LIST` | `2**13` (= 8,192) | Maximum size of the inclusion list's transactions in bytes |

### Helpers

#### Modified `compute_fork_version`

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

### The gossip domain: gossipsub

#### Topics and messages

The `execution_payload_bid` topic is modified to support Heze bids.

The new topics along with the type of the `data` field of a gossipsub message
are given in this table:

| Name             | Message Type          |
| ---------------- | --------------------- |
| `inclusion_list` | `SignedInclusionList` |

##### Global topics

###### Modified `execution_payload_bid`

The following validations are added, assuming the alias
`bid = signed_execution_payload_bid.message`:

- _[IGNORE]_ `bid.inclusion_list_bits` is inclusive of the node's view of
  inclusion lists for the slot preceding the bid's slot -- i.e.
  `is_inclusion_list_bits_inclusive(get_inclusion_list_store(), state, Slot(bid.slot - 1), bid.inclusion_list_bits, only_timely=False)`
  returns `True`, where `state` is the head state corresponding to processing
  the block up to the current slot as determined by the fork choice.

###### New `inclusion_list`

This topic is used to propagate signed inclusion list as `SignedInclusionList`.
The following validations MUST pass before forwarding the `inclusion_list` on
the network, assuming the alias `message = signed_inclusion_list.message`:

- _[REJECT]_ The size of `message.transactions` is within upperbound
  `MAX_BYTES_PER_INCLUSION_LIST`.
- _[IGNORE]_ The slot `message.slot` is equal to the current slot (with a
  `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance), i.e.
  `message.slot == current_slot`.
- _[IGNORE]_ The `message` is either the first or second valid message received
  from the validator with index `message.validator_index`.
- _[REJECT]_ The message's validator index is in
  `get_inclusion_list_committee(state, message.slot)`, where `state` is the head
  state corresponding to processing the block up to the current slot as
  determined by the fork choice.
- _[REJECT]_ The `message.inclusion_list_committee_root` is equal to
  `hash_tree_root(get_inclusion_list_committee(state, message.slot))`.
- _[REJECT]_ The signature of `signed_inclusion_list.signature` is valid with
  respect to the validator's public key.

### The Req/Resp domain

#### Messages

##### BeaconBlocksByRange v2

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

##### BeaconBlocksByRoot v2

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

##### InclusionListByCommitteeIndices v1

**Protocol ID:** `/eth2/beacon_chain/req/inclusion_list_by_committee_indices/1/`

For each successful `response_chunk`, the `ForkDigest` context epoch is
determined by `compute_epoch_at_slot(signed_inclusion_list.message.slot)`.

Per `fork_version = compute_fork_version(epoch)`:

<!-- eth_consensus_specs: skip -->

| `fork_version`      | Chunk SSZ type             |
| ------------------- | -------------------------- |
| `HEZE_FORK_VERSION` | `heze.SignedInclusionList` |

Request Content:

```
(
  slot: Slot
  committee_indices: Bitvector[INCLUSION_LIST_COMMITTEE_SIZE]
)
```

Response Content:

```
(
  List[SignedInclusionList, MAX_REQUEST_INCLUSION_LIST]
)
```
