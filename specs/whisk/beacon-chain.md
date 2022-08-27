### Constants

| Name | Value | Description |
| - | - | - |
| `WHISK_CANDIDATE_TRACKERS_COUNT` | `uint64(2**14)` (= 16,384) | number of candidate trackers |
| `WHISK_PROPOSER_TRACKERS_COUNT` | `uint64(2**13)` (= 8,192) | number of proposer trackers |
| `WHISK_EPOCHS_PER_SHUFFLING_PHASE` | `Epoch(2**8)` (= 256) | epochs per shuffling phase |
| `WHISK_VALIDATORS_PER_SHUFFLE` | `uint64(2**7)` (= 128) | number of validators shuffled per shuffle step |
| `WHISK_SHUFFLE_STEPS_PER_ROUND` | `uint64(2**7)` (= 128) | Number of stirs to complete a pass over all rows |
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
| `BLSScalar` | `Bytes48` | BLS12-381 scalar |
| `BLSG1Point` | `Bytes48` | compressed BLS12-381 G1 point |

*Note*: A subgroup check MUST be performed when deserializing a `BLSG1Point` for use in any of the functions below.

```python
def BLSG1PointFromAffine(x: int, y: int) -> BLSG1Point


def BLSG1ScalarMultiply(scalar: BLSScalar, point: BLSG1Point) -> BLSG1Point
```

| Name | Value |
| - | - |
| `BLS_G1_GENERATOR_X` | `0x17f1d3a73197d7942695638c4fa9ac0fc3688c4f9774b905a14e3a3f171bac586c55e83ff97a1aeffb3af00adb22c6bb` |
| `BLS_G1_GENERATOR_Y` | `0x08b3f481e3aaa0f1a09e30ed741d8ae4fcf5e095d5d00af600db18cb2c04b3edd03cc744a2888ae40caa232946c5e7e1` |
| `BLS_G1_GENERATOR`   | `BLSG1PointFromAffine(BLS_G1_GENERATOR_X, BLS_G1_GENERATOR_Y)`                                       |

#### Whisk

```python
class WhiskShuffleProof:

class WhiskOpeningProof:

def IsValidWhiskShuffleProof(pre_shuffle_trackers: Sequence[WhiskTracker],
                             post_shuffle_trackers: Sequence[WhiskTracker],
                             shuffle_proof: WhiskShuffleProof) -> bool:
    """
    Verify `post_shuffle_trackers` is a permutation of `pre_shuffle_trackers`.
    """


def IsValidWhiskOpeningProof(tracker: WhiskTracker, k_commitment: BLSG1Point, tracker_proof: WhiskTrackerProof) -> bool:
    """
    Verify knowledge of `k` such that `tracker.k_r_G == k * tracker.r_G` and `k_commitment == k * BLS_G1_GENERATOR`.
    """
```

### Epoch processing

```python
class WhiskTracker(Container):
    r_G: BLSG1Point  # r * G
    k_r_G: BLSG1Point  # k * r * G

class Validator(Container):
    # ...
    # Whisk
    whisk_tracker: WhiskTracker  # Whisk tracker (r * G, k * r * G) [New in Whisk]
    whisk_k_commitment: BLSG1Point  # Whisk k commitment k * BLS_G1_GENERATOR [New in Whisk]

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

    # Select candidate trackers from active validator trackers
    active_validator_indices = get_active_validator_indices(state, epoch)
    for i in range(WHISK_CANDIDATE_TRACKERS_COUNT):
        seed = hash(get_seed(state, epoch, DOMAIN_WHISK_CANDIDATE_SELECTION) + uint_to_bytes(i))
        candidate_index = compute_proposer_index(state, active_validator_indices, seed)  # sample by effective balance
        state.whisk_candidate_trackers[i] = state.validators[candidate_index].whisk_tracker


def process_whisk_updates(state: BeaconState) -> None:
    next_epoch = Epoch(get_current_epoch(state) + 1)
    if next_epoch % WHISK_EPOCHS_PER_SHUFFLING_PHASE == 0:  # select trackers at the start of shuffling phases
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
    whisk_opening_proof: WhiskOpeningProof  # [New in Whisk]
    # ...

def process_whisk_opening_proof(state: BeaconState, block: BeaconBlock) -> None:
    tracker = state.whisk_proposer_trackers[state.slot % WHISK_PROPOSER_TRACKERS_COUNT]
    k_commitment = state.validators[block.proposer_index].whisk_k_commitment
    assert whisk.IsValidWhiskOpeningProof(tracker, k_commitment, block.whisk_opening_proof)


def process_block_header(state: BeaconState, block: BeaconBlock) -> None:
    # ...
    # [Removed in Whisk] Verify that proposer index is the correct index
    # [Removed in Whisk] assert block.proposer_index == get_beacon_proposer_index(state)
    process_whisk_opening_proof(state, block)   # [New in Whisk] 
    # ...
```

#### Whisk

```python
class BeaconBlockBody(Container):
    # ...
    # Whisk
    whisk_post_shuffle_trackers: Vector[WhiskTracker, WHISK_VALIDATORS_PER_SHUFFLE]  # [New in Whisk]
    whisk_shuffle_proof: WhiskShuffleProof  # [New in Whisk]
    whisk_registration_proof: WhiskTrackerProof  # [New in Whisk]
    whisk_tracker: WhiskTracker  # [New in Whisk]
    whisk_k_commitment: BLSG1Point  # [New in Whisk]


def get_squareshuffle_indices(s: uint64, r: uint64, k: uint64) -> Sequence[uint64]:
    """
    Get indices of row `s` in round `r` assuming a square matrix of order `k`.
    """
    if r % 2 == 0: # rows get shuffled on even rounds
        return [i + k * (s % k) for i in range(k)] # indices of row `s % k`
    else: # columns get shuffled on odd rounds
        return [s + k * (i % k) for i in range(k)] # indices of column `s % k`


def get_shuffle_indices(state: BeaconState, randao_reveal: BLSSignature, epoch: Epoch) -> Sequence[uint64]:
    """
    Return the indices that the Feistel permutation shuffles in this slot.
    """
    shuffle_round = state.slot // WHISK_SHUFFLE_STEPS_PER_ROUND
    shuffled_row = uint256(hash(randao_reveal)) % WHISK_SHUFFLE_STEPS_PER_ROUND
    return get_squareshuffle_indices(shuffled_row, shuffle_round, WHISK_VALIDATORS_PER_SHUFFLE)


def whisk_process_shuffled_trackers(state: BeaconState, body: BeaconBlockBody) -> None:
    # Check the shuffle proof
    shuffle_indices = get_shuffle_indices(state, body.randao_reveal, get_current_epoch(state))
    pre_shuffle_trackers = [state.whisk_candidate_trackers[i] for i in shuffle_indices]
    post_shuffle_trackers = body.whisk_post_shuffle_trackers
    assert whisk.IsValidWhiskShuffleProof(pre_shuffle_trackers, post_shuffle_trackers, body.whisk_shuffle_proof)

    # Require unchanged trackers during cooldown
    shuffle_epoch = get_current_epoch(state) % WHISK_EPOCHS_PER_SHUFFLING_PHASE
    if shuffle_epoch + WHISK_PROPOSER_SELECTION_GAP + 1 >= WHISK_EPOCHS_PER_SHUFFLING_PHASE:
        assert pre_shuffle_trackers == post_shuffle_trackers

    # Shuffle candidate trackers
    for i, shuffle_index in enumerate(shuffle_indices):
        state.whisk_candidate_trackers[shuffle_index] = post_shuffle_trackers[i]


def is_k_commitment_unique(state: BeaconState, k_commitment: BLSG1Point) -> bool:
    return all([validator.whisk_k_commitment != k_commitment for validator in state.validators])


def process_whisk(state: BeaconState, body: BeaconBlockBody) -> None:
    whisk_process_shuffled_trackers(state, body)

    # Overwrite all validator Whisk fields (first Whisk proposal) or just the permutation commitment (next proposals)
    proposer = state.validators[get_beacon_proposer_index(state)]
    if proposer.whisk_tracker.r_G == BLS_G1_GENERATOR:  # first Whisk proposal
        assert body.whisk_tracker.r_G != BLS_G1_GENERATOR
        assert is_k_commitment_unique(state, body.whisk_k_commitment)
        assert whisk.IsValidWhiskOpeningProof(body.whisk_tracker, body.whisk_k_commitment, body.whisk_registration_proof)
        proposer.whisk_tracker = body.whisk_tracker
        proposer.whisk_k_commitment = body.whisk_k_commitment
    else:  # next Whisk proposals
        assert body.whisk_registration_proof == WhiskTrackerProof()
        assert body.whisk_tracker == WhiskTracker()
        assert body.whisk_k_commitment == BLSG1Point()


def process_block(state: BeaconState, block: BeaconBlock) -> None:
    # ...
    process_whisk(state, block.body)  # [New in Whisk]
```

#### Deposits

```python
def get_unique_whisk_k(state: BeaconState, validator_index: ValidatorIndex) -> BLSScalar:
    counter = 0
    while True:
        k = BLSScalar(hash(uint_to_bytes(validator_index) + uint_to_bytes(counter)))  # hash `validator_index || counter`
        if is_k_commitment_unique(state, bls.BLSG1ScalarMultiply(k, BLS_G1_GENERATOR)):
            return k  # unique by trial and error
        counter += 1


def get_validator_from_deposit(state: BeaconState, deposit: Deposit) -> Validator:
    validator = bellatrix.get_validator_from_deposit(state, deposit)
    k = get_unique_whisk_k(state, len(state.validators))
    validator.whisk_tracker = WhiskTracker(BLS_G1_GENERATOR, bls.BLSG1ScalarMultiply(k, BLS_G1_GENERATOR))
    validator.whisk_k_commitment = bls.BLSG1ScalarMultiply(k, BLS_G1_GENERATOR)
    return validator
```

#### `get_beacon_proposer_index`

```python
def get_beacon_proposer_index(state: BeaconState) -> ValidatorIndex:
    """
    Return the beacon proposer index at the current slot.
    """
    assert state.latest_block_header.slot == state.slot  # sanity check `process_block_header` has been called
    return state.latest_block_header.proposer_index
```
