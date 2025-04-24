# Altair -- Honest Validator

This is an accompanying document to [Altair -- The Beacon Chain](./beacon-chain.md), which describes the expected actions of a "validator" participating in the Ethereum proof-of-stake protocol.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Constants](#constants)
  - [Misc](#misc)
- [Presets](#presets)
- [Containers](#containers)
  - [`SyncCommitteeMessage`](#synccommitteemessage)
  - [`SyncCommitteeContribution`](#synccommitteecontribution)
  - [`ContributionAndProof`](#contributionandproof)
  - [`SignedContributionAndProof`](#signedcontributionandproof)
  - [`SyncAggregatorSelectionData`](#syncaggregatorselectiondata)
- [Validator assignments](#validator-assignments)
  - [Sync Committee](#sync-committee)
  - [Lookahead](#lookahead)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block proposal](#block-proposal)
    - [Preparing a `BeaconBlock`](#preparing-a-beaconblock)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Sync committee](#sync-committee)
    - [Packaging into a `SignedBeaconBlock`](#packaging-into-a-signedbeaconblock)
  - [Attesting and attestation aggregation](#attesting-and-attestation-aggregation)
  - [Sync committees](#sync-committees)
    - [Sync committee messages](#sync-committee-messages)
      - [Prepare sync committee message](#prepare-sync-committee-message)
      - [Broadcast sync committee message](#broadcast-sync-committee-message)
    - [Sync committee contributions](#sync-committee-contributions)
      - [Aggregation selection](#aggregation-selection)
      - [Construct sync committee contribution](#construct-sync-committee-contribution)
        - [Slot](#slot)
        - [Beacon block root](#beacon-block-root)
        - [Subcommittee index](#subcommittee-index)
        - [Aggregation bits](#aggregation-bits)
        - [Signature](#signature)
      - [Broadcast sync committee contribution](#broadcast-sync-committee-contribution)
- [Sync committee subnet stability](#sync-committee-subnet-stability)

<!-- mdformat-toc end -->

## Introduction

This document represents the expected behavior of an "honest validator" with respect to the Altair upgrade of the Ethereum proof-of-stake protocol.
It builds on the [previous document for the behavior of an "honest validator" from Phase 0](../phase0/validator.md) of the Ethereum proof-of-stake protocol.
This previous document is referred to below as the "Phase 0 document".

Altair introduces a new type of committee: the sync committee. Sync committees are responsible for signing each block of the canonical chain and there exists an efficient algorithm for light clients to sync the chain using the output of the sync committees.
See the [sync protocol](./light-client/sync-protocol.md) for further details on the light client sync.
Under this network upgrade, validators track their participation in this new committee type and produce the relevant signatures as required.
Block proposers incorporate the (aggregated) sync committee signatures into each block they produce.

## Prerequisites

All terminology, constants, functions, and protocol mechanics defined in the [Altair -- The Beacon Chain](./beacon-chain.md) doc are requisite for this document and used throughout.
Please see this document before continuing and use as a reference throughout.

## Constants

### Misc

| Name                                       | Value         |                                       Unit                                       |
| ------------------------------------------ | ------------- | :------------------------------------------------------------------------------: |
| `TARGET_AGGREGATORS_PER_SYNC_SUBCOMMITTEE` | `2**4` (= 16) |                                    validators                                    |
| `SYNC_COMMITTEE_SUBNET_COUNT`              | `4`           | The number of sync committee subnets used in the gossipsub aggregation protocol. |

## Presets

| Name                  | Value       |
| --------------------- | ----------- |
| `SYNC_MESSAGE_DUE_MS` | `4000`      |
| `CONTRIBUTION_DUE_MS` | `8000`      |

## Containers

### `SyncCommitteeMessage`

```python
class SyncCommitteeMessage(Container):
    # Slot to which this contribution pertains
    slot: Slot
    # Block root for this signature
    beacon_block_root: Root
    # Index of the validator that produced this signature
    validator_index: ValidatorIndex
    # Signature by the validator over the block root of `slot`
    signature: BLSSignature
```

### `SyncCommitteeContribution`

```python
class SyncCommitteeContribution(Container):
    # Slot to which this contribution pertains
    slot: Slot
    # Block root for this contribution
    beacon_block_root: Root
    # The subcommittee this contribution pertains to out of the broader sync committee
    subcommittee_index: uint64
    # A bit is set if a signature from the validator at the corresponding
    # index in the subcommittee is present in the aggregate `signature`.
    aggregation_bits: Bitvector[SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT]
    # Signature by the validator(s) over the block root of `slot`
    signature: BLSSignature
```

### `ContributionAndProof`

```python
class ContributionAndProof(Container):
    aggregator_index: ValidatorIndex
    contribution: SyncCommitteeContribution
    selection_proof: BLSSignature
```

### `SignedContributionAndProof`

```python
class SignedContributionAndProof(Container):
    message: ContributionAndProof
    signature: BLSSignature
```

### `SyncAggregatorSelectionData`

```python
class SyncAggregatorSelectionData(Container):
    slot: Slot
    subcommittee_index: uint64
```

## Validator assignments

A validator determines beacon committee assignments and beacon block proposal duties as defined in the Phase 0 document.

### Sync Committee

To determine sync committee assignments, a validator can run the following function: `is_assigned_to_sync_committee(state, epoch, validator_index)` where `epoch` is an epoch number within the current or next sync committee period.
This function is a predicate indicating the presence or absence of the validator in the corresponding sync committee for the queried sync committee period.

*Note*: Being assigned to a sync committee for a given `slot` means that the validator produces and broadcasts signatures for `slot - 1` for inclusion in `slot`.
This means that when assigned to an `epoch` sync committee signatures must be produced and broadcast for slots on range `[compute_start_slot_at_epoch(epoch) - 1, compute_start_slot_at_epoch(epoch) + SLOTS_PER_EPOCH - 1)`
rather than for the range `[compute_start_slot_at_epoch(epoch), compute_start_slot_at_epoch(epoch) + SLOTS_PER_EPOCH)`.
To reduce complexity during the Altair fork, sync committees are not expected to produce signatures for `compute_start_slot_at_epoch(ALTAIR_FORK_EPOCH) - 1`.

```python
def compute_sync_committee_period(epoch: Epoch) -> uint64:
    return epoch // EPOCHS_PER_SYNC_COMMITTEE_PERIOD
```

```python
def is_assigned_to_sync_committee(state: BeaconState,
                                  epoch: Epoch,
                                  validator_index: ValidatorIndex) -> bool:
    sync_committee_period = compute_sync_committee_period(epoch)
    current_epoch = get_current_epoch(state)
    current_sync_committee_period = compute_sync_committee_period(current_epoch)
    next_sync_committee_period = current_sync_committee_period + 1
    assert sync_committee_period in (current_sync_committee_period, next_sync_committee_period)

    pubkey = state.validators[validator_index].pubkey
    if sync_committee_period == current_sync_committee_period:
        return pubkey in state.current_sync_committee.pubkeys
    else:  # sync_committee_period == next_sync_committee_period
        return pubkey in state.next_sync_committee.pubkeys
```

### Lookahead

The sync committee shufflings give validators 1 sync committee period of lookahead which amounts to `EPOCHS_PER_SYNC_COMMITTEE_PERIOD` epochs.
At any given `epoch`, the `BeaconState` contains the current `SyncCommittee` and the next `SyncCommittee`.
Once every `EPOCHS_PER_SYNC_COMMITTEE_PERIOD` epochs, the next `SyncCommittee` becomes the current `SyncCommittee` and the next committee is computed and stored.

*Note*: The data required to compute a given committee is not cached in the `BeaconState` after committees are calculated at the period boundaries.
For this reason, *always* get committee assignments via the fields of the `BeaconState` (`current_sync_committee` and `next_sync_committee`) or use the above reference code.

A validator should plan for future sync committee assignments by noting which sync committee periods they are selected for participation.
Specifically, a validator should:

- Upon (re)syncing the chain and upon sync committee period boundaries, check for assignments in the current and next sync committee periods.
- If the validator is in the current sync committee period, then they perform the responsibilities below for sync committee rewards.
- If the validator is in the next sync committee period, they should wait until the next `EPOCHS_PER_SYNC_COMMITTEE_PERIOD` boundary and then perform the responsibilities throughout that period.

## Beacon chain responsibilities

A validator maintains the responsibilities given in the Phase 0 document.

Block proposals are modified to incorporate the sync committee signatures as detailed below.

When assigned to a sync committee, validators have a new responsibility to sign and broadcast beacon block roots during each slot of the sync committee period.
These signatures are aggregated and routed to the proposer over gossip for inclusion into a beacon block.
Assignments to a particular sync committee are infrequent at normal validator counts; however, an action every slot is required when in the current active sync committee.

### Block proposal

Refer to the phase 0 document for the majority of the [block proposal responsibility](../phase0/validator.md#block-proposal).
The validator should follow those instructions to prepare a `SignedBeaconBlock` for inclusion into the chain. All changes are additive to phase 0 and noted below.

#### Preparing a `BeaconBlock`

No change to [Preparing for a `BeaconBlock`](../phase0/validator.md#preparing-for-a-beaconblock).

#### Constructing the `BeaconBlockBody`

Each section of [Constructing the `BeaconBlockBody`](../phase0/validator.md#constructing-the-beaconblockbody) should be followed.
After constructing the `BeaconBlockBody` as per that section, the proposer has an additional task to include the sync committee signatures:

##### Sync committee

The proposer receives a number of `SyncCommitteeContribution`s (wrapped in `SignedContributionAndProof`s on the wire) from validators in the sync committee who are selected to partially aggregate signatures from independent subcommittees formed by breaking the full sync committee into `SYNC_COMMITTEE_SUBNET_COUNT` pieces (see below for details).

The proposer collects the contributions that match their local view of the chain (i.e. `contribution.beacon_block_root == block.parent_root`) for further aggregation when preparing a block.
Of these contributions, proposers should select the best contribution seen across all aggregators for each subnet/subcommittee.
A contribution with more valid signatures is better than a contribution with fewer signatures.

Recall `block.body.sync_aggregate.sync_committee_bits` is a `Bitvector` where the `i`th bit is `True` if the corresponding validator in the sync committee has produced a valid signature,
and that `block.body.sync_aggregate.sync_committee_signature` is the aggregate BLS signature combining all of the valid signatures.

Given a collection of the best seen `contributions` (with no repeating `subcommittee_index` values) and the `BeaconBlock` under construction,
the proposer processes them as follows:

```python
def process_sync_committee_contributions(block: BeaconBlock,
                                         contributions: Set[SyncCommitteeContribution]) -> None:
    sync_aggregate = SyncAggregate()
    signatures = []
    sync_subcommittee_size = SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT

    for contribution in contributions:
        subcommittee_index = contribution.subcommittee_index
        for index, participated in enumerate(contribution.aggregation_bits):
            if participated:
                participant_index = sync_subcommittee_size * subcommittee_index + index
                sync_aggregate.sync_committee_bits[participant_index] = True
        signatures.append(contribution.signature)

    sync_aggregate.sync_committee_signature = bls.Aggregate(signatures)

    block.body.sync_aggregate = sync_aggregate
```

*Note*: The resulting block must pass the validations for the `SyncAggregate` defined in `process_sync_aggregate` defined in the [state transition document](./beacon-chain.md#sync-aggregate-processing).
In particular, this means `SyncCommitteeContribution`s received from gossip must have a `beacon_block_root` that matches the proposer's local view of the chain.

#### Packaging into a `SignedBeaconBlock`

No change to [Packaging into a `SignedBeaconBlock`](../phase0/validator.md#packaging-into-a-signedbeaconblock).

### Attesting and attestation aggregation

Refer to the phase 0 document for the [attesting](../phase0/validator.md#attesting) and [attestation aggregation](../phase0/validator.md#attestation-aggregation) responsibilities.
There is no change compared to the phase 0 document.

### Sync committees

Sync committee members employ an aggregation scheme to reduce load on the global proposer channel that is monitored by all potential proposers to be able to include the full output of the sync committee every slot.
Sync committee members produce individual signatures on subnets (similar to the attestation subnets) via `SyncCommitteeMessage`s which are then collected by aggregators sampled from the sync subcommittees to produce a `SyncCommitteeContribution` which is gossiped to proposers.
This process occurs each slot.

#### Sync committee messages

##### Prepare sync committee message

If a validator is in the current sync committee (i.e. `is_assigned_to_sync_committee()` above returns `True`), then for every `slot` in the current sync committee period, the validator should prepare a `SyncCommitteeMessage` for the previous slot (`slot - 1`) according to the logic in `get_sync_committee_message` as soon as they have determined the head block of `slot - 1`. This means that when assigned to `slot` a `SyncCommitteeMessage` is prepared and broadcast in `slot-1 ` instead of `slot`.

This logic is triggered upon the same conditions as when producing an attestation.
Meaning, a sync committee member should produce and broadcast a `SyncCommitteeMessage` either when (a) the validator has received a valid block from the expected block proposer for the current `slot` or (b) `SYNC_MESSAGE_DUE_MS` milliseconds after the start of the slot has transpired -- whichever comes first.

`get_sync_committee_message(state, block_root, validator_index, privkey)` assumes the parameter `state` is the head state corresponding to processing the block up to the current slot as determined by the fork choice (including any empty slots up to the current slot processed with `process_slots` on top of the latest block), `block_root` is the root of the head block, `validator_index` is the index of the validator in the registry `state.validators` controlled by `privkey`, and `privkey` is the BLS private key for the validator.

```python
def get_sync_committee_message(state: BeaconState,
                               block_root: Root,
                               validator_index: ValidatorIndex,
                               privkey: int) -> SyncCommitteeMessage:
    epoch = get_current_epoch(state)
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE, epoch)
    signing_root = compute_signing_root(block_root, domain)
    signature = bls.Sign(privkey, signing_root)

    return SyncCommitteeMessage(
        slot=state.slot,
        beacon_block_root=block_root,
        validator_index=validator_index,
        signature=signature,
    )
```

##### Broadcast sync committee message

The validator broadcasts the assembled signature to the assigned subnet, the `sync_committee_{subnet_id}` pubsub topic.

The `subnet_id` is derived from the position in the sync committee such that the sync committee is divided into "subcommittees".
`subnet_id` can be computed via `compute_subnets_for_sync_committee(state, validator_index)` where `state` is a `BeaconState` during the matching sync committee period.

*Note*: This function returns multiple deduplicated subnets if a given validator index is included multiple times in a given sync committee across multiple subcommittees.

```python
def compute_subnets_for_sync_committee(state: BeaconState, validator_index: ValidatorIndex) -> Set[SubnetID]:
    next_slot_epoch = compute_epoch_at_slot(Slot(state.slot + 1))
    if compute_sync_committee_period(get_current_epoch(state)) == compute_sync_committee_period(next_slot_epoch):
        sync_committee = state.current_sync_committee
    else:
        sync_committee = state.next_sync_committee

    target_pubkey = state.validators[validator_index].pubkey
    sync_committee_indices = [index for index, pubkey in enumerate(sync_committee.pubkeys) if pubkey == target_pubkey]
    return set([
        SubnetID(index // (SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT))
        for index in sync_committee_indices
    ])
```

*Note*: Subnet assignment does not change during the duration of a validator's assignment to a given sync committee.

*Note*: If a validator has multiple `subnet_id` results from `compute_subnets_for_sync_committee`, the validator should broadcast a copy of the `sync_committee_message` on each of the distinct subnets.

#### Sync committee contributions

Each slot, some sync committee members in each subcommittee are selected to aggregate the `SyncCommitteeMessage`s into a `SyncCommitteeContribution` which is broadcast on a global channel for inclusion into the next block.

##### Aggregation selection

A validator is selected to aggregate based on the value returned by `is_sync_committee_aggregator()` where `signature` is the BLS signature returned by `get_sync_committee_selection_proof()`.
The signature function takes a `BeaconState` with the relevant sync committees for the queried `slot` (i.e. `state.slot` is within the span covered by the current or next sync committee period), the `subcommittee_index` equal to the `subnet_id`, and the `privkey` is the BLS private key associated with the validator.

```python
def get_sync_committee_selection_proof(state: BeaconState,
                                       slot: Slot,
                                       subcommittee_index: uint64,
                                       privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE_SELECTION_PROOF, compute_epoch_at_slot(slot))
    signing_data = SyncAggregatorSelectionData(
        slot=slot,
        subcommittee_index=subcommittee_index,
    )
    signing_root = compute_signing_root(signing_data, domain)
    return bls.Sign(privkey, signing_root)
```

```python
def is_sync_committee_aggregator(signature: BLSSignature) -> bool:
    modulo = max(1, SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT // TARGET_AGGREGATORS_PER_SYNC_SUBCOMMITTEE)
    return bytes_to_uint64(hash(signature)[0:8]) % modulo == 0
```

*Note*: The set of aggregators generally changes every slot; however, the assignments can be computed ahead of time as soon as the committee is known.

##### Construct sync committee contribution

If a validator is selected to aggregate the `SyncCommitteeMessage`s produced on a subnet during a given `slot`, they construct an aggregated `SyncCommitteeContribution`.

Collect all of the (valid) `sync_committee_messages: Set[SyncCommitteeMessage]` from the `sync_committee_{subnet_id}` gossip during the selected `slot` with an equivalent `beacon_block_root` to that of the aggregator. If `len(sync_committee_messages) > 0`, the aggregator creates a `contribution: SyncCommitteeContribution` with the following fields:

###### Slot

Set `contribution.slot = state.slot` where `state` is the `BeaconState` for the slot in question.

###### Beacon block root

Set `contribution.beacon_block_root = beacon_block_root` from the `beacon_block_root` found in the `sync_committee_messages`.

###### Subcommittee index

Set `contribution.subcommittee_index` to the index for the subcommittee index corresponding to the subcommittee assigned to this subnet. This index matches the `subnet_id` used to derive the topic name.

###### Aggregation bits

Let `contribution.aggregation_bits` be a `Bitvector[SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_SUBNET_COUNT]`, where the `index`th bit is set in the `Bitvector` for each corresponding validator included in this aggregate from the corresponding subcommittee.
An aggregator finds the index in the sync committee (as determined by a reverse pubkey lookup on `state.current_sync_committee.pubkeys`) for a given validator referenced by `sync_committee_message.validator_index` and maps the sync committee index to an index in the subcommittee (along with the prior `subcommittee_index`). This index within the subcommittee is set in `contribution.aggregation_bits`.

For example, if a validator with index `2044` is pseudo-randomly sampled to sync committee index `135`. This sync committee index maps to `subcommittee_index` `1` with position `7` in the `Bitvector` for the contribution.

*Note*: A validator **could be included multiple times** in a given subcommittee such that multiple bits are set for a single `SyncCommitteeMessage`.

###### Signature

Set `contribution.signature = aggregate_signature` where `aggregate_signature` is obtained by assembling the appropriate collection of `BLSSignature`s from the set of `sync_committee_messages` and using the `bls.Aggregate()` function to produce an aggregate `BLSSignature`.

The collection of input signatures should include one signature per validator who had a bit set in the `aggregation_bits` bitfield, with repeated signatures if one validator maps to multiple indices within the subcommittee.

##### Broadcast sync committee contribution

If the validator is selected to aggregate (`is_sync_committee_aggregator()`), then they broadcast their best aggregate as a `SignedContributionAndProof` to the global aggregate channel (`sync_committee_contribution_and_proof` topic) `CONTRIBUTION_DUE_MS` milliseconds after the start of `slot` has transpired.

Selection proofs are provided in `ContributionAndProof` to prove to the gossip channel that the validator has been selected as an aggregator.

`ContributionAndProof` messages are signed by the aggregator and broadcast inside of `SignedContributionAndProof` objects to prevent a class of DoS attacks and message forgeries.

First, `contribution_and_proof = get_contribution_and_proof(state, validator_index, contribution, privkey)` is constructed.

```python
def get_contribution_and_proof(state: BeaconState,
                               aggregator_index: ValidatorIndex,
                               contribution: SyncCommitteeContribution,
                               privkey: int) -> ContributionAndProof:
    selection_proof = get_sync_committee_selection_proof(
        state,
        contribution.slot,
        contribution.subcommittee_index,
        privkey,
    )
    return ContributionAndProof(
        aggregator_index=aggregator_index,
        contribution=contribution,
        selection_proof=selection_proof,
    )
```

Then `signed_contribution_and_proof = SignedContributionAndProof(message=contribution_and_proof, signature=signature)` is constructed and broadcast. Where `signature` is obtained from:

```python
def get_contribution_and_proof_signature(state: BeaconState,
                                         contribution_and_proof: ContributionAndProof,
                                         privkey: int) -> BLSSignature:
    contribution = contribution_and_proof.contribution
    domain = get_domain(state, DOMAIN_CONTRIBUTION_AND_PROOF, compute_epoch_at_slot(contribution.slot))
    signing_root = compute_signing_root(contribution_and_proof, domain)
    return bls.Sign(privkey, signing_root)
```

## Sync committee subnet stability

The sync committee subnets need special care to ensure stability given the relatively low number of validators involved in the sync committee at any particular time.
To provide this stability, a validator must do the following:

- Maintain advertisement of the subnet the validator in the sync committee is assigned to in their node's ENR as soon as they have joined the subnet.
  Subnet assignments are known `EPOCHS_PER_SYNC_COMMITTEE_PERIOD` epochs in advance and can be computed with `compute_subnets_for_sync_committee` defined above.
  ENR advertisement is indicated by setting the appropriate bit(s) of the bitfield found under the `syncnets` key in the ENR corresponding to the derived `subnet_id`(s).
  Any bits modified for the sync committee responsibilities are unset in the ENR once the node no longer has any validators in the subcommittee.

  *Note*: The first sync committee from phase 0 to the Altair fork will not be known until the fork happens, which implies subnet assignments are not known until then.
  Early sync committee members should listen for topic subscriptions from peers and employ discovery via the ENR advertisements near the fork boundary to form initial subnets.
  Some early sync committee rewards may be missed while the initial subnets form.

- To join a sync committee subnet, select a random number of epochs before the end of the current sync committee period between 1 and `SYNC_COMMITTEE_SUBNET_COUNT`, inclusive.
  Validators should join their member subnet at the beginning of the epoch they have randomly selected.
  For example, if the next sync committee period starts at epoch `853,248` and the validator randomly selects an offset of `3`, they should join the subnet at the beginning of epoch `853,245`.
  Validators should leverage the lookahead period on sync committee assignments so that they can join the appropriate subnets ahead of their assigned sync committee period.
