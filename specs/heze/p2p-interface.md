# Heze -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Modifications in Heze](#modifications-in-heze)
  - [Configuration](#configuration)
  - [Helpers](#helpers)
    - [Modified `compute_fork_version`](#modified-compute_fork_version)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`inclusion_list`](#inclusion_list)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [InclusionListByCommitteeIndices v1](#inclusionlistbycommitteeindices-v1)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for Heze.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Modifications in Heze

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

The new topics along with the type of the `data` field of a gossipsub message
are given in this table:

| Name             | Message Type          |
| ---------------- | --------------------- |
| `inclusion_list` | `SignedInclusionList` |

##### Global topics

Heze introduces a new global topic for inclusion lists.

###### `inclusion_list`

This topic is used to propagate signed inclusion list as `SignedInclusionList`.
The following validations MUST pass before forwarding the `inclusion_list` on
the network, assuming the alias `message = signed_inclusion_list.message`:

- _[REJECT]_ The size of `message.transactions` is within upperbound
  `MAX_BYTES_PER_INCLUSION_LIST`.
- _[REJECT]_ The slot `message.slot` is equal to the previous or current slot.
- _[IGNORE]_ The slot `message.slot` is equal to the current slot, or it is
  equal to the previous slot and the current time is less than
  `get_attestation_due_ms(epoch)` milliseconds into the slot.
- _[IGNORE]_ The `inclusion_list_committee` for slot `message.slot` on the
  current branch corresponds to `message.inclusion_list_committee_root`, as
  determined by
  `hash_tree_root(inclusion_list_committee) == message.inclusion_list_committee_root`.
- _[REJECT]_ The validator index `message.validator_index` is within the
  `inclusion_list_committee` corresponding to
  `message.inclusion_list_committee_root`.
- _[IGNORE]_ The `message` is either the first or second valid message received
  from the validator with index `message.validator_index`.
- _[REJECT]_ The signature of `signed_inclusion_list.signature` is valid with
  respect to the validator's public key.

### The Req/Resp domain

#### Messages

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
