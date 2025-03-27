# EIP-7805 -- Networking

This document contains the consensus-layer networking specification for EIP-7805.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Modifications in EIP-7805](#modifications-in-eip-7805)
  - [Configuration](#configuration)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`inclusion_list`](#inclusion_list)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [InclusionListByCommitteeIndices v1](#inclusionlistbycommitteeindices-v1)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Modifications in EIP-7805

### Configuration

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `ATTESTATION_DEADLINE` | `SECONDS_PER_SLOT // 3` | seconds | 4 seconds |

| Name | Value | Description |
| - | - | - |
| `MAX_REQUEST_INCLUSION_LIST` | `2**4` (= 16) | Maximum number of inclusion list in a single request |
| `MAX_BYTES_PER_INCLUSION_LIST` | `2**13` (= 8192) | Maximum size of the inclusion list's transactions in bytes |

### The gossip domain: gossipsub

#### Topics and messages

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name | Message Type |
| - | - |
| `inclusion_list` | `SignedInclusionList` |

##### Global topics

EIP-7805 introduces a new global topic for inclusion lists.

###### `inclusion_list`

This topic is used to propagate signed inclusion list as `SignedInclusionList`.
The following validations MUST pass before forwarding the `inclusion_list` on the network, assuming the alias `message = signed_inclusion_list.message`:

- _[REJECT]_ The size of `message.transactions` is within upperbound `MAX_BYTES_PER_INCLUSION_LIST`.
- _[REJECT]_ The slot `message.slot` is equal to the previous or current slot.
- _[IGNORE]_ The slot `message.slot` is equal to the current slot, or it is equal to the previous slot and the current time is less than `ATTESTATION_DEADLINE` seconds into the slot.
- _[IGNORE]_ The `inclusion_list_committee` for slot `message.slot` on the current branch corresponds to `message.inclusion_list_committee_root`, as determined by `hash_tree_root(inclusion_list_committee) == message.inclusion_list_committee_root`.
- _[REJECT]_ The validator index `message.validator_index` is within the `inclusion_list_committee` corresponding to `message.inclusion_list_committee_root`.
- _[REJECT]_ The transactions `message.transactions` length is within upperbound `MAX_TRANSACTIONS_PER_PAYLOAD`.
- _[IGNORE]_ The `message` is either the first or second valid message received from the validator with index `message.validator_index`.
- _[REJECT]_ The signature of `inclusion_list.signature` is valid with respect to the validator index.

### The Req/Resp domain

#### Messages

##### InclusionListByCommitteeIndices v1

**Protocol ID:** `/eth2/beacon_chain/req/inclusion_list_by_committee_indices/1/`

The `<context-bytes>` field is calculated as `context = compute_fork_digest(fork_version, genesis_validators_root)`:

[1]: # (eth2spec: skip)

| `fork_version`         | Chunk SSZ type                 |
|------------------------|--------------------------------|
| `EIP7805_FORK_VERSION` | `EIP-7805.SignedInclusionList` |

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
