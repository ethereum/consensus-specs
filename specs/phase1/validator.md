# Ethereum 2.0 Phase 0 -- Honest Validator

**Notice**: This document is a work-in-progress for researchers and implementers. This is an accompanying document to [Ethereum 2.0 Phase 1](./), which describes the expected actions of a "validator" participating in the Ethereum 2.0 Phase 1 protocol.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Constants](#constants)
  - [Misc](#misc)
- [Becoming a validator](#becoming-a-validator)
- [Beacon chain validator assignments](#beacon-chain-validator-assignments)
  - [Lookahead](#lookahead)
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
  - [Light client committee](#light-client-committee)
    - [Preparation](#preparation)
    - [Light clent vote](#light-clent-vote)
      - [Light client vote data](#light-client-vote-data)
        - [`LightClientVoteData`](#lightclientvotedata)
      - [Construct vote](#construct-vote)
        - [`LightClientVote`](#lightclientvote)
      - [Broadcast](#broadcast)
    - [Light client vote aggregation](#light-client-vote-aggregation)
    - [Aggregation selection](#aggregation-selection)
    - [Construct aggregate](#construct-aggregate)
    - [Broadcast aggregate](#broadcast-aggregate)
      - [`LightAggregateAndProof`](#lightaggregateandproof)
      - [`SignedLightAggregateAndProof`](#signedlightaggregateandproof)

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

### Misc

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `TARGET_LIGHT_CLIENT_AGGREGATORS_PER_SLOT` | `2**2` (= 8) | validators | |

## Becoming a validator

Becoming a validator in Phase 1 is unchanged from Phase 0. See the [Phase 0 validator guide](../phase0/validator.md#becoming-a-validator) for details.

## Beacon chain validator assignments

Beacon chain validator assignments to beacon committees and beacon block proposal are unchanged from Phase 0. See the [Phase 0 validator guide](../phase0/validator.md#validator-assignments) for details.

### Lookahead

Lookahead for beacon committee assignments operates in the same manner as Phase 0, but committee members must join a shard block pubsub topic in addition to the committee attestation topic.o

Specifically _after_ finding stable peers of attestation subnets (see Phase 0) a validator should:
* Let `shard = compute_shard_from_committee_index(committe_index)`
* Subscribe to the pubsub topic `shard_{shard}_shard_block` (attestation subnet peers should have this topic available).

## Beacon chain responsibilities

A validator has two primary responsibilities to the beacon chain: [proposing blocks](#block-proposal) and [creating attestations](#attestations-1). Proposals happen infrequently, whereas attestations should be created once per epoch.

These responsibilities are largely unchanged from Phase 0, but utilize the updated `SignedBeaconBlock`, `BeaconBlock`,  `BeaconBlockBody`, `Attestation`, and `AttestationData` definitions found in Phase 1. Below notes only the additional and modified behavior with respect to Phase 0.

Phase 1 adds light client committees and associated responsibilities, discussed [below](#light-client-committee).

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
    online_indices = get_online_validator_indices(state)
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
        shard_transition_roots = set([a.data.shard_transition_root for a in shard_attestations])
        for shard_transition_root in sorted(shard_transition_roots):
            transition_attestations = [
                a for a in shard_attestations
                if a.data.shard_transition_root == shard_transition_root
            ]
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
                winning_roots.append(shard_transition_root)
                break

    return shards, winning_roots
```

##### Light client fields

First retrieve `best_aggregate` from `get_best_light_client_aggregate` where `aggregates` is a list of valid aggregated `LightClientVote`s for the previous slot.

Then:
* Set `light_client_bits = best_aggregate.aggregation_bits`
* Set `light_client_signature = best_aggregate.signature`

```python
def get_best_light_client_aggregate(block: BeaconBlock,
                                    aggregates: Sequence[LightClientVote]) -> LightClientVote:
    viable_aggregates = [
        aggregate for aggregate in aggregates
        if aggregate.slot == compute_previous_slot(block.slot) and aggregate.beacon_block_root == block.parent_root
    ]

    return max(
        viable_aggregates,
        key=lambda a: len([i for i in a.aggregation_bits if i == 1]),
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

A validator should create and broadcast the `attestation` to the associated attestation subnet when either (a) the validator has received a valid `BeaconBlock` from the expected beacon block proposer and a valid `ShardBlock` for the expected shard block proposer for the assigned `slot` or (b) one-half of the `slot` has transpired (`SECONDS_PER_SLOT / 2` seconds after the start of `slot`) -- whichever comes _first_.

#### Attestation data

`attestation_data` is constructed in the same manner as Phase 0 but uses `FullAttestationData` with the addition of two fields -- `head_shard_root` and `shard_transition`.

- Let `head_block` be the result of running the fork choice during the assigned slot.
- Let `head_state` be the state of `head_block` processed through any empty slots up to the assigned slot using `process_slots(state, slot)`.
- Let `head_shard_block` be the result of running the fork choice on the assigned shard chain during the assigned slot.
- Let `shard_blocks` be the shard blocks in the chain starting immediately _after_ the most recent crosslink (`head_state.shard_transitions[shard].latest_block_root`) up to the `head_shard_block`.

*Note*: We assume that the fork choice only follows branches with valid `offset_slots` with respect to the most recent beacon state shard transition for the queried shard.

##### Head shard root

Set `attestation_data.head_shard_root = hash_tree_root(head_shard_block)`.

##### Shard transition

Set `shard_transition` to the value returned by `get_shard_transition(head_state, shard, shard_blocks)`.

```python
def get_shard_state_transition_result(
    beacon_state: BeaconState,
    shard: Shard,
    shard_blocks: Sequence[SignedShardBlock],
    validate_signature: bool=True,
) -> Tuple[Sequence[ShardState], Sequence[Root], Sequence[uint64]]:
    shard_states = []
    shard_data_roots = []
    shard_block_lengths = []

    shard_state = beacon_state.shard_states[shard]
    shard_block_slots = [shard_block.message.slot for shard_block in shard_blocks]
    for slot in get_offset_slots(beacon_state, shard):
        if slot in shard_block_slots:
            shard_block = shard_blocks[shard_block_slots.index(slot)]
            shard_data_roots.append(hash_tree_root(shard_block.message.body))
        else:
            shard_block = SignedShardBlock(message=ShardBlock(slot=slot))
            shard_data_roots.append(Root())
        shard_state = get_post_shard_state(beacon_state, shard_state, shard_block.message)
        shard_states.append(shard_state)
        shard_block_lengths.append(len(shard_block.message.body))

    return shard_states, shard_data_roots, shard_block_lengths
```

```python
def get_shard_transition(beacon_state: BeaconState,
                         shard: Shard,
                         shard_blocks: Sequence[SignedShardBlock]) -> ShardTransition:
    offset_slots = get_offset_slots(beacon_state, shard)
    shard_states, shard_data_roots, shard_block_lengths = (
        get_shard_state_transition_result(beacon_state, shard, shard_blocks)
    )

    if len(shard_blocks) > 0:
        proposer_signatures = [shard_block.signature for shard_block in shard_blocks]
        proposer_signature_aggregate = bls.Aggregate(proposer_signatures)
    else:
        proposer_signature_aggregate = NO_SIGNATURE

    return ShardTransition(
        start_slot=offset_slots[0],
        shard_block_lengths=shard_block_lengths,
        shard_data_roots=shard_data_roots,
        shard_states=shard_states,
        proposer_signature_aggregate=proposer_signature_aggregate,
    )
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
                              attestation: Attestation,
                              privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, attestation.data.target.epoch)
    attestation_data_root = hash_tree_root(attestation.data)
    index_in_committee = attestation.aggregation_bits.index(True)
    signatures = []
    for block_index, custody_bits in enumerate(attestation.custody_bits_blocks):
        custody_bit = custody_bits[index_in_committee]
        signing_root = compute_signing_root(
            AttestationCustodyBitWrapper(
                attestation_data_root=attestation_data_root,
                block_index=block_index,
                bit=custody_bit,
            ),
            domain,
        )
        signatures.append(bls.Sign(privkey, signing_root))

    return bls.Aggregate(signatures)
```

### Light client committee

In addition to the core beacon chain responsibilities, Phase 1 adds an additional role -- the Light Client Committee -- to aid in light client functionality.

Validators serve on the light client committee for `LIGHT_CLIENT_COMMITTEE_PERIOD` epochs and the assignment to be on a committee is known `LIGHT_CLIENT_COMMITTEE_PERIOD` epochs in advance.

#### Preparation

When `get_current_epoch(state) % LIGHT_CLIENT_COMMITTEE_PERIOD == LIGHT_CLIENT_COMMITTEE_PERIOD - LIGHT_CLIENT_PREPARATION_EPOCHS` each validator must check if they are in the next period light client committee by calling `is_in_next_light_client_committee()`.

If the validator is in the next light client committee, they must join the `light_client_votes` pubsub topic to begin duties at the start of the next period.

```python
def is_in_next_light_client_committee(state: BeaconState, index: ValidatorIndex) -> boolean:
    period_start_epoch = get_current_epoch(state) + LIGHT_CLIENT_COMMITTEE_PERIOD % get_current_epoch(state)
    next_committee = get_light_client_committee(state, period_start_epoch)
    return index in next_committee
```

#### Light clent vote

During a period of epochs that the validator is a part of the light client committee (`validator_index in get_light_client_committee(state, epoch)`), the validator creates and broadcasts a `LightClientVote` at each slot.

A validator should create and broadcast the `light_client_vote` to the `light_client_votes` pubsub topic when either (a) the validator has received a valid block from the expected block proposer for the current `slot` or (b) two-thirds of the `slot` have transpired (`SECONDS_PER_SLOT / 3` seconds after the start of `slot`) -- whichever comes _first_.

- Let `light_client_committee = get_light_client_committee(state, compute_epoch_at_slot(slot))`

##### Light client vote data

First the validator constructs `light_client_vote_data`, a [`LightClientVoteData`](#lightclientvotedata) object.

* Let `head_block` be the result of running the fork choice during the assigned slot.
* Set `light_client_vote.slot = slot`.
* Set `light_client_vote.beacon_block_root = hash_tree_root(head_block)`.

###### `LightClientVoteData`

```python
class LightClientVoteData(Container):
    slot: Slot
    beacon_block_root: Root
```

##### Construct vote

Then the validator constructs `light_client_vote`, a [`LightClientVote`](#lightclientvote) object.

* Set `light_client_vote.data = light_client_vote_data`.
* Set `light_client_vote.aggregation_bits` to be a `Bitvector[LIGHT_CLIENT_COMMITTEE_SIZE]`, where the bit of the index of the validator in the `light_client_committee` is set to `0b1` and all other bits are are set to `0b0`.
* Set `light_client_vote.signature = vote_signature` where `vote_signature` is obtained from:

```python
def get_light_client_vote_signature(state: BeaconState,
                                    light_client_vote_data: LightClientVoteData,
                                    privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_LIGHT_CLIENT, compute_epoch_at_slot(light_client_vote_data.slot))
    signing_root = compute_signing_root(light_client_vote_data, domain)
    return bls.Sign(privkey, signing_root)
```

###### `LightClientVote`

```python
class LightClientVote(Container):
    data: LightClientVoteData
    aggregation_bits: Bitvector[LIGHT_CLIENT_COMMITTEE_SIZE]
    signature: BLSSignature
```

##### Broadcast

Finally, the validator broadcasts `light_client_vote` to the `light_client_votes` pubsub topic.

#### Light client vote aggregation

Some validators in the light client committee are selected to locally aggregate light client votes with a similar `light_client_vote_data` to their constructed `light_client_vote` for the assigned `slot`.

#### Aggregation selection

A validator is selected to aggregate based upon the return value of `is_light_client_aggregator()`.

```python
def get_light_client_slot_signature(state: BeaconState, slot: Slot, privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_LIGHT_SELECTION_PROOF, compute_epoch_at_slot(slot))
    signing_root = compute_signing_root(slot, domain)
    return bls.Sign(privkey, signing_root)
```

```python
def is_light_client_aggregator(state: BeaconState, slot: Slot, slot_signature: BLSSignature) -> bool:
    committee = get_light_client_committee(state, compute_epoch_at_slot(slot))
    modulo = max(1, len(committee) // TARGET_LIGHT_CLIENT_AGGREGATORS_PER_SLOT)
    return bytes_to_int(hash(slot_signature)[0:8]) % modulo == 0
```

#### Construct aggregate

If the validator is selected to aggregate (`is_light_client_aggregator()`), they construct an aggregate light client vote via the following.

Collect `light_client_votes` seen via gossip during the `slot` that have an equivalent `light_client_vote_data` to that constructed by the validator, and create a `aggregate_light_client_vote: LightClientVote` with the following fields.

* Set `aggregate_light_client_vote.data = light_client_vote_data` where `light_client_vote_data` is the `LightClientVoteData` object that is the same for each individual light client vote being aggregated.
* Set `aggregate_light_client_vote.aggregation_bits` to be a `Bitvector[LIGHT_CLIENT_COMMITTEE_SIZE]`, where each bit set from each individual light client vote is set to `0b1`.
* Set `aggregate_light_client_vote.signature = aggregate_light_client_signature` where `aggregate_light_client_signature` is obtained from `get_aggregate_light_client_signature`.

```python
def get_aggregate_light_client_signature(light_client_votes: Sequence[LightClientVote]) -> BLSSignature:
    signatures = [light_client_vote.signature for light_client_vote in light_client_votes]
    return bls.Aggregate(signatures)
```

#### Broadcast aggregate

If the validator is selected to aggregate (`is_light_client_aggregator`), then they broadcast their best aggregate light client vote as a `SignedLightAggregateAndProof` to the global aggregate light client vote channel (`aggregate_light_client_votes`) two-thirds of the way through the `slot`-that is, `SECONDS_PER_SLOT * 2 / 3` seconds after the start of `slot`.

Selection proofs are provided in `LightAggregateAndProof` to prove to the gossip channel that the validator has been selected as an aggregator.

`LightAggregateAndProof` messages are signed by the aggregator and broadcast inside of `SignedLightAggregateAndProof` objects to prevent a class of DoS attacks and message forgeries.

First, `light_aggregate_and_proof = get_light_aggregate_and_proof(state, validator_index, aggregate_light_client_vote, privkey)` is constructed.

```python
def get_light_aggregate_and_proof(state: BeaconState,
                                  aggregator_index: ValidatorIndex,
                                  aggregate: Attestation,
                                  privkey: int) -> LightAggregateAndProof:
    return LightAggregateAndProof(
        aggregator_index=aggregator_index,
        aggregate=aggregate,
        selection_proof=get_light_client_slot_signature(state, aggregate.data.slot, privkey),
    )
```

Then `signed_light_aggregate_and_proof = SignedLightAggregateAndProof(message=light_aggregate_and_proof, signature=signature)` is constructed and broadast. Where `signature` is obtained from:

```python
def get_light_aggregate_and_proof_signature(state: BeaconState,
                                            aggregate_and_proof: LightAggregateAndProof,
                                            privkey: int) -> BLSSignature:
    aggregate = aggregate_and_proof.aggregate
    domain = get_domain(state, DOMAIN_LIGHT_AGGREGATE_AND_PROOF, compute_epoch_at_slot(aggregate.data.slot))
    signing_root = compute_signing_root(aggregate_and_proof, domain)
    return bls.Sign(privkey, signing_root)
```

##### `LightAggregateAndProof`

```python
class LightAggregateAndProof(Container):
    aggregator_index: ValidatorIndex
    aggregate: Attestation
    selection_proof: BLSSignature
```

##### `SignedLightAggregateAndProof`

```python
class SignedLightAggregateAndProof(Container):
    message: LightAggregateAndProof
    signature: BLSSignature
```

