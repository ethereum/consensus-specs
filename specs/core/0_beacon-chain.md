# Ethereum 2.0 Phase 0 -- The Beacon Chain

**NOTICE**: This document is a work-in-progress for researchers and implementers. It reflects recent spec changes and takes precedence over the Python proof-of-concept implementation [[python-poc]](#ref-python-poc).

## Table of contents
<!-- TOC -->

- [Ethereum 2.0 Phase 0 -- The Beacon Chain](#ethereum-20-phase-0----the-beacon-chain)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Notation](#notation)
    - [Terminology](#terminology)
    - [Constants](#constants)
    - [Ethereum 1.0 chain deposit contract](#ethereum-10-chain-deposit-contract)
        - [Contract code in Vyper](#contract-code-in-vyper)
    - [Data structures](#data-structures)
        - [Deposits](#deposits)
            - [`DepositParametersRecord`](#depositparametersrecord)
        - [Beacon chain blocks](#beacon-chain-blocks)
            - [`BeaconBlock`](#beaconblock)
            - [`AttestationRecord`](#attestationrecord)
            - [`AttestationData`](#attestationdata)
            - [`ProposalSignedData`](#proposalsigneddata)
            - [`SpecialRecord`](#specialrecord)
        - [Beacon chain state](#beacon-chain-state)
            - [`BeaconState`](#beaconstate)
            - [`ValidatorRecord`](#validatorrecord)
            - [`CrosslinkRecord`](#crosslinkrecord)
            - [`ShardAndCommittee`](#shardandcommittee)
            - [`ShardReassignmentRecord`](#shardreassignmentrecord)
            - [`CandidatePoWReceiptRootRecord`](#candidatepowreceiptrootrecord)
            - [`PendingAttestationRecord`](#pendingattestationrecord)
            - [`ForkData`](#forkdata)
    - [Beacon chain processing](#beacon-chain-processing)
        - [Beacon chain fork choice rule](#beacon-chain-fork-choice-rule)
    - [Beacon chain state transition function](#beacon-chain-state-transition-function)
        - [Helper functions](#helper-functions)
            - [`get_active_validator_indices`](#get_active_validator_indices)
            - [`shuffle`](#shuffle)
            - [`split`](#split)
            - [`clamp`](#clamp)
            - [`get_new_shuffling`](#get_new_shuffling)
            - [`get_shard_and_committees_for_slot`](#get_shard_and_committees_for_slot)
            - [`get_block_hash`](#get_block_hash)
            - [`get_beacon_proposer_index`](#get_beacon_proposer_index)
            - [`get_attestation_participants`](#get_attestation_participants)
            - [`bytes1`, `bytes2`, ...](#bytes1-bytes2-)
            - [`get_effective_balance`](#get_effective_balance)
            - [`get_new_validator_registry_delta_chain_tip`](#get_new_validator_registry_delta_chain_tip)
            - [`integer_squareroot`](#integer_squareroot)
        - [On startup](#on-startup)
        - [Routine for adding a validator](#routine-for-adding-a-validator)
        - [Routine for removing a validator](#routine-for-removing-a-validator)
    - [Per-block processing](#per-block-processing)
        - [Verify attestations](#verify-attestations)
        - [Verify proposer signature](#verify-proposer-signature)
        - [Verify and process the RANDAO reveal](#verify-and-process-the-randao-reveal)
        - [Process PoW receipt root](#process-pow-receipt-root)
        - [Process special objects](#process-special-objects)
            - [`VOLUNTARY_EXIT`](#voluntary_exit)
            - [`CASPER_SLASHING`](#casper_slashing)
            - [`PROPOSER_SLASHING`](#proposer_slashing)
            - [`DEPOSIT_PROOF`](#deposit_proof)
    - [Epoch boundary processing](#epoch-boundary-processing)
        - [Precomputation](#precomputation)
        - [Adjust justified slots and crosslink status](#adjust-justified-slots-and-crosslink-status)
        - [Balance recalculations related to FFG rewards](#balance-recalculations-related-to-ffg-rewards)
        - [Balance recalculations related to crosslink rewards](#balance-recalculations-related-to-crosslink-rewards)
        - [Ethereum 1.0 chain related rules](#ethereum-10-chain-related-rules)
        - [Validator registry change](#validator-registry-change)
        - [If a validator registry change does NOT happen](#if-a-validator-registry-change-does-not-happen)
        - [Proposer reshuffling](#proposer-reshuffling)
        - [Finally...](#finally)
- [Appendix](#appendix)
    - [Appendix A - Hash function](#appendix-a---hash-function)
- [References](#references)
    - [Normative](#normative)
    - [Informative](#informative)
- [Copyright](#copyright)

<!-- /TOC -->

## Introduction

This document represents the specification for Phase 0 of Ethereum 2.0 -- The Beacon Chain.

At the core of Ethereum 2.0 is a system chain called the "beacon chain". The beacon chain stores and manages the registry of [validators](#dfn-validator). In the initial deployment phases of Ethereum 2.0 the only mechanism to become a [validator](#dfn-validator) is to make a one-way ETH transaction to a deposit contract on Ethereum 1.0. Activation as a [validator](#dfn-validator) happens when deposit transaction receipts are processed by the beacon chain, the activation balance is reached, and after a queuing process. Exit is either voluntary or done forcibly as a penalty for misbehavior.

The primary source of load on the beacon chain is "attestations". Attestations are availability votes for a shard block, and simultaneously proof of stake votes for a beacon chain block. A sufficient number of attestations for the same shard block create a "crosslink", confirming the shard segment up to that shard block into the beacon chain. Crosslinks also serve as infrastructure for asynchronous cross-shard communication.

## Notation

Unless otherwise indicated, code appearing in `this style` is to be interpreted as an algorithm defined in Python. Implementations may implement such algorithms using any code and programming language desired as long as the behavior is identical to that of the algorithm provided.

## Terminology

* **Validator** <a id="dfn-validator"></a> - a participant in the Casper/sharding consensus system. You can become one by depositing 32 ETH into the Casper mechanism.
* **Active validator** <a id="dfn-active-validator"></a> - a [validator](#dfn-validator) currently participating in the protocol which the Casper mechanism looks to produce and attest to blocks, crosslinks and other consensus objects.
* **Committee** - a (pseudo-) randomly sampled subset of [active validators](#dfn-active-validator). When a committee is referred to collectively, as in "this committee attests to X", this is assumed to mean "some subset of that committee that contains enough [validators](#dfn-validator) that the protocol recognizes it as representing the committee".
* **Proposer** - the [validator](#dfn-validator) that creates a beacon chain block
* **Attester** - a [validator](#dfn-validator) that is part of a committee that needs to sign off on a beacon chain block while simultaneously creating a link (crosslink) to a recent shard block on a particular shard chain.
* **Beacon chain** - the central PoS chain that is the base of the sharding system.
* **Shard chain** - one of the chains on which user transactions take place and account data is stored.
* **Crosslink** - a set of signatures from a committee attesting to a block in a shard chain, which can be included into the beacon chain. Crosslinks are the main means by which the beacon chain "learns about" the updated state of shard chains.
* **Slot** - a period of `SLOT_DURATION` seconds, during which one proposer has the ability to create a beacon chain block and some attesters have the ability to make attestations
* **Epoch** - an aligned span of slots during which all [validators](#dfn-validator) get exactly one chance to make an attestation
* **Finalized**, **justified** - see Casper FFG finalization here: https://arxiv.org/abs/1710.09437
* **Withdrawal period** - the number of slots between a [validator](#dfn-validator) exit and the [validator](#dfn-validator) balance being withdrawable
* **Genesis time** - the Unix time of the genesis beacon chain block at slot 0

## Constants

| Name | Value | Unit |
| - | - | :-: |
| `SHARD_COUNT` | `2**10` (= 1,024)| shards |
| `TARGET_COMMITTEE_SIZE` | `2**8` (= 256) | [validators](#dfn-validator) |
| `MAX_ATTESTATIONS_PER_BLOCK` | `2**7` (= 128) | attestations |
| `MAX_DEPOSIT` | `2**5` (= 32) | ETH |
| `MIN_BALANCE` | `2**4` (= 16) | ETH |
| `POW_CONTRACT_MERKLE_TREE_DEPTH` | `2**5` (= 32) | - |
| `INITIAL_FORK_VERSION` | `0` | - |
| `INITIAL_SLOT_NUMBER` | `0` | - |
| `DEPOSIT_CONTRACT_ADDRESS` | **TBD** | - |
| `GWEI_PER_ETH` | `10**9` | Gwei/ETH |
| `ZERO_HASH` | `bytes([0] * 32)` | - |
| `BEACON_CHAIN_SHARD_NUMBER` | `2**64 - 1` | - |

**Time constants**

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SLOT_DURATION` | `6` | seconds | 6 seconds |
| `MIN_ATTESTATION_INCLUSION_DELAY` | `2**2` (= 4) | slots | 24 seconds |
| `EPOCH_LENGTH` | `2**6` (= 64) | slots | 6.4 minutes |
| `MIN_VALIDATOR_REGISTRY_CHANGE_INTERVAL` | `2**8` (= 256) | slots | 25.6 minutes |
| `POW_RECEIPT_ROOT_VOTING_PERIOD` | `2**10` (= 1,024) | slots | ~1.7 hours |
| `SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD` | `2**17` (= 131,072) | slots | ~9 days |
| `SQRT_E_DROP_TIME` | `2**17` (= 131,072) | slots | ~9 days |
| `COLLECTIVE_PENALTY_CALCULATION_PERIOD` | `2**20` (= 1,048,576) | slots | ~73 days |
| `DELETION_PERIOD` | `2**22` (= 16,777,216) | slots | ~290 days |

**Quotients**

| Name | Value |
| - | - |
| `BASE_REWARD_QUOTIENT` | `2**11` (= 2,048) |
| `WHISTLEBLOWER_REWARD_QUOTIENT` | `2**9` (= 512) |
| `INCLUDER_REWARD_QUOTIENT` | `2**3` (= 8) |
| `MAX_CHURN_QUOTIENT` | `2**5` (= 32) |

**Validator status codes**

| Name | Value |
| - | - |
| `PENDING_ACTIVATION` | `0` |
| `ACTIVE` | `1` |
| `EXITED_WITHOUT_PENALTY` | `2` |
| `EXITED_WITH_PENALTY` | `3` |

**Special record types**

| Name | Value | Maximum count |
| - | - | :-: |
| `VOLUNTARY_EXIT` | `0` | `16` |
| `CASPER_SLASHING` | `1` | `16` |
| `PROPOSER_SLASHING` | `2` | `16` |
| `DEPOSIT_PROOF` | `3` | `16` |

**Validator registry delta flags**

| Name | Value |
| - | - |
| `ACTIVATION` | `0` |
| `EXIT` | `1` |

**Domains for BLS signatures**

| Name | Value | 
| - | - |
| `DOMAIN_DEPOSIT` | `0` |
| `DOMAIN_ATTESTATION` | `1` |
| `DOMAIN_PROPOSAL` | `2` |
| `DOMAIN_EXIT` | `3` |

**Notes**

* See a recommended min committee size of 111 [here](https://vitalik.ca/files/Ithaca201807_Sharding.pdf); the shuffling algorithm will generally ensure the committee size is at least half the target.
* The `SQRT_E_DROP_TIME` constant is the amount of time it takes for the inactivity leak to cut deposits of non-participating [validators](#dfn-validator) by ~39.4%.
* The `BASE_REWARD_QUOTIENT` constant dictates the per-epoch interest rate assuming all [validators](#dfn-validator) are participating, assuming total deposits of 1 ETH. It corresponds to ~2.57% annual interest assuming 10 million participating ETH.
* At most `1/MAX_CHURN_QUOTIENT` of the [validators](#dfn-validator) can change during each [validator](#dfn-validator) registry change.

## Ethereum 1.0 chain deposit contract

The initial deployment phases of Ethereum 2.0 are implemented without consensus changes to Ethereum 1.0. A deposit contract is added to Ethereum 1.0 to deposit ETH. This contract has a `deposit` function which takes as arguments `pubkey`, `withdrawal_credentials`, `randao_commitment` as defined in a `ValidatorRecord` below. A BLS `proof_of_possession` of types `bytes` is given as a final argument.

The deposit contract emits a log with the various arguments for consumption by the beacon chain. It does little validation, pushing the deposit logic to the beacon chain. In particular, the proof of possession (based on the BLS12-381 curve) is not verified by the deposit contract.

### Contract code in Vyper

The beacon chain is initialized when a condition is met inside the deposit contract on the existing Ethereum 1.0 chain. This contract's code in Vyper is as follows:

```python
MIN_DEPOSIT: constant(uint256) = 1  # ETH
MAX_DEPOSIT: constant(uint256) = 32  # ETH
GWEI_PER_ETH: constant(uint256) = 1000000000  # 10**9
CHAIN_START_FULL_DEPOSIT_THRESHOLD: constant(uint256) = 16384  # 2**14
POW_CONTRACT_MERKLE_TREE_DEPTH: constant(uint256) = 32
SECONDS_PER_DAY: constant(uint256) = 86400

HashChainValue: event({previous_receipt_root: bytes32, data: bytes[2064], full_deposit_count: uint256})
ChainStart: event({receipt_root: bytes32, time: bytes[8]})

receipt_tree: bytes32[uint256]
full_deposit_count: uint256

@payable
@public
def deposit(deposit_parameters: bytes[2048]):
    index: uint256 = self.full_deposit_count + 2**POW_CONTRACT_MERKLE_TREE_DEPTH
    msg_gwei_bytes8: bytes[8] = slice(concat("", convert(msg.value / GWEI_PER_ETH, bytes32)), start=24, len=8)
    timestamp_bytes8: bytes[8] = slice(concat("", convert(block.timestamp, bytes32)), start=24, len=8)
    deposit_data: bytes[2064] = concat(msg_gwei_bytes8, timestamp_bytes8, deposit_parameters)

    log.HashChainValue(self.receipt_tree[1], deposit_data, self.full_deposit_count)

    self.receipt_tree[index] = sha3(deposit_data)
    for i in range(32):  # POW_CONTRACT_MERKLE_TREE_DEPTH (range of constant var not yet supported)
        index /= 2
        self.receipt_tree[index] = sha3(concat(self.receipt_tree[index * 2], self.receipt_tree[index * 2 + 1]))

    assert msg.value >= as_wei_value(MIN_DEPOSIT, "ether")
    assert msg.value <= as_wei_value(MAX_DEPOSIT, "ether")
    if msg.value == as_wei_value(MAX_DEPOSIT, "ether"):
        self.full_deposit_count += 1
    if self.full_deposit_count == CHAIN_START_FULL_DEPOSIT_THRESHOLD:
        timestamp_day_boundary: uint256 = as_unitless_number(block.timestamp) - as_unitless_number(block.timestamp) % SECONDS_PER_DAY + SECONDS_PER_DAY
        timestamp_day_boundary_bytes8: bytes[8] = slice(concat("", convert(timestamp_day_boundary, bytes32)), start=24, len=8)
        log.ChainStart(self.receipt_tree[1], timestamp_day_boundary_bytes8)

@public
@constant
def get_receipt_root() -> bytes32:
    return self.receipt_tree[1]

```

The contract is at address `DEPOSIT_CONTRACT_ADDRESS`. When a user wishes to become a [validator](#dfn-validator) by moving their ETH from Ethereum 1.0 to the Ethereum 2.0 chain, they should call the `deposit` function, sending up to `MAX_DEPOSIT` ETH and providing as `deposit_parameters` a SimpleSerialize'd `DepositParametersRecord` object (defined in "Data structures" below). If the user wishes to deposit more than `MAX_DEPOSIT` ETH, they would need to make multiple calls.

When the contract publishes a `ChainStart` log, this initializes the chain, calling `on_startup` with:

* `initial_validator_entries` equal to the list of data records published as HashChainValue logs so far, in the order in which they were published (oldest to newest).
* `genesis_time` equal to the `time` value published in the log
* `processed_pow_receipt_root` equal to the `receipt_root` value published in the log

## Data structures

### Deposits

#### `DepositParametersRecord`

```python
{
    # BLS pubkey
    'pubkey': 'int384',
    # BLS proof of possession (a BLS signature)
    'proof_of_possession': ['int384'],
    # Withdrawal credentials (TODO: define the format)
    'withdrawal_credentials': 'hash32',
    # The initial RANDAO commitment
    'randao_commitment': 'hash32',
}
```

### Beacon chain blocks

#### `BeaconBlock`

```python
{
    # Slot number
    'slot': 'uint64',
    # Proposer RANDAO reveal
    'randao_reveal': 'hash32',
    # Candidate PoW receipt root
    'candidate_pow_receipt_root': 'hash32',
    # Skip list of ancestor beacon block hashes
    # i'th item is the most recent ancestor whose slot is a multiple of 2**i for i = 0, ..., 31
    'ancestor_hashes': ['hash32'],
    # State root
    'state_root': 'hash32',
    # Attestations
    'attestations': [AttestationRecord],
    # Specials (e.g. exits, penalties)
    'specials': [SpecialRecord],
    # Proposer signature
    'proposer_signature': ['uint384'],
}
```

#### `AttestationRecord`

```python
{
    # Attestation data
    'data': AttestationData,
    # Attester participation bitfield
    'participation_bitfield': 'bytes',
    # Proof of custody bitfield
    'custody_bitfield': 'bytes',
    # BLS aggregate signature
    'aggregate_sig': ['uint384'],
}
```

#### `AttestationData`

```python
{
    # Slot number
    'slot': 'uint64',
    # Shard number
    'shard': 'uint64',
    # Hash of the signed beacon block
    'beacon_block_hash': 'hash32',
    # Hash of the ancestor at the epoch boundary
    'epoch_boundary_hash': 'hash32',
    # Shard block hash being attested to
    'shard_block_hash': 'hash32',
    # Last crosslink hash
    'latest_crosslink_hash': 'hash32',
    # Slot of the last justified beacon block
    'justified_slot': 'uint64',
    # Hash of the last justified beacon block
    'justified_block_hash': 'hash32',
}
```

#### `ProposalSignedData`

```python
{
    # Slot number
    'slot': 'uint64',
    # Shard number (`BEACON_CHAIN_SHARD_NUMBER` for beacon chain)
    'shard': 'uint64',
    # Block hash
    'block_hash': 'hash32',
}
```

#### `SpecialRecord`

```python
{
    # Kind
    'kind': 'uint64',
    # Data
    'data': 'bytes',
}
```

### Beacon chain state

#### `BeaconState`

```python
{
    # Validator registry
    'validator_registry': [ValidatorRecord],
    'validator_registry_latest_change_slot': 'uint64',
    'validator_registry_exit_count': 'uint64',
    'validator_registry_delta_chain_tip': 'hash32',  # For light clients to easily track delta

    # Randomness and committees
    'randao_mix': 'hash32',
    'next_seed': 'hash32',
    'shard_and_committee_for_slots': [[ShardAndCommittee]],
    'persistent_committees': [['uint24']],
    'persistent_committee_reassignments': [ShardReassignmentRecord],

    # Finality
    'previous_justified_slot': 'uint64',
    'justified_slot': 'uint64',
    'justified_slot_bitfield': 'uint64',
    'finalized_slot': 'uint64',

    # Recent state
    'latest_crosslinks': [CrosslinkRecord],
    'latest_state_recalculation_slot': 'uint64',
    'latest_block_hashes': ['hash32'],  # Needed to process attestations, older to newer
    'latest_penalized_exit_balances': ['uint64'],  # Balances penalized in the current withdrawal period
    'latest_attestations': [PendingAttestationRecord],

    # PoW receipt root
    'processed_pow_receipt_root': 'hash32',
    'candidate_pow_receipt_roots': [CandidatePoWReceiptRootRecord],

    # Misc
    'genesis_time': 'uint64',
    'fork_data': ForkData,  # For versioning hard forks
}
```

#### `ValidatorRecord`

```python
{
    # BLS public key
    'pubkey': 'uint384',
    # Withdrawal credentials
    'withdrawal_credentials': 'hash32',
    # RANDAO commitment
    'randao_commitment': 'hash32',
    # Slots the proposer has skipped (ie. layers of RANDAO expected)
    'randao_skips': 'uint64',
    # Balance in Gwei
    'balance': 'uint64',
    # Status code
    'status': 'uint64',
    # Slot when validator last changed status (or 0)
    'latest_status_change_slot': 'uint64',
    # Exit counter when validator exited (or 0)
    'exit_count': 'uint64',
}
```

#### `CrosslinkRecord`

```python
{
    # Slot number
    'slot': 'uint64',
    # Shard chain block hash
    'shard_block_hash': 'hash32',
}
```

#### `ShardAndCommittee`

```python
{
    # Shard number
    'shard': 'uint64',
    # Validator indices
    'committee': ['uint24'],
    # Total validator count (for proofs of custody)
    'total_validator_count': 'uint64',
}
```

#### `ShardReassignmentRecord`

```python
{
    # Which validator to reassign
    'validator_index': 'uint24',
    # To which shard
    'shard': 'uint64',
    # When
    'slot': 'uint64',
}
```

#### `CandidatePoWReceiptRootRecord`

```python
{
    # Candidate PoW receipt root
    'candidate_pow_receipt_root': 'hash32',
    # Vote count
    'votes': 'uint64',
}
```

#### `PendingAttestationRecord`
```python
{
    # Signed data
    'data': AttestationData,
    # Attester participation bitfield
    'participation_bitfield': 'bytes',
    # Proof of custody bitfield
    'custody_bitfield': 'bytes',
    # Slot in which it was included
    'slot_included': 'uint64',
}
```

#### `ForkData`
```python
{
    # Previous fork version
    'pre_fork_version': 'uint64',
    # Post fork version
    'post_fork_version': 'uint64',
    # Fork slot number
    'fork_slot': 'uint64',
}
```

## Beacon chain processing

The beacon chain is the system chain for Ethereum 2.0. The main responsibilities of the beacon chain are:

* Store and maintain the registry of [validators](#dfn-validator)
* Process crosslinks (see above)
* Process its own block-by-block consensus, as well as the finality gadget

Processing the beacon chain is fundamentally similar to processing the Ethereum 1.0 chain in many respects. Clients download and process blocks, and maintain a view of what is the current "canonical chain", terminating at the current "head". However, because of the beacon chain's relationship with Ethereum 1.0, and because it is a proof-of-stake chain, there are differences.

For a beacon chain block, `block`, to be processed by a node, the following conditions must be met:

* The parent block, `block.ancestor_hashes[0]`, has been processed and accepted.
* The Ethereum 1.0 block pointed to by the `state.processed_pow_receipt_root` has been processed and accepted.
* The node's local clock time is greater than or equal to `state.genesis_time + block.slot * SLOT_DURATION`.

If these conditions are not met, the client should delay processing the beacon block until the conditions are all satisfied.

Beacon block production is significantly different because of the proof of stake mechanism. A client simply checks what it thinks is the canonical chain when it should create a block, and looks up what its slot number is; when the slot arrives, it either proposes or attests to a block as required. Note that this requires each node to have a clock that is roughly (ie. within `SLOT_DURATION` seconds) synchronized with the other nodes.

### Beacon chain fork choice rule

The beacon chain fork choice rule is a hybrid that combines justification and finality with Latest Message Driven (LMD) Greediest Heaviest Observed SubTree (GHOST). At any point in time a [validator](#dfn-validator) `v` subjectively calculates the beacon chain head as follows.

* Let `store` be the set of attestations and blocks that the [validator](#dfn-validator) `v` has observed and verified (in particular, block ancestors must be recursively verified). Attestations not part of any chain are still included in `store`.
* Let `finalized_head` be the finalized block with the highest slot number. (A block `B` is finalized if there is a descendant of `B` in `store` the processing of which sets `B` as finalized.)
* Let `justified_head` be the descendant of `finalized_head` with the highest slot number that has been justified for at least `EPOCH_LENGTH` slots. (A block `B` is justified if there is a descendant of `B` in `store` the processing of which sets `B` as justified.) If no such descendant exists set `justified_head` to `finalized_head`.
* Let `get_ancestor(store, block, slot)` be the ancestor of `block` with slot number `slot`. The `get_ancestor` function can be defined recursively as `def get_ancestor(store, block, slot): return block if block.slot == slot else get_ancestor(store, store.get_parent(block), slot)`.
* Let `get_latest_attestation(store, validator)` be the attestation with the highest slot number in `store` from `validator`. If several such attestations exist, use the one the [validator](#dfn-validator) `v` observed first.
* Let `get_latest_attestation_target(store, validator)` be the target block in the attestation `get_latest_attestation(store, validator)`.
* The head is `lmd_ghost(store, justified_head)` where the function `lmd_ghost` is defined below. Note that the implementation below is suboptimal; there are implementations that compute the head in time logarithmic in slot count.

```python
def lmd_ghost(store, start):
    validators = start.state.validator_registry
    active_validators = [validators[i] for i in
                         get_active_validator_indices(validators, start.slot)]
    attestation_targets = [get_latest_attestation_target(store, validator)
                           for validator in active_validators]
    def get_vote_count(block):
        return len([target for target in attestation_targets if
                    get_ancestor(store, target, block.slot) == block])

    head = start
    while 1:
        children = get_children(head)
        if len(children) == 0:
            return head        
        head = max(children, key=get_vote_count)
```

## Beacon chain state transition function

We now define the state transition function. At a high level the state transition is made up of two parts:

1. The per-block processing, which happens every block, and only affects a few parts of the `state`.
2. The inter-epoch state recalculation, which happens only if `block.slot >= state.latest_state_recalculation_slot + EPOCH_LENGTH`, and affects the entire `state`.

The inter-epoch state recalculation generally focuses on changes to the [validator](#dfn-validator) registry, including adjusting balances and adding and removing [validators](#dfn-validator), as well as processing crosslinks and managing block justification/finalization, while the per-block processing generally focuses on verifying aggregate signatures and saving temporary records relating to the per-block activity in the `BeaconState`.

### Helper functions

Note: The definitions below are for specification purposes and are not necessarily optimal implementations.

#### `get_active_validator_indices`

```python
def get_active_validator_indices(validators: [ValidatorRecord]) -> List[int]:
    """
    Gets indices of active validators from ``validators``.
    """
    return [i for i, v in enumerate(validators) if v.status in [ACTIVE, PENDING_EXIT]]
```

#### `shuffle`

```python
def shuffle(values: List[Any], seed: Hash32) -> List[Any]:
    """
    Returns the shuffled ``values`` with ``seed`` as entropy.
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
            sample_from_source = int.from_bytes(source[position:position + rand_bytes], 'big')

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

#### `split`

```python
def split(values: List[Any], split_count: int) -> List[Any]:
    """
    Splits ``values`` into ``split_count`` pieces.
    """
    list_length = len(values)
    return [
        values[(list_length * i // split_count): (list_length * (i + 1) // split_count)]
        for i in range(split_count)
    ]
```

#### `clamp`

```python
def clamp(minval: int, maxval: int, x: int) -> int:
    """
    Clamps ``x`` between ``minval`` and ``maxval``.
    """
    if x <= minval:
        return minval
    elif x >= maxval:
        return maxval
    else:
        return x
```

#### `get_new_shuffling`

```python
def get_new_shuffling(seed: Hash32,
                      validators: List[ValidatorRecord],
                      crosslinking_start_shard: int) -> List[List[ShardAndCommittee]]:
    """
    Shuffles ``validators`` into shard committees using ``seed`` as entropy.
    """
    active_validator_indices = get_active_validator_indices(validators)

    committees_per_slot = clamp(
        1,
        SHARD_COUNT // EPOCH_LENGTH,
        len(active_validator_indices) // EPOCH_LENGTH // TARGET_COMMITTEE_SIZE,
    )

    # Shuffle with seed
    shuffled_active_validator_indices = shuffle(active_validator_indices, seed)

    # Split the shuffled list into epoch_length pieces
    validators_per_slot = split(shuffled_active_validator_indices, EPOCH_LENGTH)

    output = []
    for slot, slot_indices in enumerate(validators_per_slot):
        # Split the shuffled list into committees_per_slot pieces
        shard_indices = split(slot_indices, committees_per_slot)

        shard_id_start = crosslinking_start_shard + slot * committees_per_slot

        shards_and_committees_for_slot = [
            ShardAndCommittee(
                shard=(shard_id_start + shard_position) % SHARD_COUNT,
                committee=indices,
                total_validator_count=len(active_validator_indices),
            )
            for shard_position, indices in enumerate(shard_indices)
        ]
        output.append(shards_and_committees_for_slot)

    return output
```

Here's a diagram of what is going on:

![](http://vitalik.ca/files/ShuffleAndAssign.png?1)

#### `get_shard_and_committees_for_slot`

```python
def get_shard_and_committees_for_slot(state: BeaconState,
                                      slot: int) -> List[ShardAndCommittee]:
    """
    Returns the ``ShardAndCommittee`` for the ``slot``.
    """
    earliest_slot_in_array = state.latest_state_recalculation_slot - EPOCH_LENGTH
    assert earliest_slot_in_array <= slot < earliest_slot_in_array + EPOCH_LENGTH * 2
    return state.shard_and_committee_for_slots[slot - earliest_slot_in_array]
```

#### `get_block_hash`

```python
def get_block_hash(state: BeaconState,
                   current_block: BeaconBlock,
                   slot: int) -> Hash32:
    """
    Returns the block hash at a recent ``slot``.
    """
    earliest_slot_in_array = current_block.slot - len(state.latest_block_hashes)
    assert earliest_slot_in_array <= slot < current_block.slot
    return state.latest_block_hashes[slot - earliest_slot_in_array]
```

`get_block_hash(_, _, s)` should always return the block hash in the beacon chain at slot `s`, and `get_shard_and_committees_for_slot(_, s)` should not change unless the [validator](#dfn-validator) registry changes.

#### `get_beacon_proposer_index`

```python
def get_beacon_proposer_index(state:BeaconState, slot: int) -> int:
    """
    Returns the beacon proposer index for the ``slot``.
    """
    first_committee = get_shard_and_committees_for_slot(state, slot)[0].committee
    return first_committee[slot % len(first_committee)]
```

#### `get_attestation_participants`

```python
def get_attestation_participants(state: State,
                                 attestation_data: AttestationData,
                                 participation_bitfield: bytes) -> List[int]:
    """
    Returns the participant indices at for the ``attestation_data`` and ``participation_bitfield``.
    """
    sncs_for_slot = get_shard_and_committees_for_slot(state, attestation_data.slot)
    snc = [x for x in sncs_for_slot if x.shard == attestation_data.shard][0]
    assert len(participation_bitfield) == ceil_div8(len(snc.committee))
    participants = []
    for i, validator_index in enumerate(snc.committee):
        bit = (participation_bitfield[i//8] >> (7 - (i % 8))) % 2
        if bit == 1:
            participants.append(validator_index)
    return participants
```

#### `bytes1`, `bytes2`, ...

`bytes1(x): return x.to_bytes(1, 'big')`, `bytes2(x): return x.to_bytes(2, 'big')`, and so on for all integers, particularly 1, 2, 3, 4, 8, 32.


#### `get_effective_balance`

```python
def get_effective_balance(validator: ValidatorRecord) -> int:
    """
    Returns the effective balance (also known as "balance at stake") for the ``validator``.
    """
    return min(validator.balance, MAX_DEPOSIT)
```

#### `get_new_validator_registry_delta_chain_tip`

```python
def get_new_validator_registry_delta_chain_tip(current_validator_registry_delta_chain_tip: Hash32,
                                               index: int,
                                               pubkey: int,
                                               flag: int) -> Hash32:
    """
    Compute the next hash in the validator registry delta hash chain.
    """
    return hash(
        current_validator_registry_delta_chain_tip +
        bytes1(flag) +
        bytes3(index) +
        bytes32(pubkey)
    )
```

#### `integer_squareroot`

```python
def integer_squareroot(n: int) -> int:
    """
    The largest integer ``x`` such that ``x**2`` is less than ``n``.
    """
    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x
```

### On startup

A valid block with slot `INITIAL_SLOT_NUMBER` (a "genesis block") has the following values. Other validity rules (eg. requiring a signature) do not apply.

```python
{
    'slot': INITIAL_SLOT_NUMBER,
    'randao_reveal': ZERO_HASH,
    'candidate_pow_receipt_roots': [],
    'ancestor_hashes': [ZERO_HASH for i in range(32)],
    'state_root': STARTUP_STATE_ROOT,
    'attestations': [],
    'specials': [],
    'proposer_signature': [0, 0],
}
```

`STARTUP_STATE_ROOT` is the root of the initial state, computed by running the following code:

```python
def on_startup(initial_validator_entries: List[Any],
               genesis_time: int,
               processed_pow_receipt_root: Hash32) -> BeaconState:
    # Activate validators
    initial_validator_registry = []
    for pubkey, deposit, proof_of_possession, withdrawal_credentials, randao_commitment in initial_validator_entries:
        initial_validator_registry, _ = get_new_validators(
            current_validators=initial_validator_registry,
            fork_data=ForkData(
                pre_fork_version=INITIAL_FORK_VERSION,
                post_fork_version=INITIAL_FORK_VERSION,
                fork_slot=INITIAL_SLOT_NUMBER,
            ),
            pubkey=pubkey,
            deposit=deposit,
            proof_of_possession=proof_of_possession,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
            current_slot=INITIAL_SLOT_NUMBER,
            status=ACTIVE,
        )

    # Setup state
    initial_shuffling = get_new_shuffling(ZERO_HASH, initial_validator_registry, 0)
    state = BeaconState(
        validator_registry=initial_validator_registry,
        validator_registry_latest_change_slot=INITIAL_SLOT_NUMBER,
        validator_registry_exit_count=0,
        validator_registry_delta_chain_tip=ZERO_HASH,
        # Randomness and committees
        randao_mix=ZERO_HASH,
        next_seed=ZERO_HASH,
        shard_and_committee_for_slots=initial_shuffling + initial_shuffling,
        persistent_committees=split(shuffle(initial_validator_registry, ZERO_HASH), SHARD_COUNT),
        persistent_committee_reassignments=[],
        # Finality
        previous_justified_slot=INITIAL_SLOT_NUMBER,
        justified_slot=INITIAL_SLOT_NUMBER,
        justified_slot_bitfield=0,
        finalized_slot=INITIAL_SLOT_NUMBER,
        # Recent state
        latest_crosslinks=[CrosslinkRecord(slot=INITIAL_SLOT_NUMBER, hash=ZERO_HASH) for _ in range(SHARD_COUNT)],
        latest_state_recalculation_slot=INITIAL_SLOT_NUMBER,
        latest_block_hashes=[ZERO_HASH for _ in range(EPOCH_LENGTH * 2)],
        latest_penalized_exit_balances=[],
        latest_attestations=[],
        # PoW receipt root
        processed_pow_receipt_root=processed_pow_receipt_root,
        candidate_pow_receipt_roots=[],
        # Misc
        genesis_time=genesis_time,
        fork_data=ForkData(
            pre_fork_version=INITIAL_FORK_VERSION,
            post_fork_version=INITIAL_FORK_VERSION,
            fork_slot=INITIAL_SLOT_NUMBER,
        ),
    )

    return state
```

### Routine for adding a validator

This routine should be run for every [validator](#dfn-validator) that is activated as part of a log created on Ethereum 1.0 [TODO: explain where to check for these logs]. The status of the [validators](#dfn-validator) added after genesis is `PENDING_ACTIVATION`. These logs should be processed in the order in which they are emitted by Ethereum 1.0.

First, some helper functions:

```python
def min_empty_validator_index(validators: List[ValidatorRecord], current_slot: int) -> int:
    for i, v in enumerate(validators):
        if v.balance == 0 and v.latest_status_change_slot + DELETION_PERIOD <= current_slot:
            return i
    return None

def get_fork_version(fork_data: ForkData,
                     slot: int) -> int:
    if slot < fork_data.fork_slot:
        return fork_data.pre_fork_version
    else:
        return fork_data.post_fork_version

def get_domain(fork_data: ForkData,
               slot: int,
               domain_type: int) -> int:
    return get_fork_version(
        fork_data,
        slot
    ) * 2**32 + domain_type

def get_new_validators(validators: List[ValidatorRecord],
                       fork_data: ForkData,
                       pubkey: int,
                       deposit: int,
                       proof_of_possession: bytes,
                       withdrawal_credentials: Hash32,
                       randao_commitment: Hash32,
                       status: int,
                       current_slot: int) -> Tuple[List[ValidatorRecord], int]:
    assert BLSVerify(
        pub=pubkey,
        msg=hash(bytes32(pubkey) + withdrawal_credentials + randao_commitment),
        sig=proof_of_possession,
        domain=get_domain(
            fork_data,
            current_slot,
            DOMAIN_DEPOSIT
        )
    )
    validators_copy = copy.deepcopy(validators)
    validator_pubkeys = [v.pubkey for v in validators_copy]
    
    if pubkey not in validator_pubkeys:
        # Add new validator
        validator = ValidatorRecord(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
            randao_skips=0,
            balance=deposit,
            status=status,
            latest_status_change_slot=current_slot,
            exit_count=0
        )

        index = min_empty_validator_index(validators_copy)
        if index is None:
            validators_copy.append(validator)
            index = len(validators_copy) - 1
        else:
            validators_copy[index] = validator
    else:
        # Increase balance by deposit
        index = validator_pubkeys.index(pubkey)
        validator = validators_copy[index]
        assert validator.withdrawal_credentials == withdrawal_credentials

        validator.balance += deposit

    return validators_copy, index
```
`BLSVerify` is a function for verifying a BLS12-381 signature, defined in the [BLS12-381 spec](https://github.com/ethereum/eth2.0-specs/blob/master/specs/bls_verify.md).  
Now, to add a [validator](#dfn-validator) or top up an existing [validator](#dfn-validator)'s balance:

```python
def process_deposit(state: BeaconState,
                    pubkey: int,
                    deposit: int,
                    proof_of_possession: bytes,
                    withdrawal_credentials: Hash32,
                    randao_commitment: Hash32,
                    status: int,
                    current_slot: int) -> int:
    """
    Process a deposit from Ethereum 1.0.
    Note that this function mutates `state`.
    """
    state.validator_registry, index = get_new_validators(
        current_validators=state.validator_registry,
        fork_data=ForkData(
            pre_fork_version=state.fork_data.pre_fork_version,
            post_fork_version=state.fork_data.post_fork_version,
            fork_slot=state.fork_data.fork_slot,
        ),
        pubkey=pubkey,
        deposit=deposit,
        proof_of_possession=proof_of_possession,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        status=status,
        current_slot=current_slot,
    )

    return index
```


### Routine for removing a validator

```python
def exit_validator(index: int,
                   state: BeaconState,
                   penalize: bool,
                   current_slot: int) -> None:
    """
    Exit the validator with the given `index`.
    Note that this function mutates `state`.
    """
    state.validator_registry_exit_count += 1

    validator = state.validator_registry[index]
    validator.latest_status_change_slot = current_slot
    validator.exit_count = state.validator_registry_exit_count

    # Remove validator from persistent committees
    for committee in state.persistent_committees:
        for i, validator_index in committee:
            if validator_index == index:
                committee.pop(i)
                break

    if penalize:
        validator.status = EXITED_WITH_PENALTY
        state.latest_penalized_exit_balances[current_slot // COLLECTIVE_PENALTY_CALCULATION_PERIOD] += get_effective_balance(validator)
        
        whistleblower = state.validator_registry[get_beacon_proposer_index(state, current_slot)]
        whistleblower_reward = validator.balance // WHISTLEBLOWER_REWARD_QUOTIENT
        whistleblower.balance += whistleblower_reward
        validator.balance -= whistleblower_reward
    else:
        validator.status = PENDING_EXIT

    state.validator_registry_delta_chain_tip = get_new_validator_registry_delta_chain_tip(
        validator_registry_delta_chain_tip=state.validator_registry_delta_chain_tip,
        index=index,
        pubkey=validator.pubkey,
        flag=EXIT,
    )
```

## Per-block processing

This procedure should be carried out for every beacon block (denoted `block`).

* Let `parent_hash` be the hash of the immediate previous beacon block (ie. equal to `block.ancestor_hashes[0]`).
* Let `parent` be the beacon block with the hash `parent_hash`.

First, set `state.latest_block_hashes` to the output of the following:

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
                           parent_slot: int,
                           parent_hash: Hash32) -> List[Hash32]:
    new_ancestor_hashes = copy.copy(parent_ancestor_hashes)
    for i in range(32):
        if parent_slot % 2**i == 0:
            new_ancestor_hashes[i] = parent_hash
    return new_ancestor_hashes
```

### Verify attestations

* Verify that `len(block.attestations) <= MAX_ATTESTATIONS_PER_BLOCK`.

For each `attestation` in `block.attestations`:

* Verify that `attestation.data.slot <= block.slot - MIN_ATTESTATION_INCLUSION_DELAY`.
* Verify that `attestation.data.slot >= max(parent.slot - EPOCH_LENGTH + 1, 0)`.
* Verify that `attestation.data.justified_slot` is equal to `state.justified_slot if attestation.data.slot >= state.latest_state_recalculation_slot else state.previous_justified_slot`.
* Verify that `attestation.data.justified_block_hash` is equal to `get_block_hash(state, block, attestation.data.justified_slot)`.
* Verify that either `attestation.data.latest_crosslink_hash` or `attestation.data.shard_block_hash` equals `state.crosslinks[shard].shard_block_hash`.
* `aggregate_sig` verification:
    * Let `participants = get_attestation_participants(state, attestation.data, attestation.participation_bitfield)`.
    * Let `group_public_key = BLSAddPubkeys([state.validator_registry[v].pubkey for v in participants])`.
    * Verify that `BLSVerify(pubkey=group_public_key, msg=SSZTreeHash(attestation.data) + bytes1(0), sig=aggregate_sig, domain=get_domain(state.fork_data, slot, DOMAIN_ATTESTATION))`.
* [TO BE REMOVED IN PHASE 1] Verify that `shard_block_hash == ZERO_HASH`.
* Append `PendingAttestationRecord(data=attestation.data, participation_bitfield=attestation.participation_bitfield, custody_bitfield=attestation.custody_bitfield, slot_included=block.slot)` to `state.latest_attestations`.

### Verify proposer signature

* Let `block_hash_without_sig` be the hash of `block` where `proposer_signature` is set to `[0, 0]`.
* Let `proposal_hash = hash(ProposalSignedData(block.slot, BEACON_CHAIN_SHARD_NUMBER, block_hash_without_sig))`.
* Verify that `BLSVerify(pubkey=state.validator_registry[get_beacon_proposer_index(state, block.slot)].pubkey, data=proposal_hash, sig=block.proposer_signature, domain=get_domain(state.fork_data, block.slot, DOMAIN_PROPOSAL))`.

### Verify and process the RANDAO reveal

First run the following state transition to update `randao_skips` variables for the missing slots.

```python
for slot in range(parent.slot + 1, block.slot):
    proposer_index = get_beacon_proposer_index(state, slot)
    state.validator_registry[proposer_index].randao_skips += 1
```

Then:

* Let `repeat_hash(x, n) = x if n == 0 else repeat_hash(hash(x), n-1)`.
* Let `proposer = state.validator_registry[get_beacon_proposer_index(state, block.slot)]`.
* Verify that `repeat_hash(block.randao_reveal, proposer.randao_skips + 1) == proposer.randao_commitment`.
* Set `state.randao_mix = xor(state.randao_mix, block.randao_reveal)`.
* Set `proposer.randao_commitment = block.randao_reveal`.
* Set `proposer.randao_skips = 0`.

### Process PoW receipt root

If `block.candidate_pow_receipt_root` is `x.candidate_pow_receipt_root` for some `x` in `state.candidate_pow_receipt_roots`, set `x.votes += 1`. Otherwise, append to `state.candidate_pow_receipt_roots` a new `CandidatePoWReceiptRootRecord(candidate_pow_receipt_root=block.candidate_pow_receipt_root, votes=1)`.

### Process special objects

* Verify that the quantity of each type of object in `block.specials` is less than or equal to its maximum (see table at the top).
* Verify that objects are sorted in order of `kind`. That is, `block.specials[i+1].kind >= block.specials[i].kind` for `0 <= i < len(block.specials-1)`.

For each `special` in `block.specials`:

* Verify that `special.kind` is a valid value.
* Verify that `special.data` deserializes according to the format for the given `kind`.
* Process `special.data` as specified below for each kind.

#### `VOLUNTARY_EXIT`

```python
{
    'slot': 'unit64',
    'validator_index': 'uint64',
    'signature': '[uint384]',
}
```

* Let `validator = state.validator_registry[validator_index]`.
* Verify that `BLSVerify(pubkey=validator.pubkey, msg=ZERO_HASH, sig=signature, domain=get_domain(state.fork_data, slot, DOMAIN_EXIT))`.
* Verify that `validator.status == ACTIVE`.
* Verify that `block.slot >= slot`.
* Verify that `block.slot >= validator.latest_status_change_slot + SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD`.
* Run `exit_validator(validator_index, state, penalize=False, current_slot=block.slot)`.

#### `CASPER_SLASHING`

We define the following `SpecialAttestationData` object and the helper `verify_special_attestation_data`:
 
 ```python
{
    'aggregate_sig_poc_0_indices': '[uint24]',
    'aggregate_sig_poc_1_indices': '[uint24]',
    'data': AttestationData,
    'aggregate_sig': '[uint384]',
}
```

 ```python
def verify_special_attestation_data(state: State, obj: SpecialAttestationData) -> bool:
    pubs = [aggregate_pubkey([state.validators[i].pubkey for i in obj.aggregate_sig_poc_0_indices]),
            aggregate_pubkey([state.validators[i].pubkey for i in obj.aggregate_sig_poc_1_indices])]
    return BLSMultiVerify(pubkeys=pubs, msgs=[SSZTreeHash(obj)+bytes1(0), SSZTreeHash(obj)+bytes1(1), sig=aggregate_sig)
```

```python
{
    vote_1: SpecialAttestationData,
    vote_2: SpecialAttestationData,
}
```

* Verify that `verify_special_attestation_data(vote_1)`.
* Verify that `verify_special_attestation_data(vote_2)`.
* Verify that `vote_1.data != vote_2.data`.
* Let `indices(vote) = vote.aggregate_sig_poc_0_indices + vote.aggregate_sig_poc_1_indices`.
* Let `intersection = [x for x in indices(vote_1) if x in indices(vote_2)]`.
* Verify that `len(intersection) >= 1`.
* Verify that `vote_1.data.justified_slot + 1 < vote_2.data.justified_slot + 1 == vote_2.data.slot < vote_1.data.slot` or `vote_1.data.slot == vote_2.data.slot`.

For each [validator](#dfn-validator) index `i` in `intersection`, if `state.validator_registry[i].status` does not equal `EXITED_WITH_PENALTY`, then run `exit_validator(i, state, penalize=True, current_slot=block.slot)`

#### `PROPOSER_SLASHING`

```python
{
    'proposer_index': 'uint24',
    'proposal_data_1': ProposalSignedData,
    'proposal_signature_1': '[uint384]',
    'proposal_data_2': ProposalSignedData,
    'proposal_signature_2': '[uint384]',
}
```

* Verify that `BLSVerify(pubkey=state.validator_registry[proposer_index].pubkey, msg=hash(proposal_data_1), sig=proposal_signature_1, domain=get_domain(state.fork_data, proposal_data_1.slot, DOMAIN_PROPOSAL))`.
* Verify that `BLSVerify(pubkey=state.validator_registry[proposer_index].pubkey, msg=hash(proposal_data_2), sig=proposal_signature_2, domain=get_domain(state.fork_data, proposal_data_2.slot, DOMAIN_PROPOSAL))`.
* Verify that `proposal_data_1 != proposal_data_2`.
* Verify that `proposal_data_1.slot == proposal_data_2.slot`.
* Verify that `state.validator_registry[proposer_index].status != EXITED_WITH_PENALTY`.
* Run `exit_validator(proposer_index, state, penalize=True, current_slot=block.slot)`.

#### `DEPOSIT_PROOF`

```python
{
    'merkle_branch': '[hash32]',
    'merkle_tree_index': 'uint64',
    'deposit_data': {
        'deposit_parameters': DepositParametersRecord,
        'value': 'uint64',
        'timestamp': 'uint64'
    },
}
```

Let `serialized_deposit_data` be the serialized form of `deposit_data. It should be the `DepositParametersRecord` followed by 8 bytes for `deposit_data.value` and 8 bytes for `deposit_data.timestamp`. That is, it should match `deposit_data` in the [Ethereum 1.0 deposit contract](#ethereum-10-chain-deposit-contract) of which the hash was placed into the Merkle tree.

Use the following procedure to verify the `merkle_branch`, setting `leaf=serialized_deposit_data`, `depth=POW_CONTRACT_MERKLE_TREE_DEPTH` and `root=state.processed_pow_receipt_root`:

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

* Verify that `block.slot - (deposit_data.timestamp - state.genesis_time) // SLOT_DURATION < DELETION_PERIOD`.
* Run the following:

```python
process_deposit(
    state=state,
    pubkey=deposit_data.deposit_parameters.pubkey,
    deposit=deposit_data.value,
    proof_of_possession=deposit_data.deposit_parameters.proof_of_possession,
    withdrawal_credentials=deposit_data.deposit_parameters.withdrawal_credentials,
    randao_commitment=deposit_data.deposit_parameters.randao_commitment,
    status=PENDING_ACTIVATION,
    current_slot=block.slot
)
```

## Epoch boundary processing

Repeat the steps in this section while `block.slot - state.latest_state_recalculation_slot >= EPOCH_LENGTH`. For simplicity, we use `s` as `state.latest_state_recalculation_slot`.

Note that `state.latest_state_recalculation_slot` will always be a multiple of `EPOCH_LENGTH`. In the "happy case", this process will trigger, and loop once, every time `block.slot` passes a new exact multiple of `EPOCH_LENGTH`, but if a chain skips more than an entire epoch then the loop may run multiple times, incrementing `state.latest_state_recalculation_slot` by `EPOCH_LENGTH` with each iteration.

### Precomputation

All [validators](#dfn-validator):

* Let `active_validators = [state.validator_registry[i] for i in get_active_validator_indices(state.validator_registry)]`.
* Let `total_balance = sum([get_effective_balance(v) for v in active_validators])`. Let `total_balance_in_eth = total_balance // GWEI_PER_ETH`.
* Let `reward_quotient = BASE_REWARD_QUOTIENT * integer_squareroot(total_balance_in_eth)`. (The per-slot maximum interest rate is `2/reward_quotient`.)

[Validators](#dfn-Validator) justifying the epoch boundary block at the start of the current epoch:

* Let `this_epoch_attestations = [a for a in state.latest_attestations if s <= a.data.slot < s + EPOCH_LENGTH]`. (note: this is the set of attestations _of slots in the epoch `s...s+EPOCH_LENGTH-1`_, not attestations _that got included in the chain during the epoch `s...s+EPOCH_LENGTH-1`_)
* Let `this_epoch_boundary_attestations = [a for a in this_epoch_attestations if a.data.epoch_boundary_hash == get_block_hash(state, block, s) and a.justified_slot == state.justified_slot]`.
* Let `this_epoch_boundary_attesters` be the union of the [validator](#dfn-validator) index sets given by `[get_attestation_participants(state, a.data, a.participation_bitfield) for a in this_epoch_boundary_attestations]`.
* Let `this_epoch_boundary_attesting_balance = sum([get_effective_balance(v) for v in this_epoch_boundary_attesters])`.

[Validators](#dfn-Validator) justifying the epoch boundary block at the start of the previous epoch:

* Let `previous_epoch_attestations = [a for a in state.latest_attestations if s - EPOCH_LENGTH <= a.slot < s]`.
* Let `previous_epoch_boundary_attestations = [a for a in this_epoch_attestations + previous_epoch_attestations if a.epoch_boundary_hash == get_block_hash(state, block, s - EPOCH_LENGTH) and a.justified_slot == state.previous_justified_slot]`.
* Let `previous_epoch_boundary_attesters` be the union of the [validator](#dfn-validator) index sets given by `[get_attestation_participants(state, a.data, a.participation_bitfield) for a in previous_epoch_boundary_attestations]`.
* Let `previous_epoch_boundary_attesting_balance = sum([get_effective_balance(v) for v in previous_epoch_boundary_attesters])`.

For every `ShardAndCommittee` object `obj` in `state.shard_and_committee_for_slots`:

* Let `attesting_validators(obj, shard_block_hash)` be the union of the [validator](#dfn-validator) index sets given by `[get_attestation_participants(state, a.data, a.participation_bitfield) for a in this_epoch_attestations + previous_epoch_attestations if a.shard == obj.shard and a.shard_block_hash == shard_block_hash]`.
* Let `attesting_validators(obj)` be equal to `attesting_validators(obj, shard_block_hash)` for the value of `shard_block_hash` such that `sum([get_effective_balance(v) for v in attesting_validators(obj, shard_block_hash)])` is maximized (ties broken by favoring lower `shard_block_hash` values).
* Let `total_attesting_balance(obj)` be the sum of the balances-at-stake of `attesting_validators(obj)`.
* Let `winning_hash(obj)` be the winning `shard_block_hash` value.
* Let `total_balance(obj) = sum([get_effective_balance(v) for v in obj.committee])`.
    
Let `inclusion_slot(v)` equal `a.slot_included` for the attestation `a` where `v` is in `get_attestation_participants(state, a.data, a.participation_bitfield)`, and `inclusion_distance(v) = a.slot_included - a.data.slot` for the same attestation. We define a function `adjust_for_inclusion_distance(magnitude, distance)` which adjusts the reward of an attestation based on how long it took to get included (the longer, the lower the reward). Returns a value between 0 and `magnitude`.

```python
def adjust_for_inclusion_distance(magnitude: int, distance: int) -> int:
    return magnitude // 2 + (magnitude // 2) * MIN_ATTESTATION_INCLUSION_DELAY // distance
```

For any [validator](#dfn-validator) `v`, let `base_reward(v) = get_effective_balance(v) // reward_quotient`.

### Adjust justified slots and crosslink status

* Set `state.justified_slot_bitfield = (state.justified_slot_bitfield * 2) % 2**64`.
* If `3 * previous_epoch_boundary_attesting_balance >= 2 * total_balance` then set `state.justified_slot_bitfield &= 2` (ie. flip the second lowest bit to 1) and `new_justified_slot = s - EPOCH_LENGTH`.
* If `3 * this_epoch_boundary_attesting_balance >= 2 * total_balance` then set `state.justified_slot_bitfield &= 1` (ie. flip the lowest bit to 1) and `new_justified_slot = s`.
* If `state.justified_slot == s - EPOCH_LENGTH and state.justified_slot_bitfield % 4 == 3`, set `state.finalized_slot = state.justified_slot`.
* If `state.justified_slot == s - EPOCH_LENGTH - EPOCH_LENGTH and state.justified_slot_bitfield % 8 == 7`, set `state.finalized_slot = state.justified_slot`.
* If `state.justified_slot == s - EPOCH_LENGTH - 2 * EPOCH_LENGTH and state.justified_slot_bitfield % 16 in (15, 14)`, set `state.finalized_slot = state.justified_slot`.
* Set `state.previous_justified_slot = state.justified_slot` and if `new_justified_slot` has been set, set `state.justified_slot = new_justified_slot`.

For every `ShardAndCommittee` object `obj`:

* If `3 * total_attesting_balance(obj) >= 2 * total_balance(obj)`, set `crosslinks[shard] = CrosslinkRecord(slot=state.latest_state_recalculation_slot + EPOCH_LENGTH, hash=winning_hash(obj))`.

### Balance recalculations related to FFG rewards

Note: When applying penalties in the following balance recalculations implementers should make sure the `uint64` does not underflow.

* Let `inactivity_penalty_quotient = SQRT_E_DROP_TIME**2`. (The portion lost by offline [validators](#dfn-validator) after `D` epochs is about `D*D/2/inactivity_penalty_quotient`.)
* Let `time_since_finality = block.slot - state.finalized_slot`.

Case 1: `time_since_finality <= 4 * EPOCH_LENGTH`:

* Any [validator](#dfn-validator) `v` in `previous_epoch_boundary_attesters` gains `adjust_for_inclusion_distance(base_reward(v) * previous_epoch_boundary_attesting_balance // total_balance, inclusion_distance(v))`.
* Any [active validator](#dfn-active-validator) `v` not in `previous_epoch_boundary_attesters` loses `base_reward(v)`.

Case 2: `time_since_finality > 4 * EPOCH_LENGTH`:

* Any [validator](#dfn-validator) in `previous_epoch_boundary_attesters` sees their balance unchanged.
* Any [active validator](#dfn-active-validator) `v` not in `previous_epoch_boundary_attesters`, and any [validator](#dfn-validator) with `status == EXITED_WITH_PENALTY`, loses `base_reward(v) + get_effective_balance(v) * time_since_finality // inactivity_penalty_quotient`.

For each `v` in `previous_epoch_boundary_attesters`, we determine the proposer `proposer_index = get_beacon_proposer_index(state, inclusion_slot(v))` and set `state.validator_registry[proposer_index].balance += base_reward(v) // INCLUDER_REWARD_QUOTIENT`.

### Balance recalculations related to crosslink rewards

For every `ShardAndCommittee` object `obj` in `state.shard_and_committee_for_slots[:EPOCH_LENGTH]` (ie. the objects corresponding to the epoch before the current one), for each `v` in `[state.validator_registry[index] for index in obj.committee]`, adjust balances as follows:

* If `v in attesting_validators(obj)`, `v.balance += adjust_for_inclusion_distance(base_reward(v) * total_attesting_balance(obj) // total_balance(obj)), inclusion_distance(v))`.
* If `v not in attesting_validators(obj)`, `v.balance -= base_reward(v)`.

### Ethereum 1.0 chain related rules

If `state.latest_state_recalculation_slot % POW_RECEIPT_ROOT_VOTING_PERIOD == 0`, then:

* If for any `x` in `state.candidate_pow_receipt_root`,  `x.votes * 2 >= POW_RECEIPT_ROOT_VOTING_PERIOD` set `state.processed_pow_receipt_root = x.receipt_root`.
* Set `state.candidate_pow_receipt_roots = []`.

### Validator registry change

A [validator](#dfn-validator) registry change occurs if all of the following criteria are satisfied:

* `state.finalized_slot > state.validator_registry_latest_change_slot`
* For every shard number `shard` in `state.shard_and_committee_for_slots`, `crosslinks[shard].slot > state.validator_registry_latest_change_slot`

A helper function is defined as:

```python
def get_changed_validators(validators: List[ValidatorRecord],
                           latest_penalized_exit_balances: List[int],
                           validator_registry_delta_chain_tip: int,
                           current_slot: int) -> Tuple[List[ValidatorRecord], List[int], int]:
    """
    Return changed validator registry and `latest_penalized_exit_balances`, `validator_registry_delta_chain_tip`.
    """
    # The active validators
    active_validator_indices = get_active_validator_indices(validators)
    # The total balance of active validators
    total_balance = sum([get_effective_balance(v) for i, v in enumerate(validators) if i in active_validator_indices])
    # The maximum total Gwei that can be deposited and withdrawn
    max_allowable_change = max(
        2 * MAX_DEPOSIT * GWEI_PER_ETH,
        total_balance // MAX_CHURN_QUOTIENT
    )
    # Go through the list start to end, depositing and withdrawing as many as possible
    total_changed = 0
    for i in range(len(validators)):
        if validators[i].status == PENDING_ACTIVATION:
            validators[i].status = ACTIVE
            total_changed += get_effective_balance(validators[i])
            validator_registry_delta_chain_tip = get_new_validator_registry_delta_chain_tip(
                validator_registry_delta_chain_tip=validator_registry_delta_chain_tip,
                index=i,
                pubkey=validators[i].pubkey,
                flag=ACTIVATION,
            )
        if validators[i].status == EXITED_WITHOUT_PENALTY:
            validators[i].latest_status_change_slot = current_slot
            total_changed += get_effective_balance(validators[i])
            validator_registry_delta_chain_tip = get_new_validator_registry_delta_chain_tip(
                validator_registry_delta_chain_tip=validator_registry_delta_chain_tip,
                index=i,
                pubkey=validators[i].pubkey,
                flag=EXIT,
            )
        if total_changed >= max_allowable_change:
            break

    # Calculate the total ETH that has been penalized in the last ~2-3 withdrawal periods
    period_index = current_slot // COLLECTIVE_PENALTY_CALCULATION_PERIOD
    total_penalties = (
        (latest_penalized_exit_balances[period_index]) +
        (latest_penalized_exit_balances[period_index - 1] if period_index >= 1 else 0) +
        (latest_penalized_exit_balances[period_index - 2] if period_index >= 2 else 0)
    )

    # Calculate penalties for slashed validators
    def to_penalize(v):
        return v.status == EXITED_WITH_PENALTY
    validators_to_penalize = filter(to_penalize, validators)
    for v in validators_to_penalize:
        v.balance -= get_effective_balance(v) * min(total_penalties * 3, total_balance) // total_balance

    return validators, latest_penalized_exit_balances, validator_registry_delta_chain_tip
```

Then, run the following algorithm to update the [validator](#dfn-validator) registry:

```python
def change_validators(state: BeaconState,
                      current_slot: int) -> None:
    """
    Change validator registry.
    Note that this function mutates `state`.
    """
    state.validator_registry, state.latest_penalized_exit_balances = get_changed_validators(
        copy.deepcopy(state.validator_registry),
        copy.deepcopy(state.latest_penalized_exit_balances),
        state.validator_registry_delta_chain_tip,
        current_slot
    )
```

And perform the following updates to the `state`:

* Set `state.validator_registry_latest_change_slot = s + EPOCH_LENGTH`.
* Set `state.shard_and_committee_for_slots[:EPOCH_LENGTH] = state.shard_and_committee_for_slots[EPOCH_LENGTH:]`.
* Let `state.next_start_shard = (state.shard_and_committee_for_slots[-1][-1].shard + 1) % SHARD_COUNT`.
* Set `state.shard_and_committee_for_slots[EPOCH_LENGTH:] = get_new_shuffling(state.next_seed, state.validator_registry, next_start_shard)`.
* Set `state.next_seed = state.randao_mix`.

### If a validator registry change does NOT happen

* Set `state.shard_and_committee_for_slots[:EPOCH_LENGTH] = state.shard_and_committee_for_slots[EPOCH_LENGTH:]`.
* Let `time_since_finality = block.slot - state.validator_registry_latest_change_slot`.
* Let `start_shard = state.shard_and_committee_for_slots[0][0].shard`.
* If `time_since_finality * EPOCH_LENGTH <= MIN_VALIDATOR_REGISTRY_CHANGE_INTERVAL` or `time_since_finality` is an exact power of 2, set `state.shard_and_committee_for_slots[EPOCH_LENGTH:] = get_new_shuffling(state.next_seed, state.validator_registry, start_shard)` and set `state.next_seed = state.randao_mix`. Note that `start_shard` is not changed from the last epoch.

### Proposer reshuffling

Run the following code to update the shard proposer set:

```python
active_validator_indices = get_active_validator_indices(state.validator_registry)
num_validators_to_reshuffle = len(active_validator_indices) // SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD
for i in range(num_validators_to_reshuffle):
    # Multiplying i to 2 to ensure we have different input to all the required hashes in the shuffling
    # and none of the hashes used for entropy in this loop will be the same
    validator_index = active_validator_indices[hash(state.randao_mix + bytes8(i * 2)) % len(active_validator_indices)]
    new_shard = hash(state.randao_mix + bytes8(i * 2 + 1)) % SHARD_COUNT
    shard_reassignment_record = ShardReassignmentRecord(
        validator_index=validator_index,
        shard=new_shard,
        slot=s + SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD
    )
    state.persistent_committee_reassignments.append(shard_reassignment_record)

while len(state.persistent_committee_reassignments) > 0 and state.persistent_committee_reassignments[0].slot <= s:
    reassignment = state.persistent_committee_reassignments.pop(0)
    for committee in state.persistent_committees:
        if reassignment.validator_index in committee:
            committee.pop(committee.index(reassignment.validator_index))
    state.persistent_committees[reassignment.shard].append(reassignment.validator_index)
```

### Finally...

* Remove all attestation records older than slot `s`.
* For any [validator](#dfn-validator) with index `i` with balance less than `MIN_BALANCE` and status `ACTIVE`, run `exit_validator(i, state, penalize=False, current_slot=block.slot)`.
* Set `state.latest_block_hashes = state.latest_block_hashes[EPOCH_LENGTH:]`.
* Set `state.latest_state_recalculation_slot += EPOCH_LENGTH`.

# Appendix
## Appendix A - Hash function

We aim to have a STARK-friendly hash function `hash(x)` for the production launch of the beacon chain. While the standardisation process for a STARK-friendly hash function takes place—led by STARKware, who will produce a detailed report with recommendations—we use `BLAKE2b-512` as a placeholder. Specifically, we set `hash(x) := BLAKE2b-512(x)[0:32]` where the `BLAKE2b-512` algorithm is defined in [RFC 7693](https://tools.ietf.org/html/rfc7693) and the input `x` is of type `bytes`.

# References

This section is divided into Normative and Informative references.  Normative references are those that must be read in order to implement this specification, while Informative references are merely that, information.  An example of the former might be the details of a required consensus algorithm, and an example of the latter might be a pointer to research that demonstrates why a particular consensus algorithm might be better suited for inclusion in the standard than another.

## Normative

## Informative
<a id="ref-python-poc"></a> _**python-poc**_  
 &nbsp; _Python proof-of-concept implementation_. Ethereum Foundation. URL: https://github.com/ethereum/beacon_chain

# Copyright
Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
