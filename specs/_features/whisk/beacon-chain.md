# Whisk -- The Beacon Chain

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
- [Cryptography](#cryptography)
  - [BLS](#bls)
  - [Curdleproofs and opening proofs](#curdleproofs-and-opening-proofs)
- [Epoch processing](#epoch-processing)
  - [`WhiskTracker`](#whisktracker)
  - [`Validator`](#validator)
  - [`BeaconState`](#beaconstate)
- [Block processing](#block-processing)
  - [Block header](#block-header)
    - [`BeaconBlock`](#beaconblock)
  - [Whisk](#whisk)
    - [`BeaconBlockBody`](#beaconblockbody)
  - [Deposits](#deposits)
  - [`get_beacon_proposer_index`](#get_beacon_proposer_index)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document details the beacon chain additions and changes of to support the Whisk SSLE,

*Note:* This specification is built upon [Capella](../../capella/beacon-chain.md) and is under active development.

## Constants

| Name                               | Value                      | Description                                                 |
| ---------------------------------- | -------------------------- | ----------------------------------------------------------- |
| `WHISK_CANDIDATE_TRACKERS_COUNT`   | `uint64(2**14)` (= 16,384) | number of candidate trackers                                |
| `WHISK_PROPOSER_TRACKERS_COUNT`    | `uint64(2**13)` (= 8,192)  | number of proposer trackers                                 |
| `WHISK_EPOCHS_PER_SHUFFLING_PHASE` | `Epoch(2**8)` (= 256)      | epochs per shuffling phase                                  |
| `WHISK_VALIDATORS_PER_SHUFFLE`     | `uint64(2**7)` (= 128)     | number of validators shuffled per shuffle step              |
| `WHISK_PROPOSER_SELECTION_GAP`     | `Epoch(2)`                 | gap between proposer selection and the block proposal phase |
| `WHISK_MAX_SHUFFLE_PROOF_SIZE`     | `uint64(2**15)`            | max size of a shuffle proof                                 |
| `WHISK_MAX_OPENING_PROOF_SIZE`     | `uint64(2**10)`            | max size of a opening proof                                 |

| Name                               | Value                      |
| ---------------------------------- | -------------------------- |
| `DOMAIN_WHISK_CANDIDATE_SELECTION` | `DomainType('0x07000000')` |
| `DOMAIN_WHISK_SHUFFLE`             | `DomainType('0x07100000')` |
| `DOMAIN_WHISK_PROPOSER_SELECTION`  | `DomainType('0x07200000')` |

## Cryptography

### BLS

| Name                | SSZ equivalent                           | Description                   |
| ------------------- | ---------------------------------------- | ----------------------------- |
| `BLSFieldElement`   | `uint256`                                | BLS12-381 scalar              |
| `BLSG1Point`        | `Bytes48`                                | compressed BLS12-381 G1 point |
| `WhiskShuffleProof` | `ByteList[WHISK_MAX_SHUFFLE_PROOF_SIZE]` | Serialized shuffle proof      |
| `WhiskTrackerProof` | `ByteList[WHISK_MAX_OPENING_PROOF_SIZE]` | Serialized tracker proof      |

*Note*: A subgroup check MUST be performed when deserializing a `BLSG1Point` for use in any of the functions below.

```python
def BLSG1ScalarMultiply(scalar: BLSFieldElement, point: BLSG1Point) -> BLSG1Point:
    return bls.G1_to_bytes48(bls.multiply(bls.bytes48_to_G1(point), scalar))
```

```python
def bytes_to_bls_field(b: Bytes32) -> BLSFieldElement:
    """
    Convert bytes to a BLS field scalar. The output is not uniform over the BLS field.
    TODO: Deneb will introduces this helper too. Should delete it once it's rebased to post-Deneb.
    """
    field_element = int.from_bytes(b, ENDIANNESS)
    assert field_element < BLS_MODULUS
    return BLSFieldElement(field_element)
```

| Name               | Value                                                                           |
| ------------------ | ------------------------------------------------------------------------------- |
| `BLS_G1_GENERATOR` | `bls.G1_to_bytes48(bls.G1)`                                                     |
| `BLS_MODULUS`      | `52435875175126190479447740508185965837690552500527637822603658699938581184513` |

### Curdleproofs and opening proofs

Note that Curdleproofs (Whisk Shuffle Proofs), the tracker opening proofs and all related data structures and verifier code (along with tests) is specified in [curdleproofs.pie](https://github.com/nalinbhardwaj/curdleproofs.pie/tree/verifier-only) repository.

```python
def IsValidWhiskShuffleProof(pre_shuffle_trackers: Sequence[WhiskTracker],
                             post_shuffle_trackers: Sequence[WhiskTracker],
                             M: BLSG1Point,
                             shuffle_proof: WhiskShuffleProof) -> bool:
    """
    Verify `post_shuffle_trackers` is a permutation of `pre_shuffle_trackers`.
    Defined in https://github.com/nalinbhardwaj/curdleproofs.pie/tree/verifier-only.
    """
    # pylint: disable=unused-argument
    return True
```

```python
def IsValidWhiskOpeningProof(tracker: WhiskTracker,
                             k_commitment: BLSG1Point,
                             tracker_proof: WhiskTrackerProof) -> bool:
    """
    Verify knowledge of `k` such that `tracker.k_r_G == k * tracker.r_G` and `k_commitment == k * BLS_G1_GENERATOR`.
    Defined in https://github.com/nalinbhardwaj/curdleproofs.pie/tree/verifier-only.
    """
    # pylint: disable=unused-argument
    return True
```

## Epoch processing

### `WhiskTracker`

```python
class WhiskTracker(Container):
    r_G: BLSG1Point  # r * G
    k_r_G: BLSG1Point  # k * r * G
```

### `Validator`

```python
class Validator(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32  # Commitment to pubkey for withdrawals
    effective_balance: Gwei  # Balance at stake
    slashed: boolean
    # Status epochs
    activation_eligibility_epoch: Epoch  # When criteria for activation were met
    activation_epoch: Epoch
    exit_epoch: Epoch
    withdrawable_epoch: Epoch  # When validator can withdraw funds
    whisk_tracker: WhiskTracker  # Whisk tracker (r * G, k * r * G) [New in Whisk]
    whisk_k_commitment: BLSG1Point  # Whisk k commitment k * BLS_G1_GENERATOR [New in Whisk]
```

### `BeaconState`

```python
class BeaconState(Container):
    # Versioning
    genesis_time: uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    # History
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]  # Frozen in Capella, replaced by historical_summaries
    # Eth1
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH]
    eth1_deposit_index: uint64
    # Registry
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]  # [Modified in Whisk]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    # Randomness
    randao_mixes: Vector[Bytes32, EPOCHS_PER_HISTORICAL_VECTOR]
    # Slashings
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]  # Per-epoch sums of slashed effective balances
    # Participation
    previous_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    current_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    # Inactivity
    inactivity_scores: List[uint64, VALIDATOR_REGISTRY_LIMIT]
    # Sync
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # Execution
    latest_execution_payload_header: ExecutionPayloadHeader
    # Withdrawals
    next_withdrawal_index: WithdrawalIndex
    next_withdrawal_validator_index: ValidatorIndex
    # Deep history valid from Capella onwards
    historical_summaries: List[HistoricalSummary, HISTORICAL_ROOTS_LIMIT]
    whisk_candidate_trackers: Vector[WhiskTracker, WHISK_CANDIDATE_TRACKERS_COUNT]  # [New in Whisk]
    whisk_proposer_trackers: Vector[WhiskTracker, WHISK_PROPOSER_TRACKERS_COUNT]  # [New in Whisk]
```

```python
def select_whisk_trackers(state: BeaconState, epoch: Epoch) -> None:
    # Select proposer trackers from candidate trackers
    proposer_seed = get_seed(state, epoch - WHISK_PROPOSER_SELECTION_GAP, DOMAIN_WHISK_PROPOSER_SELECTION)
    for i in range(WHISK_PROPOSER_TRACKERS_COUNT):
        index = compute_shuffled_index(uint64(i), uint64(len(state.whisk_candidate_trackers)), proposer_seed)
        state.whisk_proposer_trackers[i] = state.whisk_candidate_trackers[index]

    # Select candidate trackers from active validator trackers
    active_validator_indices = get_active_validator_indices(state, epoch)
    for i in range(WHISK_CANDIDATE_TRACKERS_COUNT):
        seed = hash(get_seed(state, epoch, DOMAIN_WHISK_CANDIDATE_SELECTION) + uint_to_bytes(i))
        candidate_index = compute_proposer_index(state, active_validator_indices, seed)  # sample by effective balance
        state.whisk_candidate_trackers[i] = state.validators[candidate_index].whisk_tracker
```

```python
def process_whisk_updates(state: BeaconState) -> None:
    next_epoch = Epoch(get_current_epoch(state) + 1)
    if next_epoch % WHISK_EPOCHS_PER_SHUFFLING_PHASE == 0:  # select trackers at the start of shuffling phases
        select_whisk_trackers(state, next_epoch)
```

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_eth1_data_reset(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_summaries_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
    process_whisk_updates(state)  # [New in Whisk]
```

## Block processing

### Block header

#### `BeaconBlock`

```python
class BeaconBlock(Container):
    slot: Slot
    proposer_index: ValidatorIndex
    parent_root: Root
    state_root: Root
    body: BeaconBlockBody
    whisk_opening_proof: WhiskTrackerProof  # [New in Whisk]
```

```python
def process_whisk_opening_proof(state: BeaconState, block: BeaconBlock) -> None:
    tracker = state.whisk_proposer_trackers[state.slot % WHISK_PROPOSER_TRACKERS_COUNT]
    k_commitment = state.validators[block.proposer_index].whisk_k_commitment
    assert IsValidWhiskOpeningProof(tracker, k_commitment, block.whisk_opening_proof)
```

Removed `assert block.proposer_index == get_beacon_proposer_index(state)` check in Whisk.

```python
def process_block_header(state: BeaconState, block: BeaconBlock) -> None:
    # Verify that the slots match
    assert block.slot == state.slot
    # Verify that the block is newer than latest block header
    assert block.slot > state.latest_block_header.slot

    # # Verify that proposer index is the correct index
    # assert block.proposer_index == get_beacon_proposer_index(state)

    # Verify that the parent matches
    assert block.parent_root == hash_tree_root(state.latest_block_header)
    # Cache current block as the new latest block
    state.latest_block_header = BeaconBlockHeader(
        slot=block.slot,
        proposer_index=block.proposer_index,
        parent_root=block.parent_root,
        state_root=Bytes32(),  # Overwritten in the next process_slot call
        body_root=hash_tree_root(block.body),
    )

    # Verify proposer is not slashed
    proposer = state.validators[block.proposer_index]
    assert not proposer.slashed
    process_whisk_opening_proof(state, block)   # [New in Whisk]
```

### Whisk

#### `BeaconBlockBody`

```python
class BeaconBlockBody(capella.BeaconBlockBody):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data  # Eth1 data vote
    graffiti: Bytes32  # Arbitrary data
    # Operations
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    # Execution
    execution_payload: ExecutionPayload
    # Capella operations
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    whisk_post_shuffle_trackers: Vector[WhiskTracker, WHISK_VALIDATORS_PER_SHUFFLE]  # [New in Whisk]
    whisk_shuffle_proof: WhiskShuffleProof  # [New in Whisk]
    whisk_shuffle_proof_M_commitment: BLSG1Point  # [New in Whisk]
    whisk_registration_proof: WhiskTrackerProof  # [New in Whisk]
    whisk_tracker: WhiskTracker  # [New in Whisk]
    whisk_k_commitment: BLSG1Point  # [New in Whisk]
```

```python
def get_shuffle_indices(randao_reveal: BLSSignature) -> Sequence[uint64]:
    """
    Given a `randao_reveal` return the list of indices that got shuffled from the entire candidate set
    """
    indices = []
    for i in WHISK_VALIDATORS_PER_SHUFFLE:
        # XXX ensure we are not suffering from modulo bias
        shuffle_index = uint256(hash(randao_reveal + uint_to_bytes(i))) % WHISK_CANDIDATE_TRACKERS_COUNT
        indices.append(shuffle_index)

    return indices
```

```python
def process_shuffled_trackers(state: BeaconState, body: BeaconBlockBody) -> None:
    # Check the shuffle proof
    shuffle_indices = get_shuffle_indices(body.randao_reveal)
    pre_shuffle_trackers = [state.whisk_candidate_trackers[i] for i in shuffle_indices]
    post_shuffle_trackers = body.whisk_post_shuffle_trackers

    shuffle_epoch = get_current_epoch(state) % WHISK_EPOCHS_PER_SHUFFLING_PHASE
    if shuffle_epoch + WHISK_PROPOSER_SELECTION_GAP + 1 >= WHISK_EPOCHS_PER_SHUFFLING_PHASE:
        # Require unchanged trackers during cooldown
        assert pre_shuffle_trackers == post_shuffle_trackers
    else:
        # Require shuffled trackers during shuffle
        assert IsValidWhiskShuffleProof(
            pre_shuffle_trackers,
            post_shuffle_trackers,
            body.whisk_shuffle_proof_M_commitment,
            body.whisk_shuffle_proof,
        )

    # Shuffle candidate trackers
    for i, shuffle_index in enumerate(shuffle_indices):
        state.whisk_candidate_trackers[shuffle_index] = post_shuffle_trackers[i]
```

```python
def is_k_commitment_unique(state: BeaconState, k_commitment: BLSG1Point) -> bool:
    return all([validator.whisk_k_commitment != k_commitment for validator in state.validators])
```

```python
def process_whisk(state: BeaconState, body: BeaconBlockBody) -> None:
    process_shuffled_trackers(state, body)

    # Overwrite all validator Whisk fields (first Whisk proposal) or just the permutation commitment (next proposals)
    proposer = state.validators[get_beacon_proposer_index(state)]
    if proposer.whisk_tracker.r_G == BLS_G1_GENERATOR:  # first Whisk proposal
        assert body.whisk_tracker.r_G != BLS_G1_GENERATOR
        assert is_k_commitment_unique(state, body.whisk_k_commitment)
        assert IsValidWhiskOpeningProof(
            body.whisk_tracker,
            body.whisk_k_commitment,
            body.whisk_registration_proof,
        )
        proposer.whisk_tracker = body.whisk_tracker
        proposer.whisk_k_commitment = body.whisk_k_commitment
    else:  # next Whisk proposals
        assert body.whisk_registration_proof == WhiskTrackerProof()
        assert body.whisk_tracker == WhiskTracker()
        assert body.whisk_k_commitment == BLSG1Point()
    assert body.whisk_shuffle_proof_M_commitment == BLSG1Point()
```

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    if is_execution_enabled(state, block.body):
        process_withdrawals(state, block.body.execution_payload)
        process_execution_payload(state, block.body.execution_payload, EXECUTION_ENGINE)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
    process_whisk(state, block.body)  # [New in Whisk]
```

### Deposits

```python
def get_unique_whisk_k(state: BeaconState, validator_index: ValidatorIndex) -> BLSFieldElement:
    counter = 0
    while True:
        # hash `validator_index || counter`
        k = BLSFieldElement(bytes_to_bls_field(hash(uint_to_bytes(validator_index) + uint_to_bytes(uint64(counter)))))
        if is_k_commitment_unique(state, BLSG1ScalarMultiply(k, BLS_G1_GENERATOR)):
            return k  # unique by trial and error
        counter += 1
```

```python
def get_initial_commitments(k: BLSFieldElement) -> Tuple[BLSG1Point, WhiskTracker]:
    return (
        BLSG1ScalarMultiply(k, BLS_G1_GENERATOR),
        WhiskTracker(r_G=BLS_G1_GENERATOR, k_r_G=BLSG1ScalarMultiply(k, BLS_G1_GENERATOR))
    )
```

```python
def get_validator_from_deposit_whisk(
    state: BeaconState,
    pubkey: BLSPubkey,
    withdrawal_credentials: Bytes32,
    amount: uint64
) -> Validator:
    effective_balance = min(amount - amount % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE)
    k = get_unique_whisk_k(state, ValidatorIndex(len(state.validators)))
    whisk_k_commitment, whisk_tracker = get_initial_commitments(k)

    validator = Validator(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
        effective_balance=effective_balance,
        # Whisk fields
        whisk_tracker=whisk_tracker,
        whisk_k_commitment=whisk_k_commitment,
    )
    return validator
```

```python
def apply_deposit(state: BeaconState,
                  pubkey: BLSPubkey,
                  withdrawal_credentials: Bytes32,
                  amount: uint64,
                  signature: BLSSignature) -> None:
    validator_pubkeys = [validator.pubkey for validator in state.validators]
    if pubkey not in validator_pubkeys:
        # Verify the deposit signature (proof of possession) which is not checked by the deposit contract
        deposit_message = DepositMessage(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            amount=amount,
        )
        domain = compute_domain(DOMAIN_DEPOSIT)  # Fork-agnostic domain since deposits are valid across forks
        signing_root = compute_signing_root(deposit_message, domain)
        # Initialize validator if the deposit signature is valid
        if bls.Verify(pubkey, signing_root, signature):
            index = get_index_for_new_validator(state)
            validator = get_validator_from_deposit_whisk(state, pubkey, withdrawal_credentials, amount)
            set_or_append_list(state.validators, index, validator)
            set_or_append_list(state.balances, index, amount)
            # [New in Altair]
            set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
            set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
            set_or_append_list(state.inactivity_scores, index, uint64(0))
    else:
        # Increase balance by deposit amount
        index = ValidatorIndex(validator_pubkeys.index(pubkey))
        increase_balance(state, index, amount)
```

### `get_beacon_proposer_index`

```python
def get_beacon_proposer_index(state: BeaconState) -> ValidatorIndex:
    """
    Return the beacon proposer index at the current slot.
    """
    assert state.latest_block_header.slot == state.slot  # sanity check `process_block_header` has been called
    return state.latest_block_header.proposer_index
```
