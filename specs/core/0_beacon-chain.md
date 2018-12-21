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
        - [Misc](#misc)
        - [Deposit contract](#deposit-contract)
        - [Initial values](#initial-values)
        - [Time parameters](#time-parameters)
        - [Reward and penalty quotients](#reward-and-penalty-quotients)
        - [Status codes](#status-codes)
        - [Max operations per block](#max-operations-per-block)
        - [Validator registry delta flags](#validator-registry-delta-flags)
        - [Signature domains](#signature-domains)
    - [Data structures](#data-structures)
        - [Beacon chain operations](#beacon-chain-operations)
            - [Proposer slashings](#proposer-slashings)
                - [`ProposerSlashing`](#proposerslashing)
            - [Casper slashings](#casper-slashings)
                - [`CasperSlashing`](#casperslashing)
                - [`SlashableVoteData`](#slashablevotedata)
            - [Attestations](#attestations)
                - [`Attestation`](#attestation)
                - [`AttestationData`](#attestationdata)
            - [Deposits](#deposits)
                - [`Deposit`](#deposit)
                - [`DepositData`](#depositdata)
                - [`DepositInput`](#depositinput)
            - [Exits](#exits)
                - [`Exit`](#exit)
        - [Beacon chain blocks](#beacon-chain-blocks)
            - [`BeaconBlock`](#beaconblock)
            - [`BeaconBlockBody`](#beaconblockbody)
            - [`ProposalSignedData`](#proposalsigneddata)
        - [Beacon chain state](#beacon-chain-state)
            - [`BeaconState`](#beaconstate)
            - [`ValidatorRecord`](#validatorrecord)
            - [`CrosslinkRecord`](#crosslinkrecord)
            - [`ShardCommittee`](#shardcommittee)
            - [`ShardReassignmentRecord`](#shardreassignmentrecord)
            - [`CandidatePoWReceiptRootRecord`](#candidatepowreceiptrootrecord)
            - [`PendingAttestationRecord`](#pendingattestationrecord)
            - [`ForkData`](#forkdata)
            - [`ValidatorRegistryDeltaBlock`](#validatorregistrydeltablock)
    - [Ethereum 1.0 deposit contract](#ethereum-10-deposit-contract)
        - [Deposit arguments](#deposit-arguments)
        - [`Eth1Deposit` logs](#eth1deposit-logs)
        - [`ChainStart` log](#chainstart-log)
        - [Vyper code](#vyper-code)
    - [Beacon chain processing](#beacon-chain-processing)
        - [Beacon chain fork choice rule](#beacon-chain-fork-choice-rule)
    - [Beacon chain state transition function](#beacon-chain-state-transition-function)
        - [Helper functions](#helper-functions)
            - [`hash`](#hash)
            - [`hash_tree_root`](#hash_tree_root)
            - [`is_active_validator`](#is_active_validator)
            - [`get_active_validator_indices`](#get_active_validator_indices)
            - [`shuffle`](#shuffle)
            - [`split`](#split)
            - [`get_new_shuffling`](#get_new_shuffling)
            - [`get_shard_committees_at_slot`](#get_shard_committees_at_slot)
            - [`get_block_root`](#get_block_root)
            - [`get_beacon_proposer_index`](#get_beacon_proposer_index)
            - [`merkle_root`](#merkle_root)
            - [`get_attestation_participants`](#get_attestation_participants)
            - [`bytes1`, `bytes2`, ...](#bytes1-bytes2-)
            - [`get_effective_balance`](#get_effective_balance)
            - [`get_new_validator_registry_delta_chain_tip`](#get_new_validator_registry_delta_chain_tip)
            - [`get_fork_version`](#get_fork_version)
            - [`get_domain`](#get_domain)
            - [`verify_slashable_vote_data`](#verify_slashable_vote_data)
            - [`is_double_vote`](#is_double_vote)
            - [`is_surround_vote`](#is_surround_vote)
            - [`integer_squareroot`](#integer_squareroot)
            - [`bls_verify`](#bls_verify)
            - [`bls_verify_multiple`](#bls_verify_multiple)
            - [`bls_aggregate_pubkeys`](#bls_aggregate_pubkeys)
        - [On startup](#on-startup)
        - [Routine for processing deposits](#routine-for-processing-deposits)
        - [Routine for updating validator status](#routine-for-updating-validator-status)
    - [Per-slot processing](#per-slot-processing)
        - [Misc counters](#misc-counters)
        - [Block roots](#block-roots)
    - [Per-block processing](#per-block-processing)
        - [Slot](#slot)
        - [Proposer signature](#proposer-signature)
        - [RANDAO](#randao)
        - [PoW receipt root](#pow-receipt-root)
        - [Operations](#operations)
            - [Proposer slashings](#proposer-slashings-1)
            - [Casper slashings](#casper-slashings-1)
            - [Attestations](#attestations-1)
            - [Deposits](#deposits-1)
            - [Exits](#exits-1)
            - [Miscellaneous](#miscellaneous)
    - [Per-epoch processing](#per-epoch-processing)
        - [Helpers](#helpers)
        - [Receipt roots](#receipt-roots)
        - [Justification](#justification)
        - [Finalization](#finalization)
        - [Crosslinks](#crosslinks)
        - [Rewards and penalties](#rewards-and-penalties)
            - [Justification and finalization](#justification-and-finalization)
            - [Attestation inclusion](#attestation-inclusion)
            - [Crosslinks](#crosslinks-1)
        - [Ejections](#ejections)
        - [Validator registry](#validator-registry)
        - [Proposer reshuffling](#proposer-reshuffling)
        - [Final updates](#final-updates)
    - [State root processing](#state-root-processing)
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
* **Block root** - a 32-byte Merkle root of a beacon chain block or shard chain block. Previously called "block hash".
* **Crosslink** - a set of signatures from a committee attesting to a block in a shard chain, which can be included into the beacon chain. Crosslinks are the main means by which the beacon chain "learns about" the updated state of shard chains.
* **Slot** - a period of `SLOT_DURATION` seconds, during which one proposer has the ability to create a beacon chain block and some attesters have the ability to make attestations
* **Epoch** - an aligned span of slots during which all [validators](#dfn-validator) get exactly one chance to make an attestation
* **Finalized**, **justified** - see Casper FFG finalization [[casper-ffg]](#ref-casper-ffg)
* **Withdrawal period** - the number of slots between a [validator](#dfn-validator) exit and the [validator](#dfn-validator) balance being withdrawable
* **Genesis time** - the Unix time of the genesis beacon chain block at slot 0

## Constants

### Misc

| Name | Value | Unit |
| - | - | :-: |
| `SHARD_COUNT` | `2**10` (= 1,024) | shards |
| `TARGET_COMMITTEE_SIZE` | `2**8` (= 256) | [validators](#dfn-validator) |
| `EJECTION_BALANCE` | `2**4` (= 16) | ETH |
| `MAX_BALANCE_CHURN_QUOTIENT` | `2**5` (= 32) | - |
| `GWEI_PER_ETH` | `10**9` | Gwei/ETH |
| `BEACON_CHAIN_SHARD_NUMBER` | `2**64 - 1` | - |
| `BLS_WITHDRAWAL_PREFIX_BYTE` | `0x00` | - |
| `MAX_CASPER_VOTES` | `2**10` (= 1,024) | votes |
| `LATEST_BLOCK_ROOTS_LENGTH` | `2**13` (= 8,192) | block roots |
| `LATEST_RANDAO_MIXES_LENGTH` | `2**13` (= 8,192) | randao mixes |
| `EMPTY_SIGNATURE` | `[bytes48(0), bytes48(0)]` | - |

* For the safety of crosslinks a minimum committee size of 111 is [recommended](https://vitalik.ca/files/Ithaca201807_Sharding.pdf). (Unbiasable randomness with a Verifiable Delay Function (VDF) will improve committee robustness and lower the safe minimum committee size.) The shuffling algorithm generally ensures (assuming sufficient validators) committee sizes at least `TARGET_COMMITTEE_SIZE // 2`.

### Deposit contract

| Name | Value | Unit |
| - | - | :-: |
| `DEPOSIT_CONTRACT_ADDRESS` | **TBD** |
| `DEPOSIT_CONTRACT_TREE_DEPTH` | `2**5` (= 32) | - |
| `MIN_DEPOSIT` | `2**0` (= 1) | ETH |
| `MAX_DEPOSIT` | `2**5` (= 32) | ETH |

### Initial values

| Name | Value |
| - | - |
| `INITIAL_FORK_VERSION` | `0` |
| `INITIAL_SLOT_NUMBER` | `0` |
| `ZERO_HASH` | `bytes([0] * 32)` |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SLOT_DURATION` | `6` | seconds | 6 seconds |
| `MIN_ATTESTATION_INCLUSION_DELAY` | `2**2` (= 4) | slots | 24 seconds |
| `EPOCH_LENGTH` | `2**6` (= 64) | slots | 6.4 minutes |
| `POW_RECEIPT_ROOT_VOTING_PERIOD` | `2**10` (= 1,024) | slots | ~1.7 hours |
| `SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD` | `2**17` (= 131,072) | slots | ~9 days |
| `COLLECTIVE_PENALTY_CALCULATION_PERIOD` | `2**20` (= 1,048,576) | slots | ~73 days |
| `ZERO_BALANCE_VALIDATOR_TTL` | `2**22` (= 4,194,304) | slots | ~291 days |

### Reward and penalty quotients

| Name | Value |
| - | - |
| `BASE_REWARD_QUOTIENT` | `2**10` (= 1,024) |
| `WHISTLEBLOWER_REWARD_QUOTIENT` | `2**9` (= 512) |
| `INCLUDER_REWARD_QUOTIENT` | `2**3` (= 8) |
| `INACTIVITY_PENALTY_QUOTIENT` | `2**34` (= 17,179,869,184) |

* The `BASE_REWARD_QUOTIENT` parameter dictates the per-epoch reward. It corresponds to ~2.54% annual interest assuming 10 million participating ETH in every epoch.
* The `INACTIVITY_PENALTY_QUOTIENT` equals `INVERSE_SQRT_E_DROP_TIME**2` where `INVERSE_SQRT_E_DROP_TIME := 2**17 slots` (~9 days) is the time it takes the inactivity penalty to reduce the balance of non-participating [validators](#dfn-validator) to about `1/sqrt(e) ~= 60.6%`. Indeed, the balance retained by offline [validators](#dfn-validator) after `n` slots is about `(1-1/INACTIVITY_PENALTY_QUOTIENT)**(n**2/2)` so after `INVERSE_SQRT_E_DROP_TIME` slots it is roughly `(1-1/INACTIVITY_PENALTY_QUOTIENT)**(INACTIVITY_PENALTY_QUOTIENT/2) ~= 1/sqrt(e)`.

### Status codes

| Name | Value |
| - | - |
| `PENDING_ACTIVATION` | `0` |
| `ACTIVE` | `1` |
| `ACTIVE_PENDING_EXIT` | `2` |
| `EXITED_WITHOUT_PENALTY` | `3` |
| `EXITED_WITH_PENALTY` | `4` |

### Max operations per block

| Name | Value |
| - | - |
| `MAX_PROPOSER_SLASHINGS` | `2**4` (= 16) |
| `MAX_CASPER_SLASHINGS` | `2**4` (= 16) |
| `MAX_ATTESTATIONS` | `2**7` (= 128) |
| `MAX_DEPOSITS` | `2**4` (= 16) |
| `MAX_EXITS` | `2**4` (= 16) |

### Validator registry delta flags

| Name | Value |
| - | - |
| `ACTIVATION` | `0` |
| `EXIT` | `1` |

### Signature domains

| Name | Value |
| - | - |
| `DOMAIN_DEPOSIT` | `0` |
| `DOMAIN_ATTESTATION` | `1` |
| `DOMAIN_PROPOSAL` | `2` |
| `DOMAIN_EXIT` | `3` |

## Data structures

### Beacon chain operations

#### Proposer slashings

##### `ProposerSlashing`

```python
{
    # Proposer index
    'proposer_index': 'uint24',
    # First proposal data
    'proposal_data_1': ProposalSignedData,
    # First proposal signature
    'proposal_signature_1': '[uint384]',
    # Second proposal data
    'proposal_data_2': ProposalSignedData,
    # Second proposal signature
    'proposal_signature_2': '[uint384]',
}
```

#### Casper slashings

##### `CasperSlashing`

```python
{
    # First batch of votes
    'slashable_vote_data_1': SlashableVoteData,
    # Second batch of votes
    'slashable_vote_data_2': SlashableVoteData,
}
```

##### `SlashableVoteData`

```python
{
    # Proof-of-custody indices (0 bits)
    'aggregate_signature_poc_0_indices': '[uint24]',
    # Proof-of-custody indices (1 bits)
    'aggregate_signature_poc_1_indices': '[uint24]',
    # Attestation data
    'data': AttestationData,
    # Aggregate signature
    'aggregate_signature': '[uint384]',
}
```

#### Attestations

##### `Attestation`

```python
{
    # Attestation data
    'data': AttestationData,
    # Attester participation bitfield
    'participation_bitfield': 'bytes',
    # Proof of custody bitfield
    'custody_bitfield': 'bytes',
    # BLS aggregate signature
    'aggregate_signature': ['uint384'],
}
```

##### `AttestationData`

```python
{
    # Slot number
    'slot': 'uint64',
    # Shard number
    'shard': 'uint64',
    # Hash of root of the signed beacon block
    'beacon_block_root': 'hash32',
    # Hash of root of the ancestor at the epoch boundary
    'epoch_boundary_root': 'hash32',
    # Shard block's hash of root
    'shard_block_root': 'hash32',
    # Last crosslink's hash of root
    'latest_crosslink_root': 'hash32',
    # Slot of the last justified beacon block
    'justified_slot': 'uint64',
    # Hash of the last justified beacon block
    'justified_block_root': 'hash32',
}
```

#### Deposits

##### `Deposit`

```python
{
    # Receipt Merkle branch
    'merkle_branch': '[hash32]',
    # Merkle tree index
    'merkle_tree_index': 'uint64',
    # Deposit data
    'deposit_data': DepositData,
}
```

##### `DepositData`

```python
{
    # Deposit parameters
    'deposit_input': DepositInput,
    # Value in Gwei
    'value': 'uint64',
    # Timestamp from deposit contract
    'timestamp': 'uint64',
}
```

##### `DepositInput`

```python
{
    # BLS pubkey
    'pubkey': 'uint384',
    # Withdrawal credentials
    'withdrawal_credentials': 'hash32',
    # Initial RANDAO commitment
    'randao_commitment': 'hash32',
    # a BLS signature of this ``DepositInput``
    'proof_of_possession': ['uint384'],
}
```

#### Exits

##### `Exit`

```python
{
    # Minimum slot for processing exit
    'slot': 'uint64',
    # Index of the exiting validator
    'validator_index': 'uint24',
    # Validator signature
    'signature': '[uint384]',
}
```

### Beacon chain blocks

#### `BeaconBlock`

```python
{
    ## Header ##
    'slot': 'uint64',
    'parent_root': 'hash32',
    'state_root': 'hash32',
    'randao_reveal': 'hash32',
    'candidate_pow_receipt_root': 'hash32',
    'signature': ['uint384'],

    ## Body ##
    'body': BeaconBlockBody,
}
```

#### `BeaconBlockBody`

`ProofOfCustodySeedChange`, `ProofOfCustodyChallenge`, and `ProofOfCustodyResponse` will be defined in phase 1; for now, put dummy classes as these lists will remain empty throughout phase 0.

```python
{
    'proposer_slashings': [ProposerSlashing],
    'casper_slashings': [CasperSlashing],
    'attestations': [Attestation],
    'poc_seed_changes': [ProofOfCustodySeedChange],
    'poc_challenges': [ProofOfCustodyChallenge],
    'poc_responses': [ProofOfCustodyResponse],
    'deposits': [Deposit],
    'exits': [Exit],
}
```

#### `ProposalSignedData`

```python
{
    # Slot number
    'slot': 'uint64',
    # Shard number (`BEACON_CHAIN_SHARD_NUMBER` for beacon chain)
    'shard': 'uint64',
    # Block's hash of root
    'block_root': 'hash32',
}
```

### Beacon chain state

#### `BeaconState`

```python
{
    # Misc
    'slot': 'uint64',
    'genesis_time': 'uint64',
    'fork_data': ForkData,  # For versioning hard forks

    # Validator registry
    'validator_registry': [ValidatorRecord],
    'validator_balances': ['uint64'],
    'validator_registry_latest_change_slot': 'uint64',
    'validator_registry_exit_count': 'uint64',
    'validator_registry_delta_chain_tip': 'hash32',  # For light clients to track deltas

    # Randomness and committees
    'latest_randao_mixes': ['hash32'],
    'shard_committees_at_slots': [[ShardCommittee]],
    'persistent_committees': [['uint24']],
    'persistent_committee_reassignments': [ShardReassignmentRecord],

    # Proof of custody
    # Placeholders for now; ProofOfCustodyChallenge is defined in phase 1, implementers can
    # put a dummy class in for now, as the list will remain empty throughout phase 0
    'poc_challenges': [ProofOfCustodyChallenge],
    # Proof of custody commitment
    'poc_commitment': 'hash32',
    # Slot the proof of custody seed was last changed
    'last_poc_change_slot': 'uint64',
    'second_last_poc_change_slot': 'uint64',

    # Finality
    'previous_justified_slot': 'uint64',
    'justified_slot': 'uint64',
    'justification_bitfield': 'uint64',
    'finalized_slot': 'uint64',

    # Recent state
    'latest_crosslinks': [CrosslinkRecord],
    'latest_block_roots': ['hash32'],  # Needed to process attestations, older to newer
    'latest_penalized_exit_balances': ['uint64'],  # Balances penalized at every withdrawal period
    'latest_attestations': [PendingAttestationRecord],
    'batched_block_roots': ['hash32'],

    # PoW receipt root
    'processed_pow_receipt_root': 'hash32',
    'candidate_pow_receipt_roots': [CandidatePoWReceiptRootRecord],
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
    # Slots the proposer has skipped (i.e. layers of RANDAO expected)
    'randao_layers': 'uint64',
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
    # Shard block root
    'shard_block_root': 'hash32',
}
```

#### `ShardCommittee`

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
    'vote_count': 'uint64',
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

#### `ValidatorRegistryDeltaBlock`

```python
{
    latest_registry_delta_root: 'hash32',
    validator_index: 'uint24',
    pubkey: 'uint384',
    flag: 'uint64',
}
```

## Ethereum 1.0 deposit contract

The initial deployment phases of Ethereum 2.0 are implemented without consensus changes to Ethereum 1.0. A deposit contract at address `DEPOSIT_CONTRACT_ADDRESS` is added to Ethereum 1.0 for deposits of ETH to the beacon chain. Validator balances will be withdrawable to the shards when the EVM2.0 is deployed and the shards have state.

### Deposit arguments

The deposit contract has a single `deposit` function which takes as argument a SimpleSerialize'd `DepositInput`. One of the `DepositInput` fields is `withdrawal_credentials` which must satisfy:

* `withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX_BYTE`
* `withdrawal_credentials[1:] == hash(withdrawal_pubkey)[1:]` where `withdrawal_pubkey` is a BLS pubkey

We recommend the private key corresponding to `withdrawal_pubkey` be stored in cold storage until a withdrawal is required.

### `Eth1Deposit` logs

Every deposit, of size between `MIN_DEPOSIT` and `MAX_DEPOSIT`, emits an `Eth1Deposit` log for consumption by the beacon chain. The deposit contract does little validation, pushing most of the validator onboarding logic to the beacon chain. In particular, the proof of possession (a BLS12-381 signature) is not verified by the deposit contract.

### `ChainStart` log

When sufficiently many full deposits have been made the deposit contract emits the `ChainStart` log. The beacon chain state may then be initialized by calling the `get_initial_beacon_state` function (defined below) where:

* `genesis_time` equals `time` in the `ChainStart` log
* `processed_pow_receipt_root` equals `receipt_root` in the `ChainStart` log
* `initial_validator_deposits` is a list of `Deposit` objects built according to the `Eth1Deposit` logs up to the deposit that triggered the `ChainStart` log, processed in the order in which they were emitted (oldest to newest)

### Vyper code

```python
## compiled with v0.1.0-beta.4 ##

MIN_DEPOSIT: constant(uint256) = 1  # ETH
MAX_DEPOSIT: constant(uint256) = 32  # ETH
GWEI_PER_ETH: constant(uint256) = 1000000000  # 10**9
CHAIN_START_FULL_DEPOSIT_THRESHOLD: constant(uint256) = 16384  # 2**14
DEPOSIT_CONTRACT_TREE_DEPTH: constant(uint256) = 32
TWO_TO_POWER_OF_TREE_DEPTH: constant(uint256) = 4294967296  # 2**32
SECONDS_PER_DAY: constant(uint256) = 86400

Eth1Deposit: event({previous_receipt_root: bytes32, data: bytes[2064], deposit_count: uint256})
ChainStart: event({receipt_root: bytes32, time: bytes[8]})

receipt_tree: bytes32[uint256]
deposit_count: uint256
full_deposit_count: uint256

@payable
@public
def deposit(deposit_input: bytes[2048]):
    assert msg.value >= as_wei_value(MIN_DEPOSIT, "ether")
    assert msg.value <= as_wei_value(MAX_DEPOSIT, "ether")

    index: uint256 = self.deposit_count + TWO_TO_POWER_OF_TREE_DEPTH
    msg_gwei_bytes8: bytes[8] = slice(concat("", convert(msg.value / GWEI_PER_ETH, bytes32)), start=24, len=8)
    timestamp_bytes8: bytes[8] = slice(concat("", convert(block.timestamp, bytes32)), start=24, len=8)
    deposit_data: bytes[2064] = concat(msg_gwei_bytes8, timestamp_bytes8, deposit_input)

    log.Eth1Deposit(self.receipt_tree[1], deposit_data, self.deposit_count)

    # add deposit to merkle tree
    self.receipt_tree[index] = sha3(deposit_data)
    for i in range(32):  # DEPOSIT_CONTRACT_TREE_DEPTH (range of constant var not yet supported)
        index /= 2
        self.receipt_tree[index] = sha3(concat(self.receipt_tree[index * 2], self.receipt_tree[index * 2 + 1]))

    self.deposit_count += 1
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

## Beacon chain processing

The beacon chain is the system chain for Ethereum 2.0. The main responsibilities of the beacon chain are:

* Store and maintain the registry of [validators](#dfn-validator)
* Process crosslinks (see above)
* Process its per-slot consensus, as well as the finality gadget

Processing the beacon chain is similar to processing the Ethereum 1.0 chain. Clients download and process blocks, and maintain a view of what is the current "canonical chain", terminating at the current "head". However, because of the beacon chain's relationship with Ethereum 1.0, and because it is a proof-of-stake chain, there are differences.

For a beacon chain block, `block`, to be processed by a node, the following conditions must be met:

* The parent block with root `block.parent_root` has been processed and accepted.
* The node has processed its `state` up to slot, `block.slot - 1`.
* The Ethereum 1.0 block pointed to by the `state.processed_pow_receipt_root` has been processed and accepted.
* The node's local clock time is greater than or equal to `state.genesis_time + block.slot * SLOT_DURATION`.

If these conditions are not met, the client should delay processing the beacon block until the conditions are all satisfied.

Beacon block production is significantly different because of the proof of stake mechanism. A client simply checks what it thinks is the canonical chain when it should create a block, and looks up what its slot number is; when the slot arrives, it either proposes or attests to a block as required. Note that this requires each node to have a clock that is roughly (i.e. within `SLOT_DURATION` seconds) synchronized with the other nodes.

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
                         get_active_validator_indices(validators)]
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

1. The per-slot transitions, which happens every slot, and only affects a parts of the `state`.
2. The per-epoch transitions, which happens at every epoch boundary (i.e. `state.slot % EPOCH_LENGTH == 0`), and affects the entire `state`.

The per-slot transitions generally focus on verifying aggregate signatures and saving temporary records relating to the per-slot activity in the `BeaconState`. The per-epoch transitions focus on the [validator](#dfn-validator) registry, including adjusting balances and activating and exiting [validators](#dfn-validator), as well as processing crosslinks and managing block justification/finalization.

### Helper functions

Note: The definitions below are for specification purposes and are not necessarily optimal implementations.

#### `hash`

The hash function is denoted by `hash`. In Phase 0 the beacon chain is deployed with the same hash function as Ethereum 1.0, i.e. Keccak-256 (also incorrectly known as SHA3).

Note: We aim to migrate to a S[T/N]ARK-friendly hash function in a future Ethereum 2.0 deployment phase.

#### `hash_tree_root`

`hash_tree_root` is a function for hashing objects into a single root utilizing a hash tree structure. `hash_tree_root` is defined in the [SimpleSerialize spec](https://github.com/ethereum/eth2.0-specs/blob/master/specs/simple-serialize.md#tree-hash).

#### `is_active_validator`
```python
def is_active_validator(validator: ValidatorRecord) -> bool:
    """
    Checks if ``validator`` is active.
    """
    return validator.status in [ACTIVE, ACTIVE_PENDING_EXIT]
```

#### `get_active_validator_indices`

```python
def get_active_validator_indices(validators: [ValidatorRecord]) -> List[int]:
    """
    Gets indices of active validators from ``validators``.
    """
    return [i for i, v in enumerate(validators) if is_active_validator(v)]
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

#### `get_new_shuffling`

```python
def get_new_shuffling(seed: Hash32,
                      validators: List[ValidatorRecord],
                      crosslinking_start_shard: int) -> List[List[ShardCommittee]]:
    """
    Shuffles ``validators`` into shard committees using ``seed`` as entropy.
    """
    active_validator_indices = get_active_validator_indices(validators)

    committees_per_slot = max(
        1,
        min(
            SHARD_COUNT // EPOCH_LENGTH,
            len(active_validator_indices) // EPOCH_LENGTH // TARGET_COMMITTEE_SIZE,   
        )
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

        shard_committees = [
            ShardCommittee(
                shard=(shard_id_start + shard_position) % SHARD_COUNT,
                committee=indices,
                total_validator_count=len(active_validator_indices),
            )
            for shard_position, indices in enumerate(shard_indices)
        ]
        output.append(shard_committees)

    return output
```

Here's a diagram of what is going on:

![](http://vitalik.ca/files/ShuffleAndAssign.png?1)

#### `get_shard_committees_at_slot`

```python
def get_shard_committees_at_slot(state: BeaconState,
                                 slot: int) -> List[ShardCommittee]:
    """
    Returns the ``ShardCommittee`` for the ``slot``.
    """
    earliest_slot_in_array = state.slot - (state.slot % EPOCH_LENGTH) - EPOCH_LENGTH
    assert earliest_slot_in_array <= slot < earliest_slot_in_array + EPOCH_LENGTH * 2
    return state.shard_committees_at_slots[slot - earliest_slot_in_array]
```

#### `get_block_root`

```python
def get_block_root(state: BeaconState,
                   slot: int) -> Hash32:
    """
    Returns the block root at a recent ``slot``.
    """
    assert state.slot <= slot + LATEST_BLOCK_ROOTS_LENGTH
    assert slot < state.slot
    return state.latest_block_roots[slot % LATEST_BLOCK_ROOTS_LENGTH]
```

`get_block_root(_, s)` should always return `hash_tree_root` of the block in the beacon chain at slot `s`, and `get_shard_committees_at_slot(_, s)` should not change unless the [validator](#dfn-validator) registry changes.

#### `get_beacon_proposer_index`

```python
def get_beacon_proposer_index(state: BeaconState,
                              slot: int) -> int:
    """
    Returns the beacon proposer index for the ``slot``.
    """
    first_committee = get_shard_committees_at_slot(state, slot)[0].committee
    return first_committee[slot % len(first_committee)]
```

#### `merkle_root`

```python
def merkle_root(values):
    o = [0] * len(values) + values
    for i in range(len(values)-1, 0, -1):
        o[i] = hash(o[i*2] + o[i*2+1])
    return o[1]
```

#### `get_attestation_participants`

```python
def get_attestation_participants(state: BeaconState,
                                 attestation_data: AttestationData,
                                 participation_bitfield: bytes) -> List[int]:
    """
    Returns the participant indices at for the ``attestation_data`` and ``participation_bitfield``.
    """

    # Find the relevant committee
    shard_committees = get_shard_committees_at_slot(state, attestation_data.slot)
    shard_committee = [x for x in shard_committees if x.shard == attestation_data.shard][0]
    assert len(participation_bitfield) == ceil_div8(len(shard_committee.committee))

    # Find the participating attesters in the committee
    participants = []
    for i, validator_index in enumerate(shard_committee.committee):
        participation_bit = (participation_bitfield[i//8] >> (7 - (i % 8))) % 2
        if participation_bit == 1:
            participants.append(validator_index)
    return participants
```

#### `bytes1`, `bytes2`, ...

`bytes1(x): return x.to_bytes(1, 'big')`, `bytes2(x): return x.to_bytes(2, 'big')`, and so on for all integers, particularly 1, 2, 3, 4, 8, 32.

#### `get_effective_balance`

```python
def get_effective_balance(state: State, index: int) -> int:
    """
    Returns the effective balance (also known as "balance at stake") for a ``validator`` with the given ``index``.
    """
    return min(state.validator_balances[index], MAX_DEPOSIT * GWEI_PER_ETH)
```

#### `get_new_validator_registry_delta_chain_tip`

```python
def get_new_validator_registry_delta_chain_tip(current_validator_registry_delta_chain_tip: Hash32,
                                               validator_index: int,
                                               pubkey: int,
                                               flag: int) -> Hash32:
    """
    Compute the next root in the validator registry delta chain.
    """
    return hash_tree_root(
        ValidatorRegistryDeltaBlock(
            latest_registry_delta_root=current_validator_registry_delta_chain_tip,
            validator_index=validator_index,
            pubkey=pubkey,
            flag=flag,
        )
    )
```

#### `get_fork_version`

```python
def get_fork_version(fork_data: ForkData,
                     slot: int) -> int:
    if slot < fork_data.fork_slot:
        return fork_data.pre_fork_version
    else:
        return fork_data.post_fork_version
```

#### `get_domain`

```python
def get_domain(fork_data: ForkData,
               slot: int,
               domain_type: int) -> int:
    return get_fork_version(
        fork_data,
        slot
    ) * 2**32 + domain_type
```

#### `verify_slashable_vote_data`

```python
def verify_slashable_vote_data(state: BeaconState, vote_data: SlashableVoteData) -> bool:
    if len(vote_data.aggregate_signature_poc_0_indices) + len(vote_data.aggregate_signature_poc_1_indices) > MAX_CASPER_VOTES:
        return False

    pubs = [
        aggregate_pubkey([state.validators[i].pubkey for i in vote_data.aggregate_signature_poc_0_indices]),
        aggregate_pubkey([state.validators[i].pubkey for i in vote_data.aggregate_signature_poc_1_indices])
    ]
    vote_data_root = hash_tree_root(vote_data)
    messages = [
        vote_data_root + bytes1(0),
        vote_data_root + bytes1(1)
    ]
    return bls_verify_multiple(
        pubkeys=pubs,
        messages=messages,
        signature=vote_data.aggregate_signature,
        domain=get_domain(
            state.fork_data,
            state.slot,
            DOMAIN_ATTESTATION,
        ),
    )
```

#### `is_double_vote`

```python
def is_double_vote(attestation_data_1: AttestationData,
                   attestation_data_2: AttestationData) -> bool
    """
    Assumes ``attestation_data_1`` is distinct from ``attestation_data_2``.
    Returns True if the provided ``AttestationData`` are slashable
    due to a 'double vote'.
    """
    return attestation_data_1.slot == attestation_data_2.slot
```

#### `is_surround_vote`

```python
def is_surround_vote(attestation_data_1: AttestationData,
                     attestation_data_2: AttestationData) -> bool:
    """
    Assumes ``attestation_data_1`` is distinct from ``attestation_data_2``.
    Returns True if the provided ``AttestationData`` are slashable
    due to a 'surround vote'.
    Note: parameter order matters as this function only checks
    that ``attestation_data_1`` surrounds ``attestation_data_2``.
    """
    return (
        (attestation_data_1.justified_slot < attestation_data_2.justified_slot) and
        (attestation_data_2.justified_slot + 1 == attestation_data_2.slot) and
        (attestation_data_2.slot < attestation_data_1.slot)
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

#### `bls_verify`

`bls_verify` is a function for verifying a BLS12-381 signature, defined in the [BLS Signature spec](https://github.com/ethereum/eth2.0-specs/blob/master/specs/bls_signature.md#bls_verify).

#### `bls_verify_multiple`

`bls_verify_multiple` is a function for verifying a BLS12-381 signature constructed from multiple messages, defined in the [BLS Signature spec](https://github.com/ethereum/eth2.0-specs/blob/master/specs/bls_signature.md#bls_verify_multiple).

#### `bls_aggregate_pubkeys`

`bls_aggregate_pubkeys` is a function for aggregating a BLS12-381 public keys into a single aggregate key, defined in the [BLS Signature spec](https://github.com/ethereum/eth2.0-specs/blob/master/specs/bls_signature.md#bls_aggregate_pubkeys).

### On startup

A valid block with slot `INITIAL_SLOT_NUMBER` (a "genesis block") has the following values. Other validity rules (e.g. requiring a signature) do not apply.

```python
{
    slot=INITIAL_SLOT_NUMBER,
    parent_root=ZERO_HASH,
    state_root=STARTUP_STATE_ROOT,
    randao_reveal=ZERO_HASH,
    candidate_pow_receipt_root=ZERO_HASH,
    signature=EMPTY_SIGNATURE,
    body=BeaconBlockBody(
        proposer_slashings=[],
        casper_slashings=[],
        attestations=[],
        poc_seed_changes=[],
        poc_challenges=[],
        poc_responses=[],
        deposits=[],
        exits=[]
    ),
}
```

`STARTUP_STATE_ROOT` (in the above "genesis block") is generated from the `get_initial_beacon_state` function below. When enough full deposits have been made to the deposit contract and the `ChainStart` log has been emitted, `get_initial_beacon_state` will execute to compute the `hash_tree_root` of `BeaconState`.

```python
def get_initial_beacon_state(initial_validator_deposits: List[Deposit],
                             genesis_time: int,
                             processed_pow_receipt_root: Hash32) -> BeaconState:
    state = BeaconState(
        # Misc
        slot=INITIAL_SLOT_NUMBER,
        genesis_time=genesis_time,
        fork_data=ForkData(
            pre_fork_version=INITIAL_FORK_VERSION,
            post_fork_version=INITIAL_FORK_VERSION,
            fork_slot=INITIAL_SLOT_NUMBER,
        ),

        # Validator registry
        validator_registry=[],
        validator_balances=[],
        validator_registry_latest_change_slot=INITIAL_SLOT_NUMBER,
        validator_registry_exit_count=0,
        validator_registry_delta_chain_tip=ZERO_HASH,

        # Randomness and committees
        latest_randao_mixes=[ZERO_HASH for _ in range(LATEST_RANDAO_MIXES_LENGTH)],
        shard_committees_at_slots=[],
        persistent_committees=[],
        persistent_committee_reassignments=[],

        # Proof of custody
        poc_challenges=[],
        poc_commitment=ZERO_HASH,
        last_poc_change_slot=0,
        second_last_poc_change_slot=0,

        # Finality
        previous_justified_slot=INITIAL_SLOT_NUMBER,
        justified_slot=INITIAL_SLOT_NUMBER,
        justification_bitfield=0,
        finalized_slot=INITIAL_SLOT_NUMBER,

        # Recent state
        latest_crosslinks=[CrosslinkRecord(slot=INITIAL_SLOT_NUMBER, shard_block_root=ZERO_HASH) for _ in range(SHARD_COUNT)],
        latest_block_roots=[ZERO_HASH for _ in range(LATEST_BLOCK_ROOTS_LENGTH)],
        latest_penalized_exit_balances=[],
        latest_attestations=[],
        batched_block_roots=[],

        # PoW receipt root
        processed_pow_receipt_root=processed_pow_receipt_root,
        candidate_pow_receipt_roots=[],
    )

    # handle initial deposits and activations
    for deposit in initial_validator_deposits:
        validator_index = process_deposit(
            state=state,
            pubkey=deposit.deposit_data.deposit_input.pubkey,
            deposit=deposit.deposit_data.value,
            proof_of_possession=deposit.deposit_data.deposit_input.proof_of_possession,
            withdrawal_credentials=deposit.deposit_data.deposit_input.withdrawal_credentials,
            randao_commitment=deposit.deposit_data.deposit_input.randao_commitment
        )
        if get_effective_balance(state, validator_index) == MAX_DEPOSIT * GWEI_PER_ETH:
            update_validator_status(state, validator_index, ACTIVE)

    # set initial committee shuffling
    initial_shuffling = get_new_shuffling(ZERO_HASH, state.validator_registry, 0)
    state.shard_committees_at_slots = initial_shuffling + initial_shuffling

    # set initial persistent shuffling
    active_validator_indices = get_active_validator_indices(state.validator_registry)
    state.persistent_committees = split(shuffle(active_validator_indices, ZERO_HASH), SHARD_COUNT)

    return state
```

### Routine for processing deposits

First, two helper functions:

```python
def min_empty_validator_index(validators: List[ValidatorRecord],
                              validator_balances: List[int],
                              current_slot: int) -> int:
    for i, (v, vbal) in enumerate(zip(validators, validator_balances)):
        if vbal == 0 and v.latest_status_change_slot + ZERO_BALANCE_VALIDATOR_TTL <= current_slot:
            return i
    return None
```

```python
def validate_proof_of_possession(state: BeaconState,
                                 pubkey: int,
                                 proof_of_possession: bytes,
                                 withdrawal_credentials: Hash32,
                                 randao_commitment: Hash32) -> bool:
    proof_of_possession_data = DepositInput(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        randao_commitment=randao_commitment,
        proof_of_possession=EMPTY_SIGNATURE,
    )

    return bls_verify(
        pubkey=pubkey,
        message=hash_tree_root(proof_of_possession_data),
        signature=proof_of_possession,
        domain=get_domain(
            state.fork_data,
            state.slot,
            DOMAIN_DEPOSIT,
        )
    )
```

Now, to add a [validator](#dfn-validator) or top up an existing [validator](#dfn-validator)'s balance by some `deposit` amount:

```python
def process_deposit(state: BeaconState,
                    pubkey: int,
                    deposit: int,
                    proof_of_possession: bytes,
                    withdrawal_credentials: Hash32,
                    randao_commitment: Hash32) -> int:
    """
    Process a deposit from Ethereum 1.0.
    Note that this function mutates ``state``.
    """
    # Validate the given `proof_of_possession`
    assert validate_proof_of_possession(
        state,
        pubkey,
        proof_of_possession,
        withdrawal_credentials,
        randao_commitment,
    )

    validator_pubkeys = [v.pubkey for v in state.validator_registry]

    if pubkey not in validator_pubkeys:
        # Add new validator
        validator = ValidatorRecord(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            randao_commitment=randao_commitment,
            randao_layers=0,
            status=PENDING_ACTIVATION,
            latest_status_change_slot=state.slot,
            exit_count=0
        )

        index = min_empty_validator_index(state.validator_registry, state.validator_balances, state.slot)
        if index is None:
            state.validator_registry.append(validator)
            state.validator_balances.append(deposit)
            index = len(state.validator_registry) - 1
        else:
            state.validator_registry[index] = validator
            state.validator_balances[index] = deposit
    else:
        # Increase balance by deposit
        index = validator_pubkeys.index(pubkey)
        assert state.validator_registry[index].withdrawal_credentials == withdrawal_credentials

        state.validator_balances[index] += deposit

    return index
```

### Routine for updating validator status

```python
def update_validator_status(state: BeaconState,
                            index: int,
                            new_status: int) -> None:
    """
    Update the validator status with the given ``index`` to ``new_status``.
    Handle other general accounting related to this status update.
    Note that this function mutates ``state``.
    """
    if new_status == ACTIVE:
        activate_validator(state, index)
    if new_status == ACTIVE_PENDING_EXIT:
        initiate_validator_exit(state, index)
    if new_status in [EXITED_WITH_PENALTY, EXITED_WITHOUT_PENALTY]:
        exit_validator(state, index, new_status)
```

The following are helpers and should only be called via `update_validator_status`:

```python
def activate_validator(state: BeaconState,
                       index: int) -> None:
    """
    Activate the validator with the given ``index``.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[index]
    if validator.status != PENDING_ACTIVATION:
        return

    validator.status = ACTIVE
    validator.latest_status_change_slot = state.slot
    state.validator_registry_delta_chain_tip = get_new_validator_registry_delta_chain_tip(
        current_validator_registry_delta_chain_tip=state.validator_registry_delta_chain_tip,
        validator_index=index,
        pubkey=validator.pubkey,
        flag=ACTIVATION,
    )
```

```python
def initiate_validator_exit(state: BeaconState,
                            index: int) -> None:
    """
    Initiate exit for the validator with the given ``index``.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[index]
    if validator.status != ACTIVE:
        return

    validator.status = ACTIVE_PENDING_EXIT
    validator.latest_status_change_slot = state.slot
```

```python
def exit_validator(state: BeaconState,
                   index: int,
                   new_status: int) -> None:
    """
    Exit the validator with the given ``index``.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[index]
    prev_status = validator.status

    if prev_status == EXITED_WITH_PENALTY:
        return

    validator.status = new_status
    validator.latest_status_change_slot = state.slot

    if new_status == EXITED_WITH_PENALTY:
        state.latest_penalized_exit_balances[state.slot // COLLECTIVE_PENALTY_CALCULATION_PERIOD] += get_effective_balance(state, index)

        whistleblower_index = get_beacon_proposer_index(state, state.slot)
        whistleblower_reward = get_effective_balance(state, index) // WHISTLEBLOWER_REWARD_QUOTIENT
        state.validator_balances[whistleblower_index] += whistleblower_reward
        state.validator_balances[index] -= whistleblower_reward

    if prev_status == EXITED_WITHOUT_PENALTY:
        return

    # The following updates only occur if not previous exited
    state.validator_registry_exit_count += 1
    validator.exit_count = state.validator_registry_exit_count
    state.validator_registry_delta_chain_tip = get_new_validator_registry_delta_chain_tip(
        current_validator_registry_delta_chain_tip=state.validator_registry_delta_chain_tip,
        validator_index=index,
        pubkey=validator.pubkey,
        flag=EXIT
    )

    # Remove validator from persistent committees
    for committee in state.persistent_committees:
        for i, validator_index in committee:
            if validator_index == index:
                committee.pop(i)
                break
```

## Per-slot processing

Below are the processing steps that happen at every slot.

### Misc counters

* Set `state.slot += 1`.
* Set `state.validator_registry[get_beacon_proposer_index(state, state.slot)].randao_layers += 1`.
* Set `state.latest_randao_mixes[state.slot % LATEST_RANDAO_MIXES_LENGTH] = state.latest_randao_mixes[(state.slot - 1) % LATEST_RANDAO_MIXES_LENGTH]`

### Block roots

* Let `previous_block_root` be the `tree_hash_root` of the previous beacon block processed in the chain.
* Set `state.latest_block_roots[(state.slot - 1) % LATEST_BLOCK_ROOTS_LENGTH] = previous_block_root`.
* If `state.slot % LATEST_BLOCK_ROOTS_LENGTH == 0` append `merkle_root(state.latest_block_roots)` to `state.batched_block_roots`.

## Per-block processing

Below are the processing steps that happen at every `block`.

### Slot

* Verify that `block.slot == state.slot`.

### Proposer signature

* Let `block_without_signature_root` be the `hash_tree_root` of `block` where `block.signature` is set to `EMPTY_SIGNATURE`.
* Let `proposal_root = hash_tree_root(ProposalSignedData(state.slot, BEACON_CHAIN_SHARD_NUMBER, block_without_signature_root))`.
* Verify that `bls_verify(pubkey=state.validator_registry[get_beacon_proposer_index(state, state.slot)].pubkey, data=proposal_root, signature=block.signature, domain=get_domain(state.fork_data, state.slot, DOMAIN_PROPOSAL))`.

### RANDAO

* Let `repeat_hash(x, n) = x if n == 0 else repeat_hash(hash(x), n-1)`.
* Let `proposer = state.validator_registry[get_beacon_proposer_index(state, state.slot)]`.
* Verify that `repeat_hash(block.randao_reveal, proposer.randao_layers) == proposer.randao_commitment`.
* Set `state.latest_randao_mixes[state.slot % LATEST_RANDAO_MIXES_LENGTH] = xor(state.latest_randao_mixes[state.slot % LATEST_RANDAO_MIXES_LENGTH], block.randao_reveal)`
* Set `proposer.randao_commitment = block.randao_reveal`.
* Set `proposer.randao_layers = 0`.

### PoW receipt root

* If `block.candidate_pow_receipt_root` is `x.candidate_pow_receipt_root` for some `x` in `state.candidate_pow_receipt_roots`, set `x.vote_count += 1`.
* Otherwise, append to `state.candidate_pow_receipt_roots` a new `CandidatePoWReceiptRootRecord(candidate_pow_receipt_root=block.candidate_pow_receipt_root, vote_count=1)`.

### Operations

#### Proposer slashings

Verify that `len(block.body.proposer_slashings) <= MAX_PROPOSER_SLASHINGS`.

For each `proposer_slashing` in `block.body.proposer_slashings`:

* Let `proposer = state.validator_registry[proposer_slashing.proposer_index]`.
* Verify that `proposer_slashing.proposal_data_1.slot == proposer_slashing.proposal_data_2.slot`.
* Verify that `proposer_slashing.proposal_data_1.shard == proposer_slashing.proposal_data_2.shard`.
* Verify that `proposer_slashing.proposal_data_1.block_root != proposer_slashing.proposal_data_2.block_root`.
* Verify that `proposer.status != EXITED_WITH_PENALTY`.
* Verify that `bls_verify(pubkey=proposer.pubkey, message=hash_tree_root(proposer_slashing.proposal_data_1), signature=proposer_slashing.proposal_signature_1, domain=get_domain(state.fork_data, proposer_slashing.proposal_data_1.slot, DOMAIN_PROPOSAL))`.
* Verify that `bls_verify(pubkey=proposer.pubkey, message=hash_tree_root(proposer_slashing.proposal_data_2), signature=proposer_slashing.proposal_signature_2, domain=get_domain(state.fork_data, proposer_slashing.proposal_data_2.slot, DOMAIN_PROPOSAL))`.
* Run `update_validator_status(state, proposer_slashing.proposer_index, new_status=EXITED_WITH_PENALTY)`.

#### Casper slashings

Verify that `len(block.body.casper_slashings) <= MAX_CASPER_SLASHINGS`.

For each `casper_slashing` in `block.body.casper_slashings`:

* Let `slashable_vote_data_1 = casper_slashing.slashable_vote_data_1`.
* Let `slashable_vote_data_2 = casper_slashing.slashable_vote_data_2`.
* Let `indices(slashable_vote_data) = slashable_vote_data.aggregate_signature_poc_0_indices + slashable_vote_data.aggregate_signature_poc_1_indices`.
* Let `intersection = [x for x in indices(slashable_vote_data_1) if x in indices(slashable_vote_data_2)]`.
* Verify that `len(intersection) >= 1`.
* Verify that `slashable_vote_data_1.data != slashable_vote_data_2.data`.
* Verify that `is_double_vote(slashable_vote_data_1.data, slashable_vote_data_2.data)` or `is_surround_vote(slashable_vote_data_1.data, slashable_vote_data_2.data)`.
* Verify that `verify_slashable_vote_data(state, slashable_vote_data_1)`.
* Verify that `verify_slashable_vote_data(state, slashable_vote_data_2)`.
* For each [validator](#dfn-validator) index `i` in `intersection`, if `state.validator_registry[i].status` does not equal `EXITED_WITH_PENALTY`, then run `update_validator_status(state, i, new_status=EXITED_WITH_PENALTY)`

#### Attestations

Verify that `len(block.body.attestations) <= MAX_ATTESTATIONS`.

For each `attestation` in `block.body.attestations`:

* Verify that `attestation.data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot`.
* Verify that `attestation.data.slot + EPOCH_LENGTH >= state.slot`.
* Verify that `attestation.data.justified_slot` is equal to `state.justified_slot if attestation.data.slot >= state.slot - (state.slot % EPOCH_LENGTH) else state.previous_justified_slot`.
* Verify that `attestation.data.justified_block_root` is equal to `get_block_root(state, attestation.data.justified_slot)`.
* Verify that either `attestation.data.latest_crosslink_root` or `attestation.data.shard_block_root` equals `state.latest_crosslinks[shard].shard_block_root`.
* `aggregate_signature` verification:
    * Let `participants = get_attestation_participants(state, attestation.data, attestation.participation_bitfield)`.
    * Let `group_public_key = bls_aggregate_pubkeys([state.validator_registry[v].pubkey for v in participants])`.
    * Verify that `bls_verify(pubkey=group_public_key, message=hash_tree_root(attestation.data) + bytes1(0), signature=attestation.aggregate_signature, domain=get_domain(state.fork_data, attestation.data.slot, DOMAIN_ATTESTATION))`.
* [TO BE REMOVED IN PHASE 1] Verify that `attestation.data.shard_block_root == ZERO_HASH`.
* Append `PendingAttestationRecord(data=attestation.data, participation_bitfield=attestation.participation_bitfield, custody_bitfield=attestation.custody_bitfield, slot_included=state.slot)` to `state.latest_attestations`.

#### Deposits

Verify that `len(block.body.deposits) <= MAX_DEPOSITS`.

[TODO: add logic to ensure that deposits from 1.0 chain are processed in order]

For each `deposit` in `block.body.deposits`:

* Let `serialized_deposit_data` be the serialized form of `deposit.deposit_data`. It should be the `DepositInput` followed by 8 bytes for `deposit_data.value` and 8 bytes for `deposit_data.timestamp`. That is, it should match `deposit_data` in the [Ethereum 1.0 deposit contract](#ethereum-10-deposit-contract) of which the hash was placed into the Merkle tree.
* Use the following procedure to verify `deposit.merkle_branch`, setting `leaf=serialized_deposit_data`, `depth=DEPOSIT_CONTRACT_TREE_DEPTH` and `root=state.processed_pow_receipt_root`:

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

* Verify that `state.slot - (deposit.deposit_data.timestamp - state.genesis_time) // SLOT_DURATION < ZERO_BALANCE_VALIDATOR_TTL`.
* Run the following:

```python
process_deposit(
    state=state,
    pubkey=deposit.deposit_data.deposit_input.pubkey,
    deposit=deposit.deposit_data.value,
    proof_of_possession=deposit.deposit_data.deposit_input.proof_of_possession,
    withdrawal_credentials=deposit.deposit_data.deposit_input.withdrawal_credentials,
    randao_commitment=deposit.deposit_data.deposit_input.randao_commitment
)
```

#### Exits

Verify that `len(block.body.exits) <= MAX_EXITS`.

For each `exit` in `block.body.exits`:

* Let `validator = state.validator_registry[exit.validator_index]`.
* Verify that `validator.status == ACTIVE`.
* Verify that `state.slot >= exit.slot`.
* Verify that `state.slot >= validator.latest_status_change_slot + SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD`.
* Verify that `bls_verify(pubkey=validator.pubkey, message=ZERO_HASH, signature=exit.signature, domain=get_domain(state.fork_data, exit.slot, DOMAIN_EXIT))`.
* Run `update_validator_status(state, validator_index, new_status=ACTIVE_PENDING_EXIT)`.

#### Miscellaneous

[TO BE REMOVED IN PHASE 1] Verify that `len(block.body.poc_seed_changes) == len(block.body.poc_challenges) == len(block.body.poc_responses) == 0`.

## Per-epoch processing

The steps below happen when `state.slot % EPOCH_LENGTH == 0`.

### Helpers

All [validators](#dfn-validator):

* Let `active_validator_indices = get_active_validator_indices(state.validator_registry)`.
* Let `total_balance = sum([get_effective_balance(state, i) for i in active_validator_indices])`.

[Validators](#dfn-Validator) attesting during the current epoch:

* Let `this_epoch_attestations = [a for a in state.latest_attestations if state.slot - EPOCH_LENGTH <= a.data.slot < state.slot]`. (Note: this is the set of attestations of slots in the epoch `state.slot-EPOCH_LENGTH...state.slot-1`, _not_ attestations that got included in the chain during the epoch `state.slot-EPOCH_LENGTH...state.slot-1`.)
* Validators justifying the epoch boundary block at the start of the current epoch:
  * Let `this_epoch_boundary_attestations = [a for a in this_epoch_attestations if a.data.epoch_boundary_root == get_block_root(state, state.slot-EPOCH_LENGTH) and a.justified_slot == state.justified_slot]`.
  * Let `this_epoch_boundary_attester_indices` be the union of the [validator](#dfn-validator) index sets given by `[get_attestation_participants(state, a.data, a.participation_bitfield) for a in this_epoch_boundary_attestations]`.
  * Let `this_epoch_boundary_attesting_balance = sum([get_effective_balance(state, i) for i in this_epoch_boundary_attester_indices])`.

[Validators](#dfn-Validator) attesting during the previous epoch:

* Validators that made an attestation during the previous epoch:
  * Let `previous_epoch_attestations = [a for a in state.latest_attestations if state.slot - 2 * EPOCH_LENGTH <= a.slot < state.slot - EPOCH_LENGTH]`.
  * Let `previous_epoch_attester_indices` be the union of the validator index sets given by `[get_attestation_participants(state, a.data, a.participation_bitfield) for a in previous_epoch_attestations]`.
* Validators targeting the previous justified hash:
  * Let `previous_epoch_justified_attestations = [a for a in this_epoch_attestations + previous_epoch_attestations if a.justified_slot == state.previous_justified_slot]`.
  * Let `previous_epoch_justified_attester_indices` be the union of the validator index sets given by `[get_attestation_participants(state, a.data, a.participation_bitfield) for a in previous_epoch_justified_attestations]`.
  * Let `previous_epoch_justified_attesting_balance = sum([get_effective_balance(state, i) for i in previous_epoch_justified_attester_indices])`.
* Validators justifying the epoch boundary block at the start of the previous epoch:
  * Let `previous_epoch_boundary_attestations = [a for a in previous_epoch_justified_attestations if a.epoch_boundary_root == get_block_root(state, state.slot - 2 * EPOCH_LENGTH)]`.
  * Let `previous_epoch_boundary_attester_indices` be the union of the validator index sets given by `[get_attestation_participants(state, a.data, a.participation_bitfield) for a in previous_epoch_boundary_attestations]`.
  * Let `previous_epoch_boundary_attesting_balance = sum([get_effective_balance(state, i) for i in previous_epoch_boundary_attester_indices])`.
* Validators attesting to the expected beacon chain head during the previous epoch:
  * Let `previous_epoch_head_attestations = [a for a in previous_epoch_attestations if a.beacon_block_root == get_block_root(state, a.slot)]`.
  * Let `previous_epoch_head_attester_indices` be the union of the validator index sets given by `[get_attestation_participants(state, a.data, a.participation_bitfield) for a in previous_epoch_head_attestations]`.
  * Let `previous_epoch_head_attesting_balance = sum([get_effective_balance(state, i) for i in previous_epoch_head_attester_indices])`.

**Note**: `previous_epoch_boundary_attesting_balance` balance might be marginally different than `this_epoch_boundary_attesting_balance` during the previous epoch transition. Due to the tight bound on validator churn each epoch and small per-epoch rewards/penalties, the potential balance difference is very low and only marginally affects consensus safety.

For every `shard_committee` in `state.shard_committees_at_slots`:

* Let `attesting_validator_indices(shard_committee, shard_block_root)` be the union of the [validator](#dfn-validator) index sets given by `[get_attestation_participants(state, a.data, a.participation_bitfield) for a in this_epoch_attestations + previous_epoch_attestations if a.shard == shard_committee.shard and a.shard_block_root == shard_block_root]`.
* Let `winning_root(shard_committee)` be equal to the value of `shard_block_root` such that `sum([get_effective_balance(state, i) for i in attesting_validator_indices(shard_committee, shard_block_root)])` is maximized (ties broken by favoring lower `shard_block_root` values).
* Let `attesting_validators(shard_committee)` be equal to `attesting_validator_indices(shard_committee, winning_root(shard_committee))` for convenience.
* Let `total_attesting_balance(shard_committee) = sum([get_effective_balance(state, i) for i in attesting_validators(shard_committee)])`.
* Let `total_balance(shard_committee) = sum([get_effective_balance(state, i) for i in shard_committee.committee])`.
* Let `inclusion_slot(state, index) = a.slot_included` for the attestation `a` where `index` is in `get_attestation_participants(state, a.data, a.participation_bitfield)`.
* Let `inclusion_distance(state, index) = a.slot_included - a.data.slot` where `a` is the above attestation.
* Let `adjust_for_inclusion_distance(magnitude, distance)` be the function below.

```python
def adjust_for_inclusion_distance(magnitude: int, distance: int) -> int:
    """
    Adjusts the reward of an attestation based on how long it took to get included (the longer, the lower the reward).
    Returns a value between ``0`` and ``magnitude``.
    ""
    return magnitude // 2 + (magnitude // 2) * MIN_ATTESTATION_INCLUSION_DELAY // distance
```

### Receipt roots

If `state.slot % POW_RECEIPT_ROOT_VOTING_PERIOD == 0`:

* Set `state.processed_pow_receipt_root = x.receipt_root` if `x.vote_count * 2 > POW_RECEIPT_ROOT_VOTING_PERIOD` for some `x` in `state.candidate_pow_receipt_root`.
* Set `state.candidate_pow_receipt_roots = []`.

### Justification

* Set `state.previous_justified_slot = state.justified_slot`.
* Set `state.justification_bitfield = (state.justification_bitfield * 2) % 2**64`.
* Set `state.justification_bitfield |= 2` and `state.justified_slot = state.slot - 2 * EPOCH_LENGTH` if `3 * previous_epoch_boundary_attesting_balance >= 2 * total_balance`.
* Set `state.justification_bitfield |= 1` and `state.justified_slot = state.slot - 1 * EPOCH_LENGTH` if `3 * this_epoch_boundary_attesting_balance >= 2 * total_balance`.

### Finalization

Set `state.finalized_slot = state.previous_justified_slot` if any of the following are true:

* `state.previous_justified_slot == state.slot - 2 * EPOCH_LENGTH and state.justification_bitfield % 4 == 3`
* `state.previous_justified_slot == state.slot - 3 * EPOCH_LENGTH and state.justification_bitfield % 8 == 7`
* `state.previous_justified_slot == state.slot - 4 * EPOCH_LENGTH and state.justification_bitfield % 16 in (15, 14)`

### Crosslinks

For every `shard_committee` in `state.shard_committees_at_slots`:

* Set `state.latest_crosslinks[shard] = CrosslinkRecord(slot=state.slot, block_root=winning_root(shard_committee))` if `3 * total_attesting_balance(shard_committee) >= 2 * total_balance(shard_committee)`.

### Rewards and penalties

First, we define some additional helpers:

* Let `base_reward_quotient = BASE_REWARD_QUOTIENT * integer_squareroot(total_balance // GWEI_PER_ETH)`.
* Let `base_reward(state, index) = get_effective_balance(state, index) // base_reward_quotient // 4` for any validator with the given `index`.
* Let `inactivity_penalty(state, index, slots_since_finality) = base_reward(state, index) + get_effective_balance(state, index) * slots_since_finality // INACTIVITY_PENALTY_QUOTIENT` for any validator with the given `index`.

#### Justification and finalization

Note: When applying penalties in the following balance recalculations implementers should make sure the `uint64` does not underflow.

* Let `slots_since_finality = state.slot - state.finalized_slot`.

Case 1: `slots_since_finality <= 4 * EPOCH_LENGTH`:

* Expected FFG source:
  * Any [validator](#dfn-validator) `index` in `previous_epoch_justified_attester_indices` gains `adjust_for_inclusion_distance(base_reward(state, index) * previous_epoch_justified_attesting_balance // total_balance, inclusion_distance(state, index))`.
  * Any [active validator](#dfn-active-validator) `v` not in `previous_epoch_justified_attester_indices` loses `base_reward(state, index)`.
* Expected FFG target:
  * Any [validator](#dfn-validator) `index` in `previous_epoch_boundary_attester_indices` gains `adjust_for_inclusion_distance(base_reward(state, index) * previous_epoch_boundary_attesting_balance // total_balance, inclusion_distance(state, index))`.
  * Any [active validator](#dfn-active-validator) `index` not in `previous_epoch_boundary_attester_indices` loses `base_reward(state, index)`.
* Expected beacon chain head:
  * Any [validator](#dfn-validator) `index` in `previous_epoch_head_attester_indices` gains `adjust_for_inclusion_distance(base_reward(state, index) * previous_epoch_head_attesting_balance // total_balance, inclusion_distance(state, index))`.
  * Any [active validator](#dfn-active-validator) `index` not in `previous_epoch_head_attester_indices` loses `base_reward(state, index)`.

Case 2: `slots_since_finality > 4 * EPOCH_LENGTH`:

* Any [active validator](#dfn-active-validator) `index` not in `previous_epoch_justified_attester_indices`, loses `inactivity_penalty(state, index, slots_since_finality)`.
* Any [active validator](#dfn-active-validator) `index` not in `previous_epoch_boundary_attester_indices`, loses `inactivity_penalty(state, index, slots_since_finality)`.
* Any [active validator](#dfn-active-validator) `index` not in `previous_epoch_head_attester_indices`, loses `inactivity_penalty(state, index, slots_since_finality)`.
* Any [validator](#dfn-validator) `index` with `status == EXITED_WITH_PENALTY`, loses `3 * inactivity_penalty(state, index, slots_since_finality)`.

#### Attestation inclusion

For each `index` in `previous_epoch_attester_indices`, we determine the proposer `proposer_index = get_beacon_proposer_index(state, inclusion_slot(state, index))` and set `state.validator_balances[proposer_index] += base_reward(state, index) // INCLUDER_REWARD_QUOTIENT`.

#### Crosslinks

For every `shard_committee` in `state.shard_committees_at_slots[:EPOCH_LENGTH]` (i.e. the objects corresponding to the epoch before the current one), for each `index` in `shard_committee.committee`, adjust balances as follows:

* If `index in attesting_validators(shard_committee)`, `state.validator_balances[index] += adjust_for_inclusion_distance(base_reward(state, index) * total_attesting_balance(shard_committee) // total_balance(shard_committee)), inclusion_distance(state, index))`.
* If `index not in attesting_validators(shard_committee)`, `state.validator_balances[index] -= base_reward(state, index)`.

### Ejections

* Run `process_ejections(state)`.

```python
def process_ejections(state: BeaconState) -> None:
    """
    Iterate through the validator registry
    and eject active validators with balance below ``EJECTION_BALANCE``.
    """
    for index in active_validator_indices(state.validator_registry):
        if state.validator_balances[index] < EJECTION_BALANCE:
            update_validator_status(state, index, new_status=EXITED_WITHOUT_PENALTY)
```

### Validator registry

If the following are satisfied:

* `state.finalized_slot > state.validator_registry_latest_change_slot`
* `state.latest_crosslinks[shard].slot > state.validator_registry_latest_change_slot` for every shard number `shard` in `state.shard_committees_at_slots`

update the validator registry and associated fields by running

```python
def update_validator_registry(state: BeaconState) -> None:
    """
    Update validator registry.
    Note that this function mutates ``state``.
    """
    # The active validators
    active_validator_indices = get_active_validator_indices(state.validator_registry)
    # The total effective balance of active validators
    total_balance = sum([get_effective_balance(state, i) for i in active_validator_indices])

    # The maximum balance churn in Gwei (for deposits and exits separately)
    max_balance_churn = max(
        MAX_DEPOSIT * GWEI_PER_ETH,
        total_balance // (2 * MAX_BALANCE_CHURN_QUOTIENT)
    )

    # Activate validators within the allowable balance churn
    balance_churn = 0
    for index, validator in enumerate(state.validator_registry):
        if validator.status == PENDING_ACTIVATION and state.validator_balances[index] >= MAX_DEPOSIT * GWEI_PER_ETH:
            # Check the balance churn would be within the allowance
            balance_churn += get_effective_balance(state, index)
            if balance_churn > max_balance_churn:
                break

            # Activate validator
            update_validator_status(state, index, new_status=ACTIVE)

    # Exit validators within the allowable balance churn
    balance_churn = 0
    for index, validator in enumerate(state.validator_registry):
        if validator.status == ACTIVE_PENDING_EXIT:
            # Check the balance churn would be within the allowance
            balance_churn += get_effective_balance(state, index)
            if balance_churn > max_balance_churn:
                break

            # Exit validator
            update_validator_status(state, index, new_status=EXITED_WITHOUT_PENALTY)


    # Calculate the total ETH that has been penalized in the last ~2-3 withdrawal periods
    period_index = current_slot // COLLECTIVE_PENALTY_CALCULATION_PERIOD
    total_penalties = (
        (latest_penalized_exit_balances[period_index]) +
        (latest_penalized_exit_balances[period_index - 1] if period_index >= 1 else 0) +
        (latest_penalized_exit_balances[period_index - 2] if period_index >= 2 else 0)
    )

    # Calculate penalties for slashed validators
    def to_penalize(index):
        return state.validator_registry[index].status == EXITED_WITH_PENALTY
    validators_to_penalize = filter(to_penalize, range(len(validator_registry)))
    for index in validators_to_penalize:
        state.validator_balances[index] -= get_effective_balance(state, index) * min(total_penalties * 3, total_balance) // total_balance

    return validator_registry, latest_penalized_exit_balances, validator_registry_delta_chain_tip
```

Also perform the following updates:

* Set `state.validator_registry_latest_change_slot = state.slot`.
* Set `state.shard_committees_at_slots[:EPOCH_LENGTH] = state.shard_committees_at_slots[EPOCH_LENGTH:]`.
* Set `state.shard_committees_at_slots[EPOCH_LENGTH:] = get_new_shuffling(state.latest_randao_mixes[(state.slot - EPOCH_LENGTH) % LATEST_RANDAO_MIXES_LENGTH], state.validator_registry, next_start_shard)` where `next_start_shard = (state.shard_committees_at_slots[-1][-1].shard + 1) % SHARD_COUNT`.

If a validator registry update does _not_ happen do the following:

* Set `state.shard_committees_at_slots[:EPOCH_LENGTH] = state.shard_committees_at_slots[EPOCH_LENGTH:]`.
* Let `slots_since_finality = state.slot - state.validator_registry_latest_change_slot`.
* Let `start_shard = state.shard_committees_at_slots[0][0].shard`.
* If `slots_since_finality` is an exact power of 2, set `state.shard_committees_at_slots[EPOCH_LENGTH:] = get_new_shuffling(state.latest_randao_mixes[(state.slot - EPOCH_LENGTH) % LATEST_RANDAO_MIXES_LENGTH], state.validator_registry, start_shard)`. Note that `start_shard` is not changed from the last epoch.

### Proposer reshuffling

Run the following code to update the shard proposer set:

```python
active_validator_indices = get_active_validator_indices(state.validator_registry)
num_validators_to_reshuffle = len(active_validator_indices) // SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD
for i in range(num_validators_to_reshuffle):
    # Multiplying i to 2 to ensure we have different input to all the required hashes in the shuffling
    # and none of the hashes used for entropy in this loop will be the same
    validator_index = active_validator_indices[hash(state.latest_randao_mixes[state.slot % LATEST_RANDAO_MIXES_LENGTH] + bytes8(i * 2)) % len(active_validator_indices)]
    new_shard = hash(state.latest_randao_mixes[state.slot % LATEST_RANDAO_MIXES_LENGTH] + bytes8(i * 2 + 1)) % SHARD_COUNT
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

### Final updates

* Remove any `attestation` in `state.latest_attestations` such that `attestation.data.slot < state.slot - EPOCH_LENGTH`.

## State root processing

Verify `block.state_root == hash_tree_root(state)` if there exists a `block` for the slot being processed.

# References

This section is divided into Normative and Informative references.  Normative references are those that must be read in order to implement this specification, while Informative references are merely that, information.  An example of the former might be the details of a required consensus algorithm, and an example of the latter might be a pointer to research that demonstrates why a particular consensus algorithm might be better suited for inclusion in the standard than another.

## Normative

## Informative
<a id="ref-casper-ffg"></a> _**casper-ffg**_  
 &nbsp; _Casper the Friendly Finality Gadget_. V. Buterin and V. Griffith. URL: https://arxiv.org/abs/1710.09437

<a id="ref-python-poc"></a> _**python-poc**_  
 &nbsp; _Python proof-of-concept implementation_. Ethereum Foundation. URL: https://github.com/ethereum/beacon_chain

# Copyright
Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
