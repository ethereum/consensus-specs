# Ethereum 2.0 spec—Casper and sharding

###### tags: `spec`, `eth2.0`, `casper`, `sharding`

**NOTICE**: This document is a work-in-progress for researchers and implementers. It reflects recent spec changes and takes precedence over the [Python proof-of-concept implementation](https://github.com/ethereum/beacon_chain).

### Introduction

At the center of Ethereum 2.0 is a system chain called the "beacon chain". The beacon chain stores and manages the set of active proof-of-stake validators. In the initial deployment phases of Ethereum 2.0 the only mechanism to become a validator is to make a fixed-size one-way ETH deposit to a registration contract on the Ethereum 1.0 PoW chain. Induction as a validator happens after registration transaction receipts are processed by the beacon chain and after a queuing process. Deregistration is either voluntary or done forcibly as a penalty for misbehavior.

The primary source of load on the beacon chain are "attestations". Attestations simultaneously attest to a shard block and a corresponding beacon chain block. A sufficient number of attestations for the same shard block create a "crosslink", confirming the shard segment up to that shard block into the beacon chain. Crosslinks also serve as infrastructure for asynchronous cross-shard communication.

### Terminology

* **Validator** - a participant in the Casper/sharding consensus system. You can become one by depositing 32 ETH into the Casper mechanism.
* **Active validator set** - those validators who are currently participating, and which the Casper mechanism looks to produce and attest to blocks, crosslinks and other consensus objects.
* **Committee** - a (pseudo-) randomly sampled subset of the active validator set. When a committee is referred to collectively, as in "this committee attests to X", this is assumed to mean "some subset of that committee that contains enough validators that the protocol recognizes it as representing the committee".
* **Proposer** - the validator that creates a beacon chain block
* **Attester** - a validator that is part of a committee that needs to sign off on a beacon chain block while simultaneously creating a link (crosslink) to a recent shard block on a particular shard chain.
* **Beacon chain** - the central PoS chain that is the base of the sharding system.
* **Shard chain** - one of the chains on which user transactions take place and account data is stored.
* **Crosslink** - a set of signatures from a committee attesting to a block in a shard chain, which can be included into the beacon chain. Crosslinks are the main means by which the beacon chain "learns about" the updated state of shard chains.
* **Slot** - a period of `SLOT_DURATION` seconds, during which one proposer has the ability to create a beacon chain block and some attesters have the ability to make attestations
* **Cycle** - a span of slots during which all validators get exactly one chance to make an attestation
* **Finalized**, **justified** - see Casper FFG finalization here: https://arxiv.org/abs/1710.09437
* **Withdrawal period** - number of slots between a validator exit and the validator balance being withdrawable
* **Genesis time** - the Unix time of the genesis beacon chain block at slot 0

### Constants

| Constant | Value | Unit | Approximation |
| --- | --- | :---: | - |
| `SHARD_COUNT` | 2**10 (= 1,024)| shards |
| `DEPOSIT_SIZE` | 2**5 (= 32) | ETH |
| `MIN_ONLINE_DEPOSIT_SIZE` | 2**4 (= 16) | ETH |
| `GWEI_PER_ETH` | 10**9 | Gwei/ETH |
| `MIN_COMMITTEE_SIZE` | 2**7 (= 128) | validators |
| `GENESIS_TIME` | **TBD** | seconds |
| `SLOT_DURATION` | 2**4 (= 16) | seconds |
| `CYCLE_LENGTH` | 2**6 (= 64) | slots | ~17 minutes |
| `MIN_VALIDATOR_SET_CHANGE_INTERVAL` | 2**8 (= 256) | slots | ~1.1 hours |
| `RANDAO_SLOTS_PER_LAYER` | 2**12 (= 4096) | slots | ~18 hours |
| `SQRT_E_DROP_TIME` | 2**16 (= 65,536) | slots | ~12 days |
| `WITHDRAWAL_PERIOD` | 2**19 (= 524,288) | slots | ~97 days |
| `BASE_REWARD_QUOTIENT` | 2**15 (= 32,768) | — |
| `MAX_VALIDATOR_CHURN_QUOTIENT` | 2**5 (= 32) | — |
| `LOGOUT_MESSAGE` | `"LOGOUT"` | — |
| `INITIAL_FORK_VERSION` | 0 | — |

**Notes**

* See a recommended `MIN_COMMITTEE_SIZE`  of 111 here https://vitalik.ca/files/Ithaca201807_Sharding.pdf).
* The `SQRT_E_DROP_TIME` constant is the amount of time it takes for the quadratic leak to cut deposits of non-participating validators by ~39.4%. 
* The `BASE_REWARD_QUOTIENT` constant is the per-slot interest rate assuming all validators are participating, assuming total deposits of 1 ETH. It corresponds to ~3.88% annual interest assuming 10 million participating ETH.
* At most `1/MAX_VALIDATOR_CHURN_QUOTIENT` of the validators can change during each validator set change.

**Validator status codes**

| Name | Value |
| - | :-: |
| `PENDING_ACTIVATION` | `0` |
| `ACTIVE` | `1` |
| `PENDING_EXIT` | `2` |
| `PENDING_WITHDRAW` | `3` |
| `WITHDRAWN` | `4` |
| `PENALIZED` | `127` |

**Special record types**

| Name | Value |
| - | :-: |
| `LOGOUT` | `0` |
| `CASPER_SLASHING` | `1` |
| `RANDAO_CHANGE` | `2` |

**Validator set delta flags**

| Name | Value |
| - | :-: |
| `ENTRY` | `0` |
| `EXIT` | `1` |

### PoW chain registration contract

The initial deployment phases of Ethereum 2.0 are implemented without consensus changes to the PoW chain. A registration contract is added to the PoW chain to deposit ETH. This contract has a `registration` function which takes as arguments `pubkey`, `withdrawal_shard`, `withdrawal_address`, `randao_commitment` as defined in a `ValidatorRecord` below. A BLS `proof_of_possession` of types `bytes` is given as a final argument.

The registration contract emits a log with the various arguments for consumption by the beacon chain. It does not do validation, pushing the registration logic to the beacon chain. In particular, the proof of possession (based on the BLS12-381 curve) is not verified by the registration contract.

## Data structures
### Beacon chain blocks

A `BeaconBlock` has the following fields:

```python
{
    # Slot number
    'slot': 'uint64',
    # Proposer RANDAO reveal
    'randao_reveal': 'hash32',
    # Recent PoW chain reference (block hash)
    'pow_chain_reference': 'hash32',
    # Skip list of previous beacon block hashes
    # i'th item is the most recent ancestor who's slot is a multiple of 2**i for i = 0, ..., 31
    'ancestor_hashes': ['hash32'],
    # Active state root
    'active_state_root': 'hash32',
    # Crystallized state root
    'crystallized_state_root': 'hash32',
    # Attestations
    'attestations': [AttestationRecord],
    # Specials (e.g. logouts, penalties)
    'specials': [SpecialRecord]
}
```

An `AttestationRecord` has the following fields:

```python
{
    # Slot number
    'slot': 'uint64',
    # Shard number
    'shard': 'uint16',
    # Beacon block hashes not part of the current chain, oldest to newest
    'oblique_parent_hashes': ['hash32'],
    # Shard block hash being attested to
    'shard_block_hash': 'hash32',
    # Attester participation bitfield (1 bit per attester)
    'attester_bitfield': 'bytes',
    # Slot of last justified beacon block
    'justified_slot': 'uint64',
    # Hash of last justified beacon block
    'justified_block_hash': 'hash32',
    # BLS aggregate signature
    'aggregate_sig': ['uint256']
}
```

An `AttestationSignedData` has the following fields:

```python
{
    # Fork version
    'fork_version': 'uint64',
    # Slot number
    'slot': 'uint64',
    # Shard number
    'shard': 'uint16',
    # 31 parent hashes
    'parent_hashes': ['hash32'],
    # Shard block hash
    'shard_block_hash': 'hash32',
    # Slot of last justified beacon block referenced in the attestation
    'justified_slot': 'uint64'
}
```

A `SpecialRecord` has the following fields:

```python
{
    # Kind
    'kind': 'uint8',
    # Data
    'data': ['bytes']
}
```

### Beacon chain state

For convenience we define the beacon chain state in two parts: "active state" and "crystallized state".

The `ActiveState` has the following fields:

```python
{
    # Attestations not yet processed
    'pending_attestations': [AttestationRecord],
    # Specials not yet been processed
    'pending_specials': [SpecialRecord]
    # recent beacon block hashes needed to process attestations, older to newer
    'recent_block_hashes': ['hash32'],
    # RANDAO state
    'randao_mix': 'hash32'
}
```

The `CrystallizedState` has the following fields:

```python
{
    # Slot of last validator set change
    'validator_set_change_slot': 'uint64',
    # List of validators
    'validators': [ValidatorRecord],
    # Most recent crosslink for each shard
    'crosslinks': [CrosslinkRecord],
    # Last crystallized state recalculation
    'last_state_recalculation_slot': 'uint64',
    # Last finalized slot
    'last_finalized_slot': 'uint64',
    # Last justified slot
    'last_justified_slot': 'uint64',
    # Number of consecutive justified slots
    'justified_streak': 'uint64',
    # Committee members and their assigned shard, per slot
    'shard_and_committee_for_slots': [[ShardAndCommittee]],
    # Total deposits penalized in the given withdrawal period
    'deposits_penalized_in_period': ['uint32'],
    # Hash chain of validator set changes (for light clients to easily track deltas)
    'validator_set_delta_hash_chain': 'hash32'
    # Parameters relevant to hard forks / versioning.
    # Should be updated only by hard forks.
    'pre_fork_version': 'uint32',
    'post_fork_version': 'uint32',
    'fork_slot_number': 'uint64',
}
```

A `ValidatorRecord` has the following fields:

```python
{
    # BLS public key
    'pubkey': 'uint256',
    # Withdrawal shard number
    'withdrawal_shard': 'uint16',
    # Withdrawal address
    'withdrawal_address': 'address',
    # RANDAO commitment
    'randao_commitment': 'hash32',
    # Slot the RANDAO commitment was last changed
    'randao_last_change': 'uint64',
    # Balance
    'balance': 'uint64',
    # Status code
    'status': 'uint8',
    # Slot when validator exited (or 0)
    'exit_slot': 'uint64'
}
```

A `CrosslinkRecord` has the following fields:

```python
{
    # Since last validator set change?
    'recently_changed': 'bool',
    # Slot number
    'slot': 'uint64',
    # Shard chain block hash
    'shard_block_hash': 'hash32'
}
```

A `ShardAndCommittee` object has the following fields:

```python
{
    # Shard number
    'shard': 'uint16',
    # Validator indices
    'committee': ['uint24']
}
```

## Beacon chain processing

The beacon chain is the "main chain" of the PoS system. The beacon chain's main responsibilities are:

* Store and maintain the set of active, queued and exited validators
* Process crosslinks (see above)
* Process its own block-by-block consensus, as well as the finality gadget

Processing the beacon chain is fundamentally similar to processing a PoW chain in many respects. Clients download and process blocks, and maintain a view of what is the current "canonical chain", terminating at the current "head". However, because of the beacon chain's relationship with the existing PoW chain, and because it is a PoS chain, there are differences.

For a block on the beacon chain to be processed by a node, four conditions have to be met:

* The parent pointed to by the `ancestor_hashes[0]` has already been processed and accepted
* An attestation from the _proposer_ of the block (see later for definition) is included along with the block in the network message object
* The PoW chain block pointed to by the `pow_chain_reference` has already been processed and accepted
* The node's local clock time is greater than or equal to the minimum timestamp as computed by `GENESIS_TIME + block.slot * SLOT_DURATION`

If these conditions are not met, the client should delay processing the beacon block until the conditions are all satisfied.

Beacon block production is significantly different because of the proof of stake mechanism. A client simply checks what it thinks is the canonical chain when it should create a block, and looks up what its slot number is; when the slot arrives, it either proposes or attests to a block as required. Note that this requires each node to have a clock that is roughly (ie. within `SLOT_DURATION` seconds) synchronized with the other nodes.

### Beacon chain fork choice rule

The beacon chain uses the Casper FFG fork choice rule of "favor the chain containing the highest-slot-number justified block". To choose between chains that are all descended from the same justified block, the chain uses "immediate message driven GHOST" (IMD GHOST) to choose the head of the chain.

For a description see: **https://ethresear.ch/t/beacon-chain-casper-ffg-rpj-mini-spec/2760**

For an implementation with a network simulator see: **https://github.com/ethereum/research/blob/master/clock_disparity/ghost_node.py**

Here's an example of its working (green is finalized blocks, yellow is justified, grey is attestations):

![](https://vitalik.ca/files/RPJ.png)

## Beacon chain state transition function

We now define the state transition function. At the high level, the state transition is made up of two parts:

1. The per-block processing, which happens every block, and affects the `ActiveState` only
2. The crystallized state recalculation, which happens only if `block.slot >= last_state_recalculation_slot + CYCLE_LENGTH`, and affects the `CrystallizedState` and `ActiveState`

The crystallized state recalculation generally focuses on changes to the validator set, including adjusting balances and adding and removing validators, as well as processing crosslinks and managing block justification/finalization, and the per-block processing generally focuses on verifying aggregate signatures and saving temporary records relating to the in-block activity in the `ActiveState`.

### Helper functions

We start off by defining some helper algorithms. First, the function that selects the active validators:

```python
def get_active_validator_indices(validators):
    return [i for i, v in enumerate(validators) if v.status == ACTIVE]
```

Now, a function that shuffles this list:

```python
def shuffle(values: List[Any],
            seed: Hash32) -> List[Any]:
    """
    Returns the shuffled ``values`` with seed as entropy.
    """
    values_count = len(values)

    # Entropy is consumed from the seed in 3-byte (24 bit) chunks.
    rand_bytes = 3
    # The highest possible result of the RNG.
    rand_max = 2 ** (rand_bytes * 8) - 1

    # The range of the RNG places an upper-bound on the size of the list that
    # may be shuffled. It is a logic error to supply an oversized list.
    assert values_count < rand_max

    output = [x for x in values]
    source = seed
    index = 0
    while index < values_count - 1:
        # Re-hash the `source` to obtain a new pattern of bytes.
        source = hash(source)
        # Iterate through the `source` bytes in 3-byte chunks.
        for position in range(0, 32 - (32 % rand_bytes), rand_bytes):
            # Determine the number of indices remaining in `values` and exit
            # once the last index is reached.
            remaining = values_count - index
            if remaining == 1:
                break

            # Read 3-bytes of `source` as a 24-bit big-endian integer.
            sample_from_source = int.from_bytes(
                source[position:position + rand_bytes], 'big'
            )

            # Sample values greater than or equal to `sample_max` will cause
            # modulo bias when mapped into the `remaining` range.
            sample_max = rand_max - rand_max % remaining

            # Perform a swap if the consumed entropy will not cause modulo bias.
            if sample_from_source < sample_max:
                # Select a replacement index for the current index.
                replacement_position = (sample_from_source % remaining) + index
                # Swap the current index with the replacement index.
                output[index], output[replacement_position] = output[replacement_position], output[index]
                index += 1
            else:
                # The sample causes modulo bias. A new sample should be read.
                pass

    return output
```

Here's a function that splits a list into `split_count` pieces:

```python
def split(seq: List[Any], split_count: int) -> List[Any]:
    """
    Returns the split ``seq`` in ``split_count`` pieces in protocol.
    """
    list_length = len(seq)
    return [
        seq[(list_length * i // split_count): (list_length * (i + 1) // split_count)]
        for i in range(split_count)
    ]
```

A helper method for readability:

```python
def clamp(minval: int, maxval: int, x: int) -> int:
    if x <= minval:
        return minval
    elif x >= maxval:
        return maxval
    else:
        return x
```

Now, our combined helper method:

```python
def get_new_shuffling(seed: Hash32,
                      validators: List[ValidatorRecord],
                      crosslinking_start_shard: int) -> List[List[ShardAndCommittee]]:
    active_validators = get_active_validator_indices(validators)
    active_validators_size = len(active_validators)

    committees_per_slot = clamp(
        1,
        SHARD_COUNT // CYCLE_LENGTH,
        len(active_validators) // CYCLE_LENGTH // (MIN_COMMITTEE_SIZE * 2) + 1,
    )

    output = []

    # Shuffle with seed
    shuffled_active_validator_indices = shuffle(active_validators, seed)

    # Split the shuffled list into cycle_length pieces
    validators_per_slot = split(shuffled_active_validator_indices, CYCLE_LENGTH)

    for slot, slot_indices in enumerate(validators_per_slot):
        # Split the shuffled list into committees_per_slot pieces
        shard_indices = split(slot_indices, committees_per_slot)

        shard_id_start = crosslinking_start_shard + slot * committees_per_slot

        shards_and_committees_for_slot = [
            ShardAndCommittee(
                shard=(shard_id_start + shard_position) % SHARD_COUNT,
                committee=indices
            )
            for shard_position, indices in enumerate(shard_indices)
        ]
        output.append(shards_and_committees_for_slot)

    return output
```

Here's a diagram of what's going on:

![](http://vitalik.ca/files/ShuffleAndAssign.png?1)

We also define two functions for retrieving data from the state:

```python
def get_shards_and_committees_for_slot(crystallized_state: CrystallizedState,
                                       slot: int) -> List[ShardAndCommittee]:
    earliest_slot_in_array = crystallized_state.last_state_recalculation - CYCLE_LENGTH
    assert earliest_slot_in_array <= slot < earliest_slot_in_array + CYCLE_LENGTH * 2
    return crystallized_state.shard_and_committee_for_slots[slot - earliest_slot_in_array]

def get_block_hash(active_state: ActiveState,
                   current_block: BeaconBlock,
                   slot: int) -> Hash32:
    earliest_slot_in_array = current_block.slot - len(active_state.recent_block_hashes)
    assert earliest_slot_in_array <= slot < current_block.slot
    return active_state.recent_block_hashes[slot - earliest_slot_in_array]
```

`get_block_hash(_, _, s)` should always return the block in the beacon chain at slot `s`, and `get_shards_and_committees_for_slot(_, s)` should not change unless the validator set changes.

We define a function to "add a link" to the validator hash chain, used when a validator is added or removed:

```python
def add_validator_set_change_record(crystallized_state: CrystallizedState,
                                    index: int,
                                    pubkey: int,
                                    flag: int) -> None:
    crystallized_state.validator_set_delta_hash_chain = \
        hash(crystallized_state.validator_set_delta_hash_chain +
             bytes1(flag) + bytes3(index) + bytes32(pubkey))
```

Finally, we abstractly define `int_sqrt(n)` for use in reward/penalty calculations as the largest integer `k` such that `k**2 <= n`. Here is one possible implementation, though clients are free to use their own including standard libraries for [integer square root](https://en.wikipedia.org/wiki/Integer_square_root) if available and meet the specification.

```python
def int_sqrt(n: int) -> int:
    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x
```


### On startup

Run the following code:

```python
def on_startup(initial_validator_entries: List[Any]) -> Tuple[CrystallizedState, ActiveState]:
    # Induct validators
    validators = []
    for pubkey, proof_of_possession, withdrawal_shard, withdrawal_address, \
            randao_commitment in initial_validator_entries:
        add_validator(
            validators=validators,
            pubkey=pubkey,
            proof_of_possession=proof_of_possession,
            withdrawal_shard=withdrawal_shard,
            withdrawal_address=withdrawal_address,
            randao_commitment=randao_commitment,
            current_slot=0
        )
    # Setup crystallized state
    x = get_new_shuffling(bytes([0] * 32), validators, 0)
    crosslinks = [
        CrosslinkRecord(
            recently_changed=False,
            slot=0,
            hash=bytes([0] * 32)
        )
        for i in range(SHARD_COUNT)
    ]
    crystallized_state = CrystallizedState(
        validator_set_change_slot=0,
        validators=validators,
        crosslinks=crosslinks,
        last_state_recalculation_slot=0,
        last_finalized_slot=0,
        last_justified_slot=0,
        justified_streak=0,
        shard_and_committee_for_slots=x + x,
        deposits_penalized_in_period=[],
        validator_set_delta_hash_chain=bytes([0] * 32),  # stub
        pre_fork_version=INITIAL_FORK_VERSION,
        post_fork_version=INITIAL_FORK_VERSION,
        fork_slot_number=0
    )

    # Setup active state
    recent_block_hashes = [
        bytes([0] * 32)
        for _ in range(CYCLE_LENGTH * 2)
    ]
    active_state = ActiveState(
        pending_attestations=[],
        pending_specials=[],
        recent_block_hashes=recent_block_hashes,
        randao_mix=bytes([0] * 32)  # stub
    )

    return crystallized_state, active_state
```

The `CrystallizedState()` and `ActiveState()` constructors should initialize all values to zero bytes, an empty value or an empty array depending on context. The `add_validator` routine is defined below.

### Routine for adding a validator

This routine should be run for every validator that is inducted as part of a log created on the PoW chain [TODO: explain where to check for these logs]. These logs should be processed in the order in which they are emitted by the PoW chain.

First, a helper function:

```python
def min_empty_validator(validators: List[ValidatorRecord]):
    for i, v in enumerate(validators):
        if v.status == WITHDRAWN:
            return i
    return None
```

Now, to add a validator:

```python
def add_validator(validators: List[ValidatorRecord],
                  pubkey: int,
                  proof_of_possession: bytes,
                  withdrawal_shard: int,
                  withdrawal_address: Address,
                  randao_commitment: Hash32,
                  current_slot: int) -> int:
    # if following assert fails, validator induction failed
    # move on to next validator registration log
    assert BLSVerify(pub=pubkey,
                     msg=hash(pubkey),
                     sig=proof_of_possession)
    rec = ValidatorRecord(
        pubkey=pubkey,
        withdrawal_shard=withdrawal_shard,
        withdrawal_address=withdrawal_address,
        randao_commitment=randao_commitment,
        randao_last_change=current_slot,
        balance=DEPOSIT_SIZE * GWEI_PER_ETH, # in Gwei
        status=PENDING_ACTIVATION,
        exit_slot=0
    )
    index = min_empty_validator(validators)
    if index is None:
        validators.append(rec)
        return len(validators) - 1
    else:
        validators[index] = rec
        return index
```

## Routine for removing a validator

```python
def exit_validator(index, crystallized_state, penalize, current_slot):
    validator = crystallized_state.validators[index]
    validator.exit_slot = current_slot
    if penalize:
        validator.status = PENALIZED
        crystallized_state.deposits_penalized_in_period[current_slot // WITHDRAWAL_PERIOD] += validator.balance
    else:
        validator.status = PENDING_EXIT
    add_validator_set_change_record(crystallized_state, index, validator.pubkey, EXIT)
```

### Per-block processing

This procedure should be carried out every beacon block.

* Let `parent_hash` be the hash of the immediate previous beacon block (ie. equal to `ancestor_hashes[0]`).
* Let `parent` be the beacon block with the hash `parent_hash`

First, set `recent_block_hashes` to the output of the following:

```python
def append_to_recent_block_hashes(old_block_hashes: List[Hash32],
                                  parent_slot: int,
                                  current_slot: int,
                                  parent_hash: Hash32) -> List[Hash32]:
    d = current_slot - parent_slot
    return old_block_hashes + [parent_hash] * d
```

The output of `get_block_hash` should not change, except that it will no longer throw for `current_slot - 1`. Also, check that the block's `ancestor_hashes` array was correctly updated, using the following algorithm:

```python
def update_ancestor_hashes(parent_ancestor_hashes: List[Hash32],
                           parent_slot_number: int,
                           parent_hash: Hash32) -> List[Hash32]:
    new_ancestor_hashes = copy.copy(parent_ancestor_hashes)
    for i in range(32):
        if parent_slot_number % 2**i == 0:
            new_ancestor_hashes[i] = parent_hash
    return new_ancestor_hashes
```

A beacon block can have 0 or more `AttestationRecord` objects

For each one of these attestations:

* Verify that `slot <= parent.slot` and `slot >= max(parent.slot - CYCLE_LENGTH + 1, 0)`.
* Verify that `justified_slot` is equal to or earlier than `last_justified_slot`.
* Verify that `justified_block_hash` is the hash of the block in the current chain at the slot -- `justified_slot`.
* Compute `parent_hashes` = `[get_block_hash(active_state, block, slot - CYCLE_LENGTH + i) for i in range(1, CYCLE_LENGTH - len(oblique_parent_hashes) + 1)] + oblique_parent_hashes` (eg, if `CYCLE_LENGTH = 4`, `slot = 5`, the actual block hashes starting from slot 0 are `Z A B C D E F G H I J`, and `oblique_parent_hashes = [D', E']` then `parent_hashes = [B, C, D' E']`). Note that when *creating* an attestation for a block, the hash of that block itself won't yet be in the `active_state`, so you would need to add it explicitly.
* Let `attestation_indices` be `get_shards_and_committees_for_slot(crystallized_state, slot)[x]`, choosing `x` so that `attestation_indices.shard` equals the `shard` value provided to find the set of validators that is creating this attestation record.
* Verify that `len(attester_bitfield) == ceil_div8(len(attestation_indices))`, where `ceil_div8 = (x + 7) // 8`. Verify that bits `len(attestation_indices)....` and higher, if present (i.e. `len(attestation_indices)` is not a multiple of 8), are all zero.
* Derive a group public key by adding the public keys of all of the attesters in `attestation_indices` for whom the corresponding bit in `attester_bitfield` (the ith bit is `(attester_bitfield[i // 8] >> (7 - (i %8))) % 2`) equals 1.
* Let `fork_version = pre_fork_version if slot < fork_slot_number else post_fork_version`.
* Verify that `aggregate_sig` verifies using the group pubkey generated and the serialized form of `AttestationSignedData(fork_version, slot, shard, parent_hashes, shard_block_hash, justified_slot)` as the message.

Extend the list of `AttestationRecord` objects in the `active_state` with those included in the block, ordering the new additions in the same order as they came in the block. Similarly extend the list of `SpecialRecord` objects in the `active_state` with those included in the block.

Let `curblock_proposer_index` be the validator index of the `block.slot % len(get_shards_and_committees_for_slot(crystallized_state, block.slot)[0].committee)`'th attester in `get_shards_and_committees_for_slot(crystallized_state, block.slot)[0]`, and `parent_proposer_index` be the validator index of the parent block, calculated similarly. Verify that an attestation from the `parent_proposer_index`'th validator is part of the first (ie. item 0 in the array) `AttestationRecord` object; this attester can be considered to be the proposer of the parent block. In general, when a beacon block is produced, it is broadcasted at the network layer along with the attestation from its proposer.

Additionally, verify and update the RANDAO reveal. This is done as follows:

* Let `repeat_hash(x, n) = x if n == 0 else repeat_hash(hash(x), n-1)`.
* Let `V = crystallized_state.validators[curblock_proposer_index]`.
* Verify that `repeat_hash(block.randao_reveal, (block.slot - V.randao_last_reveal) // RANDAO_SLOTS_PER_LAYER + 1) == V.randao_commitment`, and set `active_state.randao_mix = xor(active_state.randao_mix, block.randao_reveal)` and append to `ActiveState.pending_specials` a `SpecialObject(kind=RANDAO_CHANGE, data=[bytes8(curblock_proposer_index), block.randao_reveal])`.

### State recalculations (every `CYCLE_LENGTH` slots)

Repeat while `slot - last_state_recalculation_slot >= CYCLE_LENGTH`:

#### Adjust justified slots and crosslink status

For every slot `s` in the range `last_state_recalculation_slot - CYCLE_LENGTH ... last_state_recalculation_slot - 1`:

* Let `total_balance` be the total balance of active validators.
* Let `total_balance_attesting_at_s` be the total balance of validators that attested to the beacon block at slot `s`.
* If `3 * total_balance_attesting_at_s >= 2 * total_balance` set `last_justified_slot = max(last_justified_slot, s)` and `justified_streak += 1`. Otherwise set `justified_streak = 0`.
* If `justified_streak >= CYCLE_LENGTH + 1` set `last_finalized_slot = max(last_finalized_slot, s - CYCLE_LENGTH - 1)`.

For every `(shard, shard_block_hash)` tuple:

* Let `total_balance_attesting_to_h` be the total balance of validators that attested to the shard block with hash `shard_block_hash`.
* Let `total_committee_balance` be the total balance in the committee of validators that could have attested to the shard block with hash `shard_block_hash`.
* If `3 * total_balance_attesting_to_h >= 2 * total_committee_balance` and `recently_changed is False`, set `crosslinks[shard] = CrosslinkRecord(recently_changed=True, slot=block.last_state_recalculation_slot + CYCLE_LENGTH, hash=shard_block_hash)`.

#### Balance recalculations related to FFG rewards

Note: When applying penalties in the following balance recalculations implementers should make sure the `uint64` does not underflow.

* Let `total_balance` be the total balance of active validators.
* Let `total_balance_in_eth = total_balance // GWEI_PER_ETH`.
* Let `reward_quotient = BASE_REWARD_QUOTIENT * int_sqrt(total_balance_in_eth)`. (The per-slot maximum interest rate is `1/reward_quotient`.)
* Let `quadratic_penalty_quotient = SQRT_E_DROP_TIME**2`. (The portion lost by offline validators after `D` slots is about `D*D/2/quadratic_penalty_quotient`.)
* Let `time_since_finality = block.slot - last_finalized_slot`.

For every slot `s` in the range `last_state_recalculation_slot - CYCLE_LENGTH ... last_state_recalculation_slot - 1`:

* Let `total_balance_participating` be the total balance of validators that voted for the canonical beacon block at slot `s`. In the normal case every validator will be in one of the `CYCLE_LENGTH` slots following slot `s` and so can vote for a block at slot `s`.
* Let `B` be the balance of any given validator whose balance we are adjusting, not including any balance changes from this round of state recalculation.
* If `time_since_finality <= 3 * CYCLE_LENGTH` adjust the balance of participating and non-participating validators as follows:
    * Participating validators gain `B // reward_quotient * (2 * total_balance_participating - total_balance) // total_balance`. (Note that this value may be negative.)
    * Non-participating validators lose `B // reward_quotient`.
* Otherwise:
    * Participating validators gain nothing.
    * Non-participating validators lose `B // reward_quotient + B * time_since_finality // quadratic_penalty_quotient`.

In addition, validators with `status == PENALIZED` lose `B // reward_quotient + B * time_since_finality // quadratic_penalty_quotient`.

#### Balance recalculations related to crosslink rewards

For every shard number `shard` for which a crosslink committee exists in the cycle prior to the most recent cycle (`last_state_recalculation_slot - CYCLE_LENGTH ... last_state_recalculation_slot - 1`), let `V` be the corresponding validator set. Let `B` be the balance of any given validator whose balance we are adjusting, not including any balance changes from this round of state recalculation. For each `shard`, `V`:

* Let `total_balance_of_v` be the total balance of `V`.
* Let `total_balance_of_v_participating` be the total balance of the subset of `V` that participated.
* Let `time_since_last_confirmation = block.slot - crosslinks[shard].slot`.
* If `recently_changed is False`, adjust balances as follows:
    * Participating validators gain `B // reward_quotient * (2 * total_balance_of_v_participating - total_balance_of_v) // total_balance_of_v`.
    * Non-participating validators lose `B // reward_quotient + B * time_since_last_confirmation // quadratic_penalty_quotient`.

In addition, validators with `status == PENALIZED` lose `B // reward_quotient + B * sum([time_since_last_confirmation(c) for c in committees]) // len(committees) // quadratic_penalty_quotient`, where `committees` is the set of committees processed and `time_since_last_confirmation(c)` is the value of `time_since_last_confirmation` in committee `c`.

#### Process penalties, logouts and other special objects

For each `SpecialRecord` `obj` in `active_state.pending_specials`:

* **[covers logouts]**: If `obj.kind == LOGOUT`, interpret `data[0]` as a validator index as an `uint32` and `data[1]` as a signature. If `BLSVerify(pubkey=validators[data[0]].pubkey, msg=hash(LOGOUT_MESSAGE + bytes8(fork_version)), sig=data[1])`, where `fork_version = pre_fork_version if slot < fork_slot_number else post_fork_version`, and `validators[i].status == ACTIVE`, run `exit_validator(data[0], crystallized_state, penalize=False, current_slot=block.slot)`
* **[covers `NO_DBL_VOTE`, `NO_SURROUND`, `NO_DBL_PROPOSE` slashing conditions]:** If `obj.kind == CASPER_SLASHING`, interpret `data[0]` as a list of concatenated `uint32` values where each value represents an index into `validators`, `data[1]` as the data being signed and `data[2]` as an aggregate signature. Interpret `data[3:6]` similarly. Verify that both signatures are valid, that the two signatures are signing distinct data, and that they are either signing the same slot number, or that one surrounds the other (ie. `source1 < source2 < target2 < target1`). Let `indices` be the list of indices in both signatures; verify that its length is at least 1. For each validator index `v` in `indices`, if its `status` does not equal `PENALIZED`, then run `exit_validator(v, crystallized_state, penalize=True, current_slot=block.slot)`
* **[covers RANDAO updates]**: If `obj.kind == RANDAO_REVEAL`, interpret `data[0]` as an integer and `data[1]` as a hash32. Set `validators[data[0]].randao_commitment = data[1]`.

#### Finally...

* For any validator with index `v` with balance less than `MIN_ONLINE_DEPOSIT_SIZE` and status `ACTIVE`, run `exit_validator(v, crystallized_state, penalize=False, current_slot=block.slot)`
* Set `crystallized_state.last_state_recalculation_slot += CYCLE_LENGTH`
* Remove all attestation records older than slot `crystallized_state.last_state_recalculation_slot`
* Empty the `active_state.pending_specials` list
* Set `active_state.recent_block_hashes = active_state.recent_block_hashes[CYCLE_LENGTH:]`

### Validator set change

A validator set change can happen after a state recalculation if all of the following criteria are satisfied:

* `block.slot - crystallized_state.validator_set_change_slot >= MIN_VALIDATOR_SET_CHANGE_INTERVAL`
* `last_finalized_slot > crystallized_state.validator_set_change_slot`
* For every shard number `shard` in `shard_and_committee_for_slots`, `crosslinks[shard].slot > crystallized_state.validator_set_change_slot`

Then, run the following algorithm to update the validator set:

```python
def change_validators(validators: List[ValidatorRecord]) -> None:
    # The active validator set
    active_validators = get_active_validator_indices(validators)
    # The total balance of active validators
    total_balance = sum([v.balance for i, v in enumerate(validators) if i in active_validators])
    # The maximum total wei that can deposit+withdraw
    max_allowable_change = max(
        2 * DEPOSIT_SIZE * GWEI_PER_ETH,
        total_balance // MAX_VALIDATOR_CHURN_QUOTIENT
    )
    # Go through the list start to end depositing+withdrawing as many as possible
    total_changed = 0
    for i in range(len(validators)):
        if validators[i].status == PENDING_ACTIVATION:
            validators[i].status = ACTIVE
            total_changed += DEPOSIT_SIZE * GWEI_PER_ETH
            add_validator_set_change_record(
                crystallized_state=crystallized_state,
                index=i,
                pubkey=validators[i].pubkey,
                flag=ENTRY
            )
        if validators[i].status == PENDING_EXIT:
            validators[i].status = PENDING_WITHDRAW
            validators[i].exit_slot = current_slot
            total_changed += validators[i].balance
            add_validator_set_change_record(
                crystallized_state=crystallized_state,
                index=i,
                pubkey=validators[i].pubkey,
                flag=EXIT
            )
        if total_changed >= max_allowable_change:
            break

    # Calculate the total ETH that has been penalized in the last ~2-3 withdrawal periods
    period_index = current_slot // WITHDRAWAL_PERIOD
    total_penalties = (
        (crystallized_state.deposits_penalized_in_period[period_index]) +
        (crystallized_state.deposits_penalized_in_period[period_index - 1] if period_index >= 1 else 0) +
        (crystallized_state.deposits_penalized_in_period[period_index - 2] if period_index >= 2 else 0)
    )
    # Separate loop to withdraw validators that have been logged out for long enough, and
    # calculate their penalties if they were slashed
    for i in range(len(validators)):
        if validators[i].status in (PENDING_WITHDRAW, PENALIZED) and current_slot >= validators[i].exit_slot + WITHDRAWAL_PERIOD:
            if validators[i].status == PENALIZED:
                validators[i].balance -= validators[i].balance * min(total_penalties * 3, total_balance) // total_balance
            validators[i].status = WITHDRAWN

            withdraw_amount = validators[i].balance
            ...
            # STUB: withdraw to shard chain
```

Finally:

* Set `crystallized_state.validator_set_change_slot = crystallized_state.last_state_recalculation_slot`
* For all `c` in `crystallized_state.crosslinks`, set `c.recently_changed = False`
* Let `next_start_shard = (shard_and_committee_for_slots[-1][-1].shard + 1) % SHARD_COUNT`
* Set `shard_and_committee_for_slots[:CYCLE_LENGTH] = shard_and_committee_for_slots[CYCLE_LENGTH:]` and `shard_and_committee_for_slots[CYCLE_LENGTH:] = get_new_shuffling(active_state.randao_mix, validators, next_start_shard)`

### TODO

Note: This spec is ~60% complete.

**Missing**

* [ ] Specify how `crystallized_state_root` and `active_state_root` are constructed, including Merklelisation logic for light clients
* [ ] Specify the rules around acceptable values for `pow_chain_reference`
* [ ] Specify the shard chain blocks, blobs, proposers, etc.
* [ ] Specify the rules for forced deregistrations
* [ ] Specify the various assumptions (global clock, networking latency, validator honesty, validator liveness, etc.)
* [ ] Specify (in a separate Vyper file) the registration contract on the PoW chain
* [ ] Specify the bootstrapping logic for the beacon chain genesis (e.g. specify a minimum number validators before the genesis block)
* [ ] Specify the logic for proofs of custody, including slashing conditions
* [ ] Add an appendix about the BLS12-381 curve
* [ ] Add an appendix on gossip networks and the offchain signature aggregation logic
* [ ] Add a glossary (in a separate `glossary.md`) to comprehensively and precisely define all the terms
* [ ] Undergo peer review, security audits and formal verification

**Possible rework/additions**

* [ ] Replace the IMD fork choice rule with LMD
* [ ] Merklelise `crystallized_state_root` and `active_state_root` into a single root
* [ ] Replace Blake with a STARK-friendly hash function
* [ ] Reduce the slot duration to 8 seconds
* [ ] Allow for the delayed inclusion of aggregated signatures
* [ ] Use a separate networking-optimised serialisation format for networking
* [ ] Harden RANDAO against orphaned reveals
* [ ] Introduce a RANDAO slashing condition for early leakage
* [ ] Use a separate hash function for the proof of possession
* [ ] Rework the `ShardAndCommittee` data structures
* [ ] Add a double-batched Merkle accumulator for historical beacon chain blocks
* [ ] Allow for deposits larger than 32 ETH, as well as deposit top-ups
* [ ] Add penalties for a deposit below 32 ETH (or some other threshold)
* [ ] Add a `SpecialRecord` to (re)register
* [ ] Rework the document for readability
* [ ] Clearly document the various edge cases, e.g. with committee sizing

# Appendix
## Appendix A - Hash function

We aim to have a STARK-friendly hash function `hash(x)` for the production launch of the beacon chain. While the standardisation process for a STARK-friendly hash function takes place—led by STARKware, who will produce a detailed report with recommendations—we use `BLAKE2b-512` as a placeholder. Specifically, we set `hash(x) := BLAKE2b-512(x)[0:32]` where the `BLAKE2b-512` algorithm is defined in [RFC 7693](https://tools.ietf.org/html/rfc7693) and the input `x` is of type `bytes`.

## Copyright
Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
