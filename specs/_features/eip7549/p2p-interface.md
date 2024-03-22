# EIP-7549 -- Networking

This document contains the consensus-layer networking specification for EIP-7549.

The specification of these changes continues in the same format as the network specifications of previous upgrades, and assumes them as pre-requisite.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Modifications in EIP-7549](#modifications-in-eip-7549)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`beacon_aggregate_and_proof`](#beacon_aggregate_and_proof)
        - [`beacon_attestation_{subnet_id}`](#beacon_attestation_subnet_id)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Modifications in EIP-7549

### The gossip domain: gossipsub

#### Topics and messages

The `beacon_aggregate_and_proof` and `beacon_attestation_{subnet_id}` topics are modified to support the gossip of a new attestation type.

##### Global topics

###### `beacon_aggregate_and_proof`

*[Modified in EIP7549]*

The following convenience variables are re-defined
- `index = get_committee_indices(aggregate.committee_bits)[0]`
- `aggregation_bits = aggregate.aggregation_bits[0]`

The following validations are added:
* [REJECT] `len(committee_indices) == len(aggregate.attestation_bits) == 1`, where `committee_indices = get_committee_indices(aggregate)`.
* [REJECT] `aggregate.data.index == 0`

###### `beacon_attestation_{subnet_id}`

The following convenience variables are re-defined
- `index = get_committee_indices(attestation.committee_bits)[0]`
- `aggregation_bits = attestation.aggregation_bits[0]`

The following validations are added:
* [REJECT] `len(committee_indices) == len(attestation.attestation_bits) == 1`, where `committee_indices = get_committee_indices(attestation)`.
* [REJECT] `attestation.data.index == 0`

