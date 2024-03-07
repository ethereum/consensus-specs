<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [EIP-7547 -- Networking](#eip-7547----networking)
    - [Execution](#execution)
  - [Containers](#containers)
    - [New Containers](#new-containers)
      - [`InclusionListSidecar`](#inclusionlistsidecar)
      - [`SignedInclusionListSidecar`](#signedinclusionlistsidecar)
  - [Modifications in EIP7547](#modifications-in-eip7547)
    - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
      - [Topics and messages](#topics-and-messages)
        - [Global topics](#global-topics)
          - [`inclusion_list_sidecar`](#inclusion_list_sidecar)
      - [Transitioning the gossip](#transitioning-the-gossip)
  - [Design rationale](#design-rationale)
  - [Why is it proposer may send multiple inclusion lists? Why not just one per slot?](#why-is-it-proposer-may-send-multiple-inclusion-lists-why-not-just-one-per-slot)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# EIP-7547 -- Networking

This document contains the consensus-layer networking specification for EIP-7547.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

### Execution

## Containers

### New Containers

#### `InclusionListSidecar`

```python
class InclusionListSidecar(Container):
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_INCLUSION_LIST]
    proposer_index: ValidatorIndex
    parent_root: Root
    slot: Slot
    signed_inclusion_list_summary: SignedInclusionListSummary
```

#### `SignedInclusionListSidecar`

```python
class SignedInclusionListSidecar(Container):
    message: InclusionListSidecar
    signature: BLSSignature
```

## Modifications in EIP7547

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork for EIP7547 to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The derivation of the `message-id` remains stable.

##### Global topics

###### `inclusion_list_sidecar`

The *type* of the payload of is `SignedInclusionListSidecar`, assuming the aliases `inclusion_list_sidecar = signed_inclusion_list_sidecar.message` and `signed_inclusion_list_summary = inclusion_list_sidecar.signed_inclusion_list_summary`.

The following validations MUST pass before forwarding the `signed_inclusion_list_sidecar` on the network.

- _[REJECT]_ The inclusion list transactions `inclusion_list_sidecar.transactions` length is within upperbound `MAX_TRANSACTIONS_PER_INCLUSION_LIST`.
- _[IGNORE]_ The sidecar is not from a future slot (with a `MAXIMUM_GOSSIP_CLOCK_DISPARITY` allowance) -- i.e. validate that `inclusion_list_sidecar.slot <= current_slot` (a client MAY queue future sidecars for processing at the appropriate slot).
- _[IGNORE]_ The sidecar is from a slot greater than the latest finalized slot -- i.e. validate that `inclusion_list_sidecar.slot > compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)`
- _[REJECT]_ The inclusion list sidecar signature, `signed_inclusion_list_sidecar.signature`, is valid with respect to the `inclusion_list_sidecar.proposer_index` pubkey.
- _[REJECT]_ The inclusion list summary signature, `signed_inclusion_list_summary.signature`, is a valid signature of `signed_inclusion_list_summary.summary` with respect to the `inclusion_list_sidecar.proposer_index` pubkey.
- _[IGNORE]_ The sidecar's block's parent (defined by `inclusion_list_sidecar.parent_root`) has been seen (via both gossip and non-gossip sources) (a client MAY queue sidecars for processing once the parent block is retrieved).
- _[REJECT]_ The sidecar's block's parent (defined by `inclusion_list_sidecar.parent_root`) passes validation.
- _[REJECT]_ The sidecar is from a higher slot than the sidecar's block's parent (defined by `inclusion_list_sidecar.parent_root`).
- _[REJECT]_ The current finalized_checkpoint is an ancestor of the sidecar's block -- i.e. `get_checkpoint_block(store, inclusion_list_sidecar.parent_root, store.finalized_checkpoint.epoch) == store.finalized_checkpoint.root`.
- _[IGNORE]_ The sidecar is the first sidecar for the tuple (inclusion_list_sidecar.slot, inclusion_list_sidecar.proposer_index) with valid signature.
- _[REJECT]_ The sidecar is proposed by the expected proposer_index for the `inclusion_list_sidecar.slot` in the context of the current shuffling (defined by parent_root/slot). If the proposer_index cannot immediately be verified against the expected shuffling, the sidecar MAY be queued for later processing while proposers for the summary's branch are calculated -- in such a case do not REJECT, instead IGNORE this message.


#### Transitioning the gossip

See gossip transition details found in the [Deneb document](../deneb/p2p-interface.md#transitioning-the-gossip) for
details on how to handle transitioning gossip topics for this upgrade.

## Design rationale

## Why is it proposer may send multiple inclusion lists? Why not just one per slot?

Proposers may submit multiple inclusion lists, providing validators with plausible deniability and eliminating a data availability attack route. This concept stems from the "no free lunch IL design" which lets proposers send multiple ILs. The idea is that since only one IL is eventually chosen from many, thus its contents can't be relied upon for data availability.