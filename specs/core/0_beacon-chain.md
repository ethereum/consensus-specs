# Ethereum 2.0 Phase 0 -- The Beacon Chain

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->

- [Ethereum 2.0 Phase 0 -- The Beacon Chain](#ethereum-20-phase-0----the-beacon-chain)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Notation](#notation)
    - [Custom types](#custom-types)
    - [Constants](#constants)
    - [Configuration](#configuration)
        - [Misc](#misc)
        - [Gwei values](#gwei-values)
        - [Initial values](#initial-values)
        - [Time parameters](#time-parameters)
        - [State list lengths](#state-list-lengths)
        - [Rewards and penalties](#rewards-and-penalties)
        - [Max operations per block](#max-operations-per-block)
        - [Signature domain types](#signature-domain-types)
    - [Containers](#containers)
        - [Misc dependencies](#misc-dependencies)
            - [`Fork`](#fork)
            - [`Checkpoint`](#checkpoint)
            - [`Validator`](#validator)
            - [`Crosslink`](#crosslink)
            - [`AttestationData`](#attestationdata)
            - [`AttestationDataAndCustodyBit`](#attestationdataandcustodybit)
            - [`IndexedAttestation`](#indexedattestation)
            - [`PendingAttestation`](#pendingattestation)
            - [`Eth1Data`](#eth1data)
            - [`HistoricalBatch`](#historicalbatch)
            - [`DepositData`](#depositdata)
            - [`CompactCommittee`](#compactcommittee)
            - [`BeaconBlockHeader`](#beaconblockheader)
        - [Beacon operations](#beacon-operations)
            - [`ProposerSlashing`](#proposerslashing)
            - [`AttesterSlashing`](#attesterslashing)
            - [`Attestation`](#attestation)
            - [`Deposit`](#deposit)
            - [`VoluntaryExit`](#voluntaryexit)
            - [`Transfer`](#transfer)
        - [Beacon blocks](#beacon-blocks)
            - [`BeaconBlockBody`](#beaconblockbody)
            - [`BeaconBlock`](#beaconblock)
        - [Beacon state](#beacon-state)
            - [`BeaconState`](#beaconstate)
    - [Helper functions](#helper-functions)
        - [Math](#math)
            - [`integer_squareroot`](#integer_squareroot)
            - [`xor`](#xor)
            - [`int_to_bytes`](#int_to_bytes)
            - [`bytes_to_int`](#bytes_to_int)
        - [Crypto](#crypto)
            - [`hash`](#hash)
            - [`hash_tree_root`](#hash_tree_root)
            - [`signing_root`](#signing_root)
            - [`bls_verify`](#bls_verify)
            - [`bls_verify_multiple`](#bls_verify_multiple)
            - [`bls_aggregate_pubkeys`](#bls_aggregate_pubkeys)
        - [Predicates](#predicates)
            - [`is_active_validator`](#is_active_validator)
            - [`is_slashable_validator`](#is_slashable_validator)
            - [`is_slashable_attestation_data`](#is_slashable_attestation_data)
            - [`is_valid_indexed_attestation`](#is_valid_indexed_attestation)
            - [`is_valid_merkle_branch`](#is_valid_merkle_branch)
        - [Misc](#misc-1)
            - [`compute_shuffled_index`](#compute_shuffled_index)
            - [`compute_committee`](#compute_committee)
            - [`compute_epoch_of_slot`](#compute_epoch_of_slot)
            - [`compute_start_slot_of_epoch`](#compute_start_slot_of_epoch)
            - [`compute_activation_exit_epoch`](#compute_activation_exit_epoch)
            - [`compute_domain`](#compute_domain)
        - [Beacon state accessors](#beacon-state-accessors)
            - [`get_current_epoch`](#get_current_epoch)
            - [`get_previous_epoch`](#get_previous_epoch)
            - [`get_block_root`](#get_block_root)
            - [`get_block_root_at_slot`](#get_block_root_at_slot)
            - [`get_randao_mix`](#get_randao_mix)
            - [`get_active_validator_indices`](#get_active_validator_indices)
            - [`get_validator_churn_limit`](#get_validator_churn_limit)
            - [`get_seed`](#get_seed)
            - [`get_committee_count`](#get_committee_count)
            - [`get_crosslink_committee`](#get_crosslink_committee)
            - [`get_start_shard`](#get_start_shard)
            - [`get_shard_delta`](#get_shard_delta)
            - [`get_beacon_proposer_index`](#get_beacon_proposer_index)
            - [`get_attestation_data_slot`](#get_attestation_data_slot)
            - [`get_compact_committees_root`](#get_compact_committees_root)
            - [`get_total_balance`](#get_total_balance)
            - [`get_total_active_balance`](#get_total_active_balance)
            - [`get_domain`](#get_domain)
            - [`get_indexed_attestation`](#get_indexed_attestation)
            - [`get_attesting_indices`](#get_attesting_indices)
        - [Beacon state mutators](#beacon-state-mutators)
            - [`increase_balance`](#increase_balance)
            - [`decrease_balance`](#decrease_balance)
            - [`initiate_validator_exit`](#initiate_validator_exit)
            - [`slash_validator`](#slash_validator)
    - [Genesis](#genesis)
        - [Genesis state](#genesis-state)
        - [Genesis block](#genesis-block)
    - [Beacon chain state transition function](#beacon-chain-state-transition-function)
        - [Epoch processing](#epoch-processing)
            - [Helper functions](#helper-functions-1)
            - [Justification and finalization](#justification-and-finalization)
            - [Crosslinks](#crosslinks)
            - [Rewards and penalties](#rewards-and-penalties-1)
            - [Registry updates](#registry-updates)
            - [Slashings](#slashings)
            - [Final updates](#final-updates)
        - [Block processing](#block-processing)
            - [Block header](#block-header)
            - [RANDAO](#randao)
            - [Eth1 data](#eth1-data)
            - [Operations](#operations)
                - [Proposer slashings](#proposer-slashings)
                - [Attester slashings](#attester-slashings)
                - [Attestations](#attestations)
                - [Deposits](#deposits)
                - [Voluntary exits](#voluntary-exits)
                - [Transfers](#transfers)

<!-- /TOC -->

## Introduction

This document represents the specification for Phase 0 of Ethereum 2.0 -- The Beacon Chain.

At the core of Ethereum 2.0 is a system chain called the "beacon chain". The beacon chain stores and manages the registry of validators. In the initial deployment phases of Ethereum 2.0, the only mechanism to become a validator is to make a one-way ETH transaction to a deposit contract on Ethereum 1.0. Activation as a validator happens when Ethereum 1.0 deposit receipts are processed by the beacon chain, the activation balance is reached, and a queuing process is completed. Exit is either voluntary or done forcibly as a penalty for misbehavior.
The primary source of load on the beacon chain is "attestations". Attestations are simultaneously availability votes for a shard block and proof-of-stake votes for a beacon block. A sufficient number of attestations for the same shard block create a "crosslink", confirming the shard segment up to that shard block into the beacon chain. Crosslinks also serve as infrastructure for asynchronous cross-shard communication.

## Notation

Code snippets appearing in `this style` are to be interpreted as Python 3 code.

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `Slot` | `uint64` | a slot number |
| `Epoch` | `uint64` | an epoch number |
| `Shard` | `uint64` | a shard number |
| `ValidatorIndex` | `uint64` | a validator registry index |
| `Gwei` | `uint64` | an amount in Gwei |
| `Hash` | `Bytes32` | a hash |
| `Version` | `Bytes4` | a fork version number |
| `DomainType` | `Bytes4` | a signature domain type |
| `Domain` | `Bytes8` | a signature domain |
| `BLSPubkey` | `Bytes48` | a BLS12-381 public key |
| `BLSSignature` | `Bytes96` | a BLS12-381 signature |

## Constants

The following values are (non-configurable) constants used throughout the specification.

| Name | Value |
| - | - |
| `FAR_FUTURE_EPOCH` | `Epoch(2**64 - 1)` |
| `BASE_REWARDS_PER_EPOCH` | `5` |
| `DEPOSIT_CONTRACT_TREE_DEPTH` | `2**5` (= 32) |
| `SECONDS_PER_DAY` | `86400` |
| `JUSTIFICATION_BITS_LENGTH` | `4` |
| `ENDIANNESS` | `'little'` |

## Configuration

*Note*: The default mainnet configuration values are included here for spec-design purposes. The different configurations for mainnet, testnets, and YAML-based testing can be found in the [`configs/constant_presets`](../../configs/constant_presets) directory. These configurations are updated for releases and may be out of sync during `dev` changes.

### Misc

| Name | Value |
| - | - |
| `SHARD_COUNT` | `2**10` (= 1,024) |
| `TARGET_COMMITTEE_SIZE` | `2**7` (= 128) |
| `MAX_VALIDATORS_PER_COMMITTEE` | `2**12` (= 4,096) |
| `MIN_PER_EPOCH_CHURN_LIMIT` | `2**2` (= 4) |
| `CHURN_LIMIT_QUOTIENT` | `2**16` (= 65,536) |
| `SHUFFLE_ROUND_COUNT` | `90` |
| `MIN_GENESIS_ACTIVE_VALIDATOR_COUNT` | `2**16` (= 65,536) |
| `MIN_GENESIS_TIME` | `1578009600` (Jan 3, 2020) |

- For the safety of crosslinks, `TARGET_COMMITTEE_SIZE` exceeds [the recommended minimum committee size of 111](https://vitalik.ca/files/Ithaca201807_Sharding.pdf); with sufficient active validators (at least `SLOTS_PER_EPOCH * TARGET_COMMITTEE_SIZE`), the shuffling algorithm ensures committee sizes of at least `TARGET_COMMITTEE_SIZE`. (Unbiasable randomness with a Verifiable Delay Function (VDF) will improve committee robustness and lower the safe minimum committee size.)

### Gwei values

| Name | Value |
| - | - |
| `MIN_DEPOSIT_AMOUNT` | `Gwei(2**0 * 10**9)` (= 1,000,000,000) |
| `MAX_EFFECTIVE_BALANCE` | `Gwei(2**5 * 10**9)` (= 32,000,000,000) |
| `EJECTION_BALANCE` | `Gwei(2**4 * 10**9)` (= 16,000,000,000) |
| `EFFECTIVE_BALANCE_INCREMENT` | `Gwei(2**0 * 10**9)` (= 1,000,000,000) |

### Initial values

| Name | Value |
| - | - |
| `GENESIS_SLOT` | `Slot(0)` |
| `GENESIS_EPOCH` | `Epoch(0)` |
| `BLS_WITHDRAWAL_PREFIX` | `Bytes1(b'\x00')` |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `MIN_ATTESTATION_INCLUSION_DELAY` | `2**0` (= 1) | slots | 6 seconds |
| `SLOTS_PER_EPOCH` | `2**6` (= 64) | slots | 6.4 minutes |
| `MIN_SEED_LOOKAHEAD` | `2**0` (= 1) | epochs | 6.4 minutes |
| `ACTIVATION_EXIT_DELAY` | `2**2` (= 4) | epochs | 25.6 minutes |
| `SLOTS_PER_ETH1_VOTING_PERIOD` | `2**10` (= 1,024) | slots | ~1.7 hours |
| `SLOTS_PER_HISTORICAL_ROOT` | `2**13` (= 8,192) | slots | ~13 hours |
| `MIN_VALIDATOR_WITHDRAWABILITY_DELAY` | `2**8` (= 256) | epochs | ~27 hours |
| `PERSISTENT_COMMITTEE_PERIOD` | `2**11` (= 2,048) | epochs | 9 days |
| `MAX_EPOCHS_PER_CROSSLINK` | `2**6` (= 64) | epochs | ~7 hours |
| `MIN_EPOCHS_TO_INACTIVITY_PENALTY` | `2**2` (= 4) | epochs | 25.6 minutes |

### State list lengths

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `EPOCHS_PER_HISTORICAL_VECTOR` | `2**16` (= 65,536) | epochs | ~0.8 years |
| `EPOCHS_PER_SLASHINGS_VECTOR` | `2**13` (= 8,192) | epochs | ~36 days |
| `HISTORICAL_ROOTS_LIMIT` | `2**24` (= 16,777,216) | historical roots | ~26,131 years |
| `VALIDATOR_REGISTRY_LIMIT` | `2**40` (= 1,099,511,627,776) | validator spots |

### Rewards and penalties

| Name | Value |
| - | - |
| `BASE_REWARD_FACTOR` | `2**6` (= 64) |
| `WHISTLEBLOWER_REWARD_QUOTIENT` | `2**9` (= 512) |
| `PROPOSER_REWARD_QUOTIENT` | `2**3` (= 8) |
| `INACTIVITY_PENALTY_QUOTIENT` | `2**25` (= 33,554,432) |
| `MIN_SLASHING_PENALTY_QUOTIENT` | `2**5` (= 32) |

- The `INACTIVITY_PENALTY_QUOTIENT` equals `INVERSE_SQRT_E_DROP_TIME**2` where `INVERSE_SQRT_E_DROP_TIME := 2**12 epochs` (about 18 days) is the time it takes the inactivity penalty to reduce the balance of non-participating validators to about `1/sqrt(e) ~= 60.6%`. Indeed, the balance retained by offline validators after `n` epochs is about `(1 - 1/INACTIVITY_PENALTY_QUOTIENT)**(n**2/2)`; so after `INVERSE_SQRT_E_DROP_TIME` epochs, it is roughly `(1 - 1/INACTIVITY_PENALTY_QUOTIENT)**(INACTIVITY_PENALTY_QUOTIENT/2) ~= 1/sqrt(e)`.

### Max operations per block

| Name | Value |
| - | - |
| `MAX_PROPOSER_SLASHINGS` | `2**4` (= 16) |
| `MAX_ATTESTER_SLASHINGS` | `2**0` (= 1) |
| `MAX_ATTESTATIONS` | `2**7` (= 128) |
| `MAX_DEPOSITS` | `2**4` (= 16) |
| `MAX_VOLUNTARY_EXITS` | `2**4` (= 16) |
| `MAX_TRANSFERS` | `0` |

### Signature domain types

The following types are defined, mapping into `DomainType` (little endian):

| Name | Value |
| - | - |
| `DOMAIN_BEACON_PROPOSER` | `0` |
| `DOMAIN_RANDAO` | `1` |
| `DOMAIN_ATTESTATION` | `2` |
| `DOMAIN_DEPOSIT` | `3` |
| `DOMAIN_VOLUNTARY_EXIT` | `4` |
| `DOMAIN_TRANSFER` | `5` |

## Containers

The following types are [SimpleSerialize (SSZ)](../simple-serialize.md) containers.

*Note*: The definitions are ordered topologically to facilitate execution of the spec.

*Note*: Fields missing in container instantiations default to their zero value.

### Misc dependencies

#### `Fork`

```python
class Fork(Container):
    previous_version: Version
    current_version: Version
    epoch: Epoch  # Epoch of latest fork
```

#### `Checkpoint`

```python
class Checkpoint(Container):
    epoch: Epoch
    root: Hash
```

#### `Validator`

```python
class Validator(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Hash  # Commitment to pubkey for withdrawals and transfers
    effective_balance: Gwei  # Balance at stake
    slashed: boolean
    # Status epochs
    activation_eligibility_epoch: Epoch  # When criteria for activation were met
    activation_epoch: Epoch
    exit_epoch: Epoch
    withdrawable_epoch: Epoch  # When validator can withdraw or transfer funds
```

#### `Crosslink`

```python
class Crosslink(Container):
    shard: Shard
    parent_root: Hash
    # Crosslinking data
    start_epoch: Epoch
    end_epoch: Epoch
    data_root: Hash
```

#### `AttestationData`

```python
class AttestationData(Container):
    # LMD GHOST vote
    beacon_block_root: Hash
    # FFG vote
    source: Checkpoint
    target: Checkpoint
    # Crosslink vote
    crosslink: Crosslink
```

#### `AttestationDataAndCustodyBit`

```python
class AttestationDataAndCustodyBit(Container):
    data: AttestationData
    custody_bit: bit  # Challengeable bit (SSZ-bool, 1 byte) for the custody of crosslink data
```

#### `IndexedAttestation`

```python
class IndexedAttestation(Container):
    custody_bit_0_indices: List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE]  # Indices with custody bit equal to 0
    custody_bit_1_indices: List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE]  # Indices with custody bit equal to 1
    data: AttestationData
    signature: BLSSignature
```

#### `PendingAttestation`

```python
class PendingAttestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    inclusion_delay: Slot
    proposer_index: ValidatorIndex
```

#### `Eth1Data`

```python
class Eth1Data(Container):
    deposit_root: Hash
    deposit_count: uint64
    block_hash: Hash
```

#### `HistoricalBatch`

```python
class HistoricalBatch(Container):
    block_roots: Vector[Hash, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Hash, SLOTS_PER_HISTORICAL_ROOT]
```

#### `DepositData`

```python
class DepositData(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Hash
    amount: Gwei
    signature: BLSSignature
```

#### `CompactCommittee`

```python
class CompactCommittee(Container):
    pubkeys: List[BLSPubkey, MAX_VALIDATORS_PER_COMMITTEE]
    compact_validators: List[uint64, MAX_VALIDATORS_PER_COMMITTEE]
```

#### `BeaconBlockHeader`

```python
class BeaconBlockHeader(Container):
    slot: Slot
    parent_root: Hash
    state_root: Hash
    body_root: Hash
    signature: BLSSignature
```

### Beacon operations

#### `ProposerSlashing`

```python
class ProposerSlashing(Container):
    proposer_index: ValidatorIndex
    header_1: BeaconBlockHeader
    header_2: BeaconBlockHeader
```

#### `AttesterSlashing`

```python
class AttesterSlashing(Container):
    attestation_1: IndexedAttestation
    attestation_2: IndexedAttestation
```

#### `Attestation`

```python
class Attestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    custody_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    signature: BLSSignature
```

#### `Deposit`

```python
class Deposit(Container):
    proof: Vector[Hash, DEPOSIT_CONTRACT_TREE_DEPTH + 1]  # Merkle path to deposit data list root
    data: DepositData
```

#### `VoluntaryExit`

```python
class VoluntaryExit(Container):
    epoch: Epoch  # Earliest epoch when voluntary exit can be processed
    validator_index: ValidatorIndex
    signature: BLSSignature
```

#### `Transfer`

```python
class Transfer(Container):
    sender: ValidatorIndex
    recipient: ValidatorIndex
    amount: Gwei
    fee: Gwei
    slot: Slot  # Slot at which transfer must be processed
    pubkey: BLSPubkey  # Withdrawal pubkey
    signature: BLSSignature  # Signature checked against withdrawal pubkey
```

### Beacon blocks

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
    voluntary_exits: List[VoluntaryExit, MAX_VOLUNTARY_EXITS]
    transfers: List[Transfer, MAX_TRANSFERS]
```

#### `BeaconBlock`

```python
class BeaconBlock(Container):
    slot: Slot
    parent_root: Hash
    state_root: Hash
    body: BeaconBlockBody
    signature: BLSSignature
```

### Beacon state

#### `BeaconState`

```python
class BeaconState(Container):
    # Versioning
    genesis_time: uint64
    slot: Slot
    fork: Fork
    # History
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Hash, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Hash, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Hash, HISTORICAL_ROOTS_LIMIT]
    # Eth1
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, SLOTS_PER_ETH1_VOTING_PERIOD]
    eth1_deposit_index: uint64
    # Registry
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    # Shuffling
    start_shard: Shard
    randao_mixes: Vector[Hash, EPOCHS_PER_HISTORICAL_VECTOR]
    active_index_roots: Vector[Hash, EPOCHS_PER_HISTORICAL_VECTOR]  # Active index digests for light clients
    compact_committees_roots: Vector[Hash, EPOCHS_PER_HISTORICAL_VECTOR]  # Committee digests for light clients
    # Slashings
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]  # Per-epoch sums of slashed effective balances
    # Attestations
    previous_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    current_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    # Crosslinks
    previous_crosslinks: Vector[Crosslink, SHARD_COUNT]  # Previous epoch snapshot
    current_crosslinks: Vector[Crosslink, SHARD_COUNT]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint  # Previous epoch snapshot
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
```

## Helper functions

*Note*: The definitions below are for specification purposes and are not necessarily optimal implementations.

### Math

#### `integer_squareroot`

```python
def integer_squareroot(n: uint64) -> uint64:
    """
    Return the largest integer ``x`` such that ``x**2 <= n``.
    """
    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x
```

#### `xor`

```python
def xor(bytes1: Bytes32, bytes2: Bytes32) -> Bytes32:
    """
    Return the exclusive-or of two 32-byte strings.
    """
    return Bytes32(a ^ b for a, b in zip(bytes1, bytes2))
```

#### `int_to_bytes`

```python
def int_to_bytes(n: uint64, length: uint64) -> bytes:
    """
    Return the ``length``-byte serialization of ``n``.
    """
    return n.to_bytes(length, ENDIANNESS)
```

#### `bytes_to_int`

```python
def bytes_to_int(data: bytes) -> uint64:
    """
    Return the integer deserialization of ``data``.
    """
    return int.from_bytes(data, ENDIANNESS)
```

### Crypto

#### `hash`

`def hash(data: bytes) -> Hash` is SHA256.

#### `hash_tree_root`

`def hash_tree_root(object: SSZSerializable) -> Hash` is a function for hashing objects into a single root by utilizing a hash tree structure, as defined in the [SSZ spec](../simple-serialize.md#merkleization).

#### `signing_root`

`def signing_root(object: Container) -> Hash` is a function for computing signing messages, as defined in the [SSZ spec](../simple-serialize.md#self-signed-containers).

#### `bls_verify`

`bls_verify` is a function for verifying a BLS signature, as defined in the [BLS Signature spec](../bls_signature.md#bls_verify).

#### `bls_verify_multiple`

`bls_verify_multiple` is a function for verifying a BLS signature constructed from multiple messages, as defined in the [BLS Signature spec](../bls_signature.md#bls_verify_multiple).

#### `bls_aggregate_pubkeys`

`bls_aggregate_pubkeys` is a function for aggregating multiple BLS public keys into a single aggregate key, as defined in the [BLS Signature spec](../bls_signature.md#bls_aggregate_pubkeys).

### Predicates

#### `is_active_validator`

```python
def is_active_validator(validator: Validator, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is active.
    """
    return validator.activation_epoch <= epoch < validator.exit_epoch
```

#### `is_slashable_validator`

```python
def is_slashable_validator(validator: Validator, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is slashable.
    """
    return (not validator.slashed) and (validator.activation_epoch <= epoch < validator.withdrawable_epoch)
```

#### `is_slashable_attestation_data`

```python
def is_slashable_attestation_data(data_1: AttestationData, data_2: AttestationData) -> bool:
    """
    Check if ``data_1`` and ``data_2`` are slashable according to Casper FFG rules.
    """
    return (
        # Double vote
        (data_1 != data_2 and data_1.target.epoch == data_2.target.epoch) or
        # Surround vote
        (data_1.source.epoch < data_2.source.epoch and data_2.target.epoch < data_1.target.epoch)
    )
```

#### `is_valid_indexed_attestation`

```python
def is_valid_indexed_attestation(state: BeaconState, indexed_attestation: IndexedAttestation) -> bool:
    """
    Verify validity of ``indexed_attestation``.
    """
    bit_0_indices = indexed_attestation.custody_bit_0_indices
    bit_1_indices = indexed_attestation.custody_bit_1_indices

    # Verify no index has custody bit equal to 1 [to be removed in phase 1]
    if not len(bit_1_indices) == 0:
        return False
    # Verify max number of indices
    if not len(bit_0_indices) + len(bit_1_indices) <= MAX_VALIDATORS_PER_COMMITTEE:
        return False
    # Verify index sets are disjoint
    if not len(set(bit_0_indices).intersection(bit_1_indices)) == 0:
        return False
    # Verify indices are sorted
    if not (bit_0_indices == sorted(bit_0_indices) and bit_1_indices == sorted(bit_1_indices)):
        return False
    # Verify aggregate signature
    if not bls_verify_multiple(
        pubkeys=[
            bls_aggregate_pubkeys([state.validators[i].pubkey for i in bit_0_indices]),
            bls_aggregate_pubkeys([state.validators[i].pubkey for i in bit_1_indices]),
        ],
        message_hashes=[
            hash_tree_root(AttestationDataAndCustodyBit(data=indexed_attestation.data, custody_bit=0b0)),
            hash_tree_root(AttestationDataAndCustodyBit(data=indexed_attestation.data, custody_bit=0b1)),
        ],
        signature=indexed_attestation.signature,
        domain=get_domain(state, DOMAIN_ATTESTATION, indexed_attestation.data.target.epoch),
    ):
        return False
    return True
```

#### `is_valid_merkle_branch`

```python
def is_valid_merkle_branch(leaf: Hash, branch: Sequence[Hash], depth: uint64, index: uint64, root: Hash) -> bool:
    """
    Check if ``leaf`` at ``index`` verifies against the Merkle ``root`` and ``branch``.
    """
    value = leaf
    for i in range(depth):
        if index // (2**i) % 2:
            value = hash(branch[i] + value)
        else:
            value = hash(value + branch[i])
    return value == root
```

### Misc

#### `compute_shuffled_index`

```python
def compute_shuffled_index(index: ValidatorIndex, index_count: uint64, seed: Hash) -> ValidatorIndex:
    """
    Return the shuffled validator index corresponding to ``seed`` (and ``index_count``).
    """
    assert index < index_count

    # Swap or not (https://link.springer.com/content/pdf/10.1007%2F978-3-642-32009-5_1.pdf)
    # See the 'generalized domain' algorithm on page 3
    for current_round in range(SHUFFLE_ROUND_COUNT):
        pivot = bytes_to_int(hash(seed + int_to_bytes(current_round, length=1))[0:8]) % index_count
        flip = ValidatorIndex((pivot + index_count - index) % index_count)
        position = max(index, flip)
        source = hash(seed + int_to_bytes(current_round, length=1) + int_to_bytes(position // 256, length=4))
        byte = source[(position % 256) // 8]
        bit = (byte >> (position % 8)) % 2
        index = flip if bit else index

    return ValidatorIndex(index)
```

#### `compute_committee`

```python
def compute_committee(indices: Sequence[ValidatorIndex],
                      seed: Hash,
                      index: uint64,
                      count: uint64) -> Sequence[ValidatorIndex]:
    """
    Return the committee corresponding to ``indices``, ``seed``, ``index``, and committee ``count``.
    """
    start = (len(indices) * index) // count
    end = (len(indices) * (index + 1)) // count
    return [indices[compute_shuffled_index(ValidatorIndex(i), len(indices), seed)] for i in range(start, end)]
```

#### `compute_epoch_of_slot`

```python
def compute_epoch_of_slot(slot: Slot) -> Epoch:
    """
    Return the epoch number of ``slot``.
    """
    return Epoch(slot // SLOTS_PER_EPOCH)
```

#### `compute_start_slot_of_epoch`

```python
def compute_start_slot_of_epoch(epoch: Epoch) -> Slot:
    """
    Return the start slot of ``epoch``.
    """
    return Slot(epoch * SLOTS_PER_EPOCH)
```

#### `compute_activation_exit_epoch`

```python
def compute_activation_exit_epoch(epoch: Epoch) -> Epoch:
    """
    Return the epoch during which validator activations and exits initiated in ``epoch`` take effect.
    """
    return Epoch(epoch + 1 + ACTIVATION_EXIT_DELAY)
```

#### `compute_domain`

```python
def compute_domain(domain_type: DomainType, fork_version: Version=Version()) -> Domain:
    """
    Return the domain for the ``domain_type`` and ``fork_version``.
    """
    return Domain(domain_type + fork_version)
```

### Beacon state accessors

#### `get_current_epoch`

```python
def get_current_epoch(state: BeaconState) -> Epoch:
    """
    Return the current epoch.
    """
    return compute_epoch_of_slot(state.slot)
```

#### `get_previous_epoch`

```python
def get_previous_epoch(state: BeaconState) -> Epoch:
    """`
    Return the previous epoch (unless the current epoch is ``GENESIS_EPOCH``).
    """
    current_epoch = get_current_epoch(state)
    return GENESIS_EPOCH if current_epoch == GENESIS_EPOCH else Epoch(current_epoch - 1)
```

#### `get_block_root`

```python
def get_block_root(state: BeaconState, epoch: Epoch) -> Hash:
    """
    Return the block root at the start of a recent ``epoch``.
    """
    return get_block_root_at_slot(state, compute_start_slot_of_epoch(epoch))
```

#### `get_block_root_at_slot`

```python
def get_block_root_at_slot(state: BeaconState, slot: Slot) -> Hash:
    """
    Return the block root at a recent ``slot``.
    """
    assert slot < state.slot <= slot + SLOTS_PER_HISTORICAL_ROOT
    return state.block_roots[slot % SLOTS_PER_HISTORICAL_ROOT]
```

#### `get_randao_mix`

```python
def get_randao_mix(state: BeaconState, epoch: Epoch) -> Hash:
    """
    Return the randao mix at a recent ``epoch``.
    """
    return state.randao_mixes[epoch % EPOCHS_PER_HISTORICAL_VECTOR]
```

#### `get_active_validator_indices`

```python
def get_active_validator_indices(state: BeaconState, epoch: Epoch) -> Sequence[ValidatorIndex]:
    """
    Return the sequence of active validator indices at ``epoch``.
    """
    return [ValidatorIndex(i) for i, v in enumerate(state.validators) if is_active_validator(v, epoch)]
```

#### `get_validator_churn_limit`

```python
def get_validator_churn_limit(state: BeaconState) -> uint64:
    """
    Return the validator churn limit for the current epoch.
    """
    active_validator_indices = get_active_validator_indices(state, get_current_epoch(state))
    return max(MIN_PER_EPOCH_CHURN_LIMIT, len(active_validator_indices) // CHURN_LIMIT_QUOTIENT)
```

#### `get_seed`

```python
def get_seed(state: BeaconState, epoch: Epoch) -> Hash:
    """
    Return the seed at ``epoch``.
    """
    mix = get_randao_mix(state, Epoch(epoch + EPOCHS_PER_HISTORICAL_VECTOR - MIN_SEED_LOOKAHEAD))  # Avoid underflow
    active_index_root = state.active_index_roots[epoch % EPOCHS_PER_HISTORICAL_VECTOR]
    return hash(mix + active_index_root + int_to_bytes(epoch, length=32))
```

#### `get_committee_count`

```python
def get_committee_count(state: BeaconState, epoch: Epoch) -> uint64:
    """
    Return the number of committees at ``epoch``.
    """
    committees_per_slot = max(1, min(
        SHARD_COUNT // SLOTS_PER_EPOCH,
        len(get_active_validator_indices(state, epoch)) // SLOTS_PER_EPOCH // TARGET_COMMITTEE_SIZE,
    ))
    return committees_per_slot * SLOTS_PER_EPOCH
```

#### `get_crosslink_committee`

```python
def get_crosslink_committee(state: BeaconState, epoch: Epoch, shard: Shard) -> Sequence[ValidatorIndex]:
    """
    Return the crosslink committee at ``epoch`` for ``shard``.
    """
    return compute_committee(
        indices=get_active_validator_indices(state, epoch),
        seed=get_seed(state, epoch),
        index=(shard + SHARD_COUNT - get_start_shard(state, epoch)) % SHARD_COUNT,
        count=get_committee_count(state, epoch),
    )
```

#### `get_start_shard`

```python
def get_start_shard(state: BeaconState, epoch: Epoch) -> Shard:
    """
    Return the start shard of the 0th committee at ``epoch``.
    """
    assert epoch <= get_current_epoch(state) + 1
    check_epoch = Epoch(get_current_epoch(state) + 1)
    shard = Shard((state.start_shard + get_shard_delta(state, get_current_epoch(state))) % SHARD_COUNT)
    while check_epoch > epoch:
        check_epoch -= Epoch(1)
        shard = Shard((shard + SHARD_COUNT - get_shard_delta(state, check_epoch)) % SHARD_COUNT)
    return shard
```

#### `get_shard_delta`

```python
def get_shard_delta(state: BeaconState, epoch: Epoch) -> uint64:
    """
    Return the number of shards to increment ``state.start_shard`` at ``epoch``.
    """
    return min(get_committee_count(state, epoch), SHARD_COUNT - SHARD_COUNT // SLOTS_PER_EPOCH)
```

#### `get_beacon_proposer_index`

```python
def get_beacon_proposer_index(state: BeaconState) -> ValidatorIndex:
    """
    Return the beacon proposer index at the current slot.
    """
    epoch = get_current_epoch(state)
    committees_per_slot = get_committee_count(state, epoch) // SLOTS_PER_EPOCH
    offset = committees_per_slot * (state.slot % SLOTS_PER_EPOCH)
    shard = Shard((get_start_shard(state, epoch) + offset) % SHARD_COUNT)
    first_committee = get_crosslink_committee(state, epoch, shard)
    MAX_RANDOM_BYTE = 2**8 - 1
    seed = get_seed(state, epoch)
    i = 0
    while True:
        candidate_index = first_committee[(epoch + i) % len(first_committee)]
        random_byte = hash(seed + int_to_bytes(i // 32, length=8))[i % 32]
        effective_balance = state.validators[candidate_index].effective_balance
        if effective_balance * MAX_RANDOM_BYTE >= MAX_EFFECTIVE_BALANCE * random_byte:
            return ValidatorIndex(candidate_index)
        i += 1
```

#### `get_attestation_data_slot`

```python
def get_attestation_data_slot(state: BeaconState, data: AttestationData) -> Slot:
    """
    Return the slot corresponding to the attestation ``data``.
    """
    committee_count = get_committee_count(state, data.target.epoch)
    offset = (data.crosslink.shard + SHARD_COUNT - get_start_shard(state, data.target.epoch)) % SHARD_COUNT
    return Slot(compute_start_slot_of_epoch(data.target.epoch) + offset // (committee_count // SLOTS_PER_EPOCH))
```

#### `get_compact_committees_root`

```python
def get_compact_committees_root(state: BeaconState, epoch: Epoch) -> Hash:
    """
    Return the compact committee root at ``epoch``.
    """
    committees = [CompactCommittee() for _ in range(SHARD_COUNT)]
    start_shard = get_start_shard(state, epoch)
    for committee_number in range(get_committee_count(state, epoch)):
        shard = Shard((start_shard + committee_number) % SHARD_COUNT)
        for index in get_crosslink_committee(state, epoch, shard):
            validator = state.validators[index]
            committees[shard].pubkeys.append(validator.pubkey)
            compact_balance = validator.effective_balance // EFFECTIVE_BALANCE_INCREMENT
            # `index` (top 6 bytes) + `slashed` (16th bit) + `compact_balance` (bottom 15 bits)
            compact_validator = uint64((index << 16) + (validator.slashed << 15) + compact_balance)
            committees[shard].compact_validators.append(compact_validator)
    return hash_tree_root(Vector[CompactCommittee, SHARD_COUNT](committees))
```

#### `get_total_balance`

```python
def get_total_balance(state: BeaconState, indices: Set[ValidatorIndex]) -> Gwei:
    """
    Return the combined effective balance of the ``indices``. (1 Gwei minimum to avoid divisions by zero.)
    """
    return Gwei(max(sum([state.validators[index].effective_balance for index in indices]), 1))
```

#### `get_total_active_balance`

```python
def get_total_active_balance(state: BeaconState) -> Gwei:
    """
    Return the combined effective balance of the active validators.
    """
    return get_total_balance(state, set(get_active_validator_indices(state, get_current_epoch(state))))
```

#### `get_domain`

```python
def get_domain(state: BeaconState, domain_type: DomainType, message_epoch: Epoch=None) -> Domain:
    """
    Return the signature domain (fork version concatenated with domain type) of a message.
    """
    epoch = get_current_epoch(state) if message_epoch is None else message_epoch
    fork_version = state.fork.previous_version if epoch < state.fork.epoch else state.fork.current_version
    return compute_domain(domain_type, fork_version)
```

#### `get_indexed_attestation`

```python
def get_indexed_attestation(state: BeaconState, attestation: Attestation) -> IndexedAttestation:
    """
    Return the indexed attestation corresponding to ``attestation``.
    """
    attesting_indices = get_attesting_indices(state, attestation.data, attestation.aggregation_bits)
    custody_bit_1_indices = get_attesting_indices(state, attestation.data, attestation.custody_bits)
    assert custody_bit_1_indices.issubset(attesting_indices)
    custody_bit_0_indices = attesting_indices.difference(custody_bit_1_indices)

    return IndexedAttestation(
        custody_bit_0_indices=sorted(custody_bit_0_indices),
        custody_bit_1_indices=sorted(custody_bit_1_indices),
        data=attestation.data,
        signature=attestation.signature,
    )
```

#### `get_attesting_indices`

```python
def get_attesting_indices(state: BeaconState,
                          data: AttestationData,
                          bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]) -> Set[ValidatorIndex]:
    """
    Return the set of attesting indices corresponding to ``data`` and ``bits``.
    """
    committee = get_crosslink_committee(state, data.target.epoch, data.crosslink.shard)
    return set(index for i, index in enumerate(committee) if bits[i])
```

### Beacon state mutators

#### `increase_balance`

```python
def increase_balance(state: BeaconState, index: ValidatorIndex, delta: Gwei) -> None:
    """
    Increase the validator balance at index ``index`` by ``delta``.
    """
    state.balances[index] += delta
```

#### `decrease_balance`

```python
def decrease_balance(state: BeaconState, index: ValidatorIndex, delta: Gwei) -> None:
    """
    Decrease the validator balance at index ``index`` by ``delta``, with underflow protection.
    """
    state.balances[index] = 0 if delta > state.balances[index] else state.balances[index] - delta
```

#### `initiate_validator_exit`

```python
def initiate_validator_exit(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Initiate the exit of the validator with index ``index``.
    """
    # Return if validator already initiated exit
    validator = state.validators[index]
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return

    # Compute exit queue epoch
    exit_epochs = [v.exit_epoch for v in state.validators if v.exit_epoch != FAR_FUTURE_EPOCH]
    exit_queue_epoch = max(exit_epochs + [compute_activation_exit_epoch(get_current_epoch(state))])
    exit_queue_churn = len([v for v in state.validators if v.exit_epoch == exit_queue_epoch])
    if exit_queue_churn >= get_validator_churn_limit(state):
        exit_queue_epoch += Epoch(1)

    # Set validator exit epoch and withdrawable epoch
    validator.exit_epoch = exit_queue_epoch
    validator.withdrawable_epoch = Epoch(validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY)
```

#### `slash_validator`

```python
def slash_validator(state: BeaconState,
                    slashed_index: ValidatorIndex,
                    whistleblower_index: ValidatorIndex=None) -> None:
    """
    Slash the validator with index ``slashed_index``.
    """
    epoch = get_current_epoch(state)
    initiate_validator_exit(state, slashed_index)
    validator = state.validators[slashed_index]
    validator.slashed = True
    validator.withdrawable_epoch = max(validator.withdrawable_epoch, Epoch(epoch + EPOCHS_PER_SLASHINGS_VECTOR))
    state.slashings[epoch % EPOCHS_PER_SLASHINGS_VECTOR] += validator.effective_balance
    decrease_balance(state, slashed_index, validator.effective_balance // MIN_SLASHING_PENALTY_QUOTIENT)

    # Apply proposer and whistleblower rewards
    proposer_index = get_beacon_proposer_index(state)
    if whistleblower_index is None:
        whistleblower_index = proposer_index
    whistleblower_reward = Gwei(validator.effective_balance // WHISTLEBLOWER_REWARD_QUOTIENT)
    proposer_reward = Gwei(whistleblower_reward // PROPOSER_REWARD_QUOTIENT)
    increase_balance(state, proposer_index, proposer_reward)
    increase_balance(state, whistleblower_index, whistleblower_reward - proposer_reward)
```

## Genesis

Before the Ethereum 2.0 genesis has been triggered, and for every Ethereum 1.0 block, let `candidate_state = initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)` where:

- `eth1_block_hash` is the hash of the Ethereum 1.0 block
- `eth1_timestamp` is the Unix timestamp corresponding to `eth1_block_hash`
- `deposits` is the sequence of all deposits, ordered chronologically, up to the block with hash `eth1_block_hash`

```python
def initialize_beacon_state_from_eth1(eth1_block_hash: Hash,
                                      eth1_timestamp: uint64,
                                      deposits: Sequence[Deposit]) -> BeaconState:
    state = BeaconState(
        genesis_time=eth1_timestamp - eth1_timestamp % SECONDS_PER_DAY + 2 * SECONDS_PER_DAY,
        eth1_data=Eth1Data(block_hash=eth1_block_hash, deposit_count=len(deposits)),
        latest_block_header=BeaconBlockHeader(body_root=hash_tree_root(BeaconBlockBody())),
    )

    # Process deposits
    leaves = list(map(lambda deposit: deposit.data, deposits))
    for index, deposit in enumerate(deposits):
        deposit_data_list = List[DepositData, 2**DEPOSIT_CONTRACT_TREE_DEPTH](*leaves[:index + 1])
        state.eth1_data.deposit_root = hash_tree_root(deposit_data_list)
        process_deposit(state, deposit)

    # Process activations
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        validator.effective_balance = min(balance - balance % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE)
        if validator.effective_balance == MAX_EFFECTIVE_BALANCE:
            validator.activation_eligibility_epoch = GENESIS_EPOCH
            validator.activation_epoch = GENESIS_EPOCH

    # Populate active_index_roots and compact_committees_roots
    indices_list = List[ValidatorIndex, VALIDATOR_REGISTRY_LIMIT](get_active_validator_indices(state, GENESIS_EPOCH))
    active_index_root = hash_tree_root(indices_list)
    committee_root = get_compact_committees_root(state, GENESIS_EPOCH)
    for index in range(EPOCHS_PER_HISTORICAL_VECTOR):
        state.active_index_roots[index] = active_index_root
        state.compact_committees_roots[index] = committee_root
    return state
```

### Genesis state

Let `genesis_state = candidate_state` whenever `is_valid_genesis_state(candidate_state) is True` for the first time.

```python
def is_valid_genesis_state(state: BeaconState) -> bool:
    if state.genesis_time < MIN_GENESIS_TIME:
        return False
    if len(get_active_validator_indices(state, GENESIS_EPOCH)) < MIN_GENESIS_ACTIVE_VALIDATOR_COUNT:
        return False
    return True
```

*Note*: The `is_valid_genesis_state` function (including `MIN_GENESIS_TIME` and `MIN_GENESIS_ACTIVE_VALIDATOR_COUNT`) is a placeholder for testing. It has yet to be finalized by the community, and can be updated as necessary.

### Genesis block

Let `genesis_block = BeaconBlock(state_root=hash_tree_root(genesis_state))`.

## Beacon chain state transition function

The post-state corresponding to a pre-state `state` and a block `block` is defined as `state_transition(state, block)`. State transitions that trigger an unhandled exception (e.g. a failed `assert` or an out-of-range list access) are considered invalid.

```python
def state_transition(state: BeaconState, block: BeaconBlock, validate_state_root: bool=False) -> BeaconState:
    # Process slots (including those with no blocks) since block
    process_slots(state, block.slot)
    # Process block
    process_block(state, block)
    # Validate state root (`validate_state_root == True` in production)
    if validate_state_root:
        assert block.state_root == hash_tree_root(state)
    # Return post-state
    return state
```

```python
def process_slots(state: BeaconState, slot: Slot) -> None:
    assert state.slot <= slot
    while state.slot < slot:
        process_slot(state)
        # Process epoch on the start slot of the next epoch
        if (state.slot + 1) % SLOTS_PER_EPOCH == 0:
            process_epoch(state)
        state.slot += Slot(1)
```

```python
def process_slot(state: BeaconState) -> None:
    # Cache state root
    previous_state_root = hash_tree_root(state)
    state.state_roots[state.slot % SLOTS_PER_HISTORICAL_ROOT] = previous_state_root
    # Cache latest block header state root
    if state.latest_block_header.state_root == Hash():
        state.latest_block_header.state_root = previous_state_root
    # Cache block root
    previous_block_root = signing_root(state.latest_block_header)
    state.block_roots[state.slot % SLOTS_PER_HISTORICAL_ROOT] = previous_block_root
```

### Epoch processing

*Note*: The `# @LabelHere` lines below are placeholders to show that code will be inserted here in a future phase.

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_crosslinks(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    # @process_reveal_deadlines
    # @process_challenge_deadlines
    process_slashings(state)
    process_final_updates(state)
    # @after_process_final_updates
```

#### Helper functions

```python
def get_matching_source_attestations(state: BeaconState, epoch: Epoch) -> Sequence[PendingAttestation]:
    assert epoch in (get_previous_epoch(state), get_current_epoch(state))
    return state.current_epoch_attestations if epoch == get_current_epoch(state) else state.previous_epoch_attestations
```

```python
def get_matching_target_attestations(state: BeaconState, epoch: Epoch) -> Sequence[PendingAttestation]:
    return [
        a for a in get_matching_source_attestations(state, epoch)
        if a.data.target.root == get_block_root(state, epoch)
    ]
```

```python
def get_matching_head_attestations(state: BeaconState, epoch: Epoch) -> Sequence[PendingAttestation]:
    return [
        a for a in get_matching_source_attestations(state, epoch)
        if a.data.beacon_block_root == get_block_root_at_slot(state, get_attestation_data_slot(state, a.data))
    ]
```

```python
def get_unslashed_attesting_indices(state: BeaconState,
                                    attestations: Sequence[PendingAttestation]) -> Set[ValidatorIndex]:
    output = set()  # type: Set[ValidatorIndex]
    for a in attestations:
        output = output.union(get_attesting_indices(state, a.data, a.aggregation_bits))
    return set(filter(lambda index: not state.validators[index].slashed, list(output)))
```

```python
def get_attesting_balance(state: BeaconState, attestations: Sequence[PendingAttestation]) -> Gwei:
    return get_total_balance(state, get_unslashed_attesting_indices(state, attestations))
```

```python
def get_winning_crosslink_and_attesting_indices(state: BeaconState,
                                                epoch: Epoch,
                                                shard: Shard) -> Tuple[Crosslink, Set[ValidatorIndex]]:
    attestations = [a for a in get_matching_source_attestations(state, epoch) if a.data.crosslink.shard == shard]
    crosslinks = list(filter(
        lambda c: hash_tree_root(state.current_crosslinks[shard]) in (c.parent_root, hash_tree_root(c)),
        [a.data.crosslink for a in attestations]
    ))
    # Winning crosslink has the crosslink data root with the most balance voting for it (ties broken lexicographically)
    winning_crosslink = max(crosslinks, key=lambda c: (
        get_attesting_balance(state, [a for a in attestations if a.data.crosslink == c]), c.data_root
    ), default=Crosslink())
    winning_attestations = [a for a in attestations if a.data.crosslink == winning_crosslink]
    return winning_crosslink, get_unslashed_attesting_indices(state, winning_attestations)
```

#### Justification and finalization

```python
def process_justification_and_finalization(state: BeaconState) -> None:
    if get_current_epoch(state) <= GENESIS_EPOCH + 1:
        return

    previous_epoch = get_previous_epoch(state)
    current_epoch = get_current_epoch(state)
    old_previous_justified_checkpoint = state.previous_justified_checkpoint
    old_current_justified_checkpoint = state.current_justified_checkpoint

    # Process justifications
    state.previous_justified_checkpoint = state.current_justified_checkpoint
    state.justification_bits[1:] = state.justification_bits[:-1]
    state.justification_bits[0] = 0b0
    matching_target_attestations = get_matching_target_attestations(state, previous_epoch)  # Previous epoch
    if get_attesting_balance(state, matching_target_attestations) * 3 >= get_total_active_balance(state) * 2:
        state.current_justified_checkpoint = Checkpoint(epoch=previous_epoch,
                                                        root=get_block_root(state, previous_epoch))
        state.justification_bits[1] = 0b1
    matching_target_attestations = get_matching_target_attestations(state, current_epoch)  # Current epoch
    if get_attesting_balance(state, matching_target_attestations) * 3 >= get_total_active_balance(state) * 2:
        state.current_justified_checkpoint = Checkpoint(epoch=current_epoch,
                                                        root=get_block_root(state, current_epoch))
        state.justification_bits[0] = 0b1

    # Process finalizations
    bits = state.justification_bits
    # The 2nd/3rd/4th most recent epochs are justified, the 2nd using the 4th as source
    if all(bits[1:4]) and old_previous_justified_checkpoint.epoch + 3 == current_epoch:
        state.finalized_checkpoint = old_previous_justified_checkpoint
    # The 2nd/3rd most recent epochs are justified, the 2nd using the 3rd as source
    if all(bits[1:3]) and old_previous_justified_checkpoint.epoch + 2 == current_epoch:
        state.finalized_checkpoint = old_previous_justified_checkpoint
    # The 1st/2nd/3rd most recent epochs are justified, the 1st using the 3rd as source
    if all(bits[0:3]) and old_current_justified_checkpoint.epoch + 2 == current_epoch:
        state.finalized_checkpoint = old_current_justified_checkpoint
    # The 1st/2nd most recent epochs are justified, the 1st using the 2nd as source
    if all(bits[0:2]) and old_current_justified_checkpoint.epoch + 1 == current_epoch:
        state.finalized_checkpoint = old_current_justified_checkpoint
```

#### Crosslinks

```python
def process_crosslinks(state: BeaconState) -> None:
    state.previous_crosslinks = [c for c in state.current_crosslinks]
    for epoch in (get_previous_epoch(state), get_current_epoch(state)):
        for offset in range(get_committee_count(state, epoch)):
            shard = Shard((get_start_shard(state, epoch) + offset) % SHARD_COUNT)
            crosslink_committee = set(get_crosslink_committee(state, epoch, shard))
            winning_crosslink, attesting_indices = get_winning_crosslink_and_attesting_indices(state, epoch, shard)
            if 3 * get_total_balance(state, attesting_indices) >= 2 * get_total_balance(state, crosslink_committee):
                state.current_crosslinks[shard] = winning_crosslink
```

#### Rewards and penalties

```python
def get_base_reward(state: BeaconState, index: ValidatorIndex) -> Gwei:
    total_balance = get_total_active_balance(state)
    effective_balance = state.validators[index].effective_balance
    return Gwei(effective_balance * BASE_REWARD_FACTOR // integer_squareroot(total_balance) // BASE_REWARDS_PER_EPOCH)
```

```python
def get_attestation_deltas(state: BeaconState) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    previous_epoch = get_previous_epoch(state)
    total_balance = get_total_active_balance(state)
    rewards = [Gwei(0) for _ in range(len(state.validators))]
    penalties = [Gwei(0) for _ in range(len(state.validators))]
    eligible_validator_indices = [
        ValidatorIndex(index) for index, v in enumerate(state.validators)
        if is_active_validator(v, previous_epoch) or (v.slashed and previous_epoch + 1 < v.withdrawable_epoch)
    ]

    # Micro-incentives for matching FFG source, FFG target, and head
    matching_source_attestations = get_matching_source_attestations(state, previous_epoch)
    matching_target_attestations = get_matching_target_attestations(state, previous_epoch)
    matching_head_attestations = get_matching_head_attestations(state, previous_epoch)
    for attestations in (matching_source_attestations, matching_target_attestations, matching_head_attestations):
        unslashed_attesting_indices = get_unslashed_attesting_indices(state, attestations)
        attesting_balance = get_total_balance(state, unslashed_attesting_indices)
        for index in eligible_validator_indices:
            if index in unslashed_attesting_indices:
                rewards[index] += get_base_reward(state, index) * attesting_balance // total_balance
            else:
                penalties[index] += get_base_reward(state, index)

    # Proposer and inclusion delay micro-rewards
    for index in get_unslashed_attesting_indices(state, matching_source_attestations):
        attestation = min([
            a for a in matching_source_attestations
            if index in get_attesting_indices(state, a.data, a.aggregation_bits)
        ], key=lambda a: a.inclusion_delay)
        proposer_reward = Gwei(get_base_reward(state, index) // PROPOSER_REWARD_QUOTIENT)
        rewards[attestation.proposer_index] += proposer_reward
        max_attester_reward = get_base_reward(state, index) - proposer_reward
        rewards[index] += Gwei(
            max_attester_reward
            * (SLOTS_PER_EPOCH + MIN_ATTESTATION_INCLUSION_DELAY - attestation.inclusion_delay)
            // SLOTS_PER_EPOCH
        )

    # Inactivity penalty
    finality_delay = previous_epoch - state.finalized_checkpoint.epoch
    if finality_delay > MIN_EPOCHS_TO_INACTIVITY_PENALTY:
        matching_target_attesting_indices = get_unslashed_attesting_indices(state, matching_target_attestations)
        for index in eligible_validator_indices:
            penalties[index] += Gwei(BASE_REWARDS_PER_EPOCH * get_base_reward(state, index))
            if index not in matching_target_attesting_indices:
                penalties[index] += Gwei(
                    state.validators[index].effective_balance * finality_delay // INACTIVITY_PENALTY_QUOTIENT
                )

    return rewards, penalties
```

```python
def get_crosslink_deltas(state: BeaconState) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    rewards = [Gwei(0) for _ in range(len(state.validators))]
    penalties = [Gwei(0) for _ in range(len(state.validators))]
    epoch = get_previous_epoch(state)
    for offset in range(get_committee_count(state, epoch)):
        shard = Shard((get_start_shard(state, epoch) + offset) % SHARD_COUNT)
        crosslink_committee = set(get_crosslink_committee(state, epoch, shard))
        winning_crosslink, attesting_indices = get_winning_crosslink_and_attesting_indices(state, epoch, shard)
        attesting_balance = get_total_balance(state, attesting_indices)
        committee_balance = get_total_balance(state, crosslink_committee)
        for index in crosslink_committee:
            base_reward = get_base_reward(state, index)
            if index in attesting_indices:
                rewards[index] += base_reward * attesting_balance // committee_balance
            else:
                penalties[index] += base_reward
    return rewards, penalties
```

```python
def process_rewards_and_penalties(state: BeaconState) -> None:
    if get_current_epoch(state) == GENESIS_EPOCH:
        return

    rewards1, penalties1 = get_attestation_deltas(state)
    rewards2, penalties2 = get_crosslink_deltas(state)
    for index in range(len(state.validators)):
        increase_balance(state, ValidatorIndex(index), rewards1[index] + rewards2[index])
        decrease_balance(state, ValidatorIndex(index), penalties1[index] + penalties2[index])
```

#### Registry updates

```python
def process_registry_updates(state: BeaconState) -> None:
    # Process activation eligibility and ejections
    for index, validator in enumerate(state.validators):
        if (
            validator.activation_eligibility_epoch == FAR_FUTURE_EPOCH
            and validator.effective_balance == MAX_EFFECTIVE_BALANCE
        ):
            validator.activation_eligibility_epoch = get_current_epoch(state)

        if is_active_validator(validator, get_current_epoch(state)) and validator.effective_balance <= EJECTION_BALANCE:
            initiate_validator_exit(state, ValidatorIndex(index))

    # Queue validators eligible for activation and not dequeued for activation prior to finalized epoch
    activation_queue = sorted([
        index for index, validator in enumerate(state.validators)
        if validator.activation_eligibility_epoch != FAR_FUTURE_EPOCH
        and validator.activation_epoch >= compute_activation_exit_epoch(state.finalized_checkpoint.epoch)
    ], key=lambda index: state.validators[index].activation_eligibility_epoch)
    # Dequeued validators for activation up to churn limit (without resetting activation epoch)
    for index in activation_queue[:get_validator_churn_limit(state)]:
        validator = state.validators[index]
        if validator.activation_epoch == FAR_FUTURE_EPOCH:
            validator.activation_epoch = compute_activation_exit_epoch(get_current_epoch(state))
```

#### Slashings

```python
def process_slashings(state: BeaconState) -> None:
    epoch = get_current_epoch(state)
    total_balance = get_total_active_balance(state)
    for index, validator in enumerate(state.validators):
        if validator.slashed and epoch + EPOCHS_PER_SLASHINGS_VECTOR // 2 == validator.withdrawable_epoch:
            increment = EFFECTIVE_BALANCE_INCREMENT  # Factored out from penalty numerator to avoid uint64 overflow
            penalty_numerator = validator.effective_balance // increment * min(sum(state.slashings) * 3, total_balance)
            penalty = penalty_numerator // total_balance * increment
            decrease_balance(state, ValidatorIndex(index), penalty)
```

#### Final updates

```python
def process_final_updates(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    next_epoch = Epoch(current_epoch + 1)
    # Reset eth1 data votes
    if (state.slot + 1) % SLOTS_PER_ETH1_VOTING_PERIOD == 0:
        state.eth1_data_votes = []
    # Update effective balances with hysteresis
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        HALF_INCREMENT = EFFECTIVE_BALANCE_INCREMENT // 2
        if balance < validator.effective_balance or validator.effective_balance + 3 * HALF_INCREMENT < balance:
            validator.effective_balance = min(balance - balance % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE)
    # Update start shard
    state.start_shard = Shard((state.start_shard + get_shard_delta(state, current_epoch)) % SHARD_COUNT)
    # Set active index root
    index_epoch = Epoch(next_epoch + ACTIVATION_EXIT_DELAY)
    index_root_position = index_epoch % EPOCHS_PER_HISTORICAL_VECTOR
    indices_list = List[ValidatorIndex, VALIDATOR_REGISTRY_LIMIT](get_active_validator_indices(state, index_epoch))
    state.active_index_roots[index_root_position] = hash_tree_root(indices_list)
    # Set committees root
    committee_root_position = next_epoch % EPOCHS_PER_HISTORICAL_VECTOR
    state.compact_committees_roots[committee_root_position] = get_compact_committees_root(state, next_epoch)
    # Reset slashings
    state.slashings[next_epoch % EPOCHS_PER_SLASHINGS_VECTOR] = Gwei(0)
    # Set randao mix
    state.randao_mixes[next_epoch % EPOCHS_PER_HISTORICAL_VECTOR] = get_randao_mix(state, current_epoch)
    # Set historical root accumulator
    if next_epoch % (SLOTS_PER_HISTORICAL_ROOT // SLOTS_PER_EPOCH) == 0:
        historical_batch = HistoricalBatch(block_roots=state.block_roots, state_roots=state.state_roots)
        state.historical_roots.append(hash_tree_root(historical_batch))
    # Rotate current/previous epoch attestations
    state.previous_epoch_attestations = state.current_epoch_attestations
    state.current_epoch_attestations = []
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
```

#### Block header

```python
def process_block_header(state: BeaconState, block: BeaconBlock) -> None:
    # Verify that the slots match
    assert block.slot == state.slot
    # Verify that the parent matches
    assert block.parent_root == signing_root(state.latest_block_header)
    # Save current block as the new latest block
    state.latest_block_header = BeaconBlockHeader(
        slot=block.slot,
        parent_root=block.parent_root,
        state_root=Hash(),  # Overwritten in the next `process_slot` call
        body_root=hash_tree_root(block.body),
    )
    # Verify proposer is not slashed
    proposer = state.validators[get_beacon_proposer_index(state)]
    assert not proposer.slashed
    # Verify proposer signature
    assert bls_verify(proposer.pubkey, signing_root(block), block.signature, get_domain(state, DOMAIN_BEACON_PROPOSER))
```

#### RANDAO

```python
def process_randao(state: BeaconState, body: BeaconBlockBody) -> None:
    epoch = get_current_epoch(state)
    # Verify RANDAO reveal
    proposer = state.validators[get_beacon_proposer_index(state)]
    assert bls_verify(proposer.pubkey, hash_tree_root(epoch), body.randao_reveal, get_domain(state, DOMAIN_RANDAO))
    # Mix in RANDAO reveal
    mix = xor(get_randao_mix(state, epoch), hash(body.randao_reveal))
    state.randao_mixes[epoch % EPOCHS_PER_HISTORICAL_VECTOR] = mix
```

#### Eth1 data

```python
def process_eth1_data(state: BeaconState, body: BeaconBlockBody) -> None:
    state.eth1_data_votes.append(body.eth1_data)
    if state.eth1_data_votes.count(body.eth1_data) * 2 > SLOTS_PER_ETH1_VOTING_PERIOD:
        state.eth1_data = body.eth1_data
```

#### Operations

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # Verify that outstanding deposits are processed up to the maximum number of deposits
    assert len(body.deposits) == min(MAX_DEPOSITS, state.eth1_data.deposit_count - state.eth1_deposit_index)
    # Verify that there are no duplicate transfers
    assert len(body.transfers) == len(set(body.transfers))

    for operations, function in (
        (body.proposer_slashings, process_proposer_slashing),
        (body.attester_slashings, process_attester_slashing),
        (body.attestations, process_attestation),
        (body.deposits, process_deposit),
        (body.voluntary_exits, process_voluntary_exit),
        (body.transfers, process_transfer),
    ):
        for operation in operations:
            function(state, operation)
```

##### Proposer slashings

```python
def process_proposer_slashing(state: BeaconState, proposer_slashing: ProposerSlashing) -> None:
    proposer = state.validators[proposer_slashing.proposer_index]
    # Verify that the epoch is the same
    assert (compute_epoch_of_slot(proposer_slashing.header_1.slot)
            == compute_epoch_of_slot(proposer_slashing.header_2.slot))
    # But the headers are different
    assert proposer_slashing.header_1 != proposer_slashing.header_2
    # Check proposer is slashable
    assert is_slashable_validator(proposer, get_current_epoch(state))
    # Signatures are valid
    for header in (proposer_slashing.header_1, proposer_slashing.header_2):
        domain = get_domain(state, DOMAIN_BEACON_PROPOSER, compute_epoch_of_slot(header.slot))
        assert bls_verify(proposer.pubkey, signing_root(header), header.signature, domain)

    slash_validator(state, proposer_slashing.proposer_index)
```

##### Attester slashings

```python
def process_attester_slashing(state: BeaconState, attester_slashing: AttesterSlashing) -> None:
    attestation_1 = attester_slashing.attestation_1
    attestation_2 = attester_slashing.attestation_2
    assert is_slashable_attestation_data(attestation_1.data, attestation_2.data)
    assert is_valid_indexed_attestation(state, attestation_1)
    assert is_valid_indexed_attestation(state, attestation_2)

    slashed_any = False
    attesting_indices_1 = attestation_1.custody_bit_0_indices + attestation_1.custody_bit_1_indices
    attesting_indices_2 = attestation_2.custody_bit_0_indices + attestation_2.custody_bit_1_indices
    for index in sorted(set(attesting_indices_1).intersection(attesting_indices_2)):
        if is_slashable_validator(state.validators[index], get_current_epoch(state)):
            slash_validator(state, index)
            slashed_any = True
    assert slashed_any
```

##### Attestations

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.crosslink.shard < SHARD_COUNT
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))

    attestation_slot = get_attestation_data_slot(state, data)
    assert attestation_slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot <= attestation_slot + SLOTS_PER_EPOCH

    pending_attestation = PendingAttestation(
        data=data,
        aggregation_bits=attestation.aggregation_bits,
        inclusion_delay=state.slot - attestation_slot,
        proposer_index=get_beacon_proposer_index(state),
    )

    if data.target.epoch == get_current_epoch(state):
        assert data.source == state.current_justified_checkpoint
        parent_crosslink = state.current_crosslinks[data.crosslink.shard]
        state.current_epoch_attestations.append(pending_attestation)
    else:
        assert data.source == state.previous_justified_checkpoint
        parent_crosslink = state.previous_crosslinks[data.crosslink.shard]
        state.previous_epoch_attestations.append(pending_attestation)

    # Check crosslink against expected parent crosslink
    assert data.crosslink.parent_root == hash_tree_root(parent_crosslink)
    assert data.crosslink.start_epoch == parent_crosslink.end_epoch
    assert data.crosslink.end_epoch == min(data.target.epoch, parent_crosslink.end_epoch + MAX_EPOCHS_PER_CROSSLINK)
    assert data.crosslink.data_root == Hash()  # [to be removed in phase 1]

    # Check signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))
```

##### Deposits

```python
def process_deposit(state: BeaconState, deposit: Deposit) -> None:
    # Verify the Merkle branch
    assert is_valid_merkle_branch(
        leaf=hash_tree_root(deposit.data),
        branch=deposit.proof,
        depth=DEPOSIT_CONTRACT_TREE_DEPTH + 1,  # Add 1 for the `List` length mix-in
        index=state.eth1_deposit_index,
        root=state.eth1_data.deposit_root,
    )

    # Deposits must be processed in order
    state.eth1_deposit_index += 1

    pubkey = deposit.data.pubkey
    amount = deposit.data.amount
    validator_pubkeys = [v.pubkey for v in state.validators]
    if pubkey not in validator_pubkeys:
        # Verify the deposit signature (proof of possession) for new validators.
        # Note: The deposit contract does not check signatures.
        # Note: Deposits are valid across forks, thus the deposit domain is retrieved directly from `compute_domain`.
        domain = compute_domain(DOMAIN_DEPOSIT)
        if not bls_verify(pubkey, signing_root(deposit.data), deposit.data.signature, domain):
            return

        # Add validator and balance entries
        state.validators.append(Validator(
            pubkey=pubkey,
            withdrawal_credentials=deposit.data.withdrawal_credentials,
            activation_eligibility_epoch=FAR_FUTURE_EPOCH,
            activation_epoch=FAR_FUTURE_EPOCH,
            exit_epoch=FAR_FUTURE_EPOCH,
            withdrawable_epoch=FAR_FUTURE_EPOCH,
            effective_balance=min(amount - amount % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE),
        ))
        state.balances.append(amount)
    else:
        # Increase balance by deposit amount
        index = ValidatorIndex(validator_pubkeys.index(pubkey))
        increase_balance(state, index, amount)
```

##### Voluntary exits

```python
def process_voluntary_exit(state: BeaconState, exit: VoluntaryExit) -> None:
    validator = state.validators[exit.validator_index]
    # Verify the validator is active
    assert is_active_validator(validator, get_current_epoch(state))
    # Verify the validator has not yet exited
    assert validator.exit_epoch == FAR_FUTURE_EPOCH
    # Exits must specify an epoch when they become valid; they are not valid before then
    assert get_current_epoch(state) >= exit.epoch
    # Verify the validator has been active long enough
    assert get_current_epoch(state) >= validator.activation_epoch + PERSISTENT_COMMITTEE_PERIOD
    # Verify signature
    domain = get_domain(state, DOMAIN_VOLUNTARY_EXIT, exit.epoch)
    assert bls_verify(validator.pubkey, signing_root(exit), exit.signature, domain)
    # Initiate exit
    initiate_validator_exit(state, exit.validator_index)
```

##### Transfers

```python
def process_transfer(state: BeaconState, transfer: Transfer) -> None:
    # Verify the balance the covers amount and fee (with overflow protection)
    assert state.balances[transfer.sender] >= max(transfer.amount + transfer.fee, transfer.amount, transfer.fee)
    # A transfer is valid in only one slot
    assert state.slot == transfer.slot
    # Sender must satisfy at least one of the following:
    assert (
        # 1) Never have been eligible for activation
        state.validators[transfer.sender].activation_eligibility_epoch == FAR_FUTURE_EPOCH or
        # 2) Be withdrawable
        get_current_epoch(state) >= state.validators[transfer.sender].withdrawable_epoch or
        # 3) Have a balance of at least MAX_EFFECTIVE_BALANCE after the transfer
        state.balances[transfer.sender] >= transfer.amount + transfer.fee + MAX_EFFECTIVE_BALANCE
    )
    # Verify that the pubkey is valid
    assert state.validators[transfer.sender].withdrawal_credentials == BLS_WITHDRAWAL_PREFIX + hash(transfer.pubkey)[1:]
    # Verify that the signature is valid
    assert bls_verify(transfer.pubkey, signing_root(transfer), transfer.signature, get_domain(state, DOMAIN_TRANSFER))
    # Process the transfer
    decrease_balance(state, transfer.sender, transfer.amount + transfer.fee)
    increase_balance(state, transfer.recipient, transfer.amount)
    increase_balance(state, get_beacon_proposer_index(state), transfer.fee)
    # Verify balances are not dust
    assert not (0 < state.balances[transfer.sender] < MIN_DEPOSIT_AMOUNT)
    assert not (0 < state.balances[transfer.recipient] < MIN_DEPOSIT_AMOUNT)
```
