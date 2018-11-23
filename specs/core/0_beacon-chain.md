# Ethereum 2.0 Phase 0 -- The Beacon Chain

###### tags: `spec`, `eth2.0`, `casper`, `sharding`, `beacon`

**NOTICE**: This document is a work-in-progress for researchers and implementers. It reflects recent spec changes and takes precedence over the [Python proof-of-concept implementation](https://github.com/ethereum/beacon_chain).

### Introduction

This document represents the specification for Phase 0 of Ethereum 2.0 -- The Beacon Chain.

At the core of Ethereum 2.0 is a system chain called the "beacon chain". The beacon chain stores and manages the set of active proof-of-stake validators. In the initial deployment phases of Ethereum 2.0 the only mechanism to become a validator is to make a fixed-size one-way ETH deposit to a registration contract on the Ethereum 1.0 PoW chain. Induction as a validator happens after registration transaction receipts are processed by the beacon chain and after a queuing process. Deregistration is either voluntary or done forcibly as a penalty for misbehavior.

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
| `DEPOSIT_CONTRACT_ADDRESS` | **TBD** | - |
| `TARGET_COMMITTEE_SIZE` | 2**8 (= 256) | validators |
| `GENESIS_TIME` | **TBD** | seconds |
| `SLOT_DURATION` | 6 | seconds |
| `CYCLE_LENGTH` | 2**6 (= 64) | slots | ~6 minutes |
| `MIN_VALIDATOR_SET_CHANGE_INTERVAL` | 2**8 (= 256) | slots | ~25 minutes |
| `SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD` | 2**17 (= 131,072) | slots | ~9 days |
| `MIN_ATTESTATION_INCLUSION_DELAY` | 2**2 (= 4) | slots | ~24 seconds |
| `RANDAO_SLOTS_PER_LAYER` | 2**12 (= 4096) | slots | ~7 hours |
| `SQRT_E_DROP_TIME` | 2**11 (= 1,024) | cycles | ~9 days |
| `WITHDRAWALS_PER_CYCLE` | 2**2 (=4) | validators | 5.2m ETH in ~6 months |
| `MIN_WITHDRAWAL_PERIOD` | 2**13 (= 8192) | slots | ~14 hours |
| `DELETION_PERIOD` | 2**22 (= 4,194,304) | slots | ~290 days |
| `COLLECTIVE_PENALTY_CALCULATION_PERIOD` | 2**20 (= 1,048,576) | slots | ~2.4 months |
| `SLASHING_WHISTLEBLOWER_REWARD_DENOMINATOR` | 2**9 (= 512) |
| `BASE_REWARD_QUOTIENT` | 2**11 (= 2,048) | — |
| `MAX_VALIDATOR_CHURN_QUOTIENT` | 2**5 (= 32) | — |
| `POW_HASH_VOTING_PERIOD` | 2**10 (=1024) | - |
| `POW_CONTRACT_MERKLE_TREE_DEPTH` | 2**5 (=32) | - |
| `LOGOUT_MESSAGE` | `"LOGOUT"` | — |
| `INITIAL_FORK_VERSION` | 0 | — |

**Notes**

* See a recommended min committee size of 111 [here](https://vitalik.ca/files/Ithaca201807_Sharding.pdf); our algorithm will generally ensure the committee size is at least half the target.
* The `SQRT_E_DROP_TIME` constant is the amount of time it takes for the quadratic leak to cut deposits of non-participating validators by ~39.4%.
* The `BASE_REWARD_QUOTIENT` constant dictates the per-cycle interest rate assuming all validators are participating, assuming total deposits of 1 ETH. It corresponds to ~2.57% annual interest assuming 10 million participating ETH.
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

| Name | Value | Maximum count |
| - | :-: | :-: |
| `LOGOUT` | `0` | `16` |
| `CASPER_SLASHING` | `1` | `16` |
| `PROPOSER_SLASHING` | `2` | `16` |
| `DEPOSIT_PROOF` | `3` | `16` |

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
    # Recent PoW chain reference (receipt root)
    'candidate_pow_receipt_root': 'hash32',
    # Skip list of previous beacon block hashes
    # i'th item is the most recent ancestor whose slot is a multiple of 2**i for i = 0, ..., 31
    'ancestor_hashes': ['hash32'],
    # State root
    'state_root': 'hash32',
    # Attestations
    'attestations': [AttestationRecord],
    # Specials (e.g. logouts, penalties)
    'specials': [SpecialRecord],
    # Proposer signature
    'proposer_signature': ['uint256'],
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
    'parent_hashes': ['hash32'],
    # Shard block hash being attested to
    'shard_block_hash': 'hash32',
    # Last crosslink hash
    'last_crosslink_hash': 'hash32',
    # Root of data between last hash and this one
    'shard_block_combined_data_root': 'hash32',
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

A `ProposalSignedData` has the following fields:

```python
{
    # Fork version
    'fork_version': 'uint64',
    # Slot number
    'slot': 'uint64',
    # Shard ID (or `2**64 - 1` for beacon chain)
    'shard_id': 'uint64',
    # Block hash
    'block_hash': 'hash32',
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
    # CYCLE_LENGTH parent hashes
    'parent_hashes': ['hash32'],
    # Shard block hash
    'shard_block_hash': 'hash32',
    # Last crosslink hash
    'last_crosslink_hash': 'hash32',
    # Root of data between last hash and this one
    'shard_block_combined_data_root': 'hash32',
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
    'data': 'bytes'
}
```

### Beacon chain state

The `BeaconState` has the following fields:

```python
{
    # Slot of last validator set change
    'validator_set_change_slot': 'uint64',
    # List of validators
    'validators': [ValidatorRecord],
    # Most recent crosslink for each shard
    'crosslinks': [CrosslinkRecord],
    # Last cycle-boundary state recalculation
    'last_state_recalculation_slot': 'uint64',
    # Last finalized slot
    'last_finalized_slot': 'uint64',
    # Last justified slot
    'last_justified_slot': 'uint64',
    # Committee members and their assigned shard, per slot
    'shard_and_committee_for_slots': [[ShardAndCommittee]],
    # Persistent shard committees
    'persistent_committees': [['uint24']],
    'persistent_committee_reassignments': [ShardReassignmentRecord],
    # Randao seed used for next shuffling
    'next_shuffling_seed': 'hash32',
    # Total deposits penalized in the given withdrawal period
    'deposits_penalized_in_period': ['uint64'],
    # Hash chain of validator set changes (for light clients to easily track deltas)
    'validator_set_delta_hash_chain': 'hash32'
    # Current sequence number for withdrawals
    'current_exit_seq': 'uint64',
    # Genesis time
    'genesis_time': 'uint64',
    # PoW chain reference
    'known_pow_receipt_root': 'hash32',
    'candidate_pow_receipt_root': 'hash32',
    'candidate_pow_receipt_root_votes': 'uint64',
    # Parameters relevant to hard forks / versioning.
    # Should be updated only by hard forks.
    'pre_fork_version': 'uint64',
    'post_fork_version': 'uint64',
    'fork_slot_number': 'uint64',
    # Attestations not yet processed
    'pending_attestations': [AttestationRecord],
    # recent beacon block hashes needed to process attestations, older to newer
    'recent_block_hashes': ['hash32'],
    # RANDAO state
    'randao_mix': 'hash32'
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
    # Balance in Gwei
    'balance': 'uint64',
    # Status code
    'status': 'uint8',
    # Slot when validator exited (or 0)
    'exit_slot': 'uint64'
    # Sequence number when validator exited (or 0)
    'exit_seq': 'uint64'
}
```

A `CrosslinkRecord` has the following fields:

```python
{
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

A `ShardReassignmentRecord` object has the following fields:

```python
{
    # Which validator to reassign
    'validator_index': 'uint24',
    # To which shard
    'shard': 'uint16',
    # When
    'slot': 'uint64'
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

1. The per-block processing, which happens every block, and only affects a few parts of the `state`.
2. The inter-cycle state recalculation, which happens only if `block.slot >= last_state_recalculation_slot + CYCLE_LENGTH`, and affects the entire `state`.

The inter-cycle state recalculation generally focuses on changes to the validator set, including adjusting balances and adding and removing validators, as well as processing crosslinks and managing block justification/finalization, while the per-block processing generally focuses on verifying aggregate signatures and saving temporary records relating to the per-block activity in the `BeaconState`.

### Helper functions

Below are various helper functions.

The following is a function that gets active validator indices from the validator list:
```python
def get_active_validator_indices(validators)
    return [i for i, v in enumerate(validators) if v.status == ACTIVE]
```

The following is a function that shuffles the validator list:

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

    committees_per_slot = clamp(
        1,
        SHARD_COUNT // CYCLE_LENGTH,
        len(active_validators) // CYCLE_LENGTH // TARGET_COMMITTEE_SIZE,
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
def get_shards_and_committees_for_slot(state: BeaconState,
                                       slot: int) -> List[ShardAndCommittee]:
    earliest_slot_in_array = state.last_state_recalculation_slot - CYCLE_LENGTH
    assert earliest_slot_in_array <= slot < earliest_slot_in_array + CYCLE_LENGTH * 2
    return state.shard_and_committee_for_slots[slot - earliest_slot_in_array]

def get_block_hash(state: BeaconState,
                   current_block: BeaconBlock,
                   slot: int) -> Hash32:
    earliest_slot_in_array = current_block.slot - len(state.recent_block_hashes)
    assert earliest_slot_in_array <= slot < current_block.slot
    return state.recent_block_hashes[slot - earliest_slot_in_array]
```

`get_block_hash(_, _, s)` should always return the block hash in the beacon chain at slot `s`, and `get_shards_and_committees_for_slot(_, s)` should not change unless the validator set changes.

The following is a function that determines the proposer of a beacon block:

```python
def get_beacon_proposer(state:BeaconState, slot: int) -> ValidatorRecord:
    first_committee = get_shards_and_committees_for_slot(state, slot)[0]
    index = first_committee[slot % len(first_committee)]
    return state.validators[index]
```

The following is a function that determines the validators that participated in an attestation:

```python
def get_attestation_participants(state: State, attestation: AttestationRecord):
    sncs_for_slot = get_shards_and_committees_for_slot(state, attestation.slot)
    snc = [x for x in sncs_for_slot if x.shard == attestation.shard][0]
    assert len(attestation.attester_bitfield) == ceil_div8(len(snc.committee) * 2)
    bit0_participants, bit1_participants = [], []
    for i, vindex in snc.committee:
        bits = (attestation.attester_bitfield[i//4] >> (3 - (i % 4)) * 2) % 4
        assert bits in (0, 2, 3)
        if bits == 2:
            bit0_participants.append(vindex)
        elif bits == 3:
            bit1_participants.append(vindex)
    return bit0_participants, bit1_participants
```

We define another set of helpers to be used throughout: `bytes1(x): return x.to_bytes(1, 'big')`, `bytes2(x): return x.to_bytes(2, 'big')`, and so on for all integers, particularly 1, 2, 3, 4, 8, 32.

We define a function to "add a link" to the validator hash chain, used when a validator is added or removed:

```python
def add_validator_set_change_record(state: BeaconState,
                                    index: int,
                                    pubkey: int,
                                    flag: int) -> None:
    state.validator_set_delta_hash_chain = \
        hash(state.validator_set_delta_hash_chain +
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

### PoW chain contract

The beacon chain is initialized when a condition is met inside a contract on the existing PoW chain. This contract's code in Vyper is as follows:

```python
HashChainValue: event({prev_tip: bytes32, data: bytes[2064], total_deposit_count: int128})
ChainStart: event({hash_chain_tip: bytes32, time: bytes[8]})

receipt_tree: bytes32[int128]
total_deposit_count: int128

@payable
@public
def deposit(deposit_params: bytes[2048]):
    index:int128 = self.total_deposit_count + 2**POW_CONTRACT_MERKLE_TREE_DEPTH
    msg_gwei_bytes8: bytes[8] = slice(convert(msg.value / 10**9, 'bytes32'), 24, 8)
    timestamp_bytes8: bytes[8] = slice(convert(block.timestamp, 'bytes32'), 24, 8)
    deposit_data: bytes[2064] = concat(deposit_params, msg_gwei_bytes8, timestamp_bytes8)

    log.HashChainValue(self.receipt_tree[1], deposit_data, self.total_deposit_count)    

    self.receipt_tree[index] = sha3(deposit_data)
    for i in range(POW_CONTRACT_MERKLE_TREE_DEPTH):
        index //= 2
        self.receipt_tree[index] = sha3(concat(self.receipt_tree[index * 2], self.receipt_tree[index * 2 + 1]))
    self.total_deposit_count += 1
    if self.total_deposit_count == 16384:
        log.ChainStart(self.receipt_tree[1], timestamp_bytes8)

@public
@constant
def get_receipt_root() -> bytes32:
    return self.receipt_tree[1]
```

The contract is at address `DEPOSIT_CONTRACT_ADDRESS`. When a user wishes to become a validator by moving their ETH from the 1.0 chain to the 2.0 chain, they should call the `deposit` function, sending along 32 ETH and providing as `deposit_params` a SimpleSerialize'd `DepositParams` object of the form:

```python
{
    'pubkey': 'int256',
    'proof_of_possession': ['int256'],
    'withdrawal_shard': 'int64',
    'withdrawal_address`: 'bytes20',
    'randao_commitment`: 'hash32'
}
```

If the user wishes to deposit more than `DEPOSIT_SIZE` ETH, they would need to make multiple calls. When the contract publishes a `ChainStart` log, this initializes the chain, calling `on_startup` with:

* `initial_validator_entries` equal to the list of data records published as HashChainValue logs so far, in the order in which they were published (oldest to newest).
* `genesis_time` equal to the `time` value published in the log
* `pow_hash_chain_tip` equal to the `hash_chain_tip` value published in the log

### On startup

A valid block with slot `0` (the "genesis block") has the following values. Other validity rules (eg. requiring a signature) do not apply.

```python
{
    'slot': 0,
    'randao_reveal': bytes32(0),
    'candidate_pow_receipt_root': bytes32(0),
    'ancestor_hashes': [bytes32(0) for i in range(32)],
    'state_root': STARTUP_STATE_ROOT,
    'attestations': [],
    'specials': [],
    'proposer_signature': [0, 0]
}
```

`STARTUP_STATE_ROOT` is the root of the initial state, computed by running the following code:

```python
def on_startup(initial_validator_entries: List[Any], genesis_time: uint64, pow_hash_chain_tip: Hash32) -> BeaconState:
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
            current_slot=0,
            status=ACTIVE,
        )
    # Setup state
    x = get_new_shuffling(bytes([0] * 32), validators, 0)
    crosslinks = [
        CrosslinkRecord(
            slot=0,
            hash=bytes([0] * 32)
        )
        for i in range(SHARD_COUNT)
    ]
    state = BeaconState(
        validator_set_change_slot=0,
        validators=validators,
        crosslinks=crosslinks,
        last_state_recalculation_slot=0,
        last_finalized_slot=0,
        last_justified_slot=0,
        shard_and_committee_for_slots=x + x,
        persistent_committees=split(shuffle(validators, bytes([0] * 32)), SHARD_COUNT),
        persistent_committee_reassignments=[],
        deposits_penalized_in_period=[],
        next_shuffling_seed=b'\x00'*32,
        validator_set_delta_hash_chain=bytes([0] * 32),  # stub
        current_exit_seq=0,
        genesis_time=genesis_time,
        known_pow_hash_chain_tip=pow_hash_chain_tip,
        processed_pow_hash_chain_tip=pow_hash_chain_tip,
        candidate_pow_hash_chain_tip=bytes([0] * 32),
        candidate_pow_hash_chain_tip_votes=0,
        pre_fork_version=INITIAL_FORK_VERSION,
        post_fork_version=INITIAL_FORK_VERSION,
        fork_slot_number=0,
        pending_attestations=[],
        pending_specials=[],
        recent_block_hashes=[bytes([0] * 32) for _ in range(CYCLE_LENGTH * 2)],
        randao_mix=bytes([0] * 32)  # stub
    )

    return state
```

The `add_validator` routine is defined below.

### Routine for adding a validator

This routine should be run for every validator that is inducted as part of a log created on the PoW chain [TODO: explain where to check for these logs]. The status of the validators added after genesis is `PENDING_ACTIVATION`. These logs should be processed in the order in which they are emitted by the PoW chain.

First, a helper function:

```python
def min_empty_validator(validators: List[ValidatorRecord], current_slot: int):
    for i, v in enumerate(validators):
        if v.status == WITHDRAWN and v.exit_slot <= current_slot - DELETION_PERIOD:
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
                  status: int,
                  current_slot: int) -> int:
    # if following assert fails, validator induction failed
    # move on to next validator registration log
    signed_message = bytes32(pubkey) + bytes2(withdrawal_shard) + withdrawal_address + randao_commitment
    assert BLSVerify(pub=pubkey,
                     msg=hash(signed_message),
                     sig=proof_of_possession)
    # Pubkey uniqueness
    assert pubkey not in [v.pubkey for v in validators]
    rec = ValidatorRecord(
        pubkey=pubkey,
        withdrawal_shard=withdrawal_shard,
        withdrawal_address=withdrawal_address,
        randao_commitment=randao_commitment,
        randao_last_change=current_slot,
        balance=DEPOSIT_SIZE * GWEI_PER_ETH,
        status=status,
        exit_slot=0,
        exit_seq=0
    )
    # Add the validator
    index = min_empty_validator(validators)
    if index is None:
        validators.append(rec)
        index = len(validators) - 1
    else:
        validators[index] = rec
    return index
```

### Routine for removing a validator

```python
def exit_validator(index, state, block, penalize, current_slot):
    validator = state.validators[index]
    validator.exit_slot = current_slot
    validator.exit_seq = state.current_exit_seq
    state.current_exit_seq += 1
    for committee in state.persistent_committees:
        for i, vindex in committee:
            if vindex == index:
                committee.pop(i)
                break
    if penalize:
        validator.status = PENALIZED
        whistleblower_xfer_amount = validator.deposit // SLASHING_WHISTLEBLOWER_REWARD_DENOMINATOR
        validator.deposit -= whistleblower_xfer_amount
        get_beacon_proposer(state, block.slot).deposit += whistleblower_xfer_amount
        state.deposits_penalized_in_period[current_slot // COLLECTIVE_PENALTY_CALCULATION_PERIOD] += validator.balance
    else:
        validator.status = PENDING_EXIT
    add_validator_set_change_record(state, index, validator.pubkey, EXIT)
```

## On startup

Run the following code:

```python
def on_startup(initial_validator_entries: List[Any]) -> BeaconState:
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
            current_slot=0,
            status=ACTIVE,
        )
    # Setup state
    x = get_new_shuffling(bytes([0] * 32), validators, 0)
    crosslinks = [
        CrosslinkRecord(
            slot=0,
            hash=bytes([0] * 32)
        )
        for i in range(SHARD_COUNT)
    ]
    state = BeaconState(
        validator_set_change_slot=0,
        validators=validators,
        crosslinks=crosslinks,
        last_state_recalculation_slot=0,
        last_finalized_slot=0,
        last_justified_slot=0,
        shard_and_committee_for_slots=x + x,
        persistent_committees=split(shuffle(validators, bytes([0] * 32)), SHARD_COUNT),
        persistent_committee_reassignments=[],
        deposits_penalized_in_period=[],
        next_shuffling_seed=b'\x00'*32,
        validator_set_delta_hash_chain=bytes([0] * 32),  # stub
        pre_fork_version=INITIAL_FORK_VERSION,
        post_fork_version=INITIAL_FORK_VERSION,
        fork_slot_number=0,
        pending_attestations=[],
        recent_block_hashes=[bytes([0] * 32) for _ in range(CYCLE_LENGTH * 2)],
        randao_mix=bytes([0] * 32)  # stub
    )

    return state
```

## Per-block processing

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

### Verify attestations

For each `AttestationRecord` object `obj`:

* Verify that `slot <= block.slot - MIN_ATTESTATION_INCLUSION_DELAY` and `slot >= max(parent.slot - CYCLE_LENGTH + 1, 0)`.
* Verify that `justified_slot` is equal to or earlier than `last_justified_slot`.
* Verify that `justified_block_hash` is the hash of the block in the current chain at the slot -- `justified_slot`.
* Verify that either `last_crosslink_hash` or `shard_block_hash` equals `state.crosslinks[shard].shard_block_hash`.
* Compute `full_parent_hashes` = `[get_block_hash(state, block, slot - CYCLE_LENGTH + i) for i in range(1, CYCLE_LENGTH - len(parent_hashes) + 1)] + parent_hashes` (eg, if `CYCLE_LENGTH = 4`, `slot = 5`, the actual block hashes starting from slot 0 are `Z A B C D E F G H I J`, and `parent_hashes = [D', E']` then `parent_hashes = [B, C, D' E']`). Note that when *creating* an attestation for a block, the hash of that block itself won't yet be in the `state`, so you would need to add it explicitly.
* Let `bit0_attestation_indices, bit1_attestation_indices = get_attestation_participants(state, obj)` (and verify that the method returns successfully)
* Let `bit0_group_public_key = BLSAddPubkeys(bit0_attestation_indices)` and `bit1_group_public_key = BLSAddPubkeys(bit1_attestation_indices)`
* Let `fork_version = pre_fork_version if slot < fork_slot_number else post_fork_version`.
* Verify that `aggregate_sig` verifies using the group pubkey generated and the serialized form of `AttestationSignedData(fork_version, slot, shard, parent_hashes, shard_block_hash, last_crosslinked_hash, shard_block_combined_data_root, justified_slot)` as the message.

Extend the list of `AttestationRecord` objects in the `state` with those included in the block, ordering the new additions in the same order as they came in the block, and replacing `obj.parent_hashes` with the calculated value of `full_parent_hashes`.

### Verify proposer signature

Let `proposal_hash = hash(ProposalSignedData(fork_version, block.slot, 2**64 - 1, block_hash_without_sig))` where `block_hash_without_sig` is the hash of the block except setting `proposer_signature` to `[0, 0]`.

Verify that `BLSVerify(pubkey=get_beacon_proposer(state, block.slot).pubkey, data=proposal_hash, sig=block.proposer_signature)` passes.

### Verify and process RANDAO reveal

* Let `repeat_hash(x, n) = x if n == 0 else repeat_hash(hash(x), n-1)`.
* Let `V = get_beacon_proposer(state, block.slot).
* Verify that `repeat_hash(block.randao_reveal, (block.slot - V.randao_last_change) // RANDAO_SLOTS_PER_LAYER + 1) == V.randao_commitment`
* Set `state.randao_mix = xor(state.randao_mix, block.randao_reveal)`, `V.randao_commitment = block.randao_reveal`, `V.randao_last_change = block.slot`

Finally, if `block.candidate_pow_hash_chain_tip = state.candidate_pow_hash_chain_tip`, set `state.candidate_hash_chain_tip_votes += 1`.

### Process penalties, logouts and other special objects

Verify that the quantity of each type of object in `block.specials` is less than or equal to its maximum (see table at the top). Verify that objects are sorted in order of `kind` (ie. `block.specials[i+1].kind >= block.specials[i].kind` for all `0 <= i < len(block.specials-1)`).

For each `SpecialRecord` `obj` in `block.specials`, verify that its `kind` is one of the below values, and that `obj.data` deserializes according to the format for the given `kind`, then process it. The word "verify" when used below means that if the given verification check fails, the block containing that `SpecialRecord` is invalid.

#### LOGOUT

```python
{
    'validator_index': 'uint64',
    'signature': '[uint256]'
}
```
Perform the following checks:

* Let `fork_version = pre_fork_version if block.slot < fork_slot_number else post_fork_version`. Verify that `BLSVerify(pubkey=validators[data.validator_index].pubkey, msg=hash(LOGOUT_MESSAGE + bytes8(fork_version)), sig=data.signature)`
* Verify that `validators[validator_index].status == ACTIVE`.

Run `exit_validator(data.validator_index, state, block, penalize=False, current_slot=block.slot)`.

#### CASPER_SLASHING

```python
{
    'vote1_aggregate_sig_indices': '[uint24]',
    'vote1_data': AttestationSignedData,
    'vote1_aggregate_sig': '[uint256]',
    'vote2_aggregate_sig_indices': '[uint24]',
    'vote2_data': AttestationSignedData,
    'vote2_aggregate_sig': '[uint256]',
}
```

Perform the following checks:

* For each `aggregate_sig`, verify that `BLSVerify(pubkey=aggregate_pubkey([validators[i].pubkey for i in aggregate_sig_indices]), msg=vote_data, sig=aggsig)` passes.
* Verify that `vote1_data != vote2_data`.
* Let `intersection = [x for x in vote1_aggregate_sig_indices if x in vote2_aggregate_sig_indices]`. Verify that `len(intersection) >= 1`.
* Verify that `vote1_data.justified_slot < vote2_data.justified_slot < vote2_data.slot <= vote1_data.slot`.

For each validator index `v` in `intersection`, if `state.validators[v].status` does not equal `PENALIZED`, then run `exit_validator(v, state, block, penalize=True, current_slot=block.slot)`

#### PROPOSER_SLASHING

```python
{
    'proposer_index': 'uint24',
    'proposal1_data': ProposalSignedData,
    'proposal1_signature': '[uint256]',
    'proposal2_data': ProposalSignedData,
    'proposal1_signature': '[uint256]',
}
```
For each `proposal_signature`, verify that `BLSVerify(pubkey=validators[proposer_index].pubkey, msg=hash(proposal_data), sig=proposal_signature)` passes. Verify that `proposal1_data.slot == proposal2_data.slot` but `proposal1 != proposal2`. If `state.validators[proposer_index].status` does not equal `PENALIZED`, then run `exit_validator(proposer_index, state, penalize=True, current_slot=block.slot)`

#### DEPOSIT_PROOF

```python
{
    'merkle_branch': '[hash32]',
    'merkle_tree_index': 'uint64',
    'deposit_data': {
         'deposit_params': DepositParams,
         'msg_value': 'uint64',
         'timestamp': 'uint64'
    }
}
```

Note that `deposit_data` in serialized form should be the `DepositParams` followed by 8 bytes for the `msg_value` and 8 bytes for the `timestamp`, or exactly the `deposit_data` in the PoW contract of which the hash was placed into the Merkle tree.

Use the following procedure to verify the `merkle_branch`, setting `leaf=serialized_deposit_data`, `depth=POW_CONTRACT_MERKLE_TREE_DEPTH` and `root=state.known_pow_receipt_root`:

```python
def verify_merkle_branch(leaf: Hash32, branch: [Hash32], depth: int, index: int, root: Hash32) -> bool:
    value = leaf
    for i in range(depth):
        if index % 2:
            value = hash(branch[i], value)
        else:
            value = hash(value, branch[i])
    return value == root
```

Verify that `deposit_data.msg_value == DEPOSIT_SIZE` and `block.slot - (deposit_data.timestamp - state.genesis_time) // SLOT_DURATION < DELETION_PERIOD`.

Run `add_validator(validators, deposit_data.deposit_params.pubkey, deposit_data.deposit_params.proof_of_possession, deposit_data.deposit_params.withdrawal_shard, data.deposit_params.withdrawal_address, deposit_data.deposit_params.randao_commitment, PENDING_ACTIVATION, block.slot)`.

## Cycle boundary processing

Repeat the steps in this section while `block.slot - last_state_recalculation_slot >= CYCLE_LENGTH`. For simplicity, we'll use `s` as `last_state_recalculation_slot`.

_Note: `last_state_recalculation_slot` will always be a multiple of `CYCLE_LENGTH`. In the "happy case", this process will trigger, and loop once, every time `block.slot` passes a new exact multiple of `CYCLE_LENGTH`, but if a chain skips more than an entire cycle then the loop may run multiple times, incrementing `last_state_recalculation_slot` by `CYCLE_LENGTH` with each iteration._

#### Precomputation

* Let `active_validators = [state.validators[i] for i in get_active_validator_indices(state.validators)]`
* Let `total_balance = sum([v.balance for v in active_validators])`
* Let `this_cycle_attestations = [a for a in state.pending_attestations if s <= a.slot < s + CYCLE_LENGTH]` (note: this is the set of attestations _of slots in the cycle `s...s+CYCLE_LENGTH-1`_, not attestations _that got included in the chain during the cycle `s...s+CYCLE_LENGTH-1`)
* Let `prev_cycle_attestations = [a for a in state.pending_attestations if s - CYCLE_LENGTH <= a.slot < s]
* Let `this_cycle_s_attestations = [a for a in this_cycle_attestations if get_block_hash(state, block, s) in a.parent_hashes]
* Let `s_attesters` be the union of the validator index sets given by `[get_attestation_participants(state, a) for a in this_cycle_s_attestations]`
* Let `total_balance_attesting_at_s = sum([v.balance for v in s_attesters])`

#### Adjust justified slots and crosslink status

* If `3 * total_balance_attesting_at_s >= 2 * total_balance` then first (i) if `last_justified_slot == s - CYCLE_LENGTH`, set `last_finalized_slot = last_justified_slot`, then (ii) set `last_justified_slot = s`.

For every `(shard, shard_block_hash)` tuple:

* Let `total_balance_attesting_to_h` be the total balance of validators that attested to the shard block with hash `shard_block_hash`.
* Let `total_committee_balance` be the total balance in the committee of validators that could have attested to the shard block with hash `shard_block_hash`.
* If `3 * total_balance_attesting_to_h >= 2 * total_committee_balance`, set `crosslinks[shard] = CrosslinkRecord(slot=last_state_recalculation_slot + CYCLE_LENGTH, hash=shard_block_hash)`.

#### Balance recalculations related to FFG rewards

Note: When applying penalties in the following balance recalculations implementers should make sure the `uint64` does not underflow.

* Let `total_balance` be the total balance of active validators.
* Let `total_balance_in_eth = total_balance // GWEI_PER_ETH`.
* Let `reward_quotient = BASE_REWARD_QUOTIENT * int_sqrt(total_balance_in_eth)`. (The per-slot maximum interest rate is `2/reward_quotient`.)
* Let `quadratic_penalty_quotient = SQRT_E_DROP_TIME**2`. (The portion lost by offline validators after `D` cycles is about `D*D/2/quadratic_penalty_quotient`.)
* Let `time_since_finality = slot - last_finalized_slot`.

* Let `total_balance_participating` be the total balance of validators that voted for the canonical beacon block at slot `s` (note: every attestation for a block in the slot span `s ... s + CYCLE_LENGTH - 1` counts as this)

* Let `B` be the balance of any given validator whose balance we are adjusting, not including any balance changes from this round of state recalculation.
* If `time_since_finality <= 3 * CYCLE_LENGTH` adjust the balance of participating and non-participating validators as follows:
    * Participating validators gain `B // reward_quotient * (2 * total_balance_participating - total_balance) // total_balance`. (Note that this value may be negative.)
    * Non-participating validators lose `B // reward_quotient`.
* Otherwise:
    * Participating validators gain nothing.
    * Non-participating validators lose `B // reward_quotient + B * time_since_finality // quadratic_penalty_quotient`.

In addition, validators with `status == PENALIZED` lose `B // reward_quotient + B * time_since_finality // quadratic_penalty_quotient`.

#### Balance recalculations related to crosslink rewards

For every shard number `shard` for which a crosslink committee exists in the cycle prior to the most recent cycle (`s - CYCLE_LENGTH ... s - 1`), let `V` be the corresponding validator set. Let `B` be the balance of any given validator whose balance we are adjusting, not including any balance changes from this round of state recalculation. For each `shard`, `V`:

* Let `total_balance_of_v` be the total balance of `V`.
* Let `winning_shard_hash` be the hash that the largest total deposits signed for the `shard` during the cycle.
* Define a "participating validator" as a member of `V` that signed a crosslink of `winning_shard_hash`.
* Let `total_balance_of_v_participating` be the total balance of the subset of `V` that participated.
* Let `time_since_last_confirmation = s - crosslinks[shard].slot`.
* Adjust balances as follows:
    * Participating validators gain `B // reward_quotient * (2 * total_balance_of_v_participating - total_balance_of_v) // total_balance_of_v`.
    * Non-participating validators lose `B // reward_quotient`.

#### PoW chain related rules

If `last_state_recalculation_slot % POW_HASH_VOTING_PERIOD == 0`, then:

* If `state.candidate_hash_chain_tip_votes * 3 >= POW_HASH_VOTING_PERIOD * 2`, set `state.hash_chain_tip = state.candidate_hash_chain_tip`
* Set `state.candidate_hash_chain_tip = block.candidate_pow_hash_chain_tip`
* Set `state.candidate_hash_chain_tip_votes = 0`

#### Proposer reshuffling

Run the following code:

```python
active_validator_indices = get_active_validator_indices(validators)
num_validators_to_reshuffle = len(active_validator_indices) // SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD
for i in range(num_validators_to_reshuffle):
    # Multiplying i to 2 to ensure we have different input to all the required hashes in the shuffling
    # and none of the hashes used for entropy in this loop will be the same
    vid = active_validator_indices[hash(state.randao_mix + bytes8(i * 2)) % len(active_validator_indices)]
    new_shard = hash(state.randao_mix + bytes8(i * 2 + 1)) % SHARD_COUNT
    shard_reassignment_record = ShardReassignmentRecord(
        validator_index=vid,
        shard=new_shard,
        slot=s + SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD
    )
    state.persistent_committee_reassignments.append(shard_reassignment_record)

while len(state.persistent_committee_reassignments) > 0 and state.persistent_committee_reassignments[0].slot <= s:
    rec = state.persistent_committee_reassignments.pop(0)
    for committee in state.persistent_committees:
        if rec.validator_index in committee:
            committee.pop(
                committee.index(rec.validator_index)
            )
    state.persistent_committees[rec.shard].append(rec.validator_index)
```

#### Validator set change

A validator set change can happen if all of the following criteria are satisfied:

* `last_finalized_slot > state.validator_set_change_slot`
* For every shard number `shard` in `shard_and_committee_for_slots`, `crosslinks[shard].slot > state.validator_set_change_slot`

Then, run the following algorithm to update the validator set:

```python
def change_validators(validators: List[ValidatorRecord], current_slot: int) -> None:
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
                state=state,
                index=i,
                pubkey=validators[i].pubkey,
                flag=ENTRY
            )
        if validators[i].status == PENDING_EXIT:
            validators[i].status = PENDING_WITHDRAW
            validators[i].exit_slot = current_slot
            total_changed += validators[i].balance
            add_validator_set_change_record(
                state=state,
                index=i,
                pubkey=validators[i].pubkey,
                flag=EXIT
            )
        if total_changed >= max_allowable_change:
            break

    # Calculate the total ETH that has been penalized in the last ~2-3 withdrawal periods
    period_index = current_slot // COLLECTIVE_PENALTY_CALCULATION_PERIOD
    total_penalties = (
        (state.deposits_penalized_in_period[period_index]) +
        (state.deposits_penalized_in_period[period_index - 1] if period_index >= 1 else 0) +
        (state.deposits_penalized_in_period[period_index - 2] if period_index >= 2 else 0)
    )
    # Separate loop to withdraw validators that have been logged out for long enough, and
    # calculate their penalties if they were slashed

    def withdrawable(v):
        return v.status in (PENDING_WITHDRAW, PENALIZED) and current_slot >= v.exit_slot + MIN_WITHDRAWAL_PERIOD

    withdrawable_validators = sorted(filter(withdrawable, validators), key=lambda v: v.exit_seq)
    for v in withdrawable_validators[:WITHDRAWALS_PER_CYCLE]:
        if v.status == PENALIZED:
            v.balance -= v.balance * min(total_penalties * 3, total_balance) // total_balance
        v.status = WITHDRAWN
        v.exit_slot = current_slot

        withdraw_amount = v.balance
        ...
        # STUB: withdraw to shard chain
```

* Set `state.validator_set_change_slot = s`
* Set `shard_and_committee_for_slots[:CYCLE_LENGTH] = shard_and_committee_for_slots[CYCLE_LENGTH:]`
* Let `next_start_shard = (shard_and_committee_for_slots[-1][-1].shard + 1) % SHARD_COUNT`
* Set `shard_and_committee_for_slots[CYCLE_LENGTH:] = get_new_shuffling(state.next_shuffling_seed, validators, next_start_shard)`
* Set `state.next_shuffling_seed = state.randao_mix`

#### If a validator set change does NOT happen

* Set `shard_and_committee_for_slots[:CYCLE_LENGTH] = shard_and_committee_for_slots[CYCLE_LENGTH:]`
* Let `time_since_finality = block.slot - state.validator_set_change_slot`
* Let `start_shard = shard_and_committee_for_slots[0][0].shard`
* If `time_since_finality * CYCLE_LENGTH <= MIN_VALIDATOR_SET_CHANGE_INTERVAL` or `time_since_finality` is an exact power of 2, set `shard_and_committee_for_slots[CYCLE_LENGTH:] = get_new_shuffling(state.next_shuffling_seed, validators, start_shard)` and set `state.next_shuffling_seed = state.randao_mix`. Note that `start_shard` is not changed from last cycle.

#### Finally...

* Remove all attestation records older than slot `s`
* For any validator with index `v` with balance less than `MIN_ONLINE_DEPOSIT_SIZE` and status `ACTIVE`, run `exit_validator(v, state, block, penalize=False, current_slot=block.slot)`
* Set `state.recent_block_hashes = state.recent_block_hashes[CYCLE_LENGTH:]`
* Set `state.last_state_recalculation_slot += CYCLE_LENGTH`

### TODO

Note: This spec is ~65% complete.

**Missing**

* [ ] Specify the rules around acceptable values for `pow_chain_reference` ([issue 58](https://github.com/ethereum/eth2.0-specs/issues/58))
* [ ] Specify the shard chain blocks, blobs, proposers, etc.
* [ ] Specify the deposit contract on the PoW chain in Vyper
* [ ] Specify the beacon chain genesis rules ([issue 58](https://github.com/ethereum/eth2.0-specs/issues/58))
* [ ] Specify the logic for proofs of custody, including slashing conditions
* [ ] Specify BLSVerify and rework the spec for BLS12-381 throughout
* [ ] Specify the constraints for `SpecialRecord`s ([issue 43](https://github.com/ethereum/eth2.0-specs/issues/43))
* [ ] Specify the calculation and validation of `BeaconBlock.state_root`
* [ ] Undergo peer review, security audits and formal verification

**Documentation**

* [ ] Specify the various assumptions (global clock, networking latency, validator honesty, validator liveness, etc.)
* [ ] Add an appendix on gossip networks and the offchain signature aggregation logic
* [ ] Add a glossary (in a separate `glossary.md`) to comprehensively and precisely define all the terms
* [ ] Clearly document the various edge cases, e.g. with committee sizing
* [ ] Rework the document for readability

**Possible modifications and additions**

* [ ] Replace the IMD fork choice rule with LMD
* [ ] Homogenise types to `uint64` ([PR 36](https://github.com/ethereum/eth2.0-specs/pull/36))
* [ ] Reduce the slot duration to 8 seconds
* [ ] Allow for the delayed inclusion of aggregated signatures
* [ ] Introduce a RANDAO slashing condition for early reveals
* [ ] Use a separate hash function for the proof of possession
* [ ] Rework the `ShardAndCommittee` data structures
* [ ] Add a double-batched Merkle accumulator for historical beacon chain blocks
* [ ] Allow for deposits larger than 32 ETH, as well as deposit top-ups
* [ ] Add penalties for deposits below 32 ETH (or some other threshold)
* [ ] Add a `SpecialRecord` to (re)register

# Appendix
## Appendix A - Hash function

We aim to have a STARK-friendly hash function `hash(x)` for the production launch of the beacon chain. While the standardisation process for a STARK-friendly hash function takes place—led by STARKware, who will produce a detailed report with recommendations—we use `BLAKE2b-512` as a placeholder. Specifically, we set `hash(x) := BLAKE2b-512(x)[0:32]` where the `BLAKE2b-512` algorithm is defined in [RFC 7693](https://tools.ietf.org/html/rfc7693) and the input `x` is of type `bytes`.

## Copyright
Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
