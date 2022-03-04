### Constants

| Name | Value | Description |
| - | - | - |
| `WHISK_CANDIDATE_TRACKERS_COUNT` | `uint64(2**14)` (= 16,384) | number of candidate trackers |
| `WHISK_PROPOSER_TRACKERS_COUNT` | `uint64(2**13)` (= 8,192) | number of proposer trackers |
| `WHISK_EPOCHS_PER_SHUFFLING_PHASE` | `Epoch(2**8)` (= 256) | epochs per shuffling phase |
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
| `BLSScalar` | `Bytes48` | BLS12-381 scalar |
| `BLSG1Point` | `Bytes48` | compressed BLS12-381 G1 point |
| `BLSGtPoint` | `Vector[Bytes48, 4]` | compressed BLS12-381 Gt point |

*Note*: A subgroup check MUST be performed when deserializing a `BLSG1Point` for use in any of the functions below.

#### Whisk (TODO)

```python
class WhiskShuffleProof:

class WhiskOpeningProof:

def IsValidWhiskShuffleProof(pre_shuffle_trackers: Sequence[WhiskTracker],
                             post_shuffle_trackers: Sequence[WhiskTracker],
                             shuffle_proof: WhiskShuffleProof) -> bool:
    """
    Verify `post_shuffle_trackers` is a permutation of `pre_shuffle_trackers`.
    """


def IsValidWhiskOpeningProof(pubkey: BLSPubkey, tracker: WhiskTracker, opening_proof: WhiskOpeningProof) -> bool:
    """
    Verify the `privkey` for `pubkey` satisfies `tracker.Gt_point == e(privkey * tracker.G1_point, BLS_G2_SAMPLE)`.
    """
```

### Epoch processing

```python
class WhiskTracker(Container):
    G1_point: BLSG1Point  # r * BLS_G1_GENERATOR
    Gt_point: BLSGtPoint  # r * e(privkey * BLS_G1_GENERATOR, BLS_G2_SAMPLE)

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
        state.whisk_candidate_trackers[i] = WhiskTracker(state[index].pubkey, BLS_GT_GENERATOR)


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
    pubkey = state.validators[block.proposer_index].pubkey
    tracker = state.whisk_proposer_trackers[state.slot % WHISK_PROPOSER_TRACKERS_COUNT]
    assert whisk.IsValidWhiskOpeningProof(pubkey, tracker, block.whisk_opening_proof)


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

def get_feistel_encryption(index: uint64, rounds: uin64, K: uint64) -> uint64:
    def F(x):
        return (x ** 3) % K  # F(x) = x^3 (mod K) is a bijective non-linear function

    x, y = index // K, index % K  # Compute 2D coordinates (x, y) from 1D coordinates
    for _ in range(rounds):  # Apply Feistel rounds
        x, y = y, (F(y) + x) % K
    return x * K + y  # Convert 2D coordinates (x, y) back to 1D coordinates


def get_shuffle_indices(state: BeaconState, epoch: Epoch) -> Sequence[uint64]:
    """
    Return the indices that the Feistel permutation shuffles in this slot.
    """
    shuffle_round = state.slot // WHISK_SHUFFLE_STEPS_PER_ROUND
    shuffle_step = state.slot % WHISK_SHUFFLE_STEPS_PER_ROUND
    row_indices = [i + WHISK_VALIDATORS_PER_SHUFFLE * shuffle_step for i in range(WHISK_VALIDATORS_PER_SHUFFLE)]
    return [get_feistel_encryption(index, shuffle_round, WHISK_VALIDATORS_PER_SHUFFLE) for index in row_indices]


def process_whisk(state: BeaconState, body: BeaconBlockBody) -> None:
    # Check the shuffle proof
    shuffle_indices = get_shuffle_indices(state, get_current_epoch(state))
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


def process_block(state: BeaconState, block: BeaconBlock) -> None:
    # ...
    process_whisk(state, block.body)  # [New in Whisk]
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
