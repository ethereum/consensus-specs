# Ethereum 2.0 Phase 0 -- Honest Validator

**Notice**: This document is a work-in-progress for researchers and implementers. This is an accompanying document to [Ethereum 2.0 Phase 0 -- The Beacon Chain](./beacon-chain.md), which describes the expected actions of a "validator" participating in the Ethereum 2.0 protocol.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Constants](#constants)
  - [Misc](#misc)
- [Becoming a validator](#becoming-a-validator)
  - [Initialization](#initialization)
    - [BLS public key](#bls-public-key)
    - [BLS withdrawal key](#bls-withdrawal-key)
  - [Submit deposit](#submit-deposit)
  - [Process deposit](#process-deposit)
  - [Validator index](#validator-index)
  - [Activation](#activation)
- [Validator assignments](#validator-assignments)
  - [Lookahead](#lookahead)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block proposal](#block-proposal)
    - [Preparing for a `BeaconBlock`](#preparing-for-a-beaconblock)
      - [Slot](#slot)
      - [Proposer index](#proposer-index)
      - [Parent root](#parent-root)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Randao reveal](#randao-reveal)
      - [Eth1 Data](#eth1-data)
        - [`Eth1Block`](#eth1block)
        - [`get_eth1_data`](#get_eth1_data)
      - [Proposer slashings](#proposer-slashings)
      - [Attester slashings](#attester-slashings)
      - [Attestations](#attestations)
      - [Deposits](#deposits)
      - [Voluntary exits](#voluntary-exits)
    - [Packaging into a `SignedBeaconBlock`](#packaging-into-a-signedbeaconblock)
      - [State root](#state-root)
      - [Signature](#signature)
  - [Attesting](#attesting)
    - [Attestation data](#attestation-data)
      - [General](#general)
      - [LMD GHOST vote](#lmd-ghost-vote)
      - [FFG vote](#ffg-vote)
    - [Construct attestation](#construct-attestation)
      - [Data](#data)
      - [Aggregation bits](#aggregation-bits)
      - [Aggregate signature](#aggregate-signature)
    - [Broadcast attestation](#broadcast-attestation)
  - [Attestation aggregation](#attestation-aggregation)
    - [Aggregation selection](#aggregation-selection)
    - [Construct aggregate](#construct-aggregate)
      - [Data](#data-1)
      - [Aggregation bits](#aggregation-bits-1)
      - [Aggregate signature](#aggregate-signature-1)
    - [Broadcast aggregate](#broadcast-aggregate)
      - [`AggregateAndProof`](#aggregateandproof)
      - [`SignedAggregateAndProof`](#signedaggregateandproof)
- [Phase 0 attestation subnet stability](#phase-0-attestation-subnet-stability)
- [How to avoid slashing](#how-to-avoid-slashing)
  - [Proposer slashing](#proposer-slashing)
  - [Attester slashing](#attester-slashing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the expected behavior of an "honest validator" with respect to Phase 0 of the Ethereum 2.0 protocol. This document does not distinguish between a "node" (i.e. the functionality of following and reading the beacon chain) and a "validator client" (i.e. the functionality of actively participating in consensus). The separation of concerns between these (potentially) two pieces of software is left as a design decision that is out of scope.

A validator is an entity that participates in the consensus of the Ethereum 2.0 protocol. This is an optional role for users in which they can post ETH as collateral and verify and attest to the validity of blocks to seek financial returns in exchange for building and securing the protocol. This is similar to proof-of-work networks in which miners provide collateral in the form of hardware/hash-power to seek returns in exchange for building and securing the protocol.

## Prerequisites

All terminology, constants, functions, and protocol mechanics defined in the [Phase 0 -- The Beacon Chain](./beacon-chain.md) and [Phase 0 -- Deposit Contract](./deposit-contract.md) doc are requisite for this document and used throughout. Please see the Phase 0 doc before continuing and use as a reference throughout.

## Constants

### Misc

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `ETH1_FOLLOW_DISTANCE` | `2**10` (= 1,024) | blocks | ~4 hours |
| `TARGET_AGGREGATORS_PER_COMMITTEE` | `2**4` (= 16) | validators | |
| `RANDOM_SUBNETS_PER_VALIDATOR` | `2**0` (= 1) | subnets | |
| `EPOCHS_PER_RANDOM_SUBNET_SUBSCRIPTION` | `2**8` (= 256) | epochs | ~27 hours |
| `SECONDS_PER_ETH1_BLOCK` | `14` | seconds | |

## Becoming a validator

### Initialization

A validator must initialize many parameters locally before submitting a deposit and joining the validator registry.

#### BLS public key

Validator public keys are [G1 points](beacon-chain.md#bls-signatures) on the [BLS12-381 curve](https://z.cash/blog/new-snark-curve). A private key, `privkey`, must be securely generated along with the resultant `pubkey`. This `privkey` must be "hot", that is, constantly available to sign data throughout the lifetime of the validator.

#### BLS withdrawal key

A secondary withdrawal private key, `withdrawal_privkey`, must also be securely generated along with the resultant `withdrawal_pubkey`. This `withdrawal_privkey` does not have to be available for signing during the normal lifetime of a validator and can live in "cold storage".

The validator constructs their `withdrawal_credentials` via the following:

* Set `withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX`.
* Set `withdrawal_credentials[1:] == hash(withdrawal_pubkey)[1:]`.

### Submit deposit

In Phase 0, all incoming validator deposits originate from the Ethereum 1.0 proof-of-work chain. Deposits are made to the [deposit contract](./deposit-contract.md) located at `DEPOSIT_CONTRACT_ADDRESS`.

To submit a deposit:

- Pack the validator's [initialization parameters](#initialization) into `deposit_data`, a [`DepositData`](./beacon-chain.md#depositdata) SSZ object.
- Let `amount` be the amount in Gwei to be deposited by the validator where `amount >= MIN_DEPOSIT_AMOUNT`.
- Set `deposit_data.pubkey` to validator's `pubkey`.
- Set `deposit_data.withdrawal_credentials` to `withdrawal_credentials`.
- Set `deposit_data.amount` to `amount`.
- Let `deposit_message` be a `DepositMessage` with all the `DepositData` contents except the `signature`.
- Let `signature` be the result of `bls.Sign` of the `compute_signing_root(deposit_message, domain)` with `domain=compute_domain(DOMAIN_DEPOSIT)`. (_Warning_: Deposits _must_ be signed with `GENESIS_FORK_VERSION`, calling `compute_domain` without a second argument defaults to the correct version).
- Let `deposit_data_root` be `hash_tree_root(deposit_data)`.
- Send a transaction on the Ethereum 1.0 chain to `DEPOSIT_CONTRACT_ADDRESS` executing `def deposit(pubkey: bytes[48], withdrawal_credentials: bytes[32], signature: bytes[96], deposit_data_root: bytes32)` along with a deposit of `amount` Gwei.

*Note*: Deposits made for the same `pubkey` are treated as for the same validator. A singular `Validator` will be added to `state.validators` with each additional deposit amount added to the validator's balance. A validator can only be activated when total deposits for the validator pubkey meet or exceed `MAX_EFFECTIVE_BALANCE`.

### Process deposit

Deposits cannot be processed into the beacon chain until the Eth1 block in which they were deposited or any of its descendants is added to the beacon chain `state.eth1_data`. This takes _a minimum_ of `ETH1_FOLLOW_DISTANCE` Eth1 blocks (~4 hours) plus `EPOCHS_PER_ETH1_VOTING_PERIOD` epochs (~3.4 hours). Once the requisite Eth1 data is added, the deposit will normally be added to a beacon chain block and processed into the `state.validators` within an epoch or two. The validator is then in a queue to be activated.

### Validator index

Once a validator has been processed and added to the beacon state's `validators`, the validator's `validator_index` is defined by the index into the registry at which the [`ValidatorRecord`](./beacon-chain.md#validator) contains the `pubkey` specified in the validator's deposit. A validator's `validator_index` is guaranteed to not change from the time of initial deposit until the validator exits and fully withdraws. This `validator_index` is used throughout the specification to dictate validator roles and responsibilities at any point and should be stored locally.

### Activation

In normal operation, the validator is quickly activated, at which point the validator is added to the shuffling and begins validation after an additional `MAX_SEED_LOOKAHEAD` epochs (25.6 minutes).

The function [`is_active_validator`](./beacon-chain.md#is_active_validator) can be used to check if a validator is active during a given epoch. Usage is as follows:

```python
def check_if_validator_active(state: BeaconState, validator_index: ValidatorIndex) -> bool:
    validator = state.validators[validator_index]
    return is_active_validator(validator, get_current_epoch(state))
```

Once a validator is activated, the validator is assigned [responsibilities](#beacon-chain-responsibilities) until exited.

*Note*: There is a maximum validator churn per finalized epoch, so the delay until activation is variable depending upon finality, total active validator balance, and the number of validators in the queue to be activated.

## Validator assignments

A validator can get committee assignments for a given epoch using the following helper via `get_committee_assignment(state, epoch, validator_index)` where `epoch <= next_epoch`.

```python
def get_committee_assignment(state: BeaconState,
                             epoch: Epoch,
                             validator_index: ValidatorIndex
                             ) -> Optional[Tuple[Sequence[ValidatorIndex], CommitteeIndex, Slot]]:
    """
    Return the committee assignment in the ``epoch`` for ``validator_index``.
    ``assignment`` returned is a tuple of the following form:
        * ``assignment[0]`` is the list of validators in the committee
        * ``assignment[1]`` is the index to which the committee is assigned
        * ``assignment[2]`` is the slot at which the committee is assigned
    Return None if no assignment.
    """
    next_epoch = get_current_epoch(state) + 1
    assert epoch <= next_epoch

    start_slot = compute_start_slot_at_epoch(epoch)
    for slot in range(start_slot, start_slot + SLOTS_PER_EPOCH):
        for index in range(get_committee_count_at_slot(state, Slot(slot))):
            committee = get_beacon_committee(state, Slot(slot), CommitteeIndex(index))
            if validator_index in committee:
                return committee, CommitteeIndex(index), Slot(slot)
    return None
```

A validator can use the following function to see if they are supposed to propose during a slot. This function can only be run with a `state` of the slot in question. Proposer selection is only stable within the context of the current epoch.

```python
def is_proposer(state: BeaconState, validator_index: ValidatorIndex) -> bool:
    return get_beacon_proposer_index(state) == validator_index
```

*Note*: To see if a validator is assigned to propose during the slot, the beacon state must be in the epoch in question. At the epoch boundaries, the validator must run an epoch transition into the epoch to successfully check the proposal assignment of the first slot.

*Note*: `BeaconBlock` proposal is distinct from beacon committee assignment, and in a given epoch each responsibility might occur at a different slot.

### Lookahead

The beacon chain shufflings are designed to provide a minimum of 1 epoch lookahead on the validator's upcoming committee assignments for attesting dictated by the shuffling and slot. Note that this lookahead does not apply to proposing, which must be checked during the epoch in question.

`get_committee_assignment` should be called at the start of each epoch to get the assignment for the next epoch (`current_epoch + 1`). A validator should plan for future assignments by noting at which future slot they will have to attest and joining the committee index attestation subnet related to their committee assignment.

Specifically a validator should:
* Call `get_committee_assignment(state, next_epoch, validator_index)` when checking for next epoch assignments.
* Join the pubsub topic -- `committee_index{committee_index % ATTESTATION_SUBNET_COUNT}_beacon_attestation`.
    * For any current peer subscribed to the topic, the validator simply sends a `subscribe` message for the new topic.
    * If an _insufficient_ number of current peers are subscribed to the topic, the validator must discover new peers on this topic. Via the discovery protocol, find peers with an ENR containing the `attnets` entry such that `ENR["attnets"][committee_index % ATTESTATION_SUBNET_COUNT] == True`.

## Beacon chain responsibilities

A validator has two primary responsibilities to the beacon chain: [proposing blocks](#block-proposal) and [creating attestations](#attestations-1). Proposals happen infrequently, whereas attestations should be created once per epoch.

### Block proposal

A validator is expected to propose a [`SignedBeaconBlock`](./beacon-chain.md#signedbeaconblock) at the beginning of any slot during which `is_proposer(state, validator_index)` returns `True`. To propose, the validator selects the `BeaconBlock`, `parent`, that in their view of the fork choice is the head of the chain during `slot - 1`. The validator creates, signs, and broadcasts a `block` that is a child of `parent` that satisfies a valid [beacon chain state transition](./beacon-chain.md#beacon-chain-state-transition-function).

There is one proposer per slot, so if there are N active validators any individual validator will on average be assigned to propose once per N slots (e.g. at 312,500 validators = 10 million ETH, that's once per ~6 weeks).

#### Preparing for a `BeaconBlock`

To construct a `BeaconBlockBody`, a `block` (`BeaconBlock`) is defined with the necessary context for a block proposal:

##### Slot

Set `block.slot = slot` where `slot` is the current slot at which the validator has been selected to propose. The `parent` selected must satisfy that `parent.slot < block.slot`.

*Note*: There might be "skipped" slots between the `parent` and `block`. These skipped slots are processed in the state transition function without per-block processing.

##### Proposer index

Set `block.proposer_index = validator_index` where `validator_index` is the validator chosen to propose at this slot. The private key mapping to `state.validators[validator_index].pubkey` is used to sign the block.

##### Parent root

Set `block.parent_root = hash_tree_root(parent)`.

#### Constructing the `BeaconBlockBody`

##### Randao reveal

Set `block.body.randao_reveal = epoch_signature` where `epoch_signature` is obtained from:

```python
def get_epoch_signature(state: BeaconState, block: BeaconBlock, privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_RANDAO, compute_epoch_at_slot(block.slot))
    signing_root = compute_signing_root(compute_epoch_at_slot(block.slot), domain)
    return bls.Sign(privkey, signing_root)
```

##### Eth1 Data

The `block.body.eth1_data` field is for block proposers to vote on recent Eth1 data. This recent data contains an Eth1 block hash as well as the associated deposit root (as calculated by the `get_deposit_root()` method of the deposit contract) and deposit count after execution of the corresponding Eth1 block. If over half of the block proposers in the current Eth1 voting period vote for the same `eth1_data` then `state.eth1_data` updates immediately allowing new deposits to be processed. Each deposit in `block.body.deposits` must verify against `state.eth1_data.eth1_deposit_root`.

###### `Eth1Block`

Let `Eth1Block` be an abstract object representing Eth1 blocks with the `timestamp` field available.

```python
class Eth1Block(Container):
    timestamp: uint64
    # All other eth1 block fields
```

###### `get_eth1_data`

Let `get_eth1_data(block: Eth1Block) -> Eth1Data` be the function that returns the Eth1 data for a given Eth1 block.

An honest block proposer sets `block.body.eth1_data = get_eth1_vote(state)` where:

```python
def compute_time_at_slot(state: BeaconState, slot: Slot) -> uint64:
    return state.genesis_time + slot * SECONDS_PER_SLOT
```

```python
def voting_period_start_time(state: BeaconState) -> uint64:
    eth1_voting_period_start_slot = Slot(state.slot - state.slot % (EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH))
    return compute_time_at_slot(state, eth1_voting_period_start_slot)
```

```python
def is_candidate_block(block: Eth1Block, period_start: uint64) -> bool:
    return (
        block.timestamp <= period_start - SECONDS_PER_ETH1_BLOCK * ETH1_FOLLOW_DISTANCE
        and block.timestamp >= period_start - SECONDS_PER_ETH1_BLOCK * ETH1_FOLLOW_DISTANCE * 2
    )
```

```python
def get_eth1_vote(state: BeaconState, eth1_chain: Sequence[Eth1Block]) -> Eth1Data:
    period_start = voting_period_start_time(state)
    # `eth1_chain` abstractly represents all blocks in the eth1 chain sorted by ascending block height
    votes_to_consider = [get_eth1_data(block) for block in eth1_chain if
                         is_candidate_block(block, period_start)]

    # Valid votes already cast during this period
    valid_votes = [vote for vote in state.eth1_data_votes if vote in votes_to_consider]

    # Default vote on latest eth1 block data in the period range unless eth1 chain is not live
    default_vote = votes_to_consider[-1] if any(votes_to_consider) else state.eth1_data

    return max(
        valid_votes,
        key=lambda v: (valid_votes.count(v), -valid_votes.index(v)),  # Tiebreak by smallest distance
        default=default_vote
    )
```

##### Proposer slashings

Up to `MAX_PROPOSER_SLASHINGS`, [`ProposerSlashing`](./beacon-chain.md#proposerslashing) objects can be included in the `block`. The proposer slashings must satisfy the verification conditions found in [proposer slashings processing](./beacon-chain.md#proposer-slashings). The validator receives a small "whistleblower" reward for each proposer slashing found and included.

##### Attester slashings

Up to `MAX_ATTESTER_SLASHINGS`, [`AttesterSlashing`](./beacon-chain.md#attesterslashing) objects can be included in the `block`. The attester slashings must satisfy the verification conditions found in [attester slashings processing](./beacon-chain.md#attester-slashings). The validator receives a small "whistleblower" reward for each attester slashing found and included.

##### Attestations

Up to `MAX_ATTESTATIONS`, aggregate attestations can be included in the `block`. The attestations added must satisfy the verification conditions found in [attestation processing](./beacon-chain.md#attestations). To maximize profit, the validator should attempt to gather aggregate attestations that include singular attestations from the largest number of validators whose signatures from the same epoch have not previously been added on chain.

##### Deposits

If there are any unprocessed deposits for the existing `state.eth1_data` (i.e. `state.eth1_data.deposit_count > state.eth1_deposit_index`), then pending deposits _must_ be added to the block. The expected number of deposits is exactly `min(MAX_DEPOSITS, eth1_data.deposit_count - state.eth1_deposit_index)`.  These [`deposits`](./beacon-chain.md#deposit) are constructed from the `Deposit` logs from the [Eth1 deposit contract](./deposit-contract.md) and must be processed in sequential order. The deposits included in the `block` must satisfy the verification conditions found in [deposits processing](./beacon-chain.md#deposits).

The `proof` for each deposit must be constructed against the deposit root contained in `state.eth1_data` rather than the deposit root at the time the deposit was initially logged from the 1.0 chain. This entails storing a full deposit merkle tree locally and computing updated proofs against the `eth1_data.deposit_root` as needed. See [`minimal_merkle.py`](https://github.com/ethereum/research/blob/master/spec_pythonizer/utils/merkle_minimal.py) for a sample implementation.

##### Voluntary exits

Up to `MAX_VOLUNTARY_EXITS`, [`VoluntaryExit`](./beacon-chain.md#voluntaryexit) objects can be included in the `block`. The exits must satisfy the verification conditions found in [exits processing](./beacon-chain.md#voluntary-exits).


#### Packaging into a `SignedBeaconBlock`

##### State root

Set `block.state_root = hash_tree_root(state)` of the resulting `state` of the `parent -> block` state transition.

*Note*: To calculate `state_root`, the validator should first run the state transition function on an unsigned `block` containing a stub for the `state_root`.
It is useful to be able to run a state transition function (working on a copy of the state) that does _not_ validate signatures or state root for this purpose:

```python
def compute_new_state_root(state: BeaconState, block: BeaconBlock) -> Root:
    process_slots(state, block.slot)
    process_block(state, block)
    return hash_tree_root(state)
```

##### Signature

`signed_block = SignedBeaconBlock(message=block, signature=block_signature)`, where `block_signature` is obtained from:

```python
def get_block_signature(state: BeaconState, header: BeaconBlockHeader, privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(header.slot))
    signing_root = compute_signing_root(header, domain)
    return bls.Sign(privkey, signing_root)
```

### Attesting

A validator is expected to create, sign, and broadcast an attestation during each epoch. The `committee`, assigned `index`, and assigned `slot` for which the validator performs this role during an epoch are defined by `get_committee_assignment(state, epoch, validator_index)`.

A validator should create and broadcast the `attestation` to the associated attestation subnet when either (a) the validator has received a valid block from the expected block proposer for the assigned `slot` or (b) one-third of the `slot` has transpired (`SECONDS_PER_SLOT / 3` seconds after the start of `slot`) -- whichever comes _first_.

*Note*: Although attestations during `GENESIS_EPOCH` do not count toward FFG finality, these initial attestations do give weight to the fork choice, are rewarded, and should be made.

#### Attestation data

First, the validator should construct `attestation_data`, an [`AttestationData`](./beacon-chain.md#attestationdata) object based upon the state at the assigned slot.

- Let `head_block` be the result of running the fork choice during the assigned slot.
- Let `head_state` be the state of `head_block` processed through any empty slots up to the assigned slot using `process_slots(state, slot)`.

##### General

* Set `attestation_data.slot = slot` where `slot` is the assigned slot.
* Set `attestation_data.index = index` where `index` is the index associated with the validator's committee.

##### LMD GHOST vote

Set `attestation_data.beacon_block_root = hash_tree_root(head_block)`.

##### FFG vote

- Set `attestation_data.source = head_state.current_justified_checkpoint`.
- Set `attestation_data.target = Checkpoint(epoch=get_current_epoch(head_state), root=epoch_boundary_block_root)` where `epoch_boundary_block_root` is the root of block at the most recent epoch boundary.

*Note*: `epoch_boundary_block_root` can be looked up in the state using:

- Let `start_slot = compute_start_slot_at_epoch(get_current_epoch(head_state))`.
- Let `epoch_boundary_block_root = hash_tree_root(head_block) if start_slot == head_state.slot else get_block_root(state, start_slot)`.

#### Construct attestation

Next, the validator creates `attestation`, an [`Attestation`](./beacon-chain.md#attestation) object.

##### Data

Set `attestation.data = attestation_data` where `attestation_data` is the `AttestationData` object defined in the previous section, [attestation data](#attestation-data).

##### Aggregation bits

- Let `attestation.aggregation_bits` be a `Bitlist[MAX_VALIDATORS_PER_COMMITTEE]` of length `len(committee)`, where the bit of the index of the validator in the `committee` is set to `0b1`.

*Note*: Calling `get_attesting_indices(state, attestation.data, attestation.aggregation_bits)` should return a list of length equal to 1, containing `validator_index`.

##### Aggregate signature

Set `attestation.signature = attestation_signature` where `attestation_signature` is obtained from:

```python
def get_attestation_signature(state: BeaconState, attestation: AttestationData, privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, attestation.target.epoch)
    signing_root = compute_signing_root(attestation, domain)
    return bls.Sign(privkey, signing_root)
```

#### Broadcast attestation

Finally, the validator broadcasts `attestation` to the associated attestation subnet -- the `committee_index{attestation.data.index % ATTESTATION_SUBNET_COUNT}_beacon_attestation` pubsub topic.

### Attestation aggregation

Some validators are selected to locally aggregate attestations with a similar `attestation_data` to their constructed `attestation` for the assigned `slot`.

#### Aggregation selection

A validator is selected to aggregate based upon the return value of `is_aggregator()`.

```python
def get_slot_signature(state: BeaconState, slot: Slot, privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_SELECTION_PROOF, compute_epoch_at_slot(slot))
    signing_root = compute_signing_root(slot, domain)
    return bls.Sign(privkey, signing_root)
```

```python
def is_aggregator(state: BeaconState, slot: Slot, index: CommitteeIndex, slot_signature: BLSSignature) -> bool:
    committee = get_beacon_committee(state, slot, index)
    modulo = max(1, len(committee) // TARGET_AGGREGATORS_PER_COMMITTEE)
    return bytes_to_int(hash(slot_signature)[0:8]) % modulo == 0
```

#### Construct aggregate

If the validator is selected to aggregate (`is_aggregator()`), they construct an aggregate attestation via the following.

Collect `attestations` seen via gossip during the `slot` that have an equivalent `attestation_data` to that constructed by the validator, and create an `aggregate_attestation: Attestation` with the following fields.

##### Data

Set `aggregate_attestation.data = attestation_data` where `attestation_data` is the `AttestationData` object that is the same for each individual attestation being aggregated.

##### Aggregation bits

Let `aggregate_attestation.aggregation_bits` be a `Bitlist[MAX_VALIDATORS_PER_COMMITTEE]` of length `len(committee)`, where each bit set from each individual attestation is set to `0b1`.

##### Aggregate signature

Set `aggregate_attestation.signature = aggregate_signature` where `aggregate_signature` is obtained from:

```python
def get_aggregate_signature(attestations: Sequence[Attestation]) -> BLSSignature:
    signatures = [attestation.signature for attestation in attestations]
    return bls.Aggregate(signatures)
```

#### Broadcast aggregate

If the validator is selected to aggregate (`is_aggregator`), then they broadcast their best aggregate as a `SignedAggregateAndProof` to the global aggregate channel (`beacon_aggregate_and_proof`) two-thirds of the way through the `slot`-that is, `SECONDS_PER_SLOT * 2 / 3` seconds after the start of `slot`.

Selection proofs are provided in `AggregateAndProof` to prove to the gossip channel that the validator has been selected as an aggregator.

`AggregateAndProof` messages are signed by the aggregator and broadcast inside of `SignedAggregateAndProof` objects to prevent a class of DoS attacks and message forgeries.

First, `aggregate_and_proof = get_aggregate_and_proof(state, validator_index, aggregate_attestation, privkey)` is constructed.

```python
def get_aggregate_and_proof(state: BeaconState,
                            aggregator_index: ValidatorIndex,
                            aggregate: Attestation,
                            privkey: int) -> AggregateAndProof:
    return AggregateAndProof(
        aggregator_index=aggregator_index,
        aggregate=aggregate,
        selection_proof=get_slot_signature(state, aggregate.data.slot, privkey),
    )
```

Then `signed_aggregate_and_proof = SignedAggregateAndProof(message=aggregate_and_proof, signature=signature)` is constructed and broadast. Where `signature` is obtained from:

```python
def get_aggregate_and_proof_signature(state: BeaconState,
                                      aggregate_and_proof: AggregateAndProof,
                                      privkey: int) -> BLSSignature:
    aggregate = aggregate_and_proof.aggregate
    domain = get_domain(state, DOMAIN_AGGREGATE_AND_PROOF, compute_epoch_at_slot(aggregate.data.slot))
    signing_root = compute_signing_root(aggregate_and_proof, domain)
    return bls.Sign(privkey, signing_root)
```

##### `AggregateAndProof`

```python
class AggregateAndProof(Container):
    aggregator_index: ValidatorIndex
    aggregate: Attestation
    selection_proof: BLSSignature
```

##### `SignedAggregateAndProof`

```python
class SignedAggregateAndProof(Container):
    message: AggregateAndProof
    signature: BLSSignature
```

## Phase 0 attestation subnet stability

Because Phase 0 does not have shards and thus does not have Shard Committees, there is no stable backbone to the attestation subnets (`committee_index{subnet_id}_beacon_attestation`). To provide this stability, each validator must:

* Randomly select and remain subscribed to `RANDOM_SUBNETS_PER_VALIDATOR` attestation subnets
* Maintain advertisement of the randomly selected subnets in their node's ENR `attnets` entry by setting the randomly selected `subnet_id` bits to `True` (e.g. `ENR["attnets"][subnet_id] = True`) for all persistent attestation subnets
* Set the lifetime of each random subscription to a random number of epochs between `EPOCHS_PER_RANDOM_SUBNET_SUBSCRIPTION` and `2 * EPOCHS_PER_RANDOM_SUBNET_SUBSCRIPTION]`. At the end of life for a subscription, select a new random subnet, update subnet subscriptions, and publish an updated ENR

*Note*: When preparing for a hard fork, a validator must select and subscribe to random subnets of the future fork versioning at least `EPOCHS_PER_RANDOM_SUBNET_SUBSCRIPTION` epochs in advance of the fork. These new subnets for the fork are maintained in addition to those for the current fork until the fork occurs. After the fork occurs, let the subnets from the previous fork reach the end of life with no replacements.

## How to avoid slashing

"Slashing" is the burning of some amount of validator funds and immediate ejection from the active validator set. In Phase 0, there are two ways in which funds can be slashed: [proposer slashing](#proposer-slashing) and [attester slashing](#attester-slashing). Although being slashed has serious repercussions, it is simple enough to avoid being slashed all together by remaining _consistent_ with respect to the messages a validator has previously signed.

*Note*: Signed data must be within a sequential `Fork` context to conflict. Messages cannot be slashed across diverging forks. If the previous fork version is 1 and the chain splits into fork 2 and 102, messages from 1 can slashable against messages in forks 1, 2, and 102. Messages in 2 cannot be slashable against messages in 102, and vice versa.

### Proposer slashing

To avoid "proposer slashings", a validator must not sign two conflicting [`BeaconBlock`](./beacon-chain.md#beaconblock) where conflicting is defined as two distinct blocks within the same slot.

*In Phase 0, as long as the validator does not sign two different beacon blocks for the same slot, the validator is safe against proposer slashings.*

Specifically, when signing a `BeaconBlock`, a validator should perform the following steps in the following order:

1. Save a record to hard disk that a beacon block has been signed for the `slot=block.slot`.
2. Generate and broadcast the block.

If the software crashes at some point within this routine, then when the validator comes back online, the hard disk has the record of the *potentially* signed/broadcast block and can effectively avoid slashing.

### Attester slashing

To avoid "attester slashings", a validator must not sign two conflicting [`AttestationData`](./beacon-chain.md#attestationdata) objects, i.e. two attestations that satisfy [`is_slashable_attestation_data`](./beacon-chain.md#is_slashable_attestation_data).

Specifically, when signing an `Attestation`, a validator should perform the following steps in the following order:

1. Save a record to hard disk that an attestation has been signed for source (i.e. `attestation_data.source.epoch`) and target (i.e. `attestation_data.target.epoch`).
2. Generate and broadcast attestation.

If the software crashes at some point within this routine, then when the validator comes back online, the hard disk has the record of the *potentially* signed/broadcast attestation and can effectively avoid slashing.
