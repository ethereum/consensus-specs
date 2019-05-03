# Ethereum 2.0 Phase 0 -- Honest Validator

__NOTICE__: This document is a work-in-progress for researchers and implementers. This is an accompanying document to [Ethereum 2.0 Phase 0 -- The Beacon Chain](../core/0_beacon-chain.md) that describes the expected actions of a "validator" participating in the Ethereum 2.0 protocol.

## Table of Contents

<!-- TOC -->

- [Ethereum 2.0 Phase 0 -- Honest Validator](#ethereum-20-phase-0----honest-validator)
    - [Table of Contents](#table-of-contents)
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
    - [Beacon chain responsibilities](#beacon-chain-responsibilities)
        - [Block proposal](#block-proposal)
            - [Block header](#block-header)
                - [Slot](#slot)
                - [Parent root](#parent-root)
                - [State root](#state-root)
                - [Randao reveal](#randao-reveal)
                - [Eth1 Data](#eth1-data)
                - [Signature](#signature)
            - [Block body](#block-body)
                - [Proposer slashings](#proposer-slashings)
                - [Attester slashings](#attester-slashings)
                - [Attestations](#attestations)
                - [Deposits](#deposits)
                - [Voluntary exits](#voluntary-exits)
        - [Attestations](#attestations-1)
            - [Attestation data](#attestation-data)
                - [Slot](#slot-1)
                - [Beacon block root](#beacon-block-root)
                - [Source epoch](#source-epoch)
                - [Source root](#source-root)
                - [Target root](#target-root)
                - [Shard](#shard)
                - [Previous crosslink root](#previous-crosslink-root)
                - [Crosslink data root](#crosslink-data-root)
            - [Construct attestation](#construct-attestation)
                - [Data](#data)
                - [Aggregation bitfield](#aggregation-bitfield)
                - [Custody bitfield](#custody-bitfield)
                - [Aggregate signature](#aggregate-signature)
    - [Validator assignments](#validator-assignments)
        - [Lookahead](#lookahead)
    - [How to avoid slashing](#how-to-avoid-slashing)
        - [Proposer slashing](#proposer-slashing)
        - [Attester slashing](#attester-slashing)

<!-- /TOC -->

## Introduction

This document represents the expected behavior of an "honest validator" with respect to Phase 0 of the Ethereum 2.0 protocol. This document does not distinguish between a "node" (i.e. the functionality of following and reading the beacon chain) and a "validator client" (i.e. the functionality of actively participating in consensus). The separation of concerns between these (potentially) two pieces of software is left as a design decision that is out of scope.

A validator is an entity that participates in the consensus of the Ethereum 2.0 protocol. This is an optional role for users in which they can post ETH as collateral and verify and attest to the validity of blocks to seek financial returns in exchange for building and securing the protocol. This is similar to proof of work networks in which a miner provides collateral in the form of hardware/hash-power to seek returns in exchange for building and securing the protocol.

## Prerequisites

All terminology, constants, functions, and protocol mechanics defined in the [Phase 0 -- The Beacon Chain](../core/0_beacon-chain.md) and [Phase 0 -- Deposit Contract](../core/0_deposit-contract.md) doc are requisite for this document and used throughout. Please see the Phase 0 doc before continuing and use as a reference throughout.

## Constants

### Misc

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `ETH1_FOLLOW_DISTANCE` | `2**10` (= 1,024) | blocks | ~4 hours |

## Becoming a validator

### Initialization

A validator must initialize many parameters locally before submitting a deposit and joining the validator registry.

#### BLS public key

Validator public keys are [G1 points](../bls_signature.md#g1-points) on the [BLS12-381 curve](https://z.cash/blog/new-snark-curve). A private key, `privkey`, must be securely generated along with the resultant `pubkey`. This `privkey` must be "hot", that is, constantly available to sign data throughout the lifetime of the validator.

#### BLS withdrawal key

A secondary withdrawal private key, `withdrawal_privkey`, must also be securely generated along with the resultant `withdrawal_pubkey`. This `withdrawal_privkey` does not have to be available for signing during the normal lifetime of a validator and can live in "cold storage".

The validator constructs their `withdrawal_credentials` via the following:
* Set `withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX_BYTE`.
* Set `withdrawal_credentials[1:] == hash(withdrawal_pubkey)[1:]`.

### Submit deposit

In phase 0, all incoming validator deposits originate from the Ethereum 1.0 PoW chain. Deposits are made to the [deposit contract](../core/0_deposit-contract.md) located at `DEPOSIT_CONTRACT_ADDRESS`.

To submit a deposit:

* Pack the validator's [initialization parameters](#initialization) into `deposit_data`, a [`DepositData`](../core/0_beacon-chain.md#depositdata) SSZ object.
* Let `amount` be the amount in Gwei to be deposited by the validator where `MIN_DEPOSIT_AMOUNT <= amount <= MAX_DEPOSIT_AMOUNT`.
* Set `deposit_data.amount = amount`.
* Let `signature` be the result of `bls_sign` of the `signing_root(deposit_data)` with `domain=DOMAIN_DEPOSIT`.
* Send a transaction on the Ethereum 1.0 chain to `DEPOSIT_CONTRACT_ADDRESS` executing `def deposit(pubkey: bytes[48], withdrawal_credentials: bytes[32], signature: bytes[96])` along with a deposit of `amount` Gwei.

_Note_: Deposits made for the same `pubkey` are treated as for the same validator. A singular `Validator` will be added to `state.validator_registry` with each additional deposit amount added to the validator's balance. A validator can only be activated when total deposits for the validator pubkey meet or exceed `MAX_DEPOSIT_AMOUNT`.

### Process deposit

Deposits cannot be processed into the beacon chain until the eth1.0 block in which they were deposited or any of its descendants is added to the beacon chain `state.eth1_data`. This takes _a minimum_ of `ETH1_FOLLOW_DISTANCE` eth1.0 blocks (~4 hours) plus `ETH1_DATA_VOTING_PERIOD` epochs (~1.7 hours). Once the requisite eth1.0 data is added, the deposit will normally be added to a beacon chain block and processed into the `state.validator_registry` within an epoch or two. The validator is then in a queue to be activated.

### Validator index

Once a validator has been processed and added to the beacon state's `validator_registry`, the validator's `validator_index` is defined by the index into the registry at which the [`ValidatorRecord`](../core/0_beacon-chain.md#validator) contains the `pubkey` specified in the validator's deposit. A validator's `validator_index` is guaranteed to not change from the time of initial deposit until the validator exits and fully withdraws. This `validator_index` is used throughout the specification to dictate validator roles and responsibilities at any point and should be stored locally.

### Activation

In normal operation, the validator is quickly activated at which point the validator is added to the shuffling and begins validation after an additional `ACTIVATION_EXIT_DELAY` epochs (25.6 minutes).

The function [`is_active_validator`](../core/0_beacon-chain.md#is_active_validator) can be used to check if a validator is active during a given shuffling epoch. Note that the `BeaconState` contains a field `current_shuffling_epoch` which dictates from which epoch the current active validators are taken. Usage is as follows:

```python
shuffling_epoch = state.current_shuffling_epoch
validator = state.validator_registry[validator_index]
is_active = is_active_validator(validator, shuffling_epoch)
```

Once a validator is activated, the validator is assigned [responsibilities](#beacon-chain-responsibilities) until exited.

_Note_: There is a maximum validator churn per finalized epoch so the delay until activation is variable depending upon finality, total active validator balance, and the number of validators in the queue to be activated.

## Beacon chain responsibilities

A validator has two primary responsibilities to the beacon chain -- [proposing blocks](block-proposal) and [creating attestations](attestations-1). Proposals happen infrequently, whereas attestations should be created once per epoch.

### Block proposal

A validator is expected to propose a [`BeaconBlock`](../core/0_beacon-chain.md#beaconblock) at the beginning of any slot during which `get_beacon_proposer_index(state)` returns the validator's `validator_index`. To propose, the validator selects the `BeaconBlock`, `parent`, that in their view of the fork choice is the head of the chain during `slot - 1`. The validator is to create, sign, and broadcast a `block` that is a child of `parent` and that executes a valid [beacon chain state transition](../core/0_beacon-chain.md#beacon-chain-state-transition-function).

There is one proposer per slot, so if there are N active validators any individual validator will on average be assigned to propose once per N slots (e.g. at 312500 validators = 10 million ETH, that's once per ~3 weeks).

#### Block header

##### Slot

Set `block.slot = slot` where `slot` is the current slot at which the validator has been selected to propose. The `parent` selected must satisfy that `parent.slot < block.slot`.

_Note:_ there might be "skipped" slots between the `parent` and `block`. These skipped slots are processed in the state transition function without per-block processing.

##### Parent root

Set `block.previous_block_root = signing_root(parent)`.

##### State root

Set `block.state_root = hash_tree_root(state)` of the resulting `state` of the `parent -> block` state transition.

_Note_: To calculate `state_root`, the validator should first run the state transition function on an unsigned `block` containing a stub for the `state_root`. It is useful to be able to run a state transition function that does _not_ validate signatures or state root for this purpose.

##### Randao reveal

Set `block.randao_reveal = epoch_signature` where `epoch_signature` is defined as:

```python
epoch_signature = bls_sign(
    privkey=validator.privkey,  # privkey stored locally, not in state
    message_hash=hash_tree_root(slot_to_epoch(block.slot)),
    domain=get_domain(
        fork=fork,  # `fork` is the fork object at the slot `block.slot`
        epoch=slot_to_epoch(block.slot),
        domain_type=DOMAIN_RANDAO,
    )
)
```

##### Eth1 Data

`block.eth1_data` is a mechanism used by block proposers vote on a recent Ethereum 1.0 block hash and an associated deposit root found in the Ethereum 1.0 deposit contract. When consensus is formed, `state.latest_eth1_data` is updated, and validator deposits up to this root can be processed. The deposit root can be calculated by calling the `get_deposit_root()` function of the deposit contract using the post-state of the block hash.

* Let `D` be the set of `Eth1DataVote` objects `vote` in `state.eth1_data_votes` where:
    * `vote.eth1_data.block_hash` is the hash of an eth1.0 block that is (i) part of the canonical chain, (ii) >= `ETH1_FOLLOW_DISTANCE` blocks behind the head, and (iii) newer than `state.latest_eth1_data.block_data`.
    * `vote.eth1_data.deposit_count` is the deposit count of the eth1.0 deposit contract at the block defined by `vote.eth1_data.block_hash`.
    * `vote.eth1_data.deposit_root` is the deposit root of the eth1.0 deposit contract at the block defined by `vote.eth1_data.block_hash`.
* If `D` is empty:
    * Let `block_hash` be the block hash of the `ETH1_FOLLOW_DISTANCE`'th ancestor of the head of the canonical eth1.0 chain.
    * Let `deposit_root` and `deposit_count` be the deposit root and deposit count of the eth1.0 deposit contract in the post-state of the block referenced by `block_hash`
    * Let `best_vote_data = Eth1Data(block_hash=block_hash, deposit_root=deposit_root, deposit_count=deposit_count)`.
* If `D` is nonempty:
    * Let `best_vote_data` be the `eth1_data` of the member of `D` that has the highest `vote.vote_count`, breaking ties by favoring block hashes with higher associated block height.
* Set `block.eth1_data = best_vote_data`.

##### Signature

Set `block.signature = block_signature` where `block_signature` is defined as:

```python
block_signature = bls_sign(
    privkey=validator.privkey,  # privkey store locally, not in state
    message_hash=signing_root(block),
    domain=get_domain(
        fork=fork,  # `fork` is the fork object at the slot `block.slot`
        epoch=slot_to_epoch(block.slot),
        domain_type=DOMAIN_BEACON_BLOCK,
    )
)
```

#### Block body

##### Proposer slashings

Up to `MAX_PROPOSER_SLASHINGS` [`ProposerSlashing`](../core/0_beacon-chain.md#proposerslashing) objects can be included in the `block`. The proposer slashings must satisfy the verification conditions found in [proposer slashings processing](../core/0_beacon-chain.md#proposer-slashings). The validator receives a small "whistleblower" reward for each proposer slashing found and included.

##### Attester slashings

Up to `MAX_ATTESTER_SLASHINGS` [`AttesterSlashing`](../core/0_beacon-chain.md#attesterslashing) objects can be included in the `block`. The attester slashings must satisfy the verification conditions found in [Attester slashings processing](../core/0_beacon-chain.md#attester-slashings). The validator receives a small "whistleblower" reward for each attester slashing found and included.

##### Attestations

Up to `MAX_ATTESTATIONS` aggregate attestations can be included in the `block`. The attestations added must satisfy the verification conditions found in [attestation processing](../core/0_beacon-chain.md#attestations). To maximize profit, the validator should attempt to gather aggregate attestations that include singular attestations from the largest number of validators whose signatures from the same epoch have not previously been added on chain.

##### Deposits

If there are any unprocessed deposits for the existing `state.latest_eth1_data` (i.e. `state.latest_eth1_data.deposit_count > state.deposit_index`), then pending deposits _must_ be added to the block. The expected number of deposits is exactly `min(MAX_DEPOSITS, latest_eth1_data.deposit_count - state.deposit_index)`.  These [`deposits`](../core/0_beacon-chain.md#deposit) are constructed from the `Deposit` logs from the [Eth1.0 deposit contract](../core/0_deposit-contract) and must be processed in sequential order. The deposits included in the `block` must satisfy the verification conditions found in [deposits processing](../core/0_beacon-chain.md#deposits).

The `proof` for each deposit must be constructed against the deposit root contained in `state.latest_eth1_data` rather than the deposit root at the time the deposit was initially logged from the 1.0 chain. This entails storing a full deposit merkle tree locally and computing updated proofs against the `latest_eth1_data.deposit_root` as needed. See [`minimal_merkle.py`](https://github.com/ethereum/research/blob/master/spec_pythonizer/utils/merkle_minimal.py) for a sample implementation.

##### Voluntary exits

Up to `MAX_VOLUNTARY_EXITS` [`VoluntaryExit`](../core/0_beacon-chain.md#voluntaryexit) objects can be included in the `block`. The exits must satisfy the verification conditions found in [exits processing](../core/0_beacon-chain.md#voluntary-exits).

### Attestations

A validator is expected to create, sign, and broadcast an attestation during each epoch. The slot during which the validator performs this role is any slot at which `get_crosslink_committees_at_slot(state, slot)` contains a committee that contains `validator_index`.

A validator should create and broadcast the attestation halfway through the `slot` during which the validator is assigned -- that is `SECONDS_PER_SLOT * 0.5` seconds after the start of `slot`.

#### Attestation data

First the validator should construct `attestation_data`, an [`AttestationData`](../core/0_beacon-chain.md#attestationdata) object based upon the state at the assigned slot.

* Let `head_block` be the result of running the fork choice during the assigned slot.
* Let `head_state` be the state of `head_block` processed through any empty slots up to the assigned slot.

##### Slot

Set `attestation_data.slot = head_state.slot`.

##### Beacon block root

Set `attestation_data.beacon_block_root = signing_root(head_block)`.

##### Source epoch

Set `attestation_data.source_epoch = head_state.justified_epoch`.

##### Source root

Set `attestation_data.source_root = head_state.current_justified_root`.

##### Target root

Set `attestation_data.target_root = signing_root(epoch_boundary)` where `epoch_boundary` is the block at the most recent epoch boundary.

_Note:_ This can be looked up in the state using:
* Let `epoch_start_slot = get_epoch_start_slot(get_current_epoch(head_state))`.
* Set `epoch_boundary = head if epoch_start_slot == head_state.slot else get_block_root(state, epoch_start_slot)`.

##### Shard

Set `attestation_data.shard = shard` where `shard` is the shard associated with the validator's committee defined by `get_crosslink_committees_at_slot`.

##### Previous crosslink root

Set `attestation_data.previous_crosslink_root = hash_tree_root(head_state.current_crosslinks[shard])`.

##### Crosslink data root

Set `attestation_data.crosslink_data_root = ZERO_HASH`.

_Note:_ This is a stub for phase 0.

#### Construct attestation

Next the validator creates `attestation`, an [`Attestation`](../core/0_beacon-chain.md#attestation) object.

##### Data

Set `attestation.data = attestation_data` where `attestation_data` is the `AttestationData` object defined in the previous section, [attestation data](#attestation-data).

##### Aggregation bitfield

* Let `aggregation_bitfield` be a byte array filled with zeros of length `(len(committee) + 7) // 8`.
* Let `index_into_committee` be the index into the validator's `committee` at which `validator_index` is located.
* Set `aggregation_bitfield[index_into_committee // 8] |= 2 ** (index_into_committee % 8)`.
* Set `attestation.aggregation_bitfield = aggregation_bitfield`.

_Note_: Calling `get_attesting_indices(state, attestation.data, attestation.aggregation_bitfield)` should return a list of length equal to 1, containing `validator_index`.

##### Custody bitfield

* Let `custody_bitfield` be a byte array filled with zeros of length `(len(committee) + 7) // 8`.
* Set `attestation.custody_bitfield = custody_bitfield`.

_Note:_ This is a stub for phase 0.

##### Aggregate signature

Set `attestation.aggregate_signature = signed_attestation_data` where `signed_attestation_data` is defined as:

```python
attestation_data_and_custody_bit = AttestationDataAndCustodyBit(
    data=attestation.data,
    custody_bit=0b0,
)
attestation_message = hash_tree_root(attestation_data_and_custody_bit)

signed_attestation_data = bls_sign(
    privkey=validator.privkey,  # privkey stored locally, not in state
    message_hash=attestation_message,
    domain=get_domain(
        fork=fork,  # `fork` is the fork object at the slot, `attestation_data.slot`
        epoch=slot_to_epoch(attestation_data.slot),
        domain_type=DOMAIN_ATTESTATION,
    )
)
```

## Validator assignments

A validator can get the current, previous, and next epoch committee assignments using the following helper via `get_committee_assignment(state, epoch, validator_index)` where `previous_epoch <= epoch <= next_epoch`.

```python
def get_committee_assignment(
        state: BeaconState,
        epoch: Epoch,
        validator_index: ValidatorIndex) -> Tuple[List[ValidatorIndex], Shard, Slot]:
    """
    Return the committee assignment in the ``epoch`` for ``validator_index``.
    ``assignment`` returned is a tuple of the following form:
        * ``assignment[0]`` is the list of validators in the committee
        * ``assignment[1]`` is the shard to which the committee is assigned
        * ``assignment[2]`` is the slot at which the committee is assigned
    """
    previous_epoch = get_previous_epoch(state)
    next_epoch = get_current_epoch(state) + 1
    assert previous_epoch <= epoch <= next_epoch

    epoch_start_slot = get_epoch_start_slot(epoch)
    for slot in range(epoch_start_slot, epoch_start_slot + SLOTS_PER_EPOCH):
        crosslink_committees = get_crosslink_committees_at_slot(
            state,
            slot,
        )
        selected_committees = [
            committee  # Tuple[List[ValidatorIndex], Shard]
            for committee in crosslink_committees
            if validator_index in committee[0]
        ]
        if len(selected_committees) > 0:
            validators = selected_committees[0][0]
            shard = selected_committees[0][1]

            assignment = (validators, shard, slot)
            return assignment
```

A validator can use the following function to see if they are supposed to propose during their assigned committee slot. This function can only be run during the slot in question. Proposer selection is only stable within the context of the current epoch.

```python
def is_proposer_at_slot(state: BeaconState,
                        slot: Slot,
                        validator_index: ValidatorIndex) -> bool:
    assert state.slot == slot

    return get_beacon_proposer_index(state) == validator_index
```

_Note_: To see if a validator is assigned to proposer during the slot, the validator must run an empty slot transition from the previous state to the current slot.


### Lookahead

The beacon chain shufflings are designed to provide a minimum of 1 epoch lookahead on the validator's upcoming committee assignments for attesting dictated by the shuffling and slot. Note that this lookahead does not apply to proposing which must checked during the slot in question.

`get_committee_assignment` should be called at the start of each epoch to get the assignment for the next epoch (`current_epoch + 1`). A validator should plan for future assignments which involves noting at which future slot one will have to attest and also which shard one should begin syncing (in phase 1+).

Specifically, a validator should call `get_committee_assignment(state, next_epoch, validator_index)` when checking for next epoch assignments.

## How to avoid slashing

"Slashing" is the burning of some amount of validator funds and immediate ejection from the active validator set. In Phase 0, there are two ways in which funds can be slashed -- [proposer slashing](#proposer-slashing) and [attester slashing](#attester-slashing). Although being slashed has serious repercussions, it is simple enough to avoid being slashed all together by remaining _consistent_ with respect to the messages a validator has previously signed.

_Note_: Signed data must be within a sequential `Fork` context to conflict. Messages cannot be slashed across diverging forks. If the previous fork version is 1 and the chain splits into fork 2 and 102, messages from 1 can slashable against messages in forks 1, 2, and 102. Messages in 2 cannot be slashable against messages in 102 and vice versa.

### Proposer slashing

To avoid "proposer slashings", a validator must not sign two conflicting [`BeaconBlock`](../core/0_beacon-chain.md#beaconblock) where conflicting is defined as two distinct blocks within the same epoch.

_In phase 0, as long as the validator does not sign two different beacon blocks for the same epoch, the validator is safe against proposer slashings._

Specifically, when signing an `BeaconBlock`, a validator should perform the following steps in the following order:
1. Save a record to hard disk that an beacon block has been signed for the `epoch=slot_to_epoch(block.slot)`.
2. Generate and broadcast the block.

If the software crashes at some point within this routine, then when the validator comes back online the hard disk has the record of the _potentially_ signed/broadcast block and can effectively avoid slashing.

### Attester slashing

To avoid "attester slashings", a validator must not sign two conflicting [`AttestationData`](../core/0_beacon-chain.md#attestationdata) objects, i.e. two attestations that satisfy [`is_slashable_attestation_data`](../core/0_beacon-chain.md#is_slashable_attestation_data).

Specifically, when signing an `Attestation`, a validator should perform the following steps in the following order:
1. Save a record to hard disk that an attestation has been signed for source -- `attestation_data.source_epoch` -- and target -- `slot_to_epoch(attestation_data.slot)`.
2. Generate and broadcast attestation.

If the software crashes at some point within this routine, then when the validator comes back online the hard disk has the record of the _potentially_ signed/broadcast attestation and can effectively avoid slashing.
