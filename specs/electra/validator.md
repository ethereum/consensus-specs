# Electra -- Honest Validator

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Containers](#containers)
  - [Modified Containers](#modified-containers)
    - [`AggregateAndProof`](#aggregateandproof)
    - [`SignedAggregateAndProof`](#signedaggregateandproof)
- [Block proposal](#block-proposal)
  - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
    - [Attester slashings](#attester-slashings)
    - [Attestations](#attestations)
    - [Deposits](#deposits)
    - [Execution payload](#execution-payload)
- [Attesting](#attesting)
  - [Construct attestation](#construct-attestation)
- [Attestation aggregation](#attestation-aggregation)
  - [Construct aggregate](#construct-aggregate)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement Electra.

## Prerequisites

This document is an extension of the [Deneb -- Honest Validator](../../deneb/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [Electra](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Containers

### Modified Containers

#### `AggregateAndProof`

```python
class AggregateAndProof(Container):
    aggregator_index: ValidatorIndex
    aggregate: Attestation  # [Modified in Electra:EIP7549]
    selection_proof: BLSSignature
```

#### `SignedAggregateAndProof`

```python
class SignedAggregateAndProof(Container):
    message: AggregateAndProof   # [Modified in Electra:EIP7549]
    signature: BLSSignature
```

## Block proposal

### Constructing the `BeaconBlockBody`

#### Attester slashings

Changed the max attester slashings size to `MAX_ATTESTER_SLASHINGS_ELECTRA`.

#### Attestations

Changed the max attestations size to `MAX_ATTESTATIONS_ELECTRA`.

The network attestation aggregates contain only the assigned committee attestations.
Attestation aggregates received by the block proposer from the committee aggregators with disjoint `committee_bits` sets and equal `AttestationData` SHOULD be consolidated into a single `Attestation` object.
The proposer should run the following function to construct an on chain final aggregate form a list of network aggregates with equal `AttestationData`:

```python
def compute_on_chain_aggregate(network_aggregates: Sequence[Attestation]) -> Attestation:
    aggregates = sorted(network_aggregates, key=lambda a: get_committee_indices(a.committee_bits)[0])

    data = aggregates[0].data
    aggregation_bits = Bitlist[MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT]()
    for a in aggregates:
        for b in a.aggregation_bits:
            aggregation_bits.append(b)

    signature = bls.Aggregate([a.signature for a in aggregates])

    committee_indices = [get_committee_indices(a.committee_bits)[0] for a in aggregates]
    committee_flags = [(index in committee_indices) for index in range(0, MAX_COMMITTEES_PER_SLOT)]
    committee_bits = Bitvector[MAX_COMMITTEES_PER_SLOT](committee_flags)

    return Attestation(
        aggregation_bits=aggregation_bits,
        data=data,
        committee_bits=committee_bits,
        signature=signature,
    )
```

#### Deposits

*[New in Electra:EIP6110]* The expected number of deposits MUST be changed from `min(MAX_DEPOSITS, eth1_data.deposit_count - state.eth1_deposit_index)` to the result of the following function:

```python
def get_eth1_pending_deposit_count(state: BeaconState) -> uint64:
    eth1_deposit_index_limit = min(state.eth1_data.deposit_count, state.deposit_receipts_start_index)
    if state.eth1_deposit_index < eth1_deposit_index_limit:
        return min(MAX_DEPOSITS, eth1_deposit_index_limit - state.eth1_deposit_index)
    else:
        return uint64(0)
```

#### Execution payload

`prepare_execution_payload` is updated from the Deneb specs.

*Note*: In this section, `state` is the state of the slot for the block proposal _without_ the block yet applied.
That is, `state` is the `previous_state` processed through any empty slots up to the assigned slot using `process_slots(previous_state, slot)`.

*Note*: The only change to `prepare_execution_payload` is the new definition of `get_expected_withdrawals`.

```python
def prepare_execution_payload(state: BeaconState,
                              safe_block_hash: Hash32,
                              finalized_block_hash: Hash32,
                              suggested_fee_recipient: ExecutionAddress,
                              execution_engine: ExecutionEngine) -> Optional[PayloadId]:
    # Verify consistency of the parent hash with respect to the previous execution payload header
    parent_hash = state.latest_execution_payload_header.block_hash

    # Set the forkchoice head and initiate the payload build process
    withdrawals, _ = get_expected_withdrawals(state)  # [Modified in EIP-7251]

    payload_attributes = PayloadAttributes(
        timestamp=compute_timestamp_at_slot(state, state.slot),
        prev_randao=get_randao_mix(state, get_current_epoch(state)),
        suggested_fee_recipient=suggested_fee_recipient,
        withdrawals=withdrawals,
        parent_beacon_block_root=hash_tree_root(state.latest_block_header),
    )
    return execution_engine.notify_forkchoice_updated(
        head_block_hash=parent_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
    )
```

## Attesting

### Construct attestation

- Set `attestation_data.index = 0`.
- Let `attestation.aggregation_bits` be a `Bitlist[MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT]` of length `len(committee)`, where the bit of the index of the validator in the `committee` is set to `0b1`.
- Let `attestation.committee_bits` be a `Bitvector[MAX_COMMITTEES_PER_SLOT]`, where the bit at the index associated with the validator's committee is set to `0b1`.

*Note*: Calling `get_attesting_indices(state, attestation)` should return a list of length equal to 1, containing `validator_index`.

## Attestation aggregation

### Construct aggregate

- Set `attestation_data.index = 0`.
- Let `aggregation_bits` be a `Bitlist[MAX_VALIDATORS_PER_COMMITTEE * MAX_COMMITTEES_PER_SLOT]` of length `len(committee)`, where each bit set from each individual attestation is set to `0b1`.
- Set `attestation.committee_bits = committee_bits`, where `committee_bits` has the same value as in each individual attestation.
