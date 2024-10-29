# FOCIL -- Networking

This document contains the consensus-layer networking specification for FOCIL.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Time parameters](#time-parameters)
- [Configuration](#configuration)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [`inclusion_list`](#inclusion_list)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [InclusionListByCommitteeIndices v1](#inclusionlistbycommitteeindices-v1)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `attestation_deadline` | `uint64(4)` | seconds | 4 seconds |

### Configuration

| `MAX_REQUEST_INCLUSION_LIST` | `2**4` (= 16) | Maximum number of inclusion list in a single request |

### The gossip domain: gossipsub

#### Topics and messages

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name                          | Message Type                                         |
|-------------------------------|------------------------------------------------------|
| `inclusion_list`    | `SignedInclusionList` [New in FOCIL] |

##### Global topics

FOCIL introduces a new global topic for inclusion lists.

###### `inclusion_list`

This topic is used to propagate signed inclusion list as `SignedInclusionList`.
The following validations MUST pass before forwarding the `inclusion_list` on the network, assuming the alias `message = signed_inclusion_list.message`:

- _[REJECT]_ The slot `message.slot` is equal to the previous or current slot.
- _[IGNORE]_ The slot `message.slot` is equal to the current slot, or it is equal to the previous slot and the current time is less than `attestation_deadline` seconds into the slot.
- _[IGNORE]_ The `inclusion_list_committee` for slot `message.slot` on the current branch corresponds to `message.inclusion_list_committee_root`, as determined by `hash_tree_root(inclusion_list_committee) == message.inclusion_list_committee_root`.
- _[REJECT]_ The validator index `message.validator_index` is within the `inclusion_list_committee` corresponding to `message.inclusion_list_committee_root`.  
- _[REJECT]_ The transactions `message.transactions` length is within upperbound `MAX_TRANSACTIONS_PER_INCLUSION_LIST`.
- _[IGNORE]_ The `message` is either the first or second valid message received from the validator with index `message.validator_index`.
- _[REJECT]_ The signature of `inclusion_list.signature` is valid with respect to the validator index.


### The Req/Resp domain

#### Messages

##### InclusionListByCommitteeIndices v1

**Protocol ID:** `/eth2/beacon_chain/req/inclusion_list_by_committee_indices/1/`

The `<context-bytes>` field is calculated as `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`         | Chunk SSZ type                           |
|------------------------|------------------------------------------|
| `FOCIL_FORK_VERSION` | `focil.SignedInclusionList` |

Request Content:
```
(
  slot: Slot
  committee_indices: Bitvector[IL_COMMITTEE_SIZE]
)
```

Response Content:
```
(
  List[SignedInclusionList, MAX_REQUEST_INCLUSION_LIST]
)
```