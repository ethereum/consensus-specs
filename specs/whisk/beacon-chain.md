### Diagram

```python
"""
                                          cooldown                  cooldown
                                          | ||                      | ||
                                          | ||                      | ||
           epoch N        N+1             vpvv       N+2            vpvv
                ----+~~~~~~~~~~~~~~~~~~~~~----+~~~~~~~~~~~~~~~~~~~~~----+-
                    ^        shuffling        ^         shuffling       ^
                    |                         |                         |
                    |                         |                         |
         proposer selection        proposer selection        proposer selection
        candidate selection       candidate selection       candidate selection
"""
```

### Constants

| Name | Value | Description |
| - | - | - |
| `WHISK_CANDIDATE_TRACKERS_COUNT` | `uint64(2**14)` (= 16,384) | number of candidate trackers |
| `WHISK_PROPOSER_TRACKERS_COUNT` | `uint64(2**13)` (= 8,192) | number of proposer trackers |
| `WHISK_SHUFFLING_PHASE_DURATION` | `Epoch(2**8)` (= 256) | shuffling phase duration |
| `WHISK_VALIDATORS_PER_SHUFFLE` | `uint64(2**7)` (= 128) | number of validators shuffled per shuffle step |
| `WHISK_SHUFFLE_STEPS_PER_ROUND` | `uint64(2**7)` (= 128) | Feistel permutation steps to complete a pass over all rows |
| `WHISK_PROPOSER_SELECTION_GAP` | `Epoch(2)` | gap between proposer selection and the block proposal phase |

| Name | Value |
| - | - |
| `DOMAIN_WHISK_CANDIDATE_SELECTION` | `DomainType('0x07000000')` |
| `DOMAIN_WHISK_SHUFFLE`             | `DomainType('0x07100000')` |
| `DOMAIN_WHISK_PROPOSER_SELECTION`  | `DomainType('0x07200000')` |

### Cryptography

#### BLS

| Name | SSZ equivalent | Description |
| - | - | - |
| `BLSFrScalar` | `Bytes48` | BLS12-381 Fr scalar |
| `BLSG1Point` | `Bytes48` | BLS12-381 G1 point |

*Note*: A subgroup check MUST be performed when deserializing a `BLSG1Point` for use in any of the functions below.

```python
def BLSG1PointFromAffine(x: int, y: int) -> BLSG1Point


def ScalarMultiplication(BLSFrScalar, BLSG1Point) -> BLSG1Point
```

| Name | Value |
| - | - |
| `BLS_G1_GENERATOR_X` | `0x17f1d3a73197d7942695638c4fa9ac0fc3688c4f9774b905a14e3a3f171bac586c55e83ff97a1aeffb3af00adb22c6bb` |
| `BLS_G1_GENERATOR_Y` | `0x08b3f481e3aaa0f1a09e30ed741d8ae4fcf5e095d5d00af600db18cb2c04b3edd03cc744a2888ae40caa232946c5e7e1` |
| `BLS_G1_GENERATOR`   | `BLSG1PointFromAffine(BLS_G1_GENERATOR_X, BLS_G1_GENERATOR_Y)`                                       |

#### Whisk

```python
class WhiskShuffleProof:
    ### TODO

class WhiskTrackerProof:
    T_1: BLSG1Point  # Sigma commitment
    T_2: BLSG1Point  # Sigma commitment
    s_1: BLSFrScalar  # Sigma response
    s_2: BLSFrScalar  # Sigma response

def IsValidShuffleProof(permutation_commitment: BLSG1Point,
                        pre_shuffle_trackers: Sequence[WhiskTracker],
                        post_shuffle_trackers: Sequence[WhiskTracker],
                        shuffle_proof: WhiskShuffleProof) -> bool
    """
    Verify `post_shuffle_trackers` is the permutation of `pre_shuffle_trackers` according to `permutation_commitment`.
    """


def IsValidTrackerProof(tracker: WhiskTracker, k_commitment: BLSG1Point, tracker_proof: WhiskTrackerProof) -> bool
    """
    Verify knowledge of `k` such that `tracker.k_r_G == k * tracker.r_G` and `k_commitment == k * G`.
    """
```

| Name | Value |
| - | - |
| `WHISK_TRIVIAL_PERMUTATION_COMMITMENT_X` | `TODO{Depends on CRS of shuffle proof}` |
| `WHISK_TRIVIAL_PERMUTATION_COMMITMENT_Y` | `TODO{Depends on CRS of shuffle proof}` |
| `WHISK_TRIVIAL_PERMUTATION_COMMITMENT` | `BLSG1PointFromAffine(WHISK_TRIVIAL_PERMUTATION_COMMITMENT_X, WHISK_TRIVIAL_PERMUTATION_COMMITMENT_Y)` |

### Epoch processing

```python
class WhiskTracker(Container):
    r_G: BLSG1Point  # r*G
    k_r_G: BLSG1Point  # k*r*G

class Validator(Container):
    # ...
    # Whisk
    whisk_tracker: WhiskTracker  # Whisk tracker (r*G, k*r*G) [New in Whisk]
    whisk_k_commitment: BLSG1Point  # Whisk k commitment k*G [New in Whisk]
    whisk_permutation_commitment: BLSG1Point  # Whisk permutation commitment [New in Whisk]

class BeaconState(Container):
    # ...
    # Whisk
    whisk_candidate_trackers: Vector[WhiskTracker, WHISK_CANDIDATE_TRACKERS_COUNT]  # [New in Whisk]
    whisk_proposer_trackers: Vector[WhiskTracker, WHISK_PROPOSER_TRACKERS_COUNT]  # [New in Whisk]

def select_whisk_trackers(state: BeaconState, epoch: Epoch) -> None:
    # Select proposer trackers from candidate trackers
    proposer_seed = get_seed(state, epoch - WHISK_PROPOSER_SELECTION_GAP, DOMAIN_WHISK_PROPOSER_SELECTION)
    for i in range(WHISK_PROPOSER_TRACKERS_COUNT):
        index = compute_shuffled_index(uint64(i), uint64(len(state.whisk_candidate_trackers)), proposer_seed)
        state.whisk_proposer_trackers[i] = state.whisk_candidate_trackers[index]

    # Select candidate trackers of active validators
    active_validator_indices = get_active_validator_indices(state, epoch)
    for i in range(WHISK_CANDIDATE_TRACKERS_COUNT):
        seed = hash(get_seed(state, epoch, DOMAIN_WHISK_CANDIDATE_SELECTION) + uint_to_bytes(i))
        validator_index = compute_proposer_index(state, active_validator_indices, seed)  # sample by effective balance
        state.whisk_candidate_trackers[i] = state.validators[validator_index].whisk_tracker


def process_whisk_updates(state: BeaconState) -> None:
    next_epoch = Epoch(get_current_epoch(state) + 1)
    if next_epoch % WHISK_SHUFFLING_PHASE_DURATION == 0:  # tracker selection happens at the start of shuffling phases
        select_whisk_trackers(state, next_epoch)

def process_epoch(state: BeaconState) -> None:
    # ...
    process_whisk_updates(state)  # [New in Whisk]
```

### Block processing

#### Block header

```python
class BeaconBlock(Container):
    # ...
    proposer_index: ValidatorIndex
    whisk_opening_proof: WhiskTrackerProof  # [New in Whisk]
    # ...

def process_whisk_opening_proof(state: BeaconState, block: BeaconBlock) -> None:
    tracker = state.whisk_proposer_trackers[state.slot % WHISK_PROPOSER_TRACKERS_COUNT]
    k_commitment = state.validators[block.proposer_index].whisk_k_commitment
    assert whisk.IsValidTrackerProof(tracker, k_commitment, block.whisk_opening_proof)


def process_block_header(state: BeaconState, block: BeaconBlock) -> None:
    # ...
    # [Removed in Whisk] Verify that proposer index is the correct index
    # [Removed in Whisk] assert block.proposer_index == get_beacon_proposer_index(state)
    process_whisk_opening_proof(state, block)  # [New in Whisk]
    # ...
```

#### Wisk

```python
class BeaconBlockBody(Container):
    # ...
    whisk_post_shuffle_trackers: Vector[WhiskTracker, WHISK_VALIDATORS_PER_SHUFFLE]  # [New in Whisk]
    whisk_shuffle_proof: ShuffleProof  # [New in Whisk]

    whisk_registration_proof: WhiskTrackerProof  # [New in Whisk]
    whisk_tracker: WhiskTracker  # [New in Whisk]
    whisk_k_commitment: BLSG1Point  # [New in Whisk]
    whisk_permutation_commitment: BLSG1Point  # [New in Whisk]


def get_feistel_encryption(index: uint64, rounds: uin64, K: uint64) -> uint64:
    def F(x):  # F(x) = x^3 (mod K) is a bijective non-linear function
        return (x ** 3) % K

    # Convert 2D (x, y) coordinates from 1D coordinates, apply Fiestel rounds, and convert back to 1D coordinates
    x, y = index // K, index % K
    for _ in range(rounds):
        x, y = y, (F(y) + x) % K
    return x * K + y


def get_shuffle_indices(state: BeaconState, epoch: Epoch) -> Sequence[uint64]:
    """
    Return the indices that the Feistel permutation shuffles in this slot.
    """
    shuffle_round = state.slot // WHISK_SHUFFLE_STEPS_PER_ROUND
    shuffle_step = state.slot % WHISK_SHUFFLE_STEPS_PER_ROUND
    row_indices = [i + WHISK_VALIDATORS_PER_SHUFFLE * shuffle_step for i in range(WHISK_VALIDATORS_PER_SHUFFLE)]
    return [get_feistel_encryption(index, shuffle_round, WHISK_VALIDATORS_PER_SHUFFLE) for index in row_indices]


def whisk_process_shuffled_trackers(state: BeaconState, body: BeaconBlockBody) -> None:
    epoch = get_current_epoch(state)
    epoch_in_shuffle_phase = epoch % WHISK_SHUFFLING_PHASE_DURATION
    if epoch_in_shuffle_phase + WHISK_PROPOSER_SELECTION_GAP + 1 >= WHISK_SHUFFLING_PHASE_DURATION:
        permutation_commitment = WHISK_TRIVIAL_PERMUTATION_COMMITMENT  # Require the trivial permutation during cooldown
    else:
        permutation_commitment = state.validators[get_beacon_proposer_index(state)].permutation_commitment

    # Check the shuffle proof
    shuffle_indices = get_shuffle_indices(state, epoch)
    pre_shuffle_trackers = [state.whisk_candidate_trackers[i] for i in shuffle_indices]
    post_shuffle_trackers = body.whisk_post_shuffle_trackers
    shuffle_proof = body.whisk_shuffle_proof
    assert whisk.IsValidShuffleProof(permutation_commitment, pre_shuffle_trackers, post_shuffle_trackers, shuffle_proof)

    # Shuffle candidate trackers
    for i, shuffle_index in enumerate(shuffle_indices):
        state.whisk_candidate_trackers[shuffle_index] = post_shuffle_trackers[i]


def is_k_commitment_unique(state: BeaconState, k_commitment: BLSG1Point) -> bool:
    return not any([validator.whisk_k_commitment == k_commitment for validator in state.validators])


def process_whisk(state: BeaconState, body: BeaconBlockBody) -> None:
    whisk_process_shuffled_trackers(state, body)

    # Allow proposer to register fresh Whisk commitments once
    proposer = state.validators[get_beacon_proposer_index(state)]
    if proposer.whisk_tracker.r_G == BLS_G1_GENERATOR:
        assert body.whisk_tracker.r_G != BLS_G1_GENERATOR
        # Check k is unique and that the same k is used in both the tracker and k commitment
        assert is_k_commitment_unique(state, body.whisk_k_commitment)
        assert whisk.IsValidTrackerProof(body.wisk_tracker, body.whisk_k_commitment, body.whisk_registration_proof)

        proposer.whisk_tracker = body.whisk_tracker
        proposer.whisk_k_commitment = body.whisk_k_commitment
    else:
        assert body.whisk_registration_proof == WhiskTrackerProof()
        assert body.whisk_tracker == WhiskTracker()
        assert body.whisk_k_commitment == BLSG1Point()

    # Always register a fresh permutation commitment
    proposer.whisk_permutation_commitment = body.whisk_permutation_commitment


def process_block(state: BeaconState, block: BeaconBlock) -> None:
    # ...
    process_whisk(state, block.body)  # [New in Whisk]
```

#### Deposits

```python
def get_whisk_k(state: BeaconState, validator_index: ValidatorIndex) -> BLSFrScalar:
    """
    Find a unique dummy `k` using try-and-increment.
    """
    counter = 0
    while True:
        k = BLSFrScalar(hash(uint_to_bytes(validator_index) + uint_to_bytes(counter)))  # hash `validator_index || counter`
        if is_k_commitment_unique(state, bls.ScalarMultiplication(k, BLS_G1_GENERATOR)):
            return k
        counter += 1


def get_validator_from_deposit(state: BeaconState, deposit: Deposit) -> Validator:
    amount = deposit.data.amount
    effective_balance = min(amount - amount % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE)
    k = get_whisk_k(state, len(state.validators))  # [New in Whisk]

    return Validator(
        pubkey=deposit.data.pubkey,
        withdrawal_credentials=deposit.data.withdrawal_credentials,
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
        effective_balance=effective_balance,
        whisk_tracker=WhiskTracker(BLS_G1_GENERATOR, bls.ScalarMultiplication(k, BLS_G1_GENERATOR)),  # [New in Whisk]
        whisk_k_commitment=bls.ScalarMultiplication(k, BLS_G1_GENERATOR),  # [New in Whisk]
        whisk_permutation_commitment=WHISK_TRIVIAL_PERMUTATION_COMMITMENT,  # [New in Whisk]
    )
```

#### `get_beacon_proposer_index()`

```python
def get_beacon_proposer_index(state: BeaconState) -> ValidatorIndex:
    """
    Return the beacon proposer index at the current slot.
    """
    assert state.latest_block_header.slot == state.slot  # sanity check `process_block_header` has been called
    return state.latest_block_header.proposer_index
```
