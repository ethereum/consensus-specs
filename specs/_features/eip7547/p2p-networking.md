<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [EIP-7547 -- Networking](#eip-7547----networking)
  - [Containers](#containers)
    - [New Containers](#new-containers)
      - [`SignedInclusionList`](#signedinclusionlist)
  - [Modifications in EIP7547](#modifications-in-eip7547)
    - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
      - [Topics and messages](#topics-and-messages)
        - [Global topics](#global-topics)
          - [New `inclusion_list`](#new-inclusion_list)
      - [Transitioning the gossip](#transitioning-the-gossip)
  - [Design rationale](#design-rationale)
  - [Why is it proposer may send multiple inclusion lists? Why not just one per slot?](#why-is-it-proposer-may-send-multiple-inclusion-lists-why-not-just-one-per-slot)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# EIP-7547 -- Networking

This document contains the consensus-layer networking specification for EIP-7547.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Containers

### New Containers

#### `SignedInclusionList`

```python
class SignedInclusionList(Container):
    message: InclusionList
    signature: BLSSignature
```

## Modifications in EIP7547

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork for EIP7547 to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The derivation of the `message-id` remains stable.

##### Global topics

###### New `inclusion_list`

The *type* of the payload of this topic is `SignedInclusionList`.

New validation:

The following validations MUST pass before forwarding the inclusion_list on the network.

- _[REJECT]_ The slot `message.signedSummary.message.slot` is greater than or equal to the current slot (clients can queue future inclusion lists).
- _[REJECT]_ The `signature` is valid for the current proposer `message.signedSummary.message.proposer_index`.
- _[REJECT]_ The inclusion list transactions `message.transactions` length is within upperbound `MAX_TRANSACTIONS_PER_INCLUSION_LIST`.
- _[REJECT]_ The inclusion list transactions signature, `signed_inclusion_list.signature`, is valid with respect to the `message.signedSummary.message.proposer_index` pubkey.

#### Transitioning the gossip

See gossip transition details found in the [Deneb document](../deneb/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics for this upgrade.

## Design rationale

## Why is it proposer may send multiple inclusion lists? Why not just one per slot?

Proposers may submit multiple inclusion lists which provides plausible deniability and eliminating the free data availability proplem.