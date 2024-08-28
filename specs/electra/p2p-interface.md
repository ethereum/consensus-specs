# Electra -- Networking

This document contains the consensus-layer networking specification for Electra.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Modifications in Electra](#modifications-in-electra)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [`beacon_aggregate_and_proof`](#beacon_aggregate_and_proof)
    - [Attestation subnets](#attestation-subnets)
      - [`beacon_attestation_{subnet_id}`](#beacon_attestation_subnet_id)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Modifications in Electra

### The gossip domain: gossipsub

Some gossip meshes are upgraded in the fork of Electra to support upgraded types.

#### Topics and messages

Topics follow the same specification as in prior upgrades.

The `beacon_block` topic is modified to also support Electra blocks.

The `beacon_aggregate_and_proof` and `beacon_attestation_{subnet_id}` topics are modified to support the gossip of the new attestation type.

The specification around the creation, validation, and dissemination of messages has not changed from the Capella document unless explicitly noted here.

The derivation of the `message-id` remains stable.

#### Global topics

##### `beacon_aggregate_and_proof`

The following convenience variables are re-defined
- `index = get_committee_indices(aggregate.committee_bits)[0]`

The following validations are added:
* [REJECT] `len(committee_indices) == 1`, where `committee_indices = get_committee_indices(aggregate)`.
* [REJECT] `aggregate.data.index == 0`

#### Attestation subnets

##### `beacon_attestation_{subnet_id}`

The topic is updated to propagate `SingleAttestation` objects.

The following convenience variables are re-defined:
- `index = attestation.committee_index`

The following validations are added:
- _[REJECT]_ `attestation.data.index == 0`
- _[REJECT]_ The attester is a member of the committee -- i.e.
  `atestation.attester_index in get_beacon_committee(state, attestation.data.slot, index)`.

The following validations are removed:
- _[REJECT]_ The attestation is unaggregated --
  that is, it has exactly one participating validator (`len([bit for bit in aggregation_bits if bit]) == 1`, i.e. exactly 1 bit is set).
- _[REJECT]_ The number of aggregation bits matches the committee size -- i.e.
  `len(aggregation_bits) == len(get_beacon_committee(state, attestation.data.slot, index))`.
