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
| `WHISK_CANDIDATE_SET_SIZE`         | `uint64(2**14)`  (= 16,384) | size of candidate set                                                 |
| `WHISK_PROPOSER_SET_SIZE`          | `uint64(2**13)`  (= 8,192)  | size of proposer set                                                  |
| `WHISK_SHUFFLE_DURATION`           | `Epoch(2**8)`    (= 256)    | duration of the shuffling phase                                       |
| `WHISK_VALIDATORS_PER_SHUFFLE`     | `uint64(2**7)`   (= 128)    | number of validators shuffled at each step                            |
| `WHISK_SHUFFLE_STEPS_PER_ROUND`    | `uint64(2**7)`   (= 128)    | feistelshuffle steps needed to complete one pass over all rows        |
| `WHISK_PROPOSER_SELECTION_GAP`     | `Epoch(2)`                  | epochs between proposer selection event and start of proposer phase   |

Invariant: The protocol should produce enough proposers to last for an entire shuffling phase: `WHISK_PROPOSER_SET_SIZE = WHISK_SHUFFLE_DURATION * SLOTS_PER_EPOCH`

| Name | Value |
| - | - |
| `DOMAIN_WHISK_CANDIDATE_SELECTION`        | `DomainType('0x07000000')` |
| `DOMAIN_WHISK_SHUFFLE`                    | `DomainType('0x07100000')` |
| `DOMAIN_WHISK_PROPOSER_SELECTION`         | `DomainType('0x07200000')` |

### Cryptography

#### BLS

| Name | SSZ equivalent | Description |
| - | - | - |
| `BLSFrScalar` | `Bytes48`     | BLS12-381 Fr scalar |
| `BLSG1Point`  | `Bytes48`     | point on the G1 group of BLS12-381 |

Implementations MUST perform subgroup checks when deserializing a `BLSG1Point` and before using it in any of the functions below.

```python
def BLSG1PointFromAffine(x: int, y: int) -> BLSG1Point
```

```python
# Scalar multiplication between scalar in F_r and G1 point
def ScalarMult(BLSFrScalar, BLSG1Point) -> BLSG1Point
```

| Name | Value |
| - | - |
| `BLS_G1_GENERATOR_X`  | `0x17f1d3a73197d7942695638c4fa9ac0fc3688c4f9774b905a14e3a3f171bac586c55e83ff97a1aeffb3af00adb22c6bb` |
| `BLS_G1_GENERATOR_Y`  | `0x08b3f481e3aaa0f1a09e30ed741d8ae4fcf5e095d5d00af600db18cb2c04b3edd03cc744a2888ae40caa232946c5e7e1` |
| `BLS_G1_GENERATOR`    | `BLSG1PointFromAffine(BLS_G1_GENERATOR_X, BLS_G1_GENERATOR_Y)`                                       |

#### Whisk

```python
def IsValidShuffleProof(proof: ShuffleProof,
                        pre_state: Sequence[WhiskTracker],
                        post_state: Sequence[WhiskTracker],
                        permutation_commitment: BLSG1Point) -> bool
```

```python
# Return True if `proof` is a valid discrete log equality proof.
# This translates to verifying a proof of knowledge of `k` s.t. [k_r_G = k*r_G ^ k_G = k*G]
def IsValidDLEQProof(proof: ProofOfOpening,
                     k_r_G: BLSG1Point, r_G: BLSG1Point,
                     k_G: BLSG1Point, G: BLSG1Point) -> bool
```


| Name | Value | Description |
| - | - | - |
| `WHISK_TRIVIAL_PERMUTATION_COMMITMENT_X`     | `TODO{Depends on CRS of shuffle proof}` | x coordinate of commitment to trivial permutation                           |
| `WHISK_TRIVIAL_PERMUTATION_COMMITMENT_Y`     | `TODO{Depends on CRS of shuffle proof}` | y coordinate of commitment to trivial permutation                           |
| `WHISK_TRIVIAL_PERMUTATION_COMMITMENT`       | `BLSG1PointFromAffine(WHISK_TRIVIAL_PERMUTATION_COMMITMENT_X, WHISK_TRIVIAL_PERMUTATION_COMMITMENT_Y)` | commitment to trivial permutation  |

### Epoch processing

```python
class WhiskTracker(Container):
    """A tracker is a randomized validator commitment"""
    r_G: BLSG1Point  # r*G
    k_r_G: BLSG1Point  # k*r*G

class Validator(Container):
    # ...
    # The Whisk tracker (r*G, k*r*G) of this validator
    whisk_tracker: WhiskTracker  # [New in Whisk]
    # Commitment com(k)=k*G of this validator
    whisk_commitment_k: BLSG1Point  # [New in Whisk]
    # Permutation commitment
    whisk_permutation_commitment: BLSG1Point  # [New in Whisk]

class BeaconState(Container):
    # ...
    whisk_candidates: Vector[WhiskTracker, WHISK_CANDIDATE_SET_SIZE]  # [New in Whisk]
    whisk_proposers: Vector[WhiskTracker, WHISK_PROPOSER_SET_SIZE]  # [New in Whisk]
    # ...


def whisk_candidate_selection(state: BeaconState, epoch: Epoch) -> None:
    """
    Select candidates from the entire set of validators
    """

    active_validator_indices = get_active_validator_indices(state, epoch)
    for i in range(WHISK_CANDIDATE_SET_SIZE):
        # Use compute_proposer_index() to do effective-balance-weighted sampling
        seed = hash(get_seed(state, epoch, DOMAIN_WHISK_CANDIDATE_SELECTION) + uint_to_bytes(i))
        index = compute_proposer_index(state, active_validator_indices, seed)

        # Register the tracker of this validator
        state.whisk_candidates[i] = state.validators[index].whisk_tracker


def whisk_proposer_selection(state: BeaconState, epoch: Epoch) -> None:
    """
    Select proposers from the candidate set
    """

    # Derive seed using an old epoch so that the proposer set can be predicted in advance
    seed = get_seed(state, epoch - WHISK_PROPOSER_SELECTION_GAP, DOMAIN_WHISK_PROPOSER_SELECTION)

    for i in range(WHISK_PROPOSER_SET_SIZE):
        index = compute_shuffled_index(uint64(i), uint64(len(state.whisk_candidates)), seed)
        state.whisk_proposers[i] = state.whisk_candidates[index]


def process_whisk_epoch(state: BeaconState) -> None:
    # We select candidates and proposers at the beginning of a new Whisk shuffling phase
    next_epoch = Epoch(get_current_epoch(state) + 1)
    if next_epoch % WHISK_SHUFFLE_DURATION == 0:
        whisk_proposer_selection(state, next_epoch)
        whisk_candidate_selection(state, next_epoch)


def process_epoch(state: BeaconState) -> None:
    # ...
    process_whisk_epoch(state)
```


### Block processing

#### Block header

```python
class DLEQProof:
    # Proof of knowledge to the opening of com(k) and to the opening of a Whisk tracker
    # This is a sigma DLEQ that proves knowledge of `k` s.t.:
    #    - k is the dlog of `com(k) = k*G`
    #    - k is also the dlog of `k_r_G = k*(r_G)` [Whisk tracker]
    T_1: BLSG1Point  # Sigma commitment
    T_2: BLSG1Point  # Sigma commitment
    s_1: BLSFrScalar  # Sigma response
    s_2: BLSFrScalar  # Sigma response


class BeaconBlock(Container):
    # ...
    proposer_index: ValidatorIndex
    whisk_opening_proof: DLEQProof  # [New in Whisk]
    # ...


def whisk_verify_proposer(state: BeaconState, block: BeaconBlock) -> None:
    proposer = state.validators[block.proposer_index]
    tracker = state.whisk_proposers[state.slot % WHISK_PROPOSER_SET_SIZE]

    assert whisk.IsValidDLEQProof(block.whisk_opening_proof,
                                  tracker.k_r_G, tracker.r_G,
                                  proposer.whisk_commitment_k, BLS_G1_GENERATOR)


def process_block_header(state: BeaconState, block: BeaconBlock) -> None:
    # ...
    # Verify that proposer index is the correct index
    # -- REMOVE -- assert block.proposer_index == get_beacon_proposer_index(state)
    whisk_verify_proposer(state, block)
    # ...
```

#### Shuffle block processing

```python
class ShuffleProof(Container):
    # TODO Include the scalars and group elements of the proof
    # This will depend on the final shape of the Whisk proofs


class BeaconBlockBody(Container):
    # ...
    whisk_shuffled_trackers: Vector[WhiskTracker, WHISK_VALIDATORS_PER_SHUFFLE]  # [New in Whisk]
    whisk_shuffle_proof: ShuffleProof  # [New in Whisk]

    whisk_registration_proof: DLEQProof  # [New in Whisk]
    whisk_tracker: WhiskTracker  # [New in Whisk]
    whisk_commitment_k: BLSG1Point  # [New in Whisk]
    whisk_permutation_commitment: BLSG1Point  # [New in Whisk]


def feistel_encrypt(index: uint64, r: uin64, k: uint64) -> uint64:
    """
    Apply `r` Feistel rounds on `index` and return the ciphertext.
    """
    def F(x):  # F is the bijective non-linear function: F(x) = x^3 (mod k)
        return (x ** 3) % k

    # Extract 2D (x,y) coordinates from 1D coordinates
    x = index // K
    y = index % K

    # Apply needed number of Feistel rounds using x as the left half, and y as the right half
    for _ in range(r):
        x, y = y, (F(y) + x) % K

    # Convert (x,y) coords back to 1D coords
    return x*K + y


def get_feistelshuffle_indices(s: uint64, r: uint64, k: uint64) -> Sequence[uint64]:
    """
    Return indices that the Feistelshuffle algorithm shuffles in step `s` of round `r` assuming a square matrix of
    order `k`.
    """
    original_indices = [i + k * (s % k) for i in range(k)]  # Indices of row `s % k`
    return [feistel_encrypt(index, r) for index in original_indices]


def get_shuffle_indices(state: BeaconState, epoch: Epoch) -> Sequence[uint64]:
    """
    Return the indices that the Feistelshuffle algorithm will shuffle in this slot
    """
    current_feistelshuffle_round = state.slot // WHISK_SHUFFLE_STEPS_PER_ROUND
    step_in_round = state.slot % WHISK_SHUFFLE_STEPS_PER_ROUND
    return get_feistelshuffle_indices(current_feistelshuffle_round, step_in_round, WHISK_VALIDATORS_PER_SHUFFLE)


def whisk_process_shuffled_trackers(state: BeaconState, permutation_commitment: BLSG1Point,
                                    post_shuffle_trackers: Sequence[WhiskTracker], shuffle_proof: ShuffleProof) -> None:
    epoch = get_current_epoch(state)

    # We NOP if we are cooling down. Cooldown phase starts on the epoch before the proposer selection event
    epoch_in_shuffle_phase = epoch % WHISK_SHUFFLE_DURATION
    if epoch_in_shuffle_phase + WHISK_PROPOSER_SELECTION_GAP + 1 >= WHISK_SHUFFLE_DURATION:
        return

    # Check the shuffle proof
    shuffle_indices = get_shuffle_indices(state, epoch)
    pre_shuffle_trackers = [state.whisk_candidates[i] for i in shuffle_indices]
    assert whisk.IsValidShuffleProof(shuffle_proof, pre_shuffle_trackers, post_shuffle_trackers, permutation_commitment)

    # Shuffle candidate list based on the received permutation
    for i, shuffle_index in enumerate(shuffle_indices):
        state.whisk_candidates[shuffle_index] = post_shuffle_trackers[i]


def is_commitment_unique(state: BeaconState, commitment_k: BLSG1Point) -> bool:
    # Check that no validator has `commitment_k` as their commitment
    for validator in state.validators:
        if validator.whisk_commitment_k == commitment_k:
            return False

    return True


def register_commitments_from_block(state: BeaconState, block: BeaconBlock, proposer: Validator) -> None:
    """
    Register fresh commitments for this validator
    """

    # Ensure uniqueness of k
    assert is_commitment_unique(state, block.body.whisk_commitment)

    # Check that the same k is used both in the tracker and in com(k)
    assert whisk.IsValidDLEQProof(block.body.whisk_registration_proof,
                                  block.body.whisk_tracker.k_r_G, block.body.whisk_tracker.r_G,
                                  block.body.whisk_commitment_k, BLS_G1_GENERATOR)

    # Everything is OK: register the commitments
    proposer.whisk_commitment_k = block.body.whisk_commitment_k
    proposer.whisk_tracker = block.body.whisk_tracker


def process_whisk_block(state: BeaconState, block: BeaconBlock) -> None:
    proposer = state.validators[block.proposer_index]

    whisk_process_shuffled_trackers(state, proposer.whisk_permutation_commitment,
                                    block.body.whisk_shuffled_trackers, block.body.whisk_shuffle_proof)

    # Allow proposer to register fresh Whisk commitments once
    if proposer.whisk_tracker.r_G == WHISK_TRIVIAL_PERMUTATION_COMMITMENT:
        assert block.body.whisk_tracker.r_G != WHISK_TRIVIAL_PERMUTATION_COMMITMENT
        register_commitments_from_block(state, block, proposer)
    else:
        # If proposer has already registered commitments, they should be set to zeroes in this block
        assert block.body.whisk_registration_proof == DLEQProof()
        assert block.body.whisk_tracker == WhiskTracker()
        assert block.body.whisk_commitment_k == BLSG1Point()

    # We always register a fresh permutation commitment
    proposer.whisk_permutation_commitment = block.body.whisk_permutation_commitment


def process_block(state: BeaconState, block: BeaconBlock) -> None:
    # ...
    process_whisk_block(state, block)  # [New in Whisk]
```

#### Deposits (new validator registration)

```python
def get_unique_commitment(state: BeaconState, validator_index: ValidatorIndex) -> BLSFrScalar, BLSG1Point:
    # Use try-and-increment to find a unique-but-predictable `k` for this validator
    counter = 0
    while True:
        # Hash input: validator_index || counter
        hashed_counter = hash(uint_to_bytes(validator_index) + uint_to_bytes(counter))

        k = BLSFrScalar(hashed_counter)
        commitment_k = bls.ScalarMult(k, BLS_G1_GENERATOR)

        # Return this commitment if it's unique
        if is_commitment_unique(state, commitment_k):
            return k, commitment_k

        counter += 1


def whisk_get_initial_commitments(state: BeaconState, index: ValidatorIndex) -> BLSG1Point, WhiskTracker:
    # Create trivial k and com(k)
    k, commitment_k = get_unique_commitment(state, index)

    # Create trivial tracker (G, k*G)
    tracker = WhiskTracker(
        r_G=BLS_G1_GENERATOR,
        k_r_G=bls.ScalarMult(k, BLS_G1_GENERATOR),
    )

    return commitment_k, tracker


def get_validator_from_deposit(state: BeaconState, deposit: Deposit) -> Validator:
    commitment_k, tracker = whisk_get_initial_commitments(state, len(state.validators))  # [New in Whisk]

    return Validator(
        pubkey=deposit.data.pubkey,
        withdrawal_credentials=deposit.data.withdrawal_credentials,
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
        effective_balance=effective_balance,
        whisk_commitment_k=commitment_k,  # [New in Whisk]
        whisk_tracker=tracker,  # [New in Whisk]
        whisk_permutation_commitment=WHISK_TRIVIAL_PERMUTATION_COMMITMENT,  # [New in Whisk]
    )
```

#### `get_beacon_proposer_index()`

```python
def get_beacon_proposer_index(state: BeaconState) -> ValidatorIndex:
    """
    Return the beacon proposer index at the current slot.
    TODO MUST only be called after a block header has been processed for this slot
    """
    assert state.latest_block_header.slot == state.slot

    return state.latest_block_header.proposer_index
```
