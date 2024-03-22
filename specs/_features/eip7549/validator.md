# Deneb -- Honest Validator

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Modifications in EIP-7549](#modifications-in-eip-7549)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Attestations](#attestations)
  - [Attesting](#attesting)
    - [Construct attestation](#construct-attestation)
  - [Attestation aggregation](#attestation-aggregation)
    - [Construct aggregate](#construct-aggregate)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Modifications in EIP-7549

### Block proposal

#### Constructing the `BeaconBlockBody`

##### Attestations

The network attestation aggregates contain only the assigned committee attestations.
Attestation aggregates received by the block proposer from the committee aggregators with disjoint `committee_bits` sets and equal `AttestationData` SHOULD be consolidated into a single `Attestation` object.
The proposer should run the following function to construct an on chain final aggregate form a list of network aggregates with equal `AttestationData`:

```python
def compute_on_chain_aggregate(network_aggregates: List[Attestation]) -> Attestation:
    aggregates = sorted(network_aggregates, key=lambda a: get_committee_indices(a.committee_bits)[0])

    data = aggregates[0].data
    aggregation_bits = [a.aggregation_bits[0] for a in aggregates]
    signature = bls.Aggregate([a.signature for a in aggregates])

    committee_indices = [get_committee_indices(a.committee_bits)[0] for a in aggregates]
    committee_flags = [(index in committee_indices) for index in range(0, MAX_COMMITTEES_PER_SLOT)]        
    committee_bits = Bitvector[MAX_COMMITTEES_PER_SLOT](committee_flags)

    return Attestation(aggregation_bits, data, committee_bits, signature)
```

### Attesting

#### Construct attestation

- Set `attestation_data.index = 0`.
- Let `aggregation_bits` be a `Bitlist[MAX_VALIDATORS_PER_COMMITTEE]` of length `len(committee)`, where the bit of the index of the validator in the `committee` is set to `0b1`.
- Set `attestation.aggregation_bits = [aggregation_bits]`, a list of length 1
- Let `committee_bits` be a `Bitvector[MAX_COMMITTEES_PER_SLOT]`, where the bit at the index associated with the validator's committee is set to `0b1`
- Set `attestation.committee_bits = committee_bits`

*Note*: Calling `get_attesting_indices(state, attestation)` should return a list of length equal to 1, containing `validator_index`.

### Attestation aggregation

#### Construct aggregate

- Set `attestation_data.index = 0`.
- Let `aggregation_bits` be a `Bitlist[MAX_VALIDATORS_PER_COMMITTEE]` of length `len(committee)`, where each bit set from each individual attestation is set to `0b1`.
- Set `attestation.aggregation_bits = [aggregation_bits]`, a list of length 1
- Set `attestation.committee_bits = committee_bits`, where `committee_bits` has the same value as in each individual attestation

