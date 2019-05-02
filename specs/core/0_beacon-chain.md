# Ethereum 2.0 Phase 0 -- The Beacon Chain

**NOTICE**: This document is a work in progress for researchers and implementers.

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
        - [Gwei values](#gwei-values)
        - [Initial values](#initial-values)
        - [Time parameters](#time-parameters)
        - [State list lengths](#state-list-lengths)
        - [Reward and penalty quotients](#reward-and-penalty-quotients)
        - [Max operations per block](#max-operations-per-block)
        - [Signature domains](#signature-domains)
    - [Data structures](#data-structures)
        - [Misc dependencies](#misc-dependencies)
            - [`Fork`](#fork)
            - [`Crosslink`](#crosslink)
            - [`Eth1Data`](#eth1data)
            - [`AttestationData`](#attestationdata)
            - [`AttestationDataAndCustodyBit`](#attestationdataandcustodybit)
            - [`IndexedAttestation`](#indexedattestation)
            - [`DepositData`](#depositdata)
            - [`BeaconBlockHeader`](#beaconblockheader)
            - [`Validator`](#validator)
            - [`PendingAttestation`](#pendingattestation)
            - [`HistoricalBatch`](#historicalbatch)
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
    - [Custom Types](#custom-types)
    - [Helper functions](#helper-functions)
        - [`xor`](#xor)
        - [`hash`](#hash)
        - [`hash_tree_root`](#hash_tree_root)
        - [`signing_root`](#signing_root)
        - [`slot_to_epoch`](#slot_to_epoch)
        - [`get_previous_epoch`](#get_previous_epoch)
        - [`get_current_epoch`](#get_current_epoch)
        - [`get_epoch_start_slot`](#get_epoch_start_slot)
        - [`is_active_validator`](#is_active_validator)
        - [`is_slashable_validator`](#is_slashable_validator)
        - [`get_active_validator_indices`](#get_active_validator_indices)
        - [`increase_balance`](#increase_balance)
        - [`decrease_balance`](#decrease_balance)
        - [`get_permuted_index`](#get_permuted_index)
        - [`get_split_offset`](#get_split_offset)
        - [`get_epoch_committee_count`](#get_epoch_committee_count)
        - [`get_shard_delta`](#get_shard_delta)
        - [`compute_committee`](#compute_committee)
        - [`get_crosslink_committees_at_slot`](#get_crosslink_committees_at_slot)
        - [`get_block_root_at_slot`](#get_block_root_at_slot)
        - [`get_block_root`](#get_block_root)
        - [`get_state_root`](#get_state_root)
        - [`get_randao_mix`](#get_randao_mix)
        - [`get_active_index_root`](#get_active_index_root)
        - [`generate_seed`](#generate_seed)
        - [`get_beacon_proposer_index`](#get_beacon_proposer_index)
        - [`verify_merkle_branch`](#verify_merkle_branch)
        - [`get_attesting_indices`](#get_attesting_indices)
        - [`int_to_bytes1`, `int_to_bytes2`, ...](#int_to_bytes1-int_to_bytes2-)
        - [`bytes_to_int`](#bytes_to_int)
        - [`get_total_balance`](#get_total_balance)
        - [`get_domain`](#get_domain)
        - [`get_bitfield_bit`](#get_bitfield_bit)
        - [`verify_bitfield`](#verify_bitfield)
        - [`convert_to_indexed`](#convert_to_indexed)
        - [`verify_indexed_attestation`](#verify_indexed_attestation)
        - [`is_double_vote`](#is_double_vote)
        - [`is_surround_vote`](#is_surround_vote)
        - [`integer_squareroot`](#integer_squareroot)
        - [`get_delayed_activation_exit_epoch`](#get_delayed_activation_exit_epoch)
        - [`get_churn_limit`](#get_churn_limit)
        - [`bls_verify`](#bls_verify)
        - [`bls_verify_multiple`](#bls_verify_multiple)
        - [`bls_aggregate_pubkeys`](#bls_aggregate_pubkeys)
        - [Routines for updating validator status](#routines-for-updating-validator-status)
            - [`initiate_validator_exit`](#initiate_validator_exit)
            - [`slash_validator`](#slash_validator)
    - [On genesis](#on-genesis)
    - [Beacon chain state transition function](#beacon-chain-state-transition-function)
        - [State caching](#state-caching)
        - [Epoch processing](#epoch-processing)
            - [Helper functions](#helper-functions-1)
            - [Justification and finalization](#justification-and-finalization)
            - [Crosslinks](#crosslinks)
            - [Rewards and penalties](#rewards-and-penalties)
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
            - [State root verification](#state-root-verification)

<!-- /TOC -->

## Introduction

This document represents the specification for Phase 0 of Ethereum 2.0 -- The Beacon Chain.

At the core of Ethereum 2.0 is a system chain called the "beacon chain". The beacon chain stores and manages the registry of [validators](#dfn-validator). In the initial deployment phases of Ethereum 2.0, the only mechanism to become a [validator](#dfn-validator) is to make a one-way ETH transaction to a deposit contract on Ethereum 1.0. Activation as a [validator](#dfn-validator) happens when Ethereum 1.0 deposit receipts are processed by the beacon chain, the activation balance is reached, and a queuing process is completed. Exit is either voluntary or done forcibly as a penalty for misbehavior.

The primary source of load on the beacon chain is "attestations". Attestations are simultaneously availability votes for a shard block and proof-of-stake votes for a beacon block. A sufficient number of attestations for the same shard block create a "crosslink", confirming the shard segment up to that shard block into the beacon chain. Crosslinks also serve as infrastructure for asynchronous cross-shard communication.

## Notation

Code snippets appearing in `this style` are to be interpreted as Python code.

## Terminology

* **Validator** <a id="dfn-validator"></a> - a registered participant in the beacon chain. You can become one by sending ether into the Ethereum 1.0 deposit contract.
* **Active validator** <a id="dfn-active-validator"></a> - an active participant in the Ethereum 2.0 consensus invited to, among other things, propose and attest to blocks and vote for crosslinks.
* **Committee** - a (pseudo-) randomly sampled subset of [active validators](#dfn-active-validator). When a committee is referred to collectively, as in "this committee attests to X", this is assumed to mean "some subset of that committee that contains enough [validators](#dfn-validator) that the protocol recognizes it as representing the committee".
* **Proposer** - the [validator](#dfn-validator) that creates a beacon chain block.
* **Attester** - a [validator](#dfn-validator) that is part of a committee that needs to sign off on a beacon chain block while simultaneously creating a link (crosslink) to a recent shard block on a particular shard chain.
* **Beacon chain** - the central PoS chain that is the base of the sharding system.
* **Shard chain** - one of the chains on which user transactions take place and account data is stored.
* **Block root** - a 32-byte Merkle root of a beacon chain block or shard chain block. Previously called "block hash".
* **Crosslink** - a set of signatures from a committee attesting to a block in a shard chain that can be included into the beacon chain. Crosslinks are the main means by which the beacon chain "learns about" the updated state of shard chains.
* **Slot** - a period during which one proposer has the ability to create a beacon chain block and some attesters have the ability to make attestations.
* **Epoch** - an aligned span of slots during which all [validators](#dfn-validator) get exactly one chance to make an attestation.
* **Finalized**, **justified** - see the [Casper FFG paper](https://arxiv.org/abs/1710.09437).
* **Withdrawal period** - the number of slots between a [validator](#dfn-validator) exit and the [validator](#dfn-validator) balance being withdrawable.
* **Genesis time** - the Unix time of the genesis beacon chain block at slot 0.

## Constants

Note: the default mainnet values for the constants are included here for spec-design purposes.
The different configurations for mainnet, testnets, and yaml-based testing can be found in the `configs/constant_presets/` directory.
These configurations are updated for releases, but may be out of sync during `dev` changes.

### Misc

| Name | Value |
| - | - |
| `SHARD_COUNT` | `2**10` (= 1,024) |
| `TARGET_COMMITTEE_SIZE` | `2**7` (= 128) |
| `MAX_INDICES_PER_ATTESTATION` | `2**12` (= 4,096) |
| `MIN_PER_EPOCH_CHURN_LIMIT` | `2**2` (= 4) |
| `CHURN_LIMIT_QUOTIENT` | `2**16` (= 65,536) |
| `BASE_REWARDS_PER_EPOCH` | `5` |
| `SHUFFLE_ROUND_COUNT` | 90 |

* For the safety of crosslinks `TARGET_COMMITTEE_SIZE` exceeds [the recommended minimum committee size of 111](https://vitalik.ca/files/Ithaca201807_Sharding.pdf); with sufficient active validators (at least `SLOTS_PER_EPOCH * TARGET_COMMITTEE_SIZE`), the shuffling algorithm ensures committee sizes of at least `TARGET_COMMITTEE_SIZE`. (Unbiasable randomness with a Verifiable Delay Function (VDF) will improve committee robustness and lower the safe minimum committee size.)

### Deposit contract

| Name | Value |
| - | - |
| `DEPOSIT_CONTRACT_TREE_DEPTH` | `2**5` (= 32) |

### Gwei values

| Name | Value | Unit |
| - | - | :-: |
| `MIN_DEPOSIT_AMOUNT` | `2**0 * 10**9` (= 1,000,000,000) | Gwei |
| `MAX_EFFECTIVE_BALANCE` | `2**5 * 10**9` (= 32,000,000,000) | Gwei |
| `EJECTION_BALANCE` | `2**4 * 10**9` (= 16,000,000,000) | Gwei |
| `EFFECTIVE_BALANCE_INCREMENT` | `2**0 * 10**9` (= 1,000,000,000) | Gwei |

### Initial values

| Name | Value |
| - | - |
| `GENESIS_SLOT` | `0` |
| `GENESIS_EPOCH` | `0` |
| `FAR_FUTURE_EPOCH` | `2**64 - 1` |
| `ZERO_HASH` | `int_to_bytes32(0)` |
| `BLS_WITHDRAWAL_PREFIX_BYTE` | `int_to_bytes1(0)` |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `MIN_ATTESTATION_INCLUSION_DELAY` | `2**2` (= 4) | slots | 24 seconds |
| `SLOTS_PER_EPOCH` | `2**6` (= 64) | slots | 6.4 minutes |
| `MIN_SEED_LOOKAHEAD` | `2**0` (= 1) | epochs | 6.4 minutes |
| `ACTIVATION_EXIT_DELAY` | `2**2` (= 4) | epochs | 25.6 minutes |
| `SLOTS_PER_ETH1_VOTING_PERIOD` | `2**10` (= 1,024) | slots | ~1.7 hours |
| `SLOTS_PER_HISTORICAL_ROOT` | `2**13` (= 8,192) | slots | ~13 hours |
| `MIN_VALIDATOR_WITHDRAWABILITY_DELAY` | `2**8` (= 256) | epochs | ~27 hours |
| `PERSISTENT_COMMITTEE_PERIOD` | `2**11` (= 2,048)  | epochs | 9 days  |
| `MAX_CROSSLINK_EPOCHS` | `2**6` (= 64) | epochs | ~7 hours |
| `MIN_EPOCHS_TO_INACTIVITY_PENALTY` | `2**2` (= 4) | epochs | 25.6 minutes |

* `MAX_CROSSLINK_EPOCHS` should be a small constant times `SHARD_COUNT // SLOTS_PER_EPOCH`

### State list lengths

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `LATEST_RANDAO_MIXES_LENGTH` | `2**13` (= 8,192) | epochs | ~36 days |
| `LATEST_ACTIVE_INDEX_ROOTS_LENGTH` | `2**13` (= 8,192) | epochs | ~36 days |
| `LATEST_SLASHED_EXIT_LENGTH` | `2**13` (= 8,192) | epochs | ~36 days |

### Reward and penalty quotients

| Name | Value |
| - | - |
| `BASE_REWARD_QUOTIENT` | `2**5` (= 32) |
| `WHISTLEBLOWING_REWARD_QUOTIENT` | `2**9` (= 512) |
| `PROPOSER_REWARD_QUOTIENT` | `2**3` (= 8) |
| `INACTIVITY_PENALTY_QUOTIENT` | `2**25` (= 33,554,432) |
| `MIN_SLASHING_PENALTY_QUOTIENT` | `2**5` (= 32) |

* **The `BASE_REWARD_QUOTIENT` is NOT final. Once all other protocol details are finalized it will be adjusted, to target a theoretical maximum total issuance of `2**21` ETH per year if `2**27` ETH is validating (and therefore `2**20` per year if `2**25` ETH is validating, etc etc)**
* The `INACTIVITY_PENALTY_QUOTIENT` equals `INVERSE_SQRT_E_DROP_TIME**2` where `INVERSE_SQRT_E_DROP_TIME := 2**12 epochs` (~18 days) is the time it takes the inactivity penalty to reduce the balance of non-participating [validators](#dfn-validator) to about `1/sqrt(e) ~= 60.6%`. Indeed, the balance retained by offline [validators](#dfn-validator) after `n` epochs is about `(1 - 1/INACTIVITY_PENALTY_QUOTIENT)**(n**2/2)` so after `INVERSE_SQRT_E_DROP_TIME` epochs it is roughly `(1 - 1/INACTIVITY_PENALTY_QUOTIENT)**(INACTIVITY_PENALTY_QUOTIENT/2) ~= 1/sqrt(e)`.

### Max operations per block

| Name | Value |
| - | - |
| `MAX_PROPOSER_SLASHINGS` | `2**4` (= 16) |
| `MAX_ATTESTER_SLASHINGS` | `2**0` (= 1) |
| `MAX_ATTESTATIONS` | `2**7` (= 128) |
| `MAX_DEPOSITS` | `2**4` (= 16) |
| `MAX_VOLUNTARY_EXITS` | `2**4` (= 16) |
| `MAX_TRANSFERS` | `0` |

### Signature domains

| Name | Value |
| - | - |
| `DOMAIN_BEACON_PROPOSER` | `0` |
| `DOMAIN_RANDAO` | `1` |
| `DOMAIN_ATTESTATION` | `2` |
| `DOMAIN_DEPOSIT` | `3` |
| `DOMAIN_VOLUNTARY_EXIT` | `4` |
| `DOMAIN_TRANSFER` | `5` |

## Data structures

The following data structures are defined as [SimpleSerialize (SSZ)](../simple-serialize.md) objects.

The types are defined topologically to aid in facilitating an executable version of the spec.

### Misc dependencies

#### `Fork`

```python
{
    # Previous fork version
    'previous_version': 'bytes4',
    # Current fork version
    'current_version': 'bytes4',
    # Fork epoch number
    'epoch': 'uint64',
}
```

#### `Crosslink`

```python
{
    # Epoch number
    'epoch': 'uint64',
    # Root of the previous crosslink
    'previous_crosslink_root': 'bytes32',
    # Root of the crosslinked shard data since the previous crosslink
    'crosslink_data_root': 'bytes32',
}
```

#### `Eth1Data`

```python
{
    # Root of the deposit tree
    'deposit_root': 'bytes32',
    # Total number of deposits
    'deposit_count': 'uint64',
    # Block hash
    'block_hash': 'bytes32',
}
```

#### `AttestationData`

```python
{
    # LMD GHOST vote
    'slot': 'uint64',
    'beacon_block_root': 'bytes32',

    # FFG vote
    'source_epoch': 'uint64',
    'source_root': 'bytes32',
    'target_root': 'bytes32',

    # Crosslink vote
    'shard': 'uint64',
    'previous_crosslink_root': 'bytes32',
    'crosslink_data_root': 'bytes32',
}
```

#### `AttestationDataAndCustodyBit`

```python
{
    # Attestation data
    'data': AttestationData,
    # Custody bit
    'custody_bit': 'bool',
}
```

#### `IndexedAttestation`

```python
{
    # Validator indices
    'custody_bit_0_indices': ['uint64'],
    'custody_bit_1_indices': ['uint64'],
    # Attestation data
    'data': AttestationData,
    # Aggregate signature
    'signature': 'bytes96',
}
```

#### `DepositData`

```python
{
    # BLS pubkey
    'pubkey': 'bytes48',
    # Withdrawal credentials
    'withdrawal_credentials': 'bytes32',
    # Amount in Gwei
    'amount': 'uint64',
    # Container self-signature
    'signature': 'bytes96',
}
```

#### `BeaconBlockHeader`

```python
{
    'slot': 'uint64',
    'previous_block_root': 'bytes32',
    'state_root': 'bytes32',
    'block_body_root': 'bytes32',
    'signature': 'bytes96',
}
```
#### `Validator`

```python
{
    # BLS public key
    'pubkey': 'bytes48',
    # Withdrawal credentials
    'withdrawal_credentials': 'bytes32',
    # Epoch when became eligible for activation
    'activation_eligibility_epoch': 'uint64',
    # Epoch when validator activated
    'activation_epoch': 'uint64',
    # Epoch when validator exited
    'exit_epoch': 'uint64',
    # Epoch when validator is eligible to withdraw
    'withdrawable_epoch': 'uint64',
    # Was the validator slashed
    'slashed': 'bool',
    # Effective balance
    'effective_balance': 'uint64',
}
```

#### `PendingAttestation`

```python
{
    # Attester aggregation bitfield
    'aggregation_bitfield': 'bytes',
    # Attestation data
    'data': AttestationData,
    # Inclusion slot
    'inclusion_slot': 'uint64',
    # Proposer index
    'proposer_index': 'uint64',
}
```

#### `HistoricalBatch`

```python
{
    # Block roots
    'block_roots': ['bytes32', SLOTS_PER_HISTORICAL_ROOT],
    # State roots
    'state_roots': ['bytes32', SLOTS_PER_HISTORICAL_ROOT],
}
```

### Beacon operations

#### `ProposerSlashing`

```python
{
    # Proposer index
    'proposer_index': 'uint64',
    # First block header
    'header_1': BeaconBlockHeader,
    # Second block header
    'header_2': BeaconBlockHeader,
}
```

#### `AttesterSlashing`

```python
{
    # First attestation
    'attestation_1': IndexedAttestation,
    # Second attestation
    'attestation_2': IndexedAttestation,
}
```

#### `Attestation`

```python
{
    # Attester aggregation bitfield
    'aggregation_bitfield': 'bytes',
    # Attestation data
    'data': AttestationData,
    # Custody bitfield
    'custody_bitfield': 'bytes',
    # BLS aggregate signature
    'signature': 'bytes96',
}
```

#### `Deposit`

```python
{
    # Branch in the deposit tree
    'proof': ['bytes32', DEPOSIT_CONTRACT_TREE_DEPTH],
    # Index in the deposit tree
    'index': 'uint64',
    # Data
    'data': DepositData,
}
```

#### `VoluntaryExit`

```python
{
    # Minimum epoch for processing exit
    'epoch': 'uint64',
    # Index of the exiting validator
    'validator_index': 'uint64',
    # Validator signature
    'signature': 'bytes96',
}
```

#### `Transfer`

```python
{
    # Sender index
    'sender': 'uint64',
    # Recipient index
    'recipient': 'uint64',
    # Amount in Gwei
    'amount': 'uint64',
    # Fee in Gwei for block proposer
    'fee': 'uint64',
    # Inclusion slot
    'slot': 'uint64',
    # Sender withdrawal pubkey
    'pubkey': 'bytes48',
    # Sender signature
    'signature': 'bytes96',
}
```

### Beacon blocks

#### `BeaconBlockBody`

```python
{
    'randao_reveal': 'bytes96',
    'eth1_data': Eth1Data,
    'proposer_slashings': [ProposerSlashing],
    'attester_slashings': [AttesterSlashing],
    'attestations': [Attestation],
    'deposits': [Deposit],
    'voluntary_exits': [VoluntaryExit],
    'transfers': [Transfer],
}
```

#### `BeaconBlock`

```python
{
    # Header
    'slot': 'uint64',
    'previous_block_root': 'bytes32',
    'state_root': 'bytes32',
    'body': BeaconBlockBody,
    'signature': 'bytes96',
}
```

### Beacon state

#### `BeaconState`

```python
{
    # Misc
    'slot': 'uint64',
    'genesis_time': 'uint64',
    'fork': Fork,  # For versioning hard forks

    # Validator registry
    'validator_registry': [Validator],
    'balances': ['uint64'],

    # Randomness and committees
    'latest_randao_mixes': ['bytes32', LATEST_RANDAO_MIXES_LENGTH],
    'latest_start_shard': 'uint64',

    # Finality
    'previous_epoch_attestations': [PendingAttestation],
    'current_epoch_attestations': [PendingAttestation],
    'previous_justified_epoch': 'uint64',
    'current_justified_epoch': 'uint64',
    'previous_justified_root': 'bytes32',
    'current_justified_root': 'bytes32',
    'justification_bitfield': 'uint64',
    'finalized_epoch': 'uint64',
    'finalized_root': 'bytes32',

    # Recent state
    'current_crosslinks': [Crosslink, SHARD_COUNT],
    'previous_crosslinks': [Crosslink, SHARD_COUNT],
    'latest_block_roots': ['bytes32', SLOTS_PER_HISTORICAL_ROOT],
    'latest_state_roots': ['bytes32', SLOTS_PER_HISTORICAL_ROOT],
    'latest_active_index_roots': ['bytes32', LATEST_ACTIVE_INDEX_ROOTS_LENGTH],
    'latest_slashed_balances': ['uint64', LATEST_SLASHED_EXIT_LENGTH],  # Balances slashed at every withdrawal period
    'latest_block_header': BeaconBlockHeader,  # `latest_block_header.state_root == ZERO_HASH` temporarily
    'historical_roots': ['bytes32'],

    # Ethereum 1.0 chain data
    'latest_eth1_data': Eth1Data,
    'eth1_data_votes': [Eth1Data],
    'deposit_index': 'uint64',
}
```

## Custom Types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `Slot` | `uint64` | a slot number |
| `Epoch` | `uint64` | an epoch number |
| `Shard` | `uint64` | a shard number |
| `ValidatorIndex` | `uint64` | a validator registry index |
| `Gwei` | `uint64` | an amount in Gwei |
| `Bytes32` | `bytes32` | 32 bytes of binary data |
| `BLSPubkey` | `bytes48` | a BLS12-381 public key |
| `BLSSignature` | `bytes96` | a BLS12-381 signature |

## Helper functions

Note: The definitions below are for specification purposes and are not necessarily optimal implementations.

### `xor`

```python
def xor(bytes1: Bytes32, bytes2: Bytes32) -> Bytes32:
    return bytes(a ^ b for a, b in zip(bytes1, bytes2))
```

### `hash`

The `hash` function is SHA256.

Note: We aim to migrate to a S[T/N]ARK-friendly hash function in a future Ethereum 2.0 deployment phase.

### `hash_tree_root`

`def hash_tree_root(object: SSZSerializable) -> Bytes32` is a function for hashing objects into a single root utilizing a hash tree structure. `hash_tree_root` is defined in the [SimpleSerialize spec](../simple-serialize.md#merkleization).

### `signing_root`

`def signing_root(object: SSZContainer) -> Bytes32` is a function defined in the [SimpleSerialize spec](../simple-serialize.md#self-signed-containers) to compute signing messages.

### `slot_to_epoch`

```python
def slot_to_epoch(slot: Slot) -> Epoch:
    """
    Return the epoch number of the given ``slot``.
    """
    return slot // SLOTS_PER_EPOCH
```

### `get_previous_epoch`

```python
def get_previous_epoch(state: BeaconState) -> Epoch:
    """`
    Return the previous epoch of the given ``state``.
    Return the current epoch if it's genesis epoch.
    """
    current_epoch = get_current_epoch(state)
    return (current_epoch - 1) if current_epoch > GENESIS_EPOCH else current_epoch
```

### `get_current_epoch`

```python
def get_current_epoch(state: BeaconState) -> Epoch:
    """
    Return the current epoch of the given ``state``.
    """
    return slot_to_epoch(state.slot)
```

### `get_epoch_start_slot`

```python
def get_epoch_start_slot(epoch: Epoch) -> Slot:
    """
    Return the starting slot of the given ``epoch``.
    """
    return epoch * SLOTS_PER_EPOCH
```

### `is_active_validator`

```python
def is_active_validator(validator: Validator, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is active.
    """
    return validator.activation_epoch <= epoch < validator.exit_epoch
```

### `is_slashable_validator`

```python
def is_slashable_validator(validator: Validator, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is slashable.
    """
    return validator.slashed is False and (validator.activation_epoch <= epoch < validator.withdrawable_epoch)

```

### `get_active_validator_indices`

```python
def get_active_validator_indices(state: BeaconState, epoch: Epoch) -> List[ValidatorIndex]:
    """
    Get active validator indices at ``epoch``.
    """
    return [i for i, v in enumerate(state.validator_registry) if is_active_validator(v, epoch)]
```

### `increase_balance`

```python
def increase_balance(state: BeaconState, index: ValidatorIndex, delta: Gwei) -> None:
    """
    Increase validator balance by ``delta``.
    """
    state.balances[index] += delta
```

### `decrease_balance`

```python
def decrease_balance(state: BeaconState, index: ValidatorIndex, delta: Gwei) -> None:
    """
    Decrease validator balance by ``delta`` with underflow protection.
    """
    state.balances[index] = 0 if delta > state.balances[index] else state.balances[index] - delta
```

### `get_permuted_index`

```python
def get_permuted_index(index: int, list_size: int, seed: Bytes32) -> int:
    """
    Return `p(index)` in a pseudorandom permutation `p` of `0...list_size - 1` with ``seed`` as entropy.

    Utilizes 'swap or not' shuffling found in
    https://link.springer.com/content/pdf/10.1007%2F978-3-642-32009-5_1.pdf
    See the 'generalized domain' algorithm on page 3.
    """
    assert index < list_size
    assert list_size <= 2**40

    for round in range(SHUFFLE_ROUND_COUNT):
        pivot = bytes_to_int(hash(seed + int_to_bytes1(round))[0:8]) % list_size
        flip = (pivot - index) % list_size
        position = max(index, flip)
        source = hash(seed + int_to_bytes1(round) + int_to_bytes4(position // 256))
        byte = source[(position % 256) // 8]
        bit = (byte >> (position % 8)) % 2
        index = flip if bit else index

    return index
```

### `get_split_offset`

```python
def get_split_offset(list_size: int, chunks: int, index: int) -> int:
    """
    Returns a value such that for a list L, chunk count k and index i,
    split(L, k)[i] == L[get_split_offset(len(L), k, i): get_split_offset(len(L), k, i+1)]
    """
    return (list_size * index) // chunks
```

### `get_epoch_committee_count`

```python
def get_epoch_committee_count(state: BeaconState, epoch: Epoch) -> int:
    """
    Return the number of committees at ``epoch``.
    """
    active_validator_indices = get_active_validator_indices(state, epoch)
    return max(
        1,
        min(
            SHARD_COUNT // SLOTS_PER_EPOCH,
            len(active_validator_indices) // SLOTS_PER_EPOCH // TARGET_COMMITTEE_SIZE,
        )
    ) * SLOTS_PER_EPOCH
```

### `get_shard_delta`

```python
def get_shard_delta(state: BeaconState, epoch: Epoch) -> int:
    """
    Return the number of shards to increment ``state.latest_start_shard`` during ``epoch``.
    """
    return min(get_epoch_committee_count(state, epoch), SHARD_COUNT - SHARD_COUNT // SLOTS_PER_EPOCH)
```

### `compute_committee`

```python
def compute_committee(validator_indices: List[ValidatorIndex],
                      seed: Bytes32,
                      index: int,
                      total_committees: int) -> List[ValidatorIndex]:
    """
    Return the ``index``'th shuffled committee out of a total ``total_committees``
    using ``validator_indices`` and ``seed``.
    """
    start_offset = get_split_offset(len(validator_indices), total_committees, index)
    end_offset = get_split_offset(len(validator_indices), total_committees, index + 1)
    return [
        validator_indices[get_permuted_index(i, len(validator_indices), seed)]
        for i in range(start_offset, end_offset)
    ]
```

Note: this definition and the next few definitions are highly inefficient as algorithms, as they re-calculate many sub-expressions. Production implementations are expected to appropriately use caching/memoization to avoid redoing work.

### `get_crosslink_committees_at_slot`

```python
def get_crosslink_committees_at_slot(state: BeaconState,
                                     slot: Slot) -> List[Tuple[List[ValidatorIndex], Shard]]:
    """
    Return the list of ``(committee, shard)`` tuples for the ``slot``.
    """
    epoch = slot_to_epoch(slot)
    current_epoch = get_current_epoch(state)
    previous_epoch = get_previous_epoch(state)
    next_epoch = current_epoch + 1

    assert previous_epoch <= epoch <= next_epoch
    indices = get_active_validator_indices(state, epoch)

    if epoch == current_epoch:
        start_shard = state.latest_start_shard
    elif epoch == previous_epoch:
        previous_shard_delta = get_shard_delta(state, previous_epoch)
        start_shard = (state.latest_start_shard - previous_shard_delta) % SHARD_COUNT
    elif epoch == next_epoch:
        current_shard_delta = get_shard_delta(state, current_epoch)
        start_shard = (state.latest_start_shard + current_shard_delta) % SHARD_COUNT

    committees_per_epoch = get_epoch_committee_count(state, epoch)
    committees_per_slot = committees_per_epoch // SLOTS_PER_EPOCH
    offset = slot % SLOTS_PER_EPOCH
    slot_start_shard = (start_shard + committees_per_slot * offset) % SHARD_COUNT
    seed = generate_seed(state, epoch)

    return [
        (
            compute_committee(indices, seed, committees_per_slot * offset + i, committees_per_epoch),
            (slot_start_shard + i) % SHARD_COUNT,
        )
        for i in range(committees_per_slot)
    ]
```

### `get_block_root_at_slot`

```python
def get_block_root_at_slot(state: BeaconState,
                           slot: Slot) -> Bytes32:
    """
    Return the block root at a recent ``slot``.
    """
    assert slot < state.slot <= slot + SLOTS_PER_HISTORICAL_ROOT
    return state.latest_block_roots[slot % SLOTS_PER_HISTORICAL_ROOT]
```

### `get_block_root`

```python
def get_block_root(state: BeaconState,
                   epoch: Epoch) -> Bytes32:
    """
    Return the block root at a recent ``epoch``.
    """
    return get_block_root_at_slot(state, get_epoch_start_slot(epoch))
```

### `get_state_root`

```python
def get_state_root(state: BeaconState,
                   slot: Slot) -> Bytes32:
    """
    Return the state root at a recent ``slot``.
    """
    assert slot < state.slot <= slot + SLOTS_PER_HISTORICAL_ROOT
    return state.latest_state_roots[slot % SLOTS_PER_HISTORICAL_ROOT]
```

### `get_randao_mix`

```python
def get_randao_mix(state: BeaconState,
                   epoch: Epoch) -> Bytes32:
    """
    Return the randao mix at a recent ``epoch``.
    """
    assert get_current_epoch(state) - LATEST_RANDAO_MIXES_LENGTH < epoch <= get_current_epoch(state)
    return state.latest_randao_mixes[epoch % LATEST_RANDAO_MIXES_LENGTH]
```

### `get_active_index_root`

```python
def get_active_index_root(state: BeaconState,
                          epoch: Epoch) -> Bytes32:
    """
    Return the index root at a recent ``epoch``.
    """
    assert get_current_epoch(state) - LATEST_ACTIVE_INDEX_ROOTS_LENGTH + ACTIVATION_EXIT_DELAY < epoch <= get_current_epoch(state) + ACTIVATION_EXIT_DELAY
    return state.latest_active_index_roots[epoch % LATEST_ACTIVE_INDEX_ROOTS_LENGTH]
```

### `generate_seed`

```python
def generate_seed(state: BeaconState,
                  epoch: Epoch) -> Bytes32:
    """
    Generate a seed for the given ``epoch``.
    """
    return hash(
        get_randao_mix(state, epoch - MIN_SEED_LOOKAHEAD) +
        get_active_index_root(state, epoch) +
        int_to_bytes32(epoch)
    )
```

### `get_beacon_proposer_index`

```python
def get_beacon_proposer_index(state: BeaconState) -> ValidatorIndex:
    """
    Return the beacon proposer index at ``state.slot``.
    """
    current_epoch = get_current_epoch(state)
    first_committee, _ = get_crosslink_committees_at_slot(state, state.slot)[0]
    MAX_RANDOM_BYTE = 2**8 - 1
    i = 0
    while True:
        candidate_index = first_committee[(current_epoch + i) % len(first_committee)]
        random_byte = hash(generate_seed(state, current_epoch) + int_to_bytes8(i // 32))[i % 32]
        effective_balance = state.validator_registry[candidate_index].effective_balance
        if effective_balance * MAX_RANDOM_BYTE >= MAX_EFFECTIVE_BALANCE * random_byte:
            return candidate_index
        i += 1
```

### `verify_merkle_branch`

```python
def verify_merkle_branch(leaf: Bytes32, proof: List[Bytes32], depth: int, index: int, root: Bytes32) -> bool:
    """
    Verify that the given ``leaf`` is on the merkle branch ``proof``
    starting with the given ``root``.
    """
    value = leaf
    for i in range(depth):
        if index // (2**i) % 2:
            value = hash(proof[i] + value)
        else:
            value = hash(value + proof[i])
    return value == root
```

### `get_attesting_indices`

```python
def get_attesting_indices(state: BeaconState,
                          attestation_data: AttestationData,
                          bitfield: bytes) -> List[ValidatorIndex]:
    """
    Return the sorted attesting indices corresponding to ``attestation_data`` and ``bitfield``.
    """
    crosslink_committees = get_crosslink_committees_at_slot(state, attestation_data.slot)
    crosslink_committee = [committee for committee, shard in crosslink_committees if shard == attestation_data.shard][0]
    assert verify_bitfield(bitfield, len(crosslink_committee))
    return sorted([index for i, index in enumerate(crosslink_committee) if get_bitfield_bit(bitfield, i) == 0b1])
```

### `int_to_bytes1`, `int_to_bytes2`, ...

`int_to_bytes1(x): return x.to_bytes(1, 'little')`, `int_to_bytes2(x): return x.to_bytes(2, 'little')`, and so on for all integers, particularly 1, 2, 3, 4, 8, 32, 48, 96.

### `bytes_to_int`

```python
def bytes_to_int(data: bytes) -> int:
    return int.from_bytes(data, 'little')
```

### `get_total_balance`

```python
def get_total_balance(state: BeaconState, indices: List[ValidatorIndex]) -> Gwei:
    """
    Return the combined effective balance of an array of ``validators``.
    """
    return sum([state.validator_registry[index].effective_balance for index in indices])
```

### `get_domain`

```python
def get_domain(state: BeaconState,
               domain_type: int,
               message_epoch: int=None) -> int:
    """
    Return the signature domain (fork version concatenated with domain type) of a message.
    """
    epoch = get_current_epoch(state) if message_epoch is None else message_epoch
    fork_version = state.fork.previous_version if epoch < state.fork.epoch else state.fork.current_version
    return bytes_to_int(fork_version + int_to_bytes4(domain_type))
```

### `get_bitfield_bit`

```python
def get_bitfield_bit(bitfield: bytes, i: int) -> int:
    """
    Extract the bit in ``bitfield`` at position ``i``.
    """
    return (bitfield[i // 8] >> (i % 8)) % 2
```

### `verify_bitfield`

```python
def verify_bitfield(bitfield: bytes, committee_size: int) -> bool:
    """
    Verify ``bitfield`` against the ``committee_size``.
    """
    if len(bitfield) != (committee_size + 7) // 8:
        return False

    # Check `bitfield` is padded with zero bits only
    for i in range(committee_size, len(bitfield) * 8):
        if get_bitfield_bit(bitfield, i) == 0b1:
            return False

    return True
```

### `convert_to_indexed`

```python
def convert_to_indexed(state: BeaconState, attestation: Attestation) -> IndexedAttestation:
    """
    Convert ``attestation`` to (almost) indexed-verifiable form.
    """
    attesting_indices = get_attesting_indices(state, attestation.data, attestation.aggregation_bitfield)
    custody_bit_1_indices = get_attesting_indices(state, attestation.data, attestation.custody_bitfield)
    custody_bit_0_indices = [index for index in attesting_indices if index not in custody_bit_1_indices]

    return IndexedAttestation(
        custody_bit_0_indices=custody_bit_0_indices,
        custody_bit_1_indices=custody_bit_1_indices,
        data=attestation.data,
        signature=attestation.signature,
    )
```

### `verify_indexed_attestation`

```python
def verify_indexed_attestation(state: BeaconState, indexed_attestation: IndexedAttestation) -> bool:
    """
    Verify validity of ``indexed_attestation`` fields.
    """
    custody_bit_0_indices = indexed_attestation.custody_bit_0_indices
    custody_bit_1_indices = indexed_attestation.custody_bit_1_indices

    # Ensure no duplicate indices across custody bits
    assert len(set(custody_bit_0_indices).intersection(set(custody_bit_1_indices))) == 0

    if len(custody_bit_1_indices) > 0:  # [TO BE REMOVED IN PHASE 1]
        return False

    if not (1 <= len(custody_bit_0_indices) + len(custody_bit_1_indices) <= MAX_INDICES_PER_ATTESTATION):
        return False

    if custody_bit_0_indices != sorted(custody_bit_0_indices):
        return False

    if custody_bit_1_indices != sorted(custody_bit_1_indices):
        return False

    return bls_verify_multiple(
        pubkeys=[
            bls_aggregate_pubkeys([state.validator_registry[i].pubkey for i in custody_bit_0_indices]),
            bls_aggregate_pubkeys([state.validator_registry[i].pubkey for i in custody_bit_1_indices]),
        ],
        message_hashes=[
            hash_tree_root(AttestationDataAndCustodyBit(data=indexed_attestation.data, custody_bit=0b0)),
            hash_tree_root(AttestationDataAndCustodyBit(data=indexed_attestation.data, custody_bit=0b1)),
        ],
        signature=indexed_attestation.signature,
        domain=get_domain(state, DOMAIN_ATTESTATION, slot_to_epoch(indexed_attestation.data.slot)),
    )
```

### `is_double_vote`

```python
def is_double_vote(attestation_data_1: AttestationData,
                   attestation_data_2: AttestationData) -> bool:
    """
    Check if ``attestation_data_1`` and ``attestation_data_2`` have the same target.
    """
    target_epoch_1 = slot_to_epoch(attestation_data_1.slot)
    target_epoch_2 = slot_to_epoch(attestation_data_2.slot)
    return target_epoch_1 == target_epoch_2
```

### `is_surround_vote`

```python
def is_surround_vote(attestation_data_1: AttestationData,
                     attestation_data_2: AttestationData) -> bool:
    """
    Check if ``attestation_data_1`` surrounds ``attestation_data_2``.
    """
    source_epoch_1 = attestation_data_1.source_epoch
    source_epoch_2 = attestation_data_2.source_epoch
    target_epoch_1 = slot_to_epoch(attestation_data_1.slot)
    target_epoch_2 = slot_to_epoch(attestation_data_2.slot)

    return source_epoch_1 < source_epoch_2 and target_epoch_2 < target_epoch_1
```

### `integer_squareroot`

```python
def integer_squareroot(n: int) -> int:
    """
    The largest integer ``x`` such that ``x**2`` is less than or equal to ``n``.
    """
    assert n >= 0
    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x
```

### `get_delayed_activation_exit_epoch`

```python
def get_delayed_activation_exit_epoch(epoch: Epoch) -> Epoch:
    """
    Return the epoch at which an activation or exit triggered in ``epoch`` takes effect.
    """
    return epoch + 1 + ACTIVATION_EXIT_DELAY
```

### `get_churn_limit`

```python
def get_churn_limit(state: BeaconState) -> int:
    return max(
        MIN_PER_EPOCH_CHURN_LIMIT,
        len(get_active_validator_indices(state, get_current_epoch(state))) // CHURN_LIMIT_QUOTIENT
    )
```

### `bls_verify`

`bls_verify` is a function for verifying a BLS signature, defined in the [BLS Signature spec](../bls_signature.md#bls_verify).

### `bls_verify_multiple`

`bls_verify_multiple` is a function for verifying a BLS signature constructed from multiple messages, defined in the [BLS Signature spec](../bls_signature.md#bls_verify_multiple).

### `bls_aggregate_pubkeys`

`bls_aggregate_pubkeys` is a function for aggregating multiple BLS public keys into a single aggregate key, defined in the [BLS Signature spec](../bls_signature.md#bls_aggregate_pubkeys).

### Routines for updating validator status

Note: All functions in this section mutate `state`.

#### `initiate_validator_exit`

```python
def initiate_validator_exit(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Initiate the validator of the given ``index``.
    Note that this function mutates ``state``.
    """
    # Return if validator already initiated exit
    validator = state.validator_registry[index]
    if validator.exit_epoch != FAR_FUTURE_EPOCH:
        return

    # Compute exit queue epoch
    exit_epochs = [v.exit_epoch for v in state.validator_registry if v.exit_epoch != FAR_FUTURE_EPOCH]
    exit_queue_epoch = max(exit_epochs + [get_delayed_activation_exit_epoch(get_current_epoch(state))])
    exit_queue_churn = len([v for v in state.validator_registry if v.exit_epoch == exit_queue_epoch])
    if exit_queue_churn >= get_churn_limit(state):
        exit_queue_epoch += 1

    # Set validator exit epoch and withdrawable epoch
    validator.exit_epoch = exit_queue_epoch
    validator.withdrawable_epoch = validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY
```

#### `slash_validator`

```python
def slash_validator(state: BeaconState, slashed_index: ValidatorIndex, whistleblower_index: ValidatorIndex=None) -> None:
    """
    Slash the validator with index ``slashed_index``.
    Note that this function mutates ``state``.
    """
    current_epoch = get_current_epoch(state)
    initiate_validator_exit(state, slashed_index)
    state.validator_registry[slashed_index].slashed = True
    state.validator_registry[slashed_index].withdrawable_epoch = current_epoch + LATEST_SLASHED_EXIT_LENGTH
    slashed_balance = state.validator_registry[slashed_index].effective_balance
    state.latest_slashed_balances[current_epoch % LATEST_SLASHED_EXIT_LENGTH] += slashed_balance

    proposer_index = get_beacon_proposer_index(state)
    if whistleblower_index is None:
        whistleblower_index = proposer_index
    whistleblowing_reward = slashed_balance // WHISTLEBLOWING_REWARD_QUOTIENT
    proposer_reward = whistleblowing_reward // PROPOSER_REWARD_QUOTIENT
    increase_balance(state, proposer_index, proposer_reward)
    increase_balance(state, whistleblower_index, whistleblowing_reward - proposer_reward)
    decrease_balance(state, slashed_index, whistleblowing_reward)
```

## On genesis

When enough full deposits have been made to the deposit contract, an `Eth2Genesis` log is emitted. Construct a corresponding `genesis_state` and `genesis_block` as follows:

* Let `genesis_validator_deposits` be the list of deposits, ordered chronologically, up to and including the deposit that triggered the `Eth2Genesis` log.
* Let `genesis_time` be the timestamp specified in the `Eth2Genesis` log.
* Let `genesis_eth1_data` be the `Eth1Data` object where:
    * `genesis_eth1_data.deposit_root` is the `deposit_root` contained in the `Eth2Genesis` log.
    * `genesis_eth1_data.deposit_count` is the `deposit_count` contained in the `Eth2Genesis` log.
    * `genesis_eth1_data.block_hash` is the hash of the Ethereum 1.0 block that emitted the `Eth2Genesis` log.
* Let `genesis_state = get_genesis_beacon_state(genesis_validator_deposits, genesis_time, genesis_eth1_data)`.
* Let `genesis_block = BeaconBlock(state_root=hash_tree_root(genesis_state))`.

```python
def get_genesis_beacon_state(genesis_validator_deposits: List[Deposit],
                             genesis_time: int,
                             genesis_eth1_data: Eth1Data) -> BeaconState:
    """
    Get the genesis ``BeaconState``.
    """
    state = BeaconState(genesis_time=genesis_time, latest_eth1_data=genesis_eth1_data)

    # Process genesis deposits
    for deposit in genesis_validator_deposits:
        process_deposit(state, deposit)

    # Process genesis activations
    for index, validator in enumerate(state.validator_registry):
        if validator.effective_balance >= MAX_EFFECTIVE_BALANCE:
            validator.activation_eligibility_epoch = GENESIS_EPOCH
            validator.activation_epoch = GENESIS_EPOCH

    genesis_active_index_root = hash_tree_root(get_active_validator_indices(state, GENESIS_EPOCH))
    for index in range(LATEST_ACTIVE_INDEX_ROOTS_LENGTH):
        state.latest_active_index_roots[index] = genesis_active_index_root

    return state
```

## Beacon chain state transition function

The post-state corresponding to a pre-state `state` and a block `block` is defined as `state_transition(state, block)`. State transitions that trigger an unhandled exception (e.g. a failed `assert` or an out-of-range list access) are considered invalid.

```python
def state_transition(state: BeaconState, block: BeaconBlock) -> BeaconBlock:
    # Block must post-date the state
    assert state.slot < block.slot
    # Process slots (including those with no blocks) since block
    while state.slot < block.slot:
        # Cache state at the start of every slot
        cache_state(state)
        # Process epoch at the start of the first slot of every epoch
        if (state.slot + 1) % SLOTS_PER_EPOCH == 0:
            process_epoch(state)
        # Increment slot number
        state.slot += 1
    # Process block
    process_block(state, block)
    # Return post-state
    return state
```

### State caching

```python
def cache_state(state: BeaconState) -> None:
    # Cache state root of previous slot
    previous_state_root = hash_tree_root(state)
    state.latest_state_roots[state.slot % SLOTS_PER_HISTORICAL_ROOT] = previous_state_root

    # Cache previous state root in latest_block_header, if empty
    if state.latest_block_header.state_root == ZERO_HASH:
        state.latest_block_header.state_root = previous_state_root

    # Cache block root of previous slot
    previous_block_root = signing_root(state.latest_block_header)
    state.latest_block_roots[state.slot % SLOTS_PER_HISTORICAL_ROOT] = previous_block_root

```

### Epoch processing

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_crosslinks(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_slashings(state)
    process_final_updates(state)
```

#### Helper functions

```python
def get_total_active_balance(state: BeaconState) -> Gwei:
    return get_total_balance(state, get_active_validator_indices(state, get_current_epoch(state)))
```

```python
def get_matching_source_attestations(state: BeaconState, epoch: Epoch) -> List[PendingAttestation]:
    assert epoch in (get_current_epoch(state), get_previous_epoch(state))
    return state.current_epoch_attestations if epoch == get_current_epoch(state) else state.previous_epoch_attestations
```

```python
def get_matching_target_attestations(state: BeaconState, epoch: Epoch) -> List[PendingAttestation]:
    return [
        a for a in get_matching_source_attestations(state, epoch)
        if a.data.target_root == get_block_root(state, epoch)
    ]
```

```python
def get_matching_head_attestations(state: BeaconState, epoch: Epoch) -> List[PendingAttestation]:
    return [
        a for a in get_matching_source_attestations(state, epoch)
        if a.data.beacon_block_root == get_block_root_at_slot(state, a.data.slot)
    ]
```

```python
def get_unslashed_attesting_indices(state: BeaconState, attestations: List[PendingAttestation]) -> List[ValidatorIndex]:
    output = set()
    for a in attestations:
        output = output.union(get_attesting_indices(state, a.data, a.aggregation_bitfield))
    return sorted(filter(lambda index: not state.validator_registry[index].slashed, list(output)))
```

```python
def get_attesting_balance(state: BeaconState, attestations: List[PendingAttestation]) -> Gwei:
    return get_total_balance(state, get_unslashed_attesting_indices(state, attestations))
```

```python
def get_crosslink_from_attestation_data(state: BeaconState, data: AttestationData) -> Crosslink:
    return Crosslink(
        epoch=min(slot_to_epoch(data.slot), state.current_crosslinks[data.shard].epoch + MAX_CROSSLINK_EPOCHS),
        previous_crosslink_root=data.previous_crosslink_root,
        crosslink_data_root=data.crosslink_data_root,
    )
```

```python
def get_winning_crosslink_and_attesting_indices(state: BeaconState, shard: Shard, epoch: Epoch) -> Tuple[Crosslink, List[ValidatorIndex]]:
    shard_attestations = [a for a in get_matching_source_attestations(state, epoch) if a.data.shard == shard]
    shard_crosslinks = [get_crosslink_from_attestation_data(state, a.data) for a in shard_attestations]
    candidate_crosslinks = [
        c for c in shard_crosslinks
        if hash_tree_root(state.current_crosslinks[shard]) in (c.previous_crosslink_root, hash_tree_root(c))
    ]
    if len(candidate_crosslinks) == 0:
        return Crosslink(epoch=GENESIS_EPOCH, previous_crosslink_root=ZERO_HASH, crosslink_data_root=ZERO_HASH), []

    def get_attestations_for(crosslink: Crosslink) -> List[PendingAttestation]:
        return [a for a in shard_attestations if get_crosslink_from_attestation_data(state, a.data) == crosslink]
    # Winning crosslink has the crosslink data root with the most balance voting for it (ties broken lexicographically)
    winning_crosslink = max(candidate_crosslinks, key=lambda crosslink: (
        get_attesting_balance(state, get_attestations_for(crosslink)), crosslink.crosslink_data_root
    ))

    return winning_crosslink, get_unslashed_attesting_indices(state, get_attestations_for(winning_crosslink))
```

```python
def get_earliest_attestation(state: BeaconState, attestations: List[PendingAttestation], index: ValidatorIndex) -> PendingAttestation:
    return min([
        a for a in attestations if index in get_attesting_indices(state, a.data, a.aggregation_bitfield)
    ], key=lambda a: a.inclusion_slot)
```

#### Justification and finalization

```python
def process_justification_and_finalization(state: BeaconState) -> None:
    if get_current_epoch(state) <= GENESIS_EPOCH + 1:
        return

    previous_epoch = get_previous_epoch(state)
    current_epoch = get_current_epoch(state)
    old_previous_justified_epoch = state.previous_justified_epoch
    old_current_justified_epoch = state.current_justified_epoch

    # Process justifications
    state.previous_justified_epoch = state.current_justified_epoch
    state.previous_justified_root = state.current_justified_root
    state.justification_bitfield = (state.justification_bitfield << 1) % 2**64
    previous_epoch_matching_target_balance = get_attesting_balance(state, get_matching_target_attestations(state, previous_epoch))
    if previous_epoch_matching_target_balance * 3 >= get_total_active_balance(state) * 2:
        state.current_justified_epoch = previous_epoch
        state.current_justified_root = get_block_root(state, state.current_justified_epoch)
        state.justification_bitfield |= (1 << 1)
    current_epoch_matching_target_balance = get_attesting_balance(state, get_matching_target_attestations(state, current_epoch))
    if current_epoch_matching_target_balance * 3 >= get_total_active_balance(state) * 2:
        state.current_justified_epoch = current_epoch
        state.current_justified_root = get_block_root(state, state.current_justified_epoch)
        state.justification_bitfield |= (1 << 0)

    # Process finalizations
    bitfield = state.justification_bitfield
    # The 2nd/3rd/4th most recent epochs are justified, the 2nd using the 4th as source
    if (bitfield >> 1) % 8 == 0b111 and old_previous_justified_epoch == current_epoch - 3:
        state.finalized_epoch = old_previous_justified_epoch
        state.finalized_root = get_block_root(state, state.finalized_epoch)
    # The 2nd/3rd most recent epochs are justified, the 2nd using the 3rd as source
    if (bitfield >> 1) % 4 == 0b11 and old_previous_justified_epoch == current_epoch - 2:
        state.finalized_epoch = old_previous_justified_epoch
        state.finalized_root = get_block_root(state, state.finalized_epoch)
    # The 1st/2nd/3rd most recent epochs are justified, the 1st using the 3rd as source
    if (bitfield >> 0) % 8 == 0b111 and old_current_justified_epoch == current_epoch - 2:
        state.finalized_epoch = old_current_justified_epoch
        state.finalized_root = get_block_root(state, state.finalized_epoch)
    # The 1st/2nd most recent epochs are justified, the 1st using the 2nd as source
    if (bitfield >> 0) % 4 == 0b11 and old_current_justified_epoch == current_epoch - 1:
        state.finalized_epoch = old_current_justified_epoch
        state.finalized_root = get_block_root(state, state.finalized_epoch)
```

#### Crosslinks

```python
def process_crosslinks(state: BeaconState) -> None:
    state.previous_crosslinks = [c for c in state.current_crosslinks]
    previous_epoch = get_previous_epoch(state)
    next_epoch = get_current_epoch(state) + 1
    for slot in range(get_epoch_start_slot(previous_epoch), get_epoch_start_slot(next_epoch)):
        epoch = slot_to_epoch(slot)
        for crosslink_committee, shard in get_crosslink_committees_at_slot(state, slot):
            winning_crosslink, attesting_indices = get_winning_crosslink_and_attesting_indices(state, shard, epoch)
            if 3 * get_total_balance(state, attesting_indices) >= 2 * get_total_balance(state, crosslink_committee):
                state.current_crosslinks[shard] = winning_crosslink
```

#### Rewards and penalties

```python
def get_base_reward(state: BeaconState, index: ValidatorIndex) -> Gwei:
    adjusted_quotient = integer_squareroot(get_total_active_balance(state)) // BASE_REWARD_QUOTIENT
    if adjusted_quotient == 0:
        return 0
    return state.validator_registry[index].effective_balance // adjusted_quotient // BASE_REWARDS_PER_EPOCH

```

```python
def get_attestation_deltas(state: BeaconState) -> Tuple[List[Gwei], List[Gwei]]:
    previous_epoch = get_previous_epoch(state)
    total_balance = get_total_active_balance(state)
    rewards = [0 for index in range(len(state.validator_registry))]
    penalties = [0 for index in range(len(state.validator_registry))]
    eligible_validator_indices = [
        index for index, v in enumerate(state.validator_registry)
        if is_active_validator(v, previous_epoch) or (v.slashed and previous_epoch + 1 < v.withdrawable_epoch)
    ]

    # Micro-incentives for matching FFG source, FFG target, and head
    matching_source_attestations = get_matching_source_attestations(state, previous_epoch)
    matching_target_attestations = get_matching_target_attestations(state, previous_epoch)
    matching_head_attestations = get_matching_head_attestations(state, previous_epoch)
    for attestations in (matching_source_attestations, matching_target_attestations, matching_head_attestations):
        unslashed_attesting_indices = get_unslashed_attesting_indices(state, attestations)
        attesting_balance = get_attesting_balance(state, attestations)
        for index in eligible_validator_indices:
            if index in unslashed_attesting_indices:
                rewards[index] += get_base_reward(state, index) * attesting_balance // total_balance
            else:
                penalties[index] += get_base_reward(state, index)

    # Proposer and inclusion delay micro-rewards
    for index in get_unslashed_attesting_indices(state, matching_source_attestations):
        earliest_attestation = get_earliest_attestation(state, matching_source_attestations, index)
        rewards[earliest_attestation.proposer_index] += get_base_reward(state, index) // PROPOSER_REWARD_QUOTIENT
        inclusion_delay = earliest_attestation.inclusion_slot - earliest_attestation.data.slot
        rewards[index] += get_base_reward(state, index) * MIN_ATTESTATION_INCLUSION_DELAY // inclusion_delay

    # Inactivity penalty
    finality_delay = previous_epoch - state.finalized_epoch
    if finality_delay > MIN_EPOCHS_TO_INACTIVITY_PENALTY:
        matching_target_attesting_indices = get_unslashed_attesting_indices(state, matching_target_attestations)
        for index in eligible_validator_indices:
            penalties[index] += BASE_REWARDS_PER_EPOCH * get_base_reward(state, index)
            if index not in matching_target_attesting_indices:
                penalties[index] += state.validator_registry[index].effective_balance * finality_delay // INACTIVITY_PENALTY_QUOTIENT

    return [rewards, penalties]
```

```python
def get_crosslink_deltas(state: BeaconState) -> Tuple[List[Gwei], List[Gwei]]:
    rewards = [0 for index in range(len(state.validator_registry))]
    penalties = [0 for index in range(len(state.validator_registry))]
    for slot in range(get_epoch_start_slot(get_previous_epoch(state)), get_epoch_start_slot(get_current_epoch(state))):
        epoch = slot_to_epoch(slot)
        for crosslink_committee, shard in get_crosslink_committees_at_slot(state, slot):
            winning_crosslink, attesting_indices = get_winning_crosslink_and_attesting_indices(state, shard, epoch)
            attesting_balance = get_total_balance(state, attesting_indices)
            committee_balance = get_total_balance(state, crosslink_committee)
            for index in crosslink_committee:
                base_reward = get_base_reward(state, index)
                if index in attesting_indices:
                    rewards[index] += base_reward * attesting_balance // committee_balance
                else:
                    penalties[index] += base_reward
    return [rewards, penalties]
```

```python
def process_rewards_and_penalties(state: BeaconState) -> None:
    if get_current_epoch(state) == GENESIS_EPOCH:
        return

    rewards1, penalties1 = get_attestation_deltas(state)
    rewards2, penalties2 = get_crosslink_deltas(state)
    for i in range(len(state.validator_registry)):
        increase_balance(state, i, rewards1[i] + rewards2[i])
        decrease_balance(state, i, penalties1[i] + penalties2[i])
```

#### Registry updates

```python
def process_registry_updates(state: BeaconState) -> None:
    # Process activation eligibility and ejections
    for index, validator in enumerate(state.validator_registry):
        if validator.activation_eligibility_epoch == FAR_FUTURE_EPOCH and validator.effective_balance >= MAX_EFFECTIVE_BALANCE:
            validator.activation_eligibility_epoch = get_current_epoch(state)

        if is_active_validator(validator, get_current_epoch(state)) and validator.effective_balance <= EJECTION_BALANCE:
            initiate_validator_exit(state, index)

    # Queue validators eligible for activation and not dequeued for activation prior to finalized epoch
    activation_queue = sorted([
        index for index, validator in enumerate(state.validator_registry) if
        validator.activation_eligibility_epoch != FAR_FUTURE_EPOCH and
        validator.activation_epoch >= get_delayed_activation_exit_epoch(state.finalized_epoch)
    ], key=lambda index: state.validator_registry[index].activation_eligibility_epoch)
    # Dequeued validators for activation up to churn limit (without resetting activation epoch)
    for index in activation_queue[:get_churn_limit(state)]:
        if validator.activation_epoch == FAR_FUTURE_EPOCH:
            validator.activation_epoch = get_delayed_activation_exit_epoch(get_current_epoch(state))
```

#### Slashings

```python
def process_slashings(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    active_validator_indices = get_active_validator_indices(state, current_epoch)
    total_balance = get_total_balance(state, active_validator_indices)

    # Compute `total_penalties`
    total_at_start = state.latest_slashed_balances[(current_epoch + 1) % LATEST_SLASHED_EXIT_LENGTH]
    total_at_end = state.latest_slashed_balances[current_epoch % LATEST_SLASHED_EXIT_LENGTH]
    total_penalties = total_at_end - total_at_start

    for index, validator in enumerate(state.validator_registry):
        if validator.slashed and current_epoch == validator.withdrawable_epoch - LATEST_SLASHED_EXIT_LENGTH // 2:
            penalty = max(
                validator.effective_balance * min(total_penalties * 3, total_balance) // total_balance,
                validator.effective_balance // MIN_SLASHING_PENALTY_QUOTIENT
            )
            decrease_balance(state, index, penalty)
```

#### Final updates

```python
def process_final_updates(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    next_epoch = current_epoch + 1
    # Reset eth1 data votes
    if (state.slot + 1) % SLOTS_PER_ETH1_VOTING_PERIOD == 0:
        state.eth1_data_votes = []
    # Update effective balances with hysteresis
    for index, validator in enumerate(state.validator_registry):
        balance = min(state.balances[index], MAX_EFFECTIVE_BALANCE)
        HALF_INCREMENT = EFFECTIVE_BALANCE_INCREMENT // 2
        if balance < validator.effective_balance or validator.effective_balance + 3 * HALF_INCREMENT < balance:
            validator.effective_balance = balance - balance % EFFECTIVE_BALANCE_INCREMENT
    # Update start shard
    state.latest_start_shard = (state.latest_start_shard + get_shard_delta(state, current_epoch)) % SHARD_COUNT
    # Set active index root
    index_root_position = (next_epoch + ACTIVATION_EXIT_DELAY) % LATEST_ACTIVE_INDEX_ROOTS_LENGTH
    state.latest_active_index_roots[index_root_position] = hash_tree_root(
        get_active_validator_indices(state, next_epoch + ACTIVATION_EXIT_DELAY)
    )
    # Set total slashed balances
    state.latest_slashed_balances[next_epoch % LATEST_SLASHED_EXIT_LENGTH] = (
        state.latest_slashed_balances[current_epoch % LATEST_SLASHED_EXIT_LENGTH]
    )
    # Set randao mix
    state.latest_randao_mixes[next_epoch % LATEST_RANDAO_MIXES_LENGTH] = get_randao_mix(state, current_epoch)
    # Set historical root accumulator
    if next_epoch % (SLOTS_PER_HISTORICAL_ROOT // SLOTS_PER_EPOCH) == 0:
        historical_batch = HistoricalBatch(
            block_roots=state.latest_block_roots,
            state_roots=state.latest_state_roots,
        )
        state.historical_roots.append(hash_tree_root(historical_batch))
    # Rotate current/previous epoch attestations
    state.previous_epoch_attestations = state.current_epoch_attestations
    state.current_epoch_attestations = []
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_randao(state, block)
    process_eth1_data(state, block)
    process_operations(state, block.body)
    # verify_block_state_root(state, block)
```

#### Block header

```python
def process_block_header(state: BeaconState, block: BeaconBlock) -> None:
    # Verify that the slots match
    assert block.slot == state.slot
    # Verify that the parent matches
    assert block.previous_block_root == signing_root(state.latest_block_header)
    # Save current block as the new latest block
    state.latest_block_header = BeaconBlockHeader(
        slot=block.slot,
        previous_block_root=block.previous_block_root,
        block_body_root=hash_tree_root(block.body),
    )
    # Verify proposer is not slashed
    proposer = state.validator_registry[get_beacon_proposer_index(state)]
    assert not proposer.slashed
    # Verify proposer signature
    assert bls_verify(proposer.pubkey, signing_root(block), block.signature, get_domain(state, DOMAIN_BEACON_PROPOSER))
```

#### RANDAO

```python
def process_randao(state: BeaconState, block: BeaconBlock) -> None:
    proposer = state.validator_registry[get_beacon_proposer_index(state)]
    # Verify that the provided randao value is valid
    assert bls_verify(proposer.pubkey, hash_tree_root(get_current_epoch(state)), block.body.randao_reveal, get_domain(state, DOMAIN_RANDAO))
    # Mix it in
    state.latest_randao_mixes[get_current_epoch(state) % LATEST_RANDAO_MIXES_LENGTH] = (
        xor(get_randao_mix(state, get_current_epoch(state)),
            hash(block.body.randao_reveal))
    )
```

#### Eth1 data

```python
def process_eth1_data(state: BeaconState, block: BeaconBlock) -> None:
    state.eth1_data_votes.append(block.body.eth1_data)
    if state.eth1_data_votes.count(block.body.eth1_data) * 2 > SLOTS_PER_ETH1_VOTING_PERIOD:
        state.latest_eth1_data = block.body.eth1_data
```

#### Operations

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    assert len(body.deposits) == min(MAX_DEPOSITS, state.latest_eth1_data.deposit_count - state.deposit_index)
    assert len(body.transfers) == len(set(body.transfers))

    for operations, max_operations, function in (
        (body.proposer_slashings, MAX_PROPOSER_SLASHINGS, process_proposer_slashing),
        (body.attester_slashings, MAX_ATTESTER_SLASHINGS, process_attester_slashing),
        (body.attestations, MAX_ATTESTATIONS, process_attestation),
        (body.deposits, MAX_DEPOSITS, process_deposit),
        (body.voluntary_exits, MAX_VOLUNTARY_EXITS, process_voluntary_exit),
        (body.transfers, MAX_TRANSFERS, process_transfer),
    ):
        assert len(operations) <= max_operations
        for operation in operations:
            function(state, operation)
```

##### Proposer slashings

```python
def process_proposer_slashing(state: BeaconState,
                              proposer_slashing: ProposerSlashing) -> None:
    """
    Process ``ProposerSlashing`` operation.
    Note that this function mutates ``state``.
    """
    proposer = state.validator_registry[proposer_slashing.proposer_index]
    # Verify that the epoch is the same
    assert slot_to_epoch(proposer_slashing.header_1.slot) == slot_to_epoch(proposer_slashing.header_2.slot)
    # But the headers are different
    assert proposer_slashing.header_1 != proposer_slashing.header_2
    # Check proposer is slashable
    assert is_slashable_validator(proposer, get_current_epoch(state))
    # Signatures are valid
    for header in (proposer_slashing.header_1, proposer_slashing.header_2):
        domain = get_domain(state, DOMAIN_BEACON_PROPOSER, slot_to_epoch(header.slot))
        assert bls_verify(proposer.pubkey, signing_root(header), header.signature, domain)

    slash_validator(state, proposer_slashing.proposer_index)
```

##### Attester slashings

```python
def process_attester_slashing(state: BeaconState,
                              attester_slashing: AttesterSlashing) -> None:
    """
    Process ``AttesterSlashing`` operation.
    Note that this function mutates ``state``.
    """
    attestation1 = attester_slashing.attestation_1
    attestation2 = attester_slashing.attestation_2
    # Check that the attestations are conflicting
    assert attestation1.data != attestation2.data
    assert (
        is_double_vote(attestation1.data, attestation2.data) or
        is_surround_vote(attestation1.data, attestation2.data)
    )

    assert verify_indexed_attestation(state, attestation1)
    assert verify_indexed_attestation(state, attestation2)
    attesting_indices_1 = attestation1.custody_bit_0_indices + attestation1.custody_bit_1_indices
    attesting_indices_2 = attestation2.custody_bit_0_indices + attestation2.custody_bit_1_indices
    slashable_indices = [
        index for index in attesting_indices_1
        if (
            index in attesting_indices_2 and
            is_slashable_validator(state.validator_registry[index], get_current_epoch(state))
        )
    ]
    assert len(slashable_indices) >= 1
    for index in slashable_indices:
        slash_validator(state, index)
```

##### Attestations

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    """
    Process ``Attestation`` operation.
    Note that this function mutates ``state``.
    """
    data = attestation.data
    min_slot = state.slot - SLOTS_PER_EPOCH if get_current_epoch(state) > GENESIS_EPOCH else GENESIS_SLOT
    assert min_slot <= data.slot <= state.slot - MIN_ATTESTATION_INCLUSION_DELAY

    # Check target epoch, source epoch, source root, and source crosslink
    target_epoch = slot_to_epoch(data.slot)
    assert (target_epoch, data.source_epoch, data.source_root, data.previous_crosslink_root) in {
        (get_current_epoch(state), state.current_justified_epoch, state.current_justified_root, hash_tree_root(state.current_crosslinks[data.shard])),
        (get_previous_epoch(state), state.previous_justified_epoch, state.previous_justified_root, hash_tree_root(state.previous_crosslinks[data.shard])),
    }

    # Check crosslink data root
    assert data.crosslink_data_root == ZERO_HASH  # [to be removed in phase 1]

    # Check signature and bitfields
    assert verify_indexed_attestation(state, convert_to_indexed(state, attestation))

    # Cache pending attestation
    pending_attestation = PendingAttestation(
        data=data,
        aggregation_bitfield=attestation.aggregation_bitfield,
        inclusion_slot=state.slot,
        proposer_index=get_beacon_proposer_index(state),
    )
    if target_epoch == get_current_epoch(state):
        state.current_epoch_attestations.append(pending_attestation)
    else:
        state.previous_epoch_attestations.append(pending_attestation)
```

##### Deposits

```python
def process_deposit(state: BeaconState, deposit: Deposit) -> None:
    """
    Process an Eth1 deposit, registering a validator or increasing its balance.
    Note that this function mutates ``state``.
    """
    # Verify the Merkle branch
    assert verify_merkle_branch(
        leaf=hash_tree_root(deposit.data),
        proof=deposit.proof,
        depth=DEPOSIT_CONTRACT_TREE_DEPTH,
        index=deposit.index,
        root=state.latest_eth1_data.deposit_root,
    )

    # Deposits must be processed in order
    assert deposit.index == state.deposit_index
    state.deposit_index += 1

    pubkey = deposit.data.pubkey
    amount = deposit.data.amount
    validator_pubkeys = [v.pubkey for v in state.validator_registry]
    if pubkey not in validator_pubkeys:
        # Verify the deposit signature (proof of possession)
        if not bls_verify(pubkey, signing_root(deposit.data), deposit.data.signature, get_domain(state, DOMAIN_DEPOSIT)):
            return

        # Add validator and balance entries
        state.validator_registry.append(Validator(
            pubkey=pubkey,
            withdrawal_credentials=deposit.data.withdrawal_credentials,
            activation_eligibility_epoch=FAR_FUTURE_EPOCH,
            activation_epoch=FAR_FUTURE_EPOCH,
            exit_epoch=FAR_FUTURE_EPOCH,
            withdrawable_epoch=FAR_FUTURE_EPOCH,
            effective_balance=amount - amount % EFFECTIVE_BALANCE_INCREMENT
        ))
        state.balances.append(amount)
    else:
        # Increase balance by deposit amount
        index = validator_pubkeys.index(pubkey)
        increase_balance(state, index, amount)
```

##### Voluntary exits

```python
def process_voluntary_exit(state: BeaconState, exit: VoluntaryExit) -> None:
    """
    Process ``VoluntaryExit`` operation.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[exit.validator_index]
    # Verify the validator is active
    assert is_active_validator(validator, get_current_epoch(state))
    # Verify the validator has not yet exited
    assert validator.exit_epoch == FAR_FUTURE_EPOCH
    # Exits must specify an epoch when they become valid; they are not valid before then
    assert get_current_epoch(state) >= exit.epoch
    # Verify the validator has been active long enough
    assert get_current_epoch(state) - validator.activation_epoch >= PERSISTENT_COMMITTEE_PERIOD
    # Verify signature
    domain = get_domain(state, DOMAIN_VOLUNTARY_EXIT, exit.epoch)
    assert bls_verify(validator.pubkey, signing_root(exit), exit.signature, domain)
    # Initiate exit
    initiate_validator_exit(state, exit.validator_index)
```

##### Transfers

```python
def process_transfer(state: BeaconState, transfer: Transfer) -> None:
    """
    Process ``Transfer`` operation.
    Note that this function mutates ``state``.
    """
    # Verify the amount and fee are not individually too big (for anti-overflow purposes)
    assert state.balances[transfer.sender] >= max(transfer.amount, transfer.fee)
    # A transfer is valid in only one slot
    assert state.slot == transfer.slot
    # Sender must be not yet eligible for activation, withdrawn, or transfer balance over MAX_EFFECTIVE_BALANCE
    assert (
        state.validator_registry[transfer.sender].activation_eligibility_epoch == FAR_FUTURE_EPOCH or
        get_current_epoch(state) >= state.validator_registry[transfer.sender].withdrawable_epoch or
        transfer.amount + transfer.fee + MAX_EFFECTIVE_BALANCE <= state.balances[transfer.sender]
    )
    # Verify that the pubkey is valid
    assert (
        state.validator_registry[transfer.sender].withdrawal_credentials ==
        BLS_WITHDRAWAL_PREFIX_BYTE + hash(transfer.pubkey)[1:]
    )
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

#### State root verification

```python
def verify_block_state_root(state: BeaconState, block: BeaconBlock) -> None:
    assert block.state_root == hash_tree_root(state)
```
