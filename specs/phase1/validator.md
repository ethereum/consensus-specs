# Ethereum 2.0 Phase 0 -- Honest Validator

**Notice**: This document is a work-in-progress for researchers and implementers. This is an accompanying document to [Ethereum 2.0 Phase 1](./), which describes the expected actions of a "validator" participating in the Ethereum 2.0 Phase 1 protocol.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Constants](#constants)
- [Becoming a validator](#becoming-a-validator)
- [Beacon chain validator assignments](#beacon-chain-validator-assignments)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block proposal](#block-proposal)
    - [Preparing for a `BeaconBlock`](#preparing-for-a-beaconblock)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Custody slashings](#custody-slashings)
      - [Custody key reveals](#custody-key-reveals)
      - [Early derived secret reveals](#early-derived-secret-reveals)
      - [Shard transitions](#shard-transitions)
      - [Light client fields](#light-client-fields)
    - [Packaging into a `SignedBeaconBlock`](#packaging-into-a-signedbeaconblock)
  - [Attesting](#attesting)
    - [`FullAttestationData`](#fullattestationdata)
    - [`FullAttestation`](#fullattestation)
    - [Timing](#timing)
    - [Attestation data](#attestation-data)
      - [Head shard root](#head-shard-root)
      - [Shard transition](#shard-transition)
    - [Construct attestation](#construct-attestation)
      - [Custody bits blocks](#custody-bits-blocks)
      - [Signature](#signature)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the expected behavior of an "honest validator" with respect to Phase 1 of the Ethereum 2.0 protocol. This document does not distinguish between a "node" (i.e. the functionality of following and reading the beacon chain) and a "validator client" (i.e. the functionality of actively participating in consensus). The separation of concerns between these (potentially) two pieces of software is left as a design decision that is out of scope.

A validator is an entity that participates in the consensus of the Ethereum 2.0 protocol. This is an optional role for users in which they can post ETH as collateral and verify and attest to the validity of blocks to seek financial returns in exchange for building and securing the protocol. This is similar to proof-of-work networks in which miners provide collateral in the form of hardware/hash-power to seek returns in exchange for building and securing the protocol.

## Prerequisites

This document is an extension of the [Phase 0 -- Validator](../phase0/validator.md). All behaviors and definitions defined in the Phase 0 doc carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the [Phase 1 -- The Beacon Chain](./beacon-chain.md) and [Phase 1 -- Custody Game](./custody-game.md) docs are requisite for this document and used throughout. Please see the Phase 1 docs before continuing and use as a reference throughout.

## Constants

See constants from [Phase 0 validator guide](../phase0/validator.md#constants).

## Becoming a validator

Becoming a validator in Phase 1 is unchanged from Phase 0. See the [Phase 0 validator guide](../phase0/validator.md#becoming-a-validator) for details.

## Beacon chain validator assignments

Beacon chain validator assignments to beacon committees and beacon block proposal are unchanged from Phase 0. See the [Phase 0 validator guide](../phase0/validator.md#validator-assignments) for details.

## Beacon chain responsibilities

A validator has two primary responsibilities to the beacon chain: [proposing blocks](#block-proposal) and [creating attestations](#attestations-1). Proposals happen infrequently, whereas attestations should be created once per epoch.

These responsibilities are largely unchanged from Phase 0, but utilize the updated `SignedBeaconBlock`, `BeaconBlock`,  `BeaconBlockBody`, `Attestation`, and `AttestationData` definitions found in Phase 1. Below notes only the additional and modified behavior with respect to Phase 0.

### Block proposal

#### Preparing for a `BeaconBlock`

`slot`, `proposer_index`, `parent_root` fields are unchanged.

#### Constructing the `BeaconBlockBody`

`randao_reveal`, `eth1_data`, and `graffiti` are unchanged.

`proposer_slashings`, `deposits`, and `voluntary_exits` are unchanged.

`attester_slashings` and `attestations` operate exactly as in Phase 0, but with new definitations of `AttesterSlashing` and `Attestation`, along with modified validation conditions found in `process_attester_slashing` and `process_attestation`.

##### Custody slashings

Up to `MAX_CUSTODY_SLASHINGS`, [`CustodySlashing`](./custody-game.md#custodyslashing) objects can be included in the `block`. The custody slashings must satisfy the verification conditions found in [custody slashings processing](./custody-game.md#custody-slashings). The validator receives a small "whistleblower" reward for each custody slashing included (THIS IS NOT CURRENTLY THE CASE BUT PROBABLY SHOULD BE).

##### Custody key reveals

Up to `MAX_CUSTODY_KEY_REVEALS`, [`CustodyKeyReveal`](./custody-game.md#custodykeyreveal) objects can be included in the `block`. The custody key reveals must satisfy the verification conditions found in [custody key reveal processing](./custody-game.md#custody-key-reveals). The validator receives a small reward for each custody key reveal included.

##### Early derived secret reveals

Up to `MAX_EARLY_DERIVED_SECRET_REVEALS`, [`EarlyDerivedSecretReveal`](./custody-game.md#earlyderivedsecretreveal) objects can be included in the `block`. The early derived secret reveals must satisfy the verification conditions found in [early derived secret reveal processing](./custody-game.md#custody-key-reveals). The validator receives a small "whistleblower" reward for each early derived secrete reveal included.

##### Shard transitions

Exactly `MAX_SHARDS` [`ShardTransition`](./beacon-chain#shardtransition) objects are included in the block. Default each to an empty `ShardTransition()`. Then for each committee assigned to the slot with an associated `committee_index` and `shard`, set `shard_transitions[shard] = full_transitions[winning_root]` if the committee had enough weight to form a crosslink this slot.

Specifically:
* Call `shards, winning_roots = get_successful_shard_transitions(state, block.slot, attestations)`
* Let `full_transitions` be a dictionary mapping from the `shard_transition_root`s found in `attestations` to the corresponding full `ShardTransition`
* Then for each `shard` and `winning_root` in `zip(shards, winning_roots)` set `shard_transitions[shard] = full_transitions[winning_root]`

```python
def get_successful_shard_transitions(state: BeaconState,
                                     slot: Slot,
                                     attestations: Attestation) -> Tuple[Sequence[Shard], Sequence[Root]]:
    shards = []
    winning_roots = []
    committee_count = get_committee_count_at_slot(state, slot)
    for committee_index in map(CommitteeIndex, range(committee_count)):
        shard = compute_shard_from_committee_index(state, committee_index, slot)
        # All attestations in the block for this committee/shard and current slot
        shard_attestations = [
            attestation for attestation in attestations
            if attestation.data.index == committee_index and attestation.data.slot == slot
        ]
        committee = get_beacon_committee(state, state.slot, committee_index)

        # Loop over all shard transition roots, looking for a winning root
        shard_transition_roots = set([a.data.shard_transition_root for a in attestations])
        for shard_transition_root in sorted(shard_transition_roots):
            transition_attestations = [a for a in attestations if a.data.shard_transition_root == shard_transition_root]
            transition_participants: Set[ValidatorIndex] = set()
            for attestation in transition_attestations:
                participants = get_attesting_indices(state, attestation.data, attestation.aggregation_bits)
                transition_participants = transition_participants.union(participants)

            enough_online_stake = (
                get_total_balance(state, online_indices.intersection(transition_participants)) * 3 >=
                get_total_balance(state, online_indices.intersection(committee)) * 2
            )
            if enough_online_stake:
                shards.append(shard)
                transitions.append(shard_transition_root)
                break

    return shards, winning_roots
```

##### Light client fields

First retrieve `best_aggregate` from `get_best_light_client_aggregate` where `aggregates` is a list of valid aggregated `LightClientVote`s for the previous slot.

Then:
* Set `light_client_bits = best_aggregate.aggregation_bits`
* Set `light_client_signature = best_aggregate.signature`

```python
def select_best_light_client_aggregate(block: BeaconBlock,
                                       aggregates: Sequence[LightClientVote]) -> LightClientVote:
    viable_aggregates = [
        aggregate in aggregates
        if aggregate.slot == get_previous_slot(block.slot) and aggregate.beacon_block_root == block.parent_root
    ]

    return max(
        viable_aggregates,
        key=lambda a: len([_ for i in a.aggregation_bits if i == 1]),
        default=LightClientVote(),
    )
```

#### Packaging into a `SignedBeaconBlock`

Packaging into a `SignedBeaconBlock` is unchanged from Phase 0.

### Attesting

A validator is expected to create, sign, and broadcast an attestation during each epoch.

Assignments and the core of this duty are unchanged from Phase 0. There are a few additional fields related to the assigned shard chain and custody bit.

The `Attestation` and `AttestationData` defined in the [Phase 1 Beacon Chain spec]() utilizes `shard_transition_root: Root` rather than a full `ShardTransition`. For the purposes of the validator and p2p layer, a modified `FullAttestationData` and containing `FullAttestation` are used to send the accompanying `ShardTransition` in its entirety. Note that due to the properties of SSZ `hash_tree_root`, the root and signatures of `AttestationData` and `FullAttestationData` are equivalent.

#### `FullAttestationData`

```python
class FullAttestationData(Container):
    slot: Slot
    index: CommitteeIndex
    # LMD GHOST vote
    beacon_block_root: Root
    # FFG vote
    source: Checkpoint
    target: Checkpoint
    # Current-slot shard block root
    head_shard_root: Root
    # Full shard transition
    shard_transition: ShardTransition
```

#### `FullAttestation`

```python
class FullAttestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: FullAttestationData
    custody_bits_blocks: List[Bitlist[MAX_VALIDATORS_PER_COMMITTEE], MAX_SHARD_BLOCKS_PER_ATTESTATION]
    signature: BLSSignature
```

#### Timing

Note the timing of when to create/broadcast is altered from Phase 1.

A validator should create and broadcast the `attestation` to the associated attestation subnet when either (a) the validator has received a valid `BeaconBlock` from the expected beacon block proposer and a valid `ShardBlock` for the expected shard block porposer for the assigned `slot` or (b) one-half of the `slot` has transpired (`SECONDS_PER_SLOT / 2` seconds after the start of `slot`) -- whichever comes _first_.

#### Attestation data

`attestation_data` is constructed in the same manner as Phase 0 but uses `FullAttestationData` with the addition of two fields -- `head_shard_root` and `shard_transition`.

- Let `head_block` be the result of running the fork choice during the assigned slot.
- Let `head_state` be the state of `head_block` processed through any empty slots up to the assigned slot using `process_slots(state, slot)`.
- Let `head_shard_block` be the result of running the fork choice on the assigned shard chain during the assigned slot.

##### Head shard root

Set `attestation_data.head_shard_root = hash_tree_root(head_shard_block)`.

##### Shard transition

Set `shard_transition` to the value returned by `get_shard_transition()`.

```python
def get_shard_transition(state: BeaconState, shard: Shard, shard_blocks: Sequence[ShardBlock])
    latest_shard_slot = get_latest_slot_for_shard(state, shard)
    offset_slots = [Slot(latest_shard_slot + x) for x in SHARD_BLOCK_OFFSETS if latest_shard_slot + x <= state.slot]
    return ShardTransition()
```

#### Construct attestation

Next, the validator creates `attestation`, a `FullAttestation` as defined above.

`attestation.data` and `attestation.aggregation_bits` are unchanged from Phase 0.

##### Custody bits blocks

- Let `attestation.custody_bits_blocks` be a the value returned by `get_custody_bits_blocks()`

```python
def get_custody_bits_blocks() -> List[Bitlist[MAX_VALIDATORS_PER_COMMITTEE], MAX_SHARD_BLOCKS_PER_ATTESTATION]:
    pass
```

##### Signature

Set `attestation.signature = attestation_signature` where `attestation_signature` is obtained from:

```python
def get_attestation_signature(state: BeaconState,
                              attestation_data: AttestationData,
                              custody_bits_blocks,
                              privkey: int) -> List[Bitlist[MAX_VALIDATORS_PER_COMMITTEE], MAX_SHARD_BLOCKS_PER_ATTESTATION]:
    pass
```


