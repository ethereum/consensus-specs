# EIP-7441 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Domain types](#domain-types)
- [Preset](#preset)
- [Configuration](#configuration)
- [Cryptography](#cryptography)
  - [BLS](#bls)
  - [Curdleproofs and opening proofs](#curdleproofs-and-opening-proofs)
- [Epoch processing](#epoch-processing)
  - [`WhiskTracker`](#whisktracker)
  - [`BeaconState`](#beaconstate)
- [Block processing](#block-processing)
  - [Block header](#block-header)
  - [Whisk](#whisk)
    - [`BeaconBlockBody`](#beaconblockbody)
  - [Deposits](#deposits)
  - [`get_beacon_proposer_index`](#get_beacon_proposer_index)

<!-- mdformat-toc end -->

## Introduction

This document details the beacon chain additions and changes of to support the EIP-7441 (Whisk SSLE).

*Note*: This specification is built upon [capella](../../capella/beacon-chain.md) and is under active development.

## Constants

### Domain types

| Name                         | Value                      |
| ---------------------------- | -------------------------- |
| `DOMAIN_CANDIDATE_SELECTION` | `DomainType('0x07000000')` |
| `DOMAIN_SHUFFLE`             | `DomainType('0x07100000')` |
| `DOMAIN_PROPOSER_SELECTION`  | `DomainType('0x07200000')` |

## Preset

| Name                       | Value                      | Description                                                 |
| -------------------------- | -------------------------- | ----------------------------------------------------------- |
| `CURDLEPROOFS_N_BLINDERS`  | `uint64(4)`                | number of blinders for curdleproofs                         |
| `CANDIDATE_TRACKERS_COUNT` | `uint64(2**14)` (= 16,384) | number of candidate trackers                                |
| `PROPOSER_TRACKERS_COUNT`  | `uint64(2**13)` (= 8,192)  | number of proposer trackers                                 |
| `VALIDATORS_PER_SHUFFLE`   | `uint64(2**7 - 4)` (= 124) | number of validators shuffled per shuffle step              |
| `MAX_SHUFFLE_PROOF_SIZE`   | `uint64(2**15)`            | max size of a shuffle proof                                 |
| `MAX_OPENING_PROOF_SIZE`   | `uint64(2**10)`            | max size of an opening proof                                |

## Configuration

| Name                               | Value                      | Description                                                 |
| ---------------------------------- | -------------------------- | ----------------------------------------------------------- |
| `EPOCHS_PER_SHUFFLING_PHASE` | `Epoch(2**8)` (= 256)      | epochs per shuffling phase                                  |
| `PROPOSER_SELECTION_GAP`     | `Epoch(2)`                 | gap between proposer selection and the block proposal phase |

## Cryptography

### BLS

| Name                | SSZ equivalent                     | Description                   |
| ------------------- | ---------------------------------- | ----------------------------- |
| `BLSFieldElement`   | `uint256`                          | BLS12-381 scalar              |
| `BLSG1Point`        | `Bytes48`                          | compressed BLS12-381 G1 point |
| `WhiskShuffleProof` | `ByteList[MAX_SHUFFLE_PROOF_SIZE]` | Serialized shuffle proof      |
| `WhiskTrackerProof` | `ByteList[MAX_OPENING_PROOF_SIZE]` | Serialized tracker proof      |

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
    return BLSFieldElement(field_element % BLS_MODULUS)
```

| Name                  | Value                                                                           |
| --------------------- | ------------------------------------------------------------------------------- |
| `BLS_G1_GENERATOR`    | `BLSG1Point('0x97f1d3a73197d7942695638c4fa9ac0fc3688c4f9774b905a14e3a3f171bac586c55e83ff97a1aeffb3af00adb22c6bb')  # noqa: E501` |
| `BLS_MODULUS`         | `52435875175126190479447740508185965837690552500527637822603658699938581184513` |
| `CURDLEPROOFS_CRS`    | TBD |

### Curdleproofs and opening proofs

Note that Curdleproofs (Whisk Shuffle Proofs), the tracker opening proofs and all related data structures and verifier code (along with tests) is specified in [curdleproofs.pie](https://github.com/nalinbhardwaj/curdleproofs.pie/tree/dev) repository.

```python
def IsValidWhiskShuffleProof(pre_shuffle_trackers: Sequence[WhiskTracker],
                             post_shuffle_trackers: Sequence[WhiskTracker],
                             shuffle_proof: WhiskShuffleProof) -> bool:
    """
    Verify `post_shuffle_trackers` is a permutation of `pre_shuffle_trackers`.
    Defined in https://github.com/nalinbhardwaj/curdleproofs.pie/blob/dev/curdleproofs/curdleproofs/whisk_interface.py.
    """
    return curdleproofs.IsValidWhiskShuffleProof(
        CURDLEPROOFS_CRS,
        pre_shuffle_trackers,
        post_shuffle_trackers,
        shuffle_proof,
    )
```

```python
def IsValidWhiskOpeningProof(tracker: WhiskTracker,
                             k_commitment: BLSG1Point,
                             tracker_proof: WhiskTrackerProof) -> bool:
    """
    Verify knowledge of `k` such that `tracker.k_r_G == k * tracker.r_G` and `k_commitment == k * BLS_G1_GENERATOR`.
    Defined in https://github.com/nalinbhardwaj/curdleproofs.pie/blob/dev/curdleproofs/curdleproofs/whisk_interface.py.
    """
    return curdleproofs.IsValidWhiskOpeningProof(tracker, k_commitment, tracker_proof)
```

## Epoch processing

### `WhiskTracker`

```python
class WhiskTracker(Container):
    r_G: BLSG1Point  # r * G
    k_r_G: BLSG1Point  # k * r * G
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
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
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
    # Whisk
    whisk_candidate_trackers: Vector[WhiskTracker, CANDIDATE_TRACKERS_COUNT]  # [New in EIP7441]
    whisk_proposer_trackers: Vector[WhiskTracker, PROPOSER_TRACKERS_COUNT]  # [New in EIP7441]
    whisk_trackers: List[WhiskTracker, VALIDATOR_REGISTRY_LIMIT]  # [New in EIP7441]
    whisk_k_commitments: List[BLSG1Point, VALIDATOR_REGISTRY_LIMIT]  # [New in EIP7441]
```

```python
def select_whisk_proposer_trackers(state: BeaconState, epoch: Epoch) -> None:
    # Select proposer trackers from candidate trackers
    proposer_seed = get_seed(
        state,
        Epoch(saturating_sub(epoch, PROPOSER_SELECTION_GAP)),
        DOMAIN_PROPOSER_SELECTION
    )
    for i in range(PROPOSER_TRACKERS_COUNT):
        index = compute_shuffled_index(uint64(i), uint64(len(state.whisk_candidate_trackers)), proposer_seed)
        state.whisk_proposer_trackers[i] = state.whisk_candidate_trackers[index]
```

```python
def select_whisk_candidate_trackers(state: BeaconState, epoch: Epoch) -> None:
    # Select candidate trackers from active validator trackers
    active_validator_indices = get_active_validator_indices(state, epoch)
    for i in range(CANDIDATE_TRACKERS_COUNT):
        seed = hash(get_seed(state, epoch, DOMAIN_CANDIDATE_SELECTION) + uint_to_bytes(uint64(i)))
        candidate_index = compute_proposer_index(state, active_validator_indices, seed)  # sample by effective balance
        state.whisk_candidate_trackers[i] = state.whisk_trackers[candidate_index]
```

```python
def process_whisk_updates(state: BeaconState) -> None:
    next_epoch = Epoch(get_current_epoch(state) + 1)
    if next_epoch % EPOCHS_PER_SHUFFLING_PHASE == 0:  # select trackers at the start of shuffling phases
        select_whisk_proposer_trackers(state, next_epoch)
        select_whisk_candidate_trackers(state, next_epoch)
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
    process_whisk_updates(state)  # [New in EIP7441]
```

## Block processing

### Block header

```python
def process_whisk_opening_proof(state: BeaconState, block: BeaconBlock) -> None:
    tracker = state.whisk_proposer_trackers[state.slot % PROPOSER_TRACKERS_COUNT]
    k_commitment = state.whisk_k_commitments[block.proposer_index]
    assert IsValidWhiskOpeningProof(tracker, k_commitment, block.body.whisk_opening_proof)
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
    process_whisk_opening_proof(state, block)   # [New in EIP7441]
```

### Whisk

#### `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
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
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]
    # Whisk
    whisk_opening_proof: WhiskTrackerProof  # [New in EIP7441]
    whisk_post_shuffle_trackers: Vector[WhiskTracker, VALIDATORS_PER_SHUFFLE]  # [New in EIP7441]
    whisk_shuffle_proof: WhiskShuffleProof  # [New in EIP7441]
    whisk_registration_proof: WhiskTrackerProof  # [New in EIP7441]
    whisk_tracker: WhiskTracker  # [New in EIP7441]
    whisk_k_commitment: BLSG1Point  # k * BLS_G1_GENERATOR [New in EIP7441]
```

```python
def get_shuffle_indices(randao_reveal: BLSSignature) -> Sequence[uint64]:
    """
    Given a `randao_reveal` return the list of indices that got shuffled from the entire candidate set.
    """
    indices = []
    for i in range(0, VALIDATORS_PER_SHUFFLE):
        # XXX ensure we are not suffering from modulo bias
        pre_image = randao_reveal + uint_to_bytes(uint64(i))
        shuffle_index = bytes_to_uint64(hash(pre_image)[0:8]) % CANDIDATE_TRACKERS_COUNT
        indices.append(shuffle_index)

    return indices
```

```python
def process_shuffled_trackers(state: BeaconState, body: BeaconBlockBody) -> None:
    shuffle_epoch = get_current_epoch(state) % EPOCHS_PER_SHUFFLING_PHASE
    if shuffle_epoch + PROPOSER_SELECTION_GAP + 1 >= EPOCHS_PER_SHUFFLING_PHASE:
        # Require trackers set to zero during cooldown
        assert body.whisk_post_shuffle_trackers == Vector[WhiskTracker, VALIDATORS_PER_SHUFFLE]()
        assert body.whisk_shuffle_proof == WhiskShuffleProof()
    else:
        # Require shuffled trackers during shuffle
        shuffle_indices = get_shuffle_indices(body.randao_reveal)
        pre_shuffle_trackers = [state.whisk_candidate_trackers[i] for i in shuffle_indices]
        assert IsValidWhiskShuffleProof(
            pre_shuffle_trackers,
            body.whisk_post_shuffle_trackers,
            body.whisk_shuffle_proof,
        )
        # Shuffle candidate trackers
        for i, shuffle_index in enumerate(shuffle_indices):
            state.whisk_candidate_trackers[shuffle_index] = body.whisk_post_shuffle_trackers[i]
```

```python
def is_k_commitment_unique(state: BeaconState, k_commitment: BLSG1Point) -> bool:
    return all([whisk_k_commitment != k_commitment for whisk_k_commitment in state.whisk_k_commitments])
```

```python
def process_whisk_registration(state: BeaconState, body: BeaconBlockBody) -> None:
    proposer_index = get_beacon_proposer_index(state)
    if state.whisk_trackers[proposer_index].r_G == BLS_G1_GENERATOR:  # first Whisk proposal
        assert body.whisk_tracker.r_G != BLS_G1_GENERATOR
        assert is_k_commitment_unique(state, body.whisk_k_commitment)
        assert IsValidWhiskOpeningProof(
            body.whisk_tracker,
            body.whisk_k_commitment,
            body.whisk_registration_proof,
        )
        state.whisk_trackers[proposer_index] = body.whisk_tracker
        state.whisk_k_commitments[proposer_index] = body.whisk_k_commitment
    else:  # next Whisk proposals
        assert body.whisk_registration_proof == WhiskTrackerProof()
        assert body.whisk_tracker == WhiskTracker()
        assert body.whisk_k_commitment == BLSG1Point()
```

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_withdrawals(state, block.body.execution_payload)
    process_execution_payload(state, block.body, EXECUTION_ENGINE)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
    process_shuffled_trackers(state, block.body)  # [New in EIP7441]
    process_whisk_registration(state, block.body)  # [New in EIP7441]
```

### Deposits

```python
def get_initial_whisk_k(validator_index: ValidatorIndex, counter: int) -> BLSFieldElement:
    # hash `validator_index || counter`
    return BLSFieldElement(bytes_to_bls_field(hash(uint_to_bytes(validator_index) + uint_to_bytes(uint64(counter)))))
```

```python
def get_unique_whisk_k(state: BeaconState, validator_index: ValidatorIndex) -> BLSFieldElement:
    counter = 0
    while True:
        k = get_initial_whisk_k(validator_index, counter)
        if is_k_commitment_unique(state, BLSG1ScalarMultiply(k, BLS_G1_GENERATOR)):
            return k  # unique by trial and error
        counter += 1
```

```python
def get_k_commitment(k: BLSFieldElement) -> BLSG1Point:
    return BLSG1ScalarMultiply(k, BLS_G1_GENERATOR)
```

```python
def get_initial_tracker(k: BLSFieldElement) -> WhiskTracker:
    return WhiskTracker(r_G=BLS_G1_GENERATOR, k_r_G=BLSG1ScalarMultiply(k, BLS_G1_GENERATOR))
```

```python
def add_validator_to_registry(state: BeaconState,
                              pubkey: BLSPubkey,
                              withdrawal_credentials: Bytes32,
                              amount: uint64) -> None:
    index = get_index_for_new_validator(state)
    validator = get_validator_from_deposit(pubkey, withdrawal_credentials, amount)
    set_or_append_list(state.validators, index, validator)
    set_or_append_list(state.balances, index, amount)
    set_or_append_list(state.previous_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.current_epoch_participation, index, ParticipationFlags(0b0000_0000))
    set_or_append_list(state.inactivity_scores, index, uint64(0))
    # [New in EIP7441]
    k = get_unique_whisk_k(state, ValidatorIndex(len(state.validators) - 1))
    state.whisk_trackers.append(get_initial_tracker(k))
    state.whisk_k_commitments.append(get_k_commitment(k))
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
