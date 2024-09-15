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
          - [`inclusion_list`](#inclusion_list)
          - [`inclusion_list_aggregate`](#inclusion_list_aggregate)
- [TODO](#todo)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

### Containers

#### `SignedInclusionListAggregate`

```python
class SignedInclusionListAggregate(Container):
    message: InclusionListAggregate
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
| `inclusion_list`    | `SignedInclusionList` [New in FOCIL] |
| `inclusion_list_aggregate`           | `SignedInclusionListAggregate` [New in FOCIL]       |

##### Global topics

FOCIL introduces new global topics for inclusion list and inclusion list aggregate.

###### `inclusion_list`

This topic is used to propagate execution inclusion list as `SignedInclusionList`.
The following validations MUST pass before forwarding the `inclusion_list` on the network, assuming the alias `message = signed_inclusion_list.message`:

- _[REJECT]_ The slot `message.slot` is equal to current slot + 1 
- _[REJECT]_ The transactions `message.transactions` length is within upperbound `MAX_TRANSACTIONS_PER_INCLUSION_LIST`.
- _[REJECT]_ The summaries `message.summaries` length is within upperbound `MAX_TRANSACTIONS_PER_INCLUSION_LIST`.
- _[IGNORE]_ The block hash `message.parent_block_hash` is a known execution payload in fork choice.
- _[REJECT]_ The signature of `inclusion_list.signature` is valid with respect to the validator index. 
- _[REJECT]_ The validator index is within the inclusion list committee in `get_inclusion_list_committee(state)`. The `state` is the head state corresponding to processing the block up to the current slot as determined by the fork choice. 

###### `inclusion_list_aggregate`

# TODO
