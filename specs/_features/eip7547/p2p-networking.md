<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [EIP-7547 -- Networking](#eip-7547----networking)
  - [Preset](#preset)
    - [Execution](#execution)
  - [Containers](#containers)
    - [New Containers](#new-containers)
      - [`SignedInclusionListTransactions`](#signedinclusionlisttransactions)
      - [`SignedBeaconBlockAndInclusionList`](#signedbeaconblockandinclusionlist)
  - [Modifications in EIP7547](#modifications-in-eip7547)
    - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
      - [Topics and messages](#topics-and-messages)
        - [Global topics](#global-topics)
          - [`beacon_block`](#beacon_block)
      - [Transitioning the gossip](#transitioning-the-gossip)
  - [Design rationale](#design-rationale)
  - [Why is it proposer may send multiple inclusion lists? Why not just one per slot?](#why-is-it-proposer-may-send-multiple-inclusion-lists-why-not-just-one-per-slot)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# EIP-7547 -- Networking

This document contains the consensus-layer networking specification for EIP-7547.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Preset

### Execution

| Name | Value |
| - | - |
| `MAX_TRANSACTIONS_PER_INCLUSION_LIST` |  `uint64(2**4)` (= 16) |

## Containers

### New Containers

#### `SignedInclusionListTransactions`

```python
class SignedInclusionListTransactions(Container):
    transactions: transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    signature: BLSSignature
```

#### `SignedBeaconBlockAndInclusionList`

```python
class SignedBeaconBlockAndInclusionList(Container):
    signed_block: SignedBeaconBlock
    signed_transactions: SignedInclusionListTransactions
```

## Modifications in EIP7547

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork for EIP7547 to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The derivation of the `message-id` remains stable.

##### Global topics

###### `beacon_block`

The *type* of the payload of this topic changes to the (modified) `BeaconBlockAndInclusionList`.

New validation:

The following validations MUST pass before forwarding the `beacon_block` on the network.

- _[REJECT]_ The inclusion list transactions `beacon_block.transactions` length is within upperbound `MAX_TRANSACTIONS_PER_INCLUSION_LIST`.
- _[REJECT]_ The inclusion list summary has the same length of transactions `len(beacon_block.signed_block.inclusion_list_summary) == len(beacon_block.transactions)`.
- _[REJECT]_ The inclusion list transactions signature, `beacon_block.signed_transactions.signature`, is valid with respect to the `proposer_index` pubkey.
- _[REJECT]_ The summary is proposed by the expected proposer_index for the summary's slot in the context of the current shuffling (defined by parent_root/slot). If the proposer_index cannot immediately be verified against the expected shuffling, the inclusion list MAY be queued for later processing while proposers for the summary's branch are calculated -- in such a case do not REJECT, instead IGNORE this message.

#### Transitioning the gossip

See gossip transition details found in the [Deneb document](../deneb/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics for this upgrade.

## Design rationale

## Why is it proposer may send multiple inclusion lists? Why not just one per slot?

Proposers may submit multiple inclusion lists, providing validators with plausible deniability and eliminating a data availability attack route. This concept stems from the "no free lunch IL design" which lets proposers send multiple ILs. The idea is that since only one IL is eventually chosen from many, thus its contents can't be relied upon for data availability.
