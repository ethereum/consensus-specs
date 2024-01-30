<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [EIP-7547 -- Networking](#eip-7547----networking)
  - [Table of contents](#table-of-contents)
  - [Modifications in EIP7547](#modifications-in-eip7547)
    - [Preset](#preset)
    - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
      - [Topics and messages](#topics-and-messages)
        - [Global topics](#global-topics)
          - [`inclusion_list`](#inclusion_list)
      - [Transitioning the gossip](#transitioning-the-gossip)
  - [Design rationale](#design-rationale)
  - [Why is it proposer may send multiple inclusion lists? Why not just one per slot?](#why-is-it-proposer-may-send-multiple-inclusion-lists-why-not-just-one-per-slot)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# EIP-7547 -- Networking

This document contains the consensus-layer networking specification for EIP-7547.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Table of contents


## Modifications in EIP7547

### Preset

*[New in EIP7547]*

| Name                                     | Value                             | Description                                                         |
|------------------------------------------|-----------------------------------|---------------------------------------------------------------------|
| `MIN_SLOTS_FOR_INCLUSION_LIST_REQUEST`   | `uint64(1)` |  |

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork for EIP7547 to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The `beacon_block` topic is modified to also support block with signed execution header and new topics are added per table below.

The specification around the creation, validation, and dissemination of messages has not changed from the Deneb document unless explicitly noted here.

The derivation of the `message-id` remains stable.

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name                          | Message Type                                         |
|-------------------------------|------------------------------------------------------|
| `inclusion_list`              | `InclusionList` [New in EIP7547]                     |

##### Global topics

EIP7547 introduces new global topics for the inclusion list.

###### `inclusion_list`

This topic is used to propagate inclusion list.

The following validations MUST pass before forwarding the `inclusion_list` on the network, assuming the alias `signed_summary = inclusion_list.summary`, `summary = signed_summary.message`:

- _[IGNORE]_ The inclusion list is not from a future slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) --
  i.e. validate that `inclusion_list.slot <= current_slot`
  (a client MAY queue future blocks for processing at the appropriate slot).
- _[IGNORE]_ The inclusion list is not older than min slots for inclusion list request --
  i.e. validate that `inclusion_list.slot >= current_slot - MIN_SLOTS_FOR_INCLUSION_LIST_REQUEST`
  (a client MAY queue future blocks for processing at the appropriate slot).
- _[IGNORE]_ The inclusion list is the first inclusion list with valid signature received for the proposer for the slot, `inclusion_list.slot`.
  (a client MAY gossip multiple inclusion list from the same validator for the same slot).
- _[REJECT]_ The inclusion list transactions `inclusion_list.transactions` length is within upperbound `MAX_TRANSACTIONS_PER_INCLUSION_LIST`.
- _[REJECT]_ The inclusion list summary has the same length of transactions `len(summary.summary) == len(inclusion_list.transactions)`.
- _[REJECT]_ The summary signature, `signed_summary.signature`, is valid with respect to the `proposer_index` pubkey.
- _[REJECT]_ The summary is proposed by the expected proposer_index for the summary's slot in the context of the current shuffling (defined by parent_root/slot). If the proposer_index cannot immediately be verified against the expected shuffling, the inclusion list MAY be queued for later processing while proposers for the summary's branch are calculated -- in such a case do not REJECT, instead IGNORE this message.

#### Transitioning the gossip

See gossip transition details found in the [Deneb document](../deneb/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics for this upgrade.

## Design rationale

## Why is it proposer may send multiple inclusion lists? Why not just one per slot?

Proposers may submit multiple inclusion lists, providing validators with plausible deniability and eliminating a data availability attack route. This concept stems from the "no free lunch IL design" which lets proposers send multiple ILs. The idea is that since only one IL is eventually chosen from many, thus its contents can't be relied upon for data availability.
