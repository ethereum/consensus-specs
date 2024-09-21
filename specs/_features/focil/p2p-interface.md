# FOCIL -- Networking

This document contains the consensus-layer networking specification for FOCIL.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Time parameters](#time-parameters)
- [Containers](#containers)
  - [`SignedInclusionListAggregate`](#signedinclusionlistaggregate)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [`local_inclusion_list`](#local_inclusion_list)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `LOCAL_INCLUSION_CUT_OFF` | `uint64(9)` | seconds | 9 seconds |

### Containers

#### `SignedInclusionListAggregate`

```python
class SignedInclusionSummaryAggregates(Container):
    slot: Slot
    proposer_index: ValidatorIndex
    message: InclusionSummaryAggregates
    signature: BLSSignature
```

### The gossip domain: gossipsub

#### Topics and messages

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name                          | Message Type                                         |
|-------------------------------|------------------------------------------------------|
| `local_inclusion_list`    | `SignedLocalInclusionList` [New in FOCIL] |

##### Global topics

FOCIL introduces new global topics for inclusion list and inclusion list aggregate.

###### `local_inclusion_list`

This topic is used to propagate signed local inclusion list as `SignedLocalInclusionList`.
The following validations MUST pass before forwarding the `local_inclusion_list` on the network, assuming the alias `message = signed_local_inclusion_list.message`:

- _[REJECT]_ The slot `message.slot` is equal to current slot.
- _[IGNORE]_ The current time is `LOCAL_INCLUSION_CUT_OFF` seconds into the slot.
- _[REJECT]_ The transactions `message.transactions` length is within upperbound `MAX_TRANSACTIONS_PER_INCLUSION_LIST`.
- _[REJECT]_ The summaries `message.summaries` length is within upperbound `MAX_TRANSACTIONS_PER_INCLUSION_LIST`.
- _[IGNORE]_ The `message` is the first valid message received from the validator with index `message.validate_index`. 
- _[IGNORE]_ The block hash `message.parent_block_hash` is a known execution payload in fork choice.
- _[REJECT]_ The signature of `inclusion_list.signature` is valid with respect to the validator index. 
- _[REJECT]_ The validator index is within the inclusion list committee in `get_inclusion_list_committee(state)`. The `state` is the head state corresponding to processing the block up to the current slot as determined by the fork choice. 
