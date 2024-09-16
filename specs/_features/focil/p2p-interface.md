# FOCIL -- Networking

This document contains the consensus-layer networking specification for FOCIL.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Containers](#containers)
  - [`SignedInclusionListAggregate`](#signedinclusionlistaggregate)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
  - [Topics and messages](#topics-and-messages-1)
    - [Global topics](#global-topics)
      - [`local_inclusion_list`](#local_inclusion_list)
      - [`inclusion_summary_aggregate`](#inclusion_summary_aggregate)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

### Containers

#### `SignedInclusionListAggregate`

```python
class SignedInclusionListAggregates(Container):
    slot: Slot
    proposer_index: ValidatorIndex
    message: InclusionSummaryAggregates
    signature: BLSSignature
```

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork of FOCIL to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The `beacon_block` topic is updated to support the modified type
| Name | Message Type |
| --- | --- |
| `beacon_block` | `SignedBeaconBlock` [modified in FOCIL] |

#### Topics and messages

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name                          | Message Type                                         |
|-------------------------------|------------------------------------------------------|
| `local_inclusion_list`    | `SignedLocalInclusionList` [New in FOCIL] |
| `inclusion_summary_aggregates`           | `SignedInclusionListAggregates` [New in FOCIL]       |

##### Global topics

FOCIL introduces new global topics for inclusion list and inclusion list aggregate.

###### `local_inclusion_list`

This topic is used to propagate signed local inclusion list as `SignedLocalInclusionList`.
The following validations MUST pass before forwarding the `local_inclusion_list` on the network, assuming the alias `message = signed_local_inclusion_list.message`:

- _[REJECT]_ The slot `message.slot` is equal to current slot.
- _[REJECT]_ The transactions `message.transactions` length is within upperbound `MAX_TRANSACTIONS_PER_INCLUSION_LIST`.
- _[REJECT]_ The summaries `message.summaries` length is within upperbound `MAX_TRANSACTIONS_PER_INCLUSION_LIST`.
- _[IGNORE]_ The `message` is the first valid message received from the validator with index `message.validate_index`. 
- _[IGNORE]_ The block hash `message.parent_block_hash` is a known execution payload in fork choice.
- _[REJECT]_ The signature of `inclusion_list.signature` is valid with respect to the validator index. 
- _[REJECT]_ The validator index is within the inclusion list committee in `get_inclusion_list_committee(state)`. The `state` is the head state corresponding to processing the block up to the current slot as determined by the fork choice. 

###### `inclusion_summary_aggregate`

This topic is used to propagate signed inclusion list aggregate as `SignedInclusionListAggregates`.
The following validations MUST pass before forwarding the `inclusion_summary_aggregates` on the network:

- _[REJECT]_ The slot `signed_inclusion_list_aggregates.slot` is equal to current slot + 1.
- _[REJECT]_ The signature of `signed_inclusion_list_aggregates.signature` is valid with respect to the proposer index. 
- _[REJECT]_ The proposer index `signed_inclusion_list_aggregates.proposer_index` is the proposer for slot.