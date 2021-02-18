# Ethereum Altair networking specification

This document contains the networking specification for Ethereum 2.0 clients added during the Altair deployment. 
This document should be viewed as additive to the [document from Phase 0](../phase0/p2p-interface.md) and will be referred to as the "phase 0 document" hereafter. 
Readers should understand the phase 0 document and use it as a basis to understand the changes outlined in this document.

In particular, Altair introduces changes to the gossip domain and a small change to ENR advertisement in the discovery domain. 
The phase 0 document should be consulted for specs on the network fundamentals, the existing gossip domain, the req/resp domain and the discovery domain.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

  - [Warning](#warning)
- [Modifications in Altair](#modifications-in-altair)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_block`](#beacon_block)
        - [`sync_committee_contribution_and_proof`](#sync_committee_contribution_and_proof)
      - [Sync committee subnets](#sync-committee-subnets)
        - [`sync_committee_{subnet_id}`](#sync_committee_subnet_id)
      - [Sync committees and aggregation](#sync-committees-and-aggregation)
  - [The Req/Resp domain](#the-reqresp-domain)
  - [The discovery domain: discv5](#the-discovery-domain-discv5)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Warning

This document is currently illustrative for early Altair testnets and some parts are subject to change. 
Refer to the note in the [validator guide](./validator.md) for further details. 

# Modifications in Altair

## The gossip domain: gossipsub

Gossip meshes are added in Altair to support the consensus activities of the sync committees. 
Validators use an aggregation scheme to balance the processing and networking load across all of the relevant actors.

### Topics and messages

Topics follow the same specification as in the phase 0 document. 
New topics are added in Altair to support the sync committees and the beacon block topic is updated with the modified type.

The specification around the creation, validation, and dissemination of messages has not changed from the Phase 0 document.

The new topics along with the type of the `data` field of a gossipsub message are given in this table:

| Name | Message Type |
| - | - |
| `beacon_block` | `SignedBeaconBlock` (modified) |
| `sync_committee_contribution_and_proof` | `SignedContributionAndProof` |
| `sync_committee_{subnet_id}` | `SyncCommitteeSignature` |

Definitions of these new types can be found in the [Altair validator guide](./validator.md#containers).

#### Global topics

Altair changes the type of the global beacon block topic and adds one global topic to propagate partially aggregated sync committee signatures to all potential proposers of beacon blocks.

##### `beacon_block`

The existing specification for this topic does not change from the Phase 0 document, but the type of the payload does change to the (modified) `SignedBeaconBlock`. 
This type changes due to the inclusion of the inner `BeaconBlockBody` that is modified in Altair. 
See the [state transition document](./beacon-chain.md#beaconblockbody) for Altair for further details.

##### `sync_committee_contribution_and_proof`
 
This topic is used to propagate partially aggregated sync committee signatures to be included in future blocks.

The following validations MUST pass before forwarding the `signed_contribution_and_proof` on the network; define `contribution_and_proof = signed_contribution_and_proof.message` and `contribution = contribution_and_proof.contribution` for convenience:

- _[IGNORE]_ The contribution's slot is for the current slot, i.e. `contribution.slot == current_slot`.
- _[IGNORE]_ The block being signed over (`contribution.beacon_block_root`) has been seen (via both gossip and non-gossip sources).
- _[REJECT]_ The subcommittee index is in the allowed range, i.e. `contribution.subcommittee_index < SYNC_COMMITTEE_SUBNET_COUNT`.
- _[IGNORE]_ The sync committee contribution is the first valid contribution received for the aggregator with index `contribution_and_proof.aggregator_index` for the slot `contribution.slot`.
- _[REJECT]_ The aggregator's validator index is within the current sync committee --
  i.e. `state.validators[aggregate_and_proof.aggregator_index].pubkey in state.current_sync_committee.pubkeys`.
- _[REJECT]_ The `contribution_and_proof.selection_proof` is a valid signature of the `contribution.slot` by the validator with index `contribution_and_proof.aggregator_index`.
- _[REJECT]_ `contribution_and_proof.selection_proof` selects the validator as an aggregator for the slot -- i.e. `is_sync_committee_aggregator(state, contribution.slot, contribution_and_proof.selection_proof)` returns `True`.
- _[REJECT]_ The aggregator signature, `signed_contribution_and_proof.signature`, is valid.
- _[REJECT]_ The aggregate signature is valid for the message `beacon_block_root` and aggregate pubkey derived from the participation info in `aggregation_bits` for the subcommittee specified by the `subcommittee_index`.

#### Sync committee subnets

Sync committee subnets are used to propagate unaggregated sync committee signatures to subsections of the network.

##### `sync_committee_{subnet_id}`

The `sync_committee_{subnet_id}` topics are used to propagate unaggregated sync committee signatures to the subnet `subnet_id` to be aggregated before being gossiped to the global `sync_committee_contribution_and_proof` topic.

The following validations MUST pass before forwarding the `sync_committee_signature` on the network:

- _[IGNORE]_ The signature's slot is for the current slot, i.e. `sync_committee_signature.slot == current_slot`.
- _[IGNORE]_ The block being signed over (`sync_committee_signature.beacon_block_root`) has been seen (via both gossip and non-gossip sources).
- _[IGNORE]_ There has been no other valid sync committee signature for the declared `slot` for the validator referenced by `sync_committee_signature.validator_index`.
- _[REJECT]_ The validator producing this `sync_committee_signature` is in the current sync committee, i.e. `state.validators[sync_committee_signature.validator_index].pubkey in state.current_sync_committee.pubkeys`.
- _[REJECT]_ The `subnet_id` is correct, i.e. `subnet_id in compute_subnets_for_sync_committee(state, sync_committee_signature.validator_index)`.
- _[REJECT]_ The `signature` is valid for the message `beacon_block_root` for the validator referenced by `validator_index`.

#### Sync committees and aggregation

The aggregation scheme closely follows the design of the attestation aggregation scheme. 
Sync committee signatures are broadcast into "subnets" defined by a topic. 
The number of subnets is defined by `SYNC_COMMITTEE_SUBNET_COUNT` in the [Altair validator guide](./validator.md#constants). 
Sync committee members are divided into "subcommittees" which are then assigned to a subnet for the duration of tenure in the sync committee. 
Individual validators can be duplicated in the broader sync committee such that they are included multiple times in a given subcommittee or across multiple subcommittees.

Unaggregated signatures (along with metadata) are sent as `SyncCommitteeSignature`s on the `sync_committee_{subnet_id}` topics.

Aggregated sync committee signatures are packaged into (signed) `SyncCommitteeContribution` along with proofs and gossiped to the `sync_committee_contribution_and_proof` topic.

## The Req/Resp domain

* (TODO) specify how to handle different types of blocks on RPC responses.

## The discovery domain: discv5

The `attnets` key of the ENR is used as defined in the phase 0 document.

An additional bitfield is added to the ENR under the key `syncnets` to facilitate sync committee subnet discovery.
The length of this bitfield is `SYNC_COMMITTEE_SUBNET_COUNT` where each bit corresponds to a distinct `subnet_id` for a specific sync committee subnet. 
The `i`th bit is set in this bitfield if the validator is currently subscribed to the `sync_committee_{i}` topic.

See the [validator document](./validator.md#sync-committee-subnet-stability) for further details on how the new bits are used.
