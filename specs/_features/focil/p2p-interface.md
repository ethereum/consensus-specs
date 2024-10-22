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
| `inclusion_list_CUT_OFF` | `uint64(9)` | seconds | 9 seconds |

### Configuration

| `MAX_REQUEST_INCLUSION_LIST` | `2**4` (= 16) | Maximum number of inclusion list in a single request |

### The gossip domain: gossipsub

#### Topics and messages

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name                          | Message Type                                         |
|-------------------------------|------------------------------------------------------|
| `inclusion_list`    | `SignedInclusionList` [New in FOCIL] |

##### Global topics

FOCIL introduces new global topics for inclusion list.

###### `inclusion_list`

This topic is used to propagate signed inclusion list as `SignedInclusionList`.
The following validations MUST pass before forwarding the `inclusion_list` on the network, assuming the alias `message = signed_inclusion_list.message`:

- _[REJECT]_ The slot `message.slot` is equal to current slot.
- _[REJECT]_ The transactions `message.transactions` length is within upperbound `MAX_TRANSACTIONS_PER_INCLUSION_LIST`.
- _[IGNORE]_ The `message` is either the first or second valid message received from the validator with index `message.validator_index`.
- _[REJECT]_ The signature of `inclusion_list.signature` is valid with respect to the validator index. 
- _[REJECT]_ The validator index `message.validator_index` is within the inclusion list committee given by `get_inclusion_list_committee(state, message.slot)`, where the `state` is based on `message.parent_block_root` and processed up to `message.slot`.  If the validator index cannot immediately be verified against the expected committee, the inclusion list MAY be queued for later processing while the committee for the branch of `message.parent_block_root` is calculated -- in such a case do not REJECT, instead IGNORE this message.

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