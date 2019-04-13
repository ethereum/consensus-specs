# Ethereum 2.0 Phase 0 -- The Beacon Chain

**NOTICE**: This document is a work in progress for researchers and implementers. It reflects recent spec changes and takes precedence over the Python proof-of-concept implementation [[python-poc]](#ref-python-poc).

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
            - [`Eth1DataVote`](#eth1datavote)
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
        - [`get_temporary_block_header`](#get_temporary_block_header)
        - [`slot_to_epoch`](#slot_to_epoch)
        - [`get_previous_epoch`](#get_previous_epoch)
        - [`get_current_epoch`](#get_current_epoch)
        - [`get_epoch_start_slot`](#get_epoch_start_slot)
        - [`is_active_validator`](#is_active_validator)
        - [`is_slashable_validator`](#is_slashable_validator)
        - [`get_active_validator_indices`](#get_active_validator_indices)
        - [`get_balance`](#get_balance)
        - [`set_balance`](#set_balance)
        - [`increase_balance`](#increase_balance)
        - [`decrease_balance`](#decrease_balance)
        - [`get_permuted_index`](#get_permuted_index)
        - [`get_split_offset`](#get_split_offset)
        - [`get_epoch_committee_count`](#get_epoch_committee_count)
        - [`get_shard_delta`](#get_shard_delta)
        - [`compute_committee`](#compute_committee)
        - [`get_crosslink_committees_at_slot`](#get_crosslink_committees_at_slot)
        - [`get_block_root`](#get_block_root)
        - [`get_state_root`](#get_state_root)
        - [`get_randao_mix`](#get_randao_mix)
        - [`get_active_index_root`](#get_active_index_root)
        - [`generate_seed`](#generate_seed)
        - [`get_beacon_proposer_index`](#get_beacon_proposer_index)
        - [`verify_merkle_branch`](#verify_merkle_branch)
        - [`get_crosslink_committee_for_attestation`](#get_crosslink_committee_for_attestation)
        - [`get_attestation_participants`](#get_attestation_participants)
        - [`int_to_bytes1`, `int_to_bytes2`, ...](#int_to_bytes1-int_to_bytes2-)
        - [`bytes_to_int`](#bytes_to_int)
        - [`get_effective_balance`](#get_effective_balance)
        - [`get_total_balance`](#get_total_balance)
        - [`get_fork_version`](#get_fork_version)
        - [`get_domain`](#get_domain)
        - [`get_bitfield_bit`](#get_bitfield_bit)
        - [`verify_bitfield`](#verify_bitfield)
        - [`convert_to_indexed`](#convert_to_indexed)
        - [`verify_indexed_attestation`](#verify_indexed_attestation)
        - [`is_double_vote`](#is_double_vote)
        - [`is_surround_vote`](#is_surround_vote)
        - [`integer_squareroot`](#integer_squareroot)
        - [`get_delayed_activation_exit_epoch`](#get_delayed_activation_exit_epoch)
        - [`bls_verify`](#bls_verify)
        - [`bls_verify_multiple`](#bls_verify_multiple)
        - [`bls_aggregate_pubkeys`](#bls_aggregate_pubkeys)
        - [Routines for updating validator status](#routines-for-updating-validator-status)
            - [`activate_validator`](#activate_validator)
            - [`initiate_validator_exit`](#initiate_validator_exit)
            - [`slash_validator`](#slash_validator)
    - [Ethereum 1.0 deposit contract](#ethereum-10-deposit-contract)
        - [Deposit arguments](#deposit-arguments)
        - [Withdrawal credentials](#withdrawal-credentials)
        - [`Deposit` logs](#deposit-logs)
        - [`Eth2Genesis` log](#eth2genesis-log)
        - [Vyper code](#vyper-code)
    - [On genesis](#on-genesis)
    - [Beacon chain processing](#beacon-chain-processing)
        - [Beacon chain fork choice rule](#beacon-chain-fork-choice-rule)
    - [Beacon chain state transition function](#beacon-chain-state-transition-function)
        - [State caching](#state-caching)
        - [Per-epoch processing](#per-epoch-processing)
            - [Helper functions](#helper-functions-1)
            - [Justification](#justification)
            - [Crosslinks](#crosslinks)
            - [Eth1 data](#eth1-data)
            - [Rewards and penalties](#rewards-and-penalties)
                - [Justification and finalization](#justification-and-finalization)
                - [Crosslinks](#crosslinks-1)
            - [Apply rewards](#apply-rewards)
            - [Balance-driven status transitions](#balance-driven-status-transitions)
            - [Activation queue and start shard](#activation-queue-and-start-shard)
            - [Slashings](#slashings)
            - [Final updates](#final-updates)
        - [Per-slot processing](#per-slot-processing)
        - [Per-block processing](#per-block-processing)
            - [Block header](#block-header)
            - [RANDAO](#randao)
            - [Eth1 data](#eth1-data-1)
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
| `MAX_ATTESTATION_PARTICIPANTS` | `2**12` (= 4,096) |
| `MAX_EXITS_PER_EPOCH` | `2**2` (= 4) |
| `MAX_ACTIVATIONS_PER_FINALIZED_EPOCH` | `2**2` (= 4) |
| `SHUFFLE_ROUND_COUNT` | 90 |

* For the safety of crosslinks `TARGET_COMMITTEE_SIZE` exceeds [the recommended minimum committee size of 111](https://vitalik.ca/files/Ithaca201807_Sharding.pdf); with sufficient active validators (at least `SLOTS_PER_EPOCH * TARGET_COMMITTEE_SIZE`), the shuffling algorithm ensures committee sizes of at least `TARGET_COMMITTEE_SIZE`. (Unbiasable randomness with a Verifiable Delay Function (VDF) will improve committee robustness and lower the safe minimum committee size.)

### Deposit contract

| Name | Value |
| - | - |
| `DEPOSIT_CONTRACT_ADDRESS` | **TBD** |
| `DEPOSIT_CONTRACT_TREE_DEPTH` | `2**5` (= 32) |

### Gwei values

| Name | Value | Unit |
| - | - | :-: |
| `MIN_DEPOSIT_AMOUNT` | `2**0 * 10**9` (= 1,000,000,000) | Gwei |
| `MAX_DEPOSIT_AMOUNT` | `2**5 * 10**9` (= 32,000,000,000) | Gwei |
| `EJECTION_BALANCE` | `2**4 * 10**9` (= 16,000,000,000) | Gwei |
| `HIGH_BALANCE_INCREMENT` | `2**0 * 10**9` (= 1,000,000,000) | Gwei |

### Initial values

| Name | Value |
| - | - |
| `GENESIS_FORK_VERSION` | `int_to_bytes4(0)` |
| `GENESIS_SLOT` | `2**32` |
| `GENESIS_EPOCH` | `slot_to_epoch(GENESIS_SLOT)` |
| `GENESIS_START_SHARD` | `0` |
| `FAR_FUTURE_EPOCH` | `2**64 - 1` |
| `ZERO_HASH` | `int_to_bytes32(0)` |
| `EMPTY_SIGNATURE` | `int_to_bytes96(0)` |
| `BLS_WITHDRAWAL_PREFIX_BYTE` | `int_to_bytes1(0)` |

* `GENESIS_SLOT` should be at least as large in terms of time as the largest of the time parameters or state list lengths below (ie. it should be at least as large as any value measured in slots, and at least `SLOTS_PER_EPOCH` times as large as any value measured in epochs).

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SECONDS_PER_SLOT` | `6` | seconds | 6 seconds |
| `MIN_ATTESTATION_INCLUSION_DELAY` | `2**2` (= 4) | slots | 24 seconds |
| `SLOTS_PER_EPOCH` | `2**6` (= 64) | slots | 6.4 minutes |
| `MIN_SEED_LOOKAHEAD` | `2**0` (= 1) | epochs | 6.4 minutes |
| `ACTIVATION_EXIT_DELAY` | `2**2` (= 4) | epochs | 25.6 minutes |
| `EPOCHS_PER_ETH1_VOTING_PERIOD` | `2**4` (= 16) | epochs | ~1.7 hours |
| `SLOTS_PER_HISTORICAL_ROOT` | `2**13` (= 8,192) | slots | ~13 hours |
| `MIN_VALIDATOR_WITHDRAWABILITY_DELAY` | `2**8` (= 256) | epochs | ~27 hours |
| `PERSISTENT_COMMITTEE_PERIOD` | `2**11` (= 2,048)  | epochs | 9 days  |
| `MAX_CROSSLINK_EPOCHS` | `2**6` (= 64) | epochs | ~7 hours |

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
| `INACTIVITY_PENALTY_QUOTIENT` | `2**24` (= 16,777,216) |
| `MIN_PENALTY_QUOTIENT` | `2**5` (= 32) |

* The `BASE_REWARD_QUOTIENT` parameter dictates the per-epoch reward. It corresponds to ~2.54% annual interest assuming 10 million participating ETH in every epoch.
* The `INACTIVITY_PENALTY_QUOTIENT` equals `INVERSE_SQRT_E_DROP_TIME**2` where `INVERSE_SQRT_E_DROP_TIME := 2**12 epochs` (~18 days) is the time it takes the inactivity penalty to reduce the balance of non-participating [validators](#dfn-validator) to about `1/sqrt(e) ~= 60.6%`. Indeed, the balance retained by offline [validators](#dfn-validator) after `n` epochs is about `(1 - 1/INACTIVITY_PENALTY_QUOTIENT)**(n**2/2)` so after `INVERSE_SQRT_E_DROP_TIME` epochs it is roughly `(1 - 1/INACTIVITY_PENALTY_QUOTIENT)**(INACTIVITY_PENALTY_QUOTIENT/2) ~= 1/sqrt(e)`.

### Max operations per block

| Name | Value |
| - | - |
| `MAX_PROPOSER_SLASHINGS` | `2**4` (= 16) |
| `MAX_ATTESTER_SLASHINGS` | `2**0` (= 1) |
| `MAX_ATTESTATIONS` | `2**7` (= 128) |
| `MAX_DEPOSITS` | `2**4` (= 16) |
| `MAX_VOLUNTARY_EXITS` | `2**4` (= 16) |
| `MAX_TRANSFERS` | `2**4` (= 16) |

### Signature domains

| Name | Value |
| - | - |
| `DOMAIN_BEACON_BLOCK` | `0` |
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
    # Shard data since the previous crosslink
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

#### `Eth1DataVote`

```python
{
    # Data being voted for
    'eth1_data': Eth1Data,
    # Vote count
    'vote_count': 'uint64',
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
    'previous_crosslink': Crosslink,
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
    'aggregate_signature': 'bytes96',
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
    'proof_of_possession': 'bytes96',
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
    # Rounded balance
    'high_balance': 'uint64'
}
```

#### `PendingAttestation`

```python
{
    # Attester aggregation bitfield
    'aggregation_bitfield': 'bytes',
    # Attestation data
    'data': AttestationData,
    # Custody bitfield
    'custody_bitfield': 'bytes',
    # Inclusion slot
    'inclusion_slot': 'uint64',
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
    'aggregate_signature': 'bytes96',
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
    
    # Exit queue
    'exit_epoch': 'uint64',
    'exit_queue_filled': 'uint64',

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
    'latest_crosslinks': [Crosslink, SHARD_COUNT],
    'latest_block_roots': ['bytes32', SLOTS_PER_HISTORICAL_ROOT],
    'latest_state_roots': ['bytes32', SLOTS_PER_HISTORICAL_ROOT],
    'latest_active_index_roots': ['bytes32', LATEST_ACTIVE_INDEX_ROOTS_LENGTH],
    'latest_slashed_balances': ['uint64', LATEST_SLASHED_EXIT_LENGTH],  # Balances slashed at every withdrawal period
    'latest_block_header': BeaconBlockHeader,  # `latest_block_header.state_root == ZERO_HASH` temporarily
    'historical_roots': ['bytes32'],

    # Ethereum 1.0 chain data
    'latest_eth1_data': Eth1Data,
    'eth1_data_votes': [Eth1DataVote],
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

### `get_temporary_block_header`

```python
def get_temporary_block_header(block: BeaconBlock) -> BeaconBlockHeader:
    """
    Return the block header corresponding to a block with ``state_root`` set to ``ZERO_HASH``. 
    """
    return BeaconBlockHeader(
        slot=block.slot,
        previous_block_root=block.previous_block_root,
        state_root=ZERO_HASH,
        block_body_root=hash_tree_root(block.body),
        # signing_root(block) is used for block id purposes so signature is a stub
        signature=EMPTY_SIGNATURE,
    )
```

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
    """
    return get_current_epoch(state) - 1
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
    return (
        validator.activation_epoch <= epoch < validator.withdrawable_epoch and
        validator.slashed is False
    )
```

### `get_active_validator_indices`

```python
def get_active_validator_indices(validators: List[Validator], epoch: Epoch) -> List[ValidatorIndex]:
    """
    Get indices of active validators from ``validators``.
    """
    return [i for i, v in enumerate(validators) if is_active_validator(v, epoch)]
```

### `get_balance`

```python
def get_balance(state: BeaconState, index: ValidatorIndex) -> Gwei:
    """
    Return the balance for a validator with the given ``index``.
    """
    return state.balances[index]
```

### `set_balance`

```python
def set_balance(state: BeaconState, index: ValidatorIndex, balance: Gwei) -> None:
    """
    Set the balance for a validator with the given ``index`` in both ``BeaconState``
    and validator's rounded balance ``high_balance``.
    """
    validator = state.validator_registry[index]
    HALF_INCREMENT = HIGH_BALANCE_INCREMENT // 2
    if validator.high_balance > balance or validator.high_balance + 3 * HALF_INCREMENT < balance:
        validator.high_balance = balance - balance % HIGH_BALANCE_INCREMENT
    state.balances[index] = balance
```

### `increase_balance`

```python
def increase_balance(state: BeaconState, index: ValidatorIndex, delta: Gwei) -> None:
    """
    Increase the balance for a validator with the given ``index`` by ``delta``.
    """
    set_balance(state, index, get_balance(state, index) + delta)
```

### `decrease_balance`

```python
def decrease_balance(state: BeaconState, index: ValidatorIndex, delta: Gwei) -> None:
    """
    Decrease the balance for a validator with the given ``index`` by ``delta``.
    Set to ``0`` when underflow.
    """
    current_balance = get_balance(state, index)
    set_balance(state, index, current_balance - delta if current_balance >= delta else 0)
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
    Return the number of committees in one epoch.
    """
    active_validators = get_active_validator_indices(state.validator_registry, epoch)
    return max(
        1,
        min(
            SHARD_COUNT // SLOTS_PER_EPOCH,
            len(active_validators) // SLOTS_PER_EPOCH // TARGET_COMMITTEE_SIZE,
        )
    ) * SLOTS_PER_EPOCH
```

### `get_shard_delta`

```python
def get_shard_delta(state: BeaconState, epoch: Epoch) -> int:
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

**Note**: this definition and the next few definitions are highly inefficient as algorithms, as they re-calculate many sub-expressions. Production implementations are expected to appropriately use caching/memoization to avoid redoing work.

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
    indices = get_active_validator_indices(
        state.validator_registry,
        epoch,
    )

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

### `get_block_root`

```python
def get_block_root(state: BeaconState,
                   slot: Slot) -> Bytes32:
    """
    Return the block root at a recent ``slot``.
    """
    assert slot < state.slot <= slot + SLOTS_PER_HISTORICAL_ROOT
    return state.latest_block_roots[slot % SLOTS_PER_HISTORICAL_ROOT]
```

`get_block_root(_, s)` should always return `hash_tree_root` of the block in the beacon chain at slot `s`, and `get_crosslink_committees_at_slot(_, s)` should not change unless the [validator](#dfn-validator) registry changes.

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
def get_beacon_proposer_index(state: BeaconState,
                              slot: Slot) -> ValidatorIndex:
    """
    Return the beacon proposer index for the ``slot``.
    Due to proposer selection being based upon the validator balances during
    the epoch in question, this can only be run for the current epoch.
    """
    current_epoch = get_current_epoch(state)
    assert slot_to_epoch(slot) == current_epoch

    first_committee, _ = get_crosslink_committees_at_slot(state, slot)[0]
    i = 0
    while True:
        rand_byte = hash(
            generate_seed(state, current_epoch) +
            int_to_bytes8(i // 32)
        )[i % 32]
        candidate = first_committee[(current_epoch + i) % len(first_committee)]
        if get_effective_balance(state, candidate) * 256 > MAX_DEPOSIT_AMOUNT * rand_byte:
            return candidate
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

### `get_crosslink_committee_for_attestation`

```python
def get_crosslink_committee_for_attestation(state: BeaconState,
                                            attestation_data: AttestationData) -> List[ValidatorIndex]:
    """
    Return the crosslink committee corresponding to ``attestation_data``.
    """
    crosslink_committees = get_crosslink_committees_at_slot(state, attestation_data.slot)

    # Find the committee in the list with the desired shard
    assert attestation_data.shard in [shard for _, shard in crosslink_committees]
    crosslink_committee = [committee for committee, shard in crosslink_committees if shard == attestation_data.shard][0]

    return crosslink_committee
```

### `get_attestation_participants`

```python
def get_attestation_participants(state: BeaconState,
                                 attestation_data: AttestationData,
                                 bitfield: bytes) -> List[ValidatorIndex]:
    """
    Return the sorted participant indices corresponding to ``attestation_data`` and ``bitfield``.
    """
    crosslink_committee = get_crosslink_committee_for_attestation(state, attestation_data)

    assert verify_bitfield(bitfield, len(crosslink_committee))

    # Find the participating attesters in the committee
    participants = []
    for i, validator_index in enumerate(crosslink_committee):
        aggregation_bit = get_bitfield_bit(bitfield, i)
        if aggregation_bit == 0b1:
            participants.append(validator_index)
    return sorted(participants)
```

### `int_to_bytes1`, `int_to_bytes2`, ...

`int_to_bytes1(x): return x.to_bytes(1, 'little')`, `int_to_bytes2(x): return x.to_bytes(2, 'little')`, and so on for all integers, particularly 1, 2, 3, 4, 8, 32, 48, 96.

### `bytes_to_int`

```python
def bytes_to_int(data: bytes) -> int:
    return int.from_bytes(data, 'little')
```

### `get_effective_balance`

```python
def get_effective_balance(state: BeaconState, index: ValidatorIndex) -> Gwei:
    """
    Return the effective balance (also known as "balance at stake") for a validator with the given ``index``.
    """
    return min(get_balance(state, index), MAX_DEPOSIT_AMOUNT)
```

### `get_total_balance`

```python
def get_total_balance(state: BeaconState, validators: List[ValidatorIndex]) -> Gwei:
    """
    Return the combined effective balance of an array of ``validators``.
    """
    return sum([get_effective_balance(state, i) for i in validators])
```

### `get_fork_version`

```python
def get_fork_version(fork: Fork,
                     epoch: Epoch) -> bytes:
    """
    Return the fork version of the given ``epoch``.
    """
    if epoch < fork.epoch:
        return fork.previous_version
    else:
        return fork.current_version
```

### `get_domain`

```python
def get_domain(fork: Fork,
               epoch: Epoch,
               domain_type: int) -> int:
    """
    Get the domain number that represents the fork meta and signature domain.
    """
    return bytes_to_int(get_fork_version(fork, epoch) + int_to_bytes4(domain_type))
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
    attesting_indices = get_attestation_participants(state, attestation.data, attestation.aggregation_bitfield)
    custody_bit_1_indices = get_attestation_participants(state, attestation.data, attestation.custody_bitfield)
    custody_bit_0_indices = [index for index in attesting_indices if index not in custody_bit_1_indices]

    return IndexedAttestation(
        custody_bit_0_indices=custody_bit_0_indices,
        custody_bit_1_indices=custody_bit_1_indices,
        data=attestation.data,
        aggregate_signature=attestation.aggregate_signature,
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

    # ensure no duplicate indices across custody bits
    assert len(set(custody_bit_0_indices).intersection(set(custody_bit_1_indices))) == 0

    if len(custody_bit_1_indices) > 0:  # [TO BE REMOVED IN PHASE 1]
        return False

    total_attesting_indices = len(custody_bit_0_indices) + len(custody_bit_1_indices)
    if not (1 <= total_attesting_indices <= MAX_ATTESTATION_PARTICIPANTS):
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
        signature=indexed_attestation.aggregate_signature,
        domain=get_domain(state.fork, slot_to_epoch(indexed_attestation.data.slot), DOMAIN_ATTESTATION),
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

### `bls_verify`

`bls_verify` is a function for verifying a BLS signature, defined in the [BLS Signature spec](../bls_signature.md#bls_verify).

### `bls_verify_multiple`

`bls_verify_multiple` is a function for verifying a BLS signature constructed from multiple messages, defined in the [BLS Signature spec](../bls_signature.md#bls_verify_multiple).

### `bls_aggregate_pubkeys`

`bls_aggregate_pubkeys` is a function for aggregating multiple BLS public keys into a single aggregate key, defined in the [BLS Signature spec](../bls_signature.md#bls_aggregate_pubkeys).

### Routines for updating validator status

Note: All functions in this section mutate `state`.

#### `activate_validator`

```python
def activate_validator(state: BeaconState, index: ValidatorIndex, is_genesis: bool) -> None:
    """
    Activate the validator of the given ``index``.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[index]

    if is_genesis:
        validator.activation_eligibility_epoch = GENESIS_EPOCH
        validator.activation_epoch = GENESIS_EPOCH
    else:
        validator.activation_epoch = get_delayed_activation_exit_epoch(get_current_epoch(state))
```

#### `initiate_validator_exit`

```python
def initiate_validator_exit(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Initiate the validator of the given ``index``.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[index]
    # Operation is a no-op if validator is already in the queue
    if validator.exit_epoch == FAR_FUTURE_EPOCH:
        # Update exit queue counters
        delayed_activation_exit_epoch = get_delayed_activation_exit_epoch(get_current_epoch(state))
        if state.exit_epoch < delayed_activation_exit_epoch:
            state.exit_epoch = delayed_activation_exit_epoch

        if state.exit_queue_filled >= MAX_EXITS_PER_EPOCH:
            state.exit_epoch += 1
            state.exit_queue_filled = 0

        # Set validator exit epoch and withdrawable epoch
        validator.exit_epoch = state.exit_epoch
        validator.withdrawable_epoch = validator.exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY

        # Extend queue
        state.exit_queue_filled += 1
```

#### `slash_validator`

```python
def slash_validator(state: BeaconState, slashed_index: ValidatorIndex, whistleblower_index: ValidatorIndex=None) -> None:
    """
    Slash the validator with index ``slashed_index``.
    Note that this function mutates ``state``.
    """
    initiate_validator_exit(state, slashed_index)
    state.validator_registry[slashed_index].slashed = True
    state.validator_registry[slashed_index].withdrawable_epoch = get_current_epoch(state) + LATEST_SLASHED_EXIT_LENGTH
    slashed_balance = get_effective_balance(state, slashed_index)
    state.latest_slashed_balances[get_current_epoch(state) % LATEST_SLASHED_EXIT_LENGTH] += slashed_balance

    proposer_index = get_beacon_proposer_index(state, state.slot)
    if whistleblower_index is None:
        whistleblower_index = proposer_index
    whistleblowing_reward = slashed_balance // WHISTLEBLOWING_REWARD_QUOTIENT
    proposer_reward = whistleblowing_reward // PROPOSER_REWARD_QUOTIENT
    increase_balance(state, proposer_index, proposer_reward)
    increase_balance(state, whistleblower_index, whistleblowing_reward - proposer_reward)
    decrease_balance(state, slashed_index, whistleblowing_reward)
```

## Ethereum 1.0 deposit contract

The initial deployment phases of Ethereum 2.0 are implemented without consensus changes to Ethereum 1.0. A deposit contract at address `DEPOSIT_CONTRACT_ADDRESS` is added to Ethereum 1.0 for deposits of ETH to the beacon chain. Validator balances will be withdrawable to the shards in phase 2, i.e. when the EVM2.0 is deployed and the shards have state.

### Deposit arguments

The deposit contract has a single `deposit` function which takes as argument a SimpleSerialize'd `DepositData`.

### Withdrawal credentials

One of the `DepositData` fields is `withdrawal_credentials`. It is a commitment to credentials for withdrawals to shards. The first byte of `withdrawal_credentials` is a version number. As of now the only expected format is as follows:

* `withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX_BYTE`
* `withdrawal_credentials[1:] == hash(withdrawal_pubkey)[1:]` where `withdrawal_pubkey` is a BLS pubkey

The private key corresponding to `withdrawal_pubkey` will be required to initiate a withdrawal. It can be stored separately until a withdrawal is required, e.g. in cold storage.

### `Deposit` logs

Every Ethereum 1.0 deposit, of size between `MIN_DEPOSIT_AMOUNT` and `MAX_DEPOSIT_AMOUNT`, emits a `Deposit` log for consumption by the beacon chain. The deposit contract does little validation, pushing most of the validator onboarding logic to the beacon chain. In particular, the proof of possession (a BLS12 signature) is not verified by the deposit contract.

### `Eth2Genesis` log

When a sufficient amount of full deposits have been made, the deposit contract emits the `Eth2Genesis` log. The beacon chain state may then be initialized by calling the `get_genesis_beacon_state` function (defined below) where:

* `genesis_time` equals `time` in the `Eth2Genesis` log
* `latest_eth1_data.deposit_root` equals `deposit_root` in the `Eth2Genesis` log
* `latest_eth1_data.deposit_count` equals `deposit_count` in the `Eth2Genesis` log
* `latest_eth1_data.block_hash` equals the hash of the block that included the log
* `genesis_validator_deposits` is a list of `Deposit` objects built according to the `Deposit` logs up to the deposit that triggered the `Eth2Genesis` log, processed in the order in which they were emitted (oldest to newest)

### Vyper code

The source for the Vyper contract lives in a [separate repository](https://github.com/ethereum/deposit_contract) at [https://github.com/ethereum/deposit_contract/blob/master/deposit_contract/contracts/validator_registration.v.py](https://github.com/ethereum/deposit_contract/blob/master/deposit_contract/contracts/validator_registration.v.py).

Note: to save ~10x on gas this contract uses a somewhat unintuitive progressive Merkle root calculation algo that requires only O(log(n)) storage. See https://github.com/ethereum/research/blob/master/beacon_chain_impl/progressive_merkle_tree.py for an implementation of the same algo in python tested for correctness.

For convenience, we provide the interface to the contract here:

* `__init__()`: initializes the contract
* `get_deposit_root() -> bytes32`: returns the current root of the deposit tree
* `deposit(bytes[512])`: adds a deposit instance to the deposit tree, incorporating the input argument and the value transferred in the given call. Note: the amount of value transferred *must* be within `MIN_DEPOSIT_AMOUNT` and `MAX_DEPOSIT_AMOUNT`, inclusive. Each of these constants are specified in units of Gwei.

## On genesis

When enough full deposits have been made to the deposit contract, an `Eth2Genesis` log is emitted. Construct a corresponding `genesis_state` and `genesis_block` as follows:

* Let `genesis_validator_deposits` be the list of deposits, ordered chronologically, up to and including the deposit that triggered the `Eth2Genesis` log.
* Let `genesis_time` be the timestamp specified in the `Eth2Genesis` log.
* Let `genesis_eth1_data` be the `Eth1Data` object where:
    * `genesis_eth1_data.deposit_root` is the `deposit_root` contained in the `Eth2Genesis` log.
    * `genesis_eth1_data.deposit_count` is the `deposit_count` contained in the `Eth2Genesis` log.
    * `genesis_eth1_data.block_hash` is the hash of the Ethereum 1.0 block that emitted the `Eth2Genesis` log.
* Let `genesis_state = get_genesis_beacon_state(genesis_validator_deposits, genesis_time, genesis_eth1_data)`.
* Let `genesis_block = get_empty_block()`.
* Set `genesis_block.state_root = hash_tree_root(genesis_state)`.

```python
def get_empty_block() -> BeaconBlock:
    """
    Get an empty ``BeaconBlock``.
    """
    return BeaconBlock(
        slot=GENESIS_SLOT,
        previous_block_root=ZERO_HASH,
        state_root=ZERO_HASH,
        body=BeaconBlockBody(
            randao_reveal=EMPTY_SIGNATURE,
            eth1_data=Eth1Data(
                deposit_root=ZERO_HASH,
                deposit_count=0,
                block_hash=ZERO_HASH,
            ),
            proposer_slashings=[],
            attester_slashings=[],
            attestations=[],
            deposits=[],
            voluntary_exits=[],
            transfers=[],
        ),
        signature=EMPTY_SIGNATURE,
    )
```

```python
def get_genesis_beacon_state(genesis_validator_deposits: List[Deposit],
                             genesis_time: int,
                             genesis_eth1_data: Eth1Data) -> BeaconState:
    """
    Get the genesis ``BeaconState``.
    """
    state = BeaconState(
        # Misc
        slot=GENESIS_SLOT,
        genesis_time=genesis_time,
        fork=Fork(
            previous_version=GENESIS_FORK_VERSION,
            current_version=GENESIS_FORK_VERSION,
            epoch=GENESIS_EPOCH,
        ),

        # Validator registry
        validator_registry=[],
        balances=[],

        # Randomness and committees
        latest_randao_mixes=Vector([ZERO_HASH for _ in range(LATEST_RANDAO_MIXES_LENGTH)]),
        latest_start_shard=GENESIS_START_SHARD,

        # Exit queue
        exit_epoch=GENESIS_EPOCH,
        exit_queue_filled=0,

        # Finality
        previous_epoch_attestations=[],
        current_epoch_attestations=[],
        previous_justified_epoch=GENESIS_EPOCH - 1,
        current_justified_epoch=GENESIS_EPOCH,
        previous_justified_root=ZERO_HASH,
        current_justified_root=ZERO_HASH,
        justification_bitfield=0,
        finalized_epoch=GENESIS_EPOCH,
        finalized_root=ZERO_HASH,

        # Recent state
        latest_crosslinks=Vector([Crosslink(epoch=GENESIS_EPOCH, crosslink_data_root=ZERO_HASH) for _ in range(SHARD_COUNT)]),
        latest_block_roots=Vector([ZERO_HASH for _ in range(SLOTS_PER_HISTORICAL_ROOT)]),
        latest_state_roots=Vector([ZERO_HASH for _ in range(SLOTS_PER_HISTORICAL_ROOT)]),
        latest_active_index_roots=Vector([ZERO_HASH for _ in range(LATEST_ACTIVE_INDEX_ROOTS_LENGTH)]),
        latest_slashed_balances=Vector([0 for _ in range(LATEST_SLASHED_EXIT_LENGTH)]),
        latest_block_header=get_temporary_block_header(get_empty_block()),
        historical_roots=[],

        # Ethereum 1.0 chain data
        latest_eth1_data=genesis_eth1_data,
        eth1_data_votes=[],
        deposit_index=0,
    )

    # Process genesis deposits
    for deposit in genesis_validator_deposits:
        process_deposit(state, deposit)

    # Process genesis activations
    for validator_index in range(len(state.validator_registry)):
        if get_effective_balance(state, validator_index) >= MAX_DEPOSIT_AMOUNT:
            activate_validator(state, validator_index, is_genesis=True)

    genesis_active_index_root = hash_tree_root(get_active_validator_indices(state.validator_registry, GENESIS_EPOCH))
    for index in range(LATEST_ACTIVE_INDEX_ROOTS_LENGTH):
        state.latest_active_index_roots[index] = genesis_active_index_root

    return state
```

## Beacon chain processing

The beacon chain is the system chain for Ethereum 2.0. The main responsibilities of the beacon chain are as follows:

* Store and maintain the registry of [validators](#dfn-validator)
* Process crosslinks (see above)
* Process its per-block consensus, as well as the finality gadget

Processing the beacon chain is similar to processing the Ethereum 1.0 chain. Clients download and process blocks and maintain a view of what is the current "canonical chain", terminating at the current "head". However, because of the beacon chain's relationship with Ethereum 1.0, and because it is a proof-of-stake chain, there are differences.

For a beacon chain block, `block`, to be processed by a node, the following conditions must be met:

* The parent block with root `block.previous_block_root` has been processed and accepted.
* An Ethereum 1.0 block pointed to by the `state.latest_eth1_data.block_hash` has been processed and accepted.
* The node's Unix time is greater than or equal to `state.genesis_time + (block.slot - GENESIS_SLOT) * SECONDS_PER_SLOT`. (Note that leap seconds mean that slots will occasionally last `SECONDS_PER_SLOT + 1` or `SECONDS_PER_SLOT - 1` seconds, possibly several times a year.)

If these conditions are not met, the client should delay processing the beacon block until the conditions are all satisfied.

Beacon block production is significantly different because of the proof-of-stake mechanism. A client simply checks what it thinks is the canonical chain when it should create a block and looks up what its slot number is; when the slot arrives, it either proposes or attests to a block as required. Note that this requires each node to have a clock that is roughly (i.e. within `SECONDS_PER_SLOT` seconds) synchronized with the other nodes.

### Beacon chain fork choice rule

The beacon chain fork choice rule is a hybrid that combines justification and finality with Latest Message Driven (LMD) Greediest Heaviest Observed SubTree (GHOST). At any point in time a [validator](#dfn-validator) `v` subjectively calculates the beacon chain head as follows.

* Abstractly define `Store` as the type of storage object for the chain data and `store` be the set of attestations and blocks that the [validator](#dfn-validator) `v` has observed and verified (in particular, block ancestors must be recursively verified). Attestations not yet included in any chain are still included in `store`.
* Let `finalized_head` be the finalized block with the highest epoch. (A block `B` is finalized if there is a descendant of `B` in `store` the processing of which sets `B` as finalized.)
* Let `justified_head` be the descendant of `finalized_head` with the highest epoch that has been justified for at least 1 epoch. (A block `B` is justified if there is a descendant of `B` in `store` the processing of which sets `B` as justified.) If no such descendant exists set `justified_head` to `finalized_head`.
* Let `get_ancestor(store: Store, block: BeaconBlock, slot: Slot) -> BeaconBlock` be the ancestor of `block` with slot number `slot`. The `get_ancestor` function can be defined recursively as:

```python
def get_ancestor(store: Store, block: BeaconBlock, slot: Slot) -> BeaconBlock:
    """
    Get the ancestor of ``block`` with slot number ``slot``; return ``None`` if not found.
    """
    if block.slot == slot:
        return block
    elif block.slot < slot:
        return None
    else:
        return get_ancestor(store, store.get_parent(block), slot)
```

* Let `get_latest_attestation(store: Store, validator_index: ValidatorIndex) -> Attestation` be the attestation with the highest slot number in `store` from the validator with the given `validator_index`. If several such attestations exist, use the one the [validator](#dfn-validator) `v` observed first.
* Let `get_latest_attestation_target(store: Store, validator_index: ValidatorIndex) -> BeaconBlock` be the target block in the attestation `get_latest_attestation(store, validator_index)`.
* Let `get_children(store: Store, block: BeaconBlock) -> List[BeaconBlock]` returns the child blocks of the given `block`.
* Let `justified_head_state` be the resulting `BeaconState` object from processing the chain up to the `justified_head`.
* The `head` is `lmd_ghost(store, justified_head_state, justified_head)` where the function `lmd_ghost` is defined below. Note that the implementation below is suboptimal; there are implementations that compute the head in time logarithmic in slot count.

```python
def lmd_ghost(store: Store, start_state: BeaconState, start_block: BeaconBlock) -> BeaconBlock:
    """
    Execute the LMD-GHOST algorithm to find the head ``BeaconBlock``.
    """
    validators = start_state.validator_registry
    active_validator_indices = get_active_validator_indices(validators, slot_to_epoch(start_state.slot))
    attestation_targets = [
        (validator_index, get_latest_attestation_target(store, validator_index))
        for validator_index in active_validator_indices
    ]

    # Use the rounded-balance-with-hysteresis supplied by the protocol for fork
    # choice voting. This reduces the number of recomputations that need to be
    # made for optimized implementations that precompute and save data
    def get_vote_count(block: BeaconBlock) -> int:
        return sum(
            start_state.validator_registry[validator_index].high_balance
            for validator_index, target in attestation_targets
            if get_ancestor(store, target, block.slot) == block
        )

    head = start_block
    while 1:
        children = get_children(store, head)
        if len(children) == 0:
            return head
        # Ties broken by favoring block with lexicographically higher root
        head = max(children, key=lambda x: (get_vote_count(x), hash_tree_root(x)))
```

## Beacon chain state transition function

We now define the state transition function. At a high level, the state transition is made up of four parts:

1. State caching, which happens at the start of every slot.
2. The per-epoch transitions, which happens at the start of the first slot of every epoch.
3. The per-slot transitions, which happens at every slot.
4. The per-block transitions, which happens at every block.

Transition section notes:
* The state caching caches the state root of the previous slot and updates block and state roots records.
* The per-epoch transitions focus on the [validator](#dfn-validator) registry, including adjusting balances and activating and exiting [validators](#dfn-validator), as well as processing crosslinks and managing block justification/finalization.
* The per-slot transitions focus on the slot counter.
* The per-block transitions generally focus on verifying aggregate signatures and saving temporary records relating to the per-block activity in the `BeaconState`.

Beacon blocks that trigger unhandled Python exceptions (e.g. out-of-range list accesses) and failed `assert`s during the state transition are considered invalid.

_Note_: If there are skipped slots between a block and its parent block, run the steps in the [state-root](#state-caching), [per-epoch](#per-epoch-processing), and [per-slot](#per-slot-processing) sections once for each skipped slot and then once for the slot containing the new block.

### State caching

At every `slot > GENESIS_SLOT` run the following function:

```python
def cache_state(state: BeaconState) -> None:
    previous_slot_state_root = hash_tree_root(state)

    # store the previous slot's post state transition root
    state.latest_state_roots[state.slot % SLOTS_PER_HISTORICAL_ROOT] = previous_slot_state_root

    # cache state root in stored latest_block_header if empty
    if state.latest_block_header.state_root == ZERO_HASH:
        state.latest_block_header.state_root = previous_slot_state_root

    # store latest known block for previous slot
    state.latest_block_roots[state.slot % SLOTS_PER_HISTORICAL_ROOT] = signing_root(state.latest_block_header)
```

### Per-epoch processing

The steps below happen when `state.slot > GENESIS_SLOT and (state.slot + 1) % SLOTS_PER_EPOCH == 0`.

#### Helper functions

We define some helper functions utilized when processing an epoch transition:

```python
def get_current_total_balance(state: BeaconState) -> Gwei:
    return get_total_balance(state, get_active_validator_indices(state.validator_registry, get_current_epoch(state)))
```

```python
def get_previous_total_balance(state: BeaconState) -> Gwei:
    return get_total_balance(state, get_active_validator_indices(state.validator_registry, get_previous_epoch(state)))
```

```python
def get_unslashed_attesting_indices(state: BeaconState, attestations: List[PendingAttestation]) -> List[ValidatorIndex]:
    output = set()
    for a in attestations:
        output = output.union(get_attestation_participants(state, a.data, a.aggregation_bitfield))
    return sorted(filter(lambda index: not state.validator_registry[index].slashed, list(output)))
```

```python
def get_attesting_balance(state: BeaconState, attestations: List[PendingAttestation]) -> Gwei:
    return get_total_balance(state, get_unslashed_attesting_indices(state, attestations))
```

```python
def get_current_epoch_boundary_attestations(state: BeaconState) -> List[PendingAttestation]:
    return [
        a for a in state.current_epoch_attestations
        if a.data.target_root == get_block_root(state, get_epoch_start_slot(get_current_epoch(state)))
    ]
```

```python
def get_previous_epoch_boundary_attestations(state: BeaconState) -> List[PendingAttestation]:
    return [
        a for a in state.previous_epoch_attestations
        if a.data.target_root == get_block_root(state, get_epoch_start_slot(get_previous_epoch(state)))
    ]
```

```python
def get_previous_epoch_matching_head_attestations(state: BeaconState) -> List[PendingAttestation]:
    return [
        a for a in state.previous_epoch_attestations
        if a.data.beacon_block_root == get_block_root(state, a.data.slot)
    ]
```

**Note**: Total balances computed for the previous epoch might be marginally different than the actual total balances during the previous epoch transition. Due to the tight bound on validator churn each epoch and small per-epoch rewards/penalties, the potential balance difference is very low and only marginally affects consensus safety.

```python
def get_winning_root_and_participants(state: BeaconState, shard: Shard) -> Tuple[Bytes32, List[ValidatorIndex]]:
    all_attestations = state.current_epoch_attestations + state.previous_epoch_attestations
    valid_attestations = [
        a for a in all_attestations if a.data.previous_crosslink == state.latest_crosslinks[shard]
    ]
    all_roots = [a.data.crosslink_data_root for a in valid_attestations]

    # handle when no attestations for shard available
    if len(all_roots) == 0:
        return ZERO_HASH, []

    def get_attestations_for(root) -> List[PendingAttestation]:
        return [a for a in valid_attestations if a.data.crosslink_data_root == root]

    # Winning crosslink root is the root with the most votes for it, ties broken in favor of
    # lexicographically higher hash
    winning_root = max(all_roots, key=lambda r: (get_attesting_balance(state, get_attestations_for(r)), r))

    return winning_root, get_unslashed_attesting_indices(state, get_attestations_for(winning_root))
```

```python
def earliest_attestation(state: BeaconState, validator_index: ValidatorIndex) -> PendingAttestation:
    return min([
        a for a in state.previous_epoch_attestations if
        validator_index in get_attestation_participants(state, a.data, a.aggregation_bitfield)
    ], key=lambda a: a.inclusion_slot)
```

```python
def inclusion_slot(state: BeaconState, validator_index: ValidatorIndex) -> Slot:
    return earliest_attestation(state, validator_index).inclusion_slot
```

```python
def inclusion_distance(state: BeaconState, validator_index: ValidatorIndex) -> int:
    attestation = earliest_attestation(state, validator_index)
    return attestation.inclusion_slot - attestation.data.slot
```

#### Justification

Run the following function:

```python
def update_justification_and_finalization(state: BeaconState) -> None:
    new_justified_epoch = state.current_justified_epoch
    new_finalized_epoch = state.finalized_epoch

    # Rotate the justification bitfield up one epoch to make room for the current epoch (and limit to 64 bits)
    state.justification_bitfield = (state.justification_bitfield << 1) % 2**64
    # If the previous epoch gets justified, fill the second last bit
    previous_boundary_attesting_balance = get_attesting_balance(state, get_previous_epoch_boundary_attestations(state))
    if previous_boundary_attesting_balance * 3 >= get_previous_total_balance(state) * 2:
        new_justified_epoch = get_current_epoch(state) - 1
        state.justification_bitfield |= 2
    # If the current epoch gets justified, fill the last bit
    current_boundary_attesting_balance = get_attesting_balance(state, get_current_epoch_boundary_attestations(state))
    if current_boundary_attesting_balance * 3 >= get_current_total_balance(state) * 2:
        new_justified_epoch = get_current_epoch(state)
        state.justification_bitfield |= 1

    # Process finalizations
    bitfield = state.justification_bitfield
    current_epoch = get_current_epoch(state)
    # The 2nd/3rd/4th most recent epochs are all justified, the 2nd using the 4th as source
    if (bitfield >> 1) % 8 == 0b111 and state.previous_justified_epoch == current_epoch - 3:
        new_finalized_epoch = state.previous_justified_epoch
    # The 2nd/3rd most recent epochs are both justified, the 2nd using the 3rd as source
    if (bitfield >> 1) % 4 == 0b11 and state.previous_justified_epoch == current_epoch - 2:
        new_finalized_epoch = state.previous_justified_epoch
    # The 1st/2nd/3rd most recent epochs are all justified, the 1st using the 3rd as source
    if (bitfield >> 0) % 8 == 0b111 and state.current_justified_epoch == current_epoch - 2:
        new_finalized_epoch = state.current_justified_epoch
    # The 1st/2nd most recent epochs are both justified, the 1st using the 2nd as source
    if (bitfield >> 0) % 4 == 0b11 and state.current_justified_epoch == current_epoch - 1:
        new_finalized_epoch = state.current_justified_epoch

    # Update state jusification/finality fields
    state.previous_justified_epoch = state.current_justified_epoch
    state.previous_justified_root = state.current_justified_root
    if new_justified_epoch != state.current_justified_epoch:
        state.current_justified_epoch = new_justified_epoch
        state.current_justified_root = get_block_root(state, get_epoch_start_slot(new_justified_epoch))
    if new_finalized_epoch != state.finalized_epoch:
        state.finalized_epoch = new_finalized_epoch
        state.finalized_root = get_block_root(state, get_epoch_start_slot(new_finalized_epoch))
```

#### Crosslinks

Run the following function:

```python
def process_crosslinks(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    previous_epoch = max(current_epoch - 1, GENESIS_EPOCH)
    next_epoch = current_epoch + 1
    for slot in range(get_epoch_start_slot(previous_epoch), get_epoch_start_slot(next_epoch)):
        for crosslink_committee, shard in get_crosslink_committees_at_slot(state, slot):
            winning_root, participants = get_winning_root_and_participants(state, shard)
            participating_balance = get_total_balance(state, participants)
            total_balance = get_total_balance(state, crosslink_committee)
            if 3 * participating_balance >= 2 * total_balance:
                state.latest_crosslinks[shard] = Crosslink(
                    epoch=min(slot_to_epoch(slot), state.latest_crosslinks[shard].epoch + MAX_CROSSLINK_EPOCHS),
                    crosslink_data_root=winning_root
                )
```

#### Eth1 data

Run the following function:

```python
def maybe_reset_eth1_period(state: BeaconState) -> None:
    if (get_current_epoch(state) + 1) % EPOCHS_PER_ETH1_VOTING_PERIOD == 0:
        for eth1_data_vote in state.eth1_data_votes:
            # If a majority of all votes were for a particular eth1_data value,
            # then set that as the new canonical value
            if eth1_data_vote.vote_count * 2 > EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH:
                state.latest_eth1_data = eth1_data_vote.eth1_data
        state.eth1_data_votes = []
```

#### Rewards and penalties

First, we define some additional helpers:

```python
def get_base_reward(state: BeaconState, index: ValidatorIndex) -> Gwei:
    if get_previous_total_balance(state) == 0:
        return 0

    adjusted_quotient = integer_squareroot(get_previous_total_balance(state)) // BASE_REWARD_QUOTIENT
    return get_effective_balance(state, index) // adjusted_quotient // 5
```

```python
def get_inactivity_penalty(state: BeaconState, index: ValidatorIndex, epochs_since_finality: int) -> Gwei:
    if epochs_since_finality <= 4:
        extra_penalty = 0
    else:
        extra_penalty = get_effective_balance(state, index) * epochs_since_finality // INACTIVITY_PENALTY_QUOTIENT // 2
    return get_base_reward(state, index) + extra_penalty
```

Note: When applying penalties in the following balance recalculations, implementers should make sure the `uint64` does not underflow.

##### Justification and finalization

```python
def get_justification_and_finalization_deltas(state: BeaconState) -> Tuple[List[Gwei], List[Gwei]]:
    current_epoch = get_current_epoch(state)
    epochs_since_finality = current_epoch + 1 - state.finalized_epoch
    rewards = [0 for index in range(len(state.validator_registry))]
    penalties = [0 for index in range(len(state.validator_registry))]
    # Some helper variables
    boundary_attestations = get_previous_epoch_boundary_attestations(state)
    boundary_attesting_balance = get_attesting_balance(state, boundary_attestations)
    total_balance = get_previous_total_balance(state)
    total_attesting_balance = get_attesting_balance(state, state.previous_epoch_attestations)
    matching_head_attestations = get_previous_epoch_matching_head_attestations(state)
    matching_head_balance = get_attesting_balance(state, matching_head_attestations)
    eligible_validators = [
        index for index, validator in enumerate(state.validator_registry)
        if (
            is_active_validator(validator, current_epoch) or
            (validator.slashed and current_epoch < validator.withdrawable_epoch)
        )
    ]
    # Process rewards or penalties for all validators
    for index in eligible_validators:
        base_reward = get_base_reward(state, index)
        # Expected FFG source
        if index in get_unslashed_attesting_indices(state, state.previous_epoch_attestations):
            rewards[index] += base_reward * total_attesting_balance // total_balance
            # Inclusion speed bonus
            rewards[index] += (
                base_reward * MIN_ATTESTATION_INCLUSION_DELAY //
                inclusion_distance(state, index)
            )
        else:
            penalties[index] += base_reward
        # Expected FFG target
        if index in get_unslashed_attesting_indices(state, boundary_attestations):
            rewards[index] += base_reward * boundary_attesting_balance // total_balance
        else:
            penalties[index] += get_inactivity_penalty(state, index, epochs_since_finality)
        # Expected head
        if index in get_unslashed_attesting_indices(state, matching_head_attestations):
            rewards[index] += base_reward * matching_head_balance // total_balance
        else:
            penalties[index] += base_reward
        # Proposer bonus
        if index in get_unslashed_attesting_indices(state, state.previous_epoch_attestations):
            proposer_index = get_beacon_proposer_index(state, inclusion_slot(state, index))
            rewards[proposer_index] += base_reward // PROPOSER_REWARD_QUOTIENT
        # Take away max rewards if we're not finalizing
        if epochs_since_finality > 4:
            penalties[index] += base_reward * 4
    return [rewards, penalties]
```

##### Crosslinks

```python
def get_crosslink_deltas(state: BeaconState) -> Tuple[List[Gwei], List[Gwei]]:
    rewards = [0 for index in range(len(state.validator_registry))]
    penalties = [0 for index in range(len(state.validator_registry))]
    previous_epoch_start_slot = get_epoch_start_slot(get_previous_epoch(state))
    current_epoch_start_slot = get_epoch_start_slot(get_current_epoch(state))
    for slot in range(previous_epoch_start_slot, current_epoch_start_slot):
        for crosslink_committee, shard in get_crosslink_committees_at_slot(state, slot):
            winning_root, participants = get_winning_root_and_participants(state, shard)
            participating_balance = get_total_balance(state, participants)
            total_balance = get_total_balance(state, crosslink_committee)
            for index in crosslink_committee:
                if index in participants:
                    rewards[index] += get_base_reward(state, index) * participating_balance // total_balance
                else:
                    penalties[index] += get_base_reward(state, index)
    return [rewards, penalties]
```

#### Apply rewards

Run the following:

```python
def apply_rewards(state: BeaconState) -> None:
    rewards1, penalties1 = get_justification_and_finalization_deltas(state)
    rewards2, penalties2 = get_crosslink_deltas(state)
    for i in range(len(state.validator_registry)):
        set_balance(
            state,
            i,
            max(
                0,
                get_balance(state, i) + rewards1[i] + rewards2[i] - penalties1[i] - penalties2[i],
            ),
        )
```

#### Balance-driven status transitions

Run `process_balance_driven_status_transitions(state)`.

```python
def process_balance_driven_status_transitions(state: BeaconState) -> None:
    """
    Iterate through the validator registry
    and deposit or eject active validators with sufficiently high or low balances
    """
    for index, validator in enumerate(state.validator_registry):
        balance = get_balance(state, index)
        if validator.activation_eligibility_epoch == FAR_FUTURE_EPOCH and balance >= MAX_DEPOSIT_AMOUNT:
            state.activation_eligibility_epoch = get_current_epoch(state)

        if is_active_validator(validator, get_current_epoch(state)) and balance < EJECTION_BALANCE:
            initiate_validator_exit(state, index)
```

#### Activation queue and start shard

Run the following function:

```python
def update_registry(state: BeaconState) -> None:
    activation_queue = sorted([
        validator for validator in state.validator_registry if
        validator.activation_eligibility_epoch != FAR_FUTURE_EPOCH and
        validator.activation_epoch >= get_delayed_activation_exit_epoch(state.finalized_epoch)
    ], key=lambda index: state.validator_registry[index].activation_eligibility_epoch)

    for index in activation_queue[:MAX_ACTIVATIONS_PER_FINALIZED_EPOCH]:
        activate_validator(state, index, is_genesis=False) 

    state.latest_start_shard = (
        state.latest_start_shard +
        get_shard_delta(state, get_current_epoch(state))
    ) % SHARD_COUNT
```

#### Slashings

Run `process_slashings(state)`:

```python
def process_slashings(state: BeaconState) -> None:
    """
    Process the slashings.
    Note that this function mutates ``state``.
    """
    current_epoch = get_current_epoch(state)
    active_validator_indices = get_active_validator_indices(state.validator_registry, current_epoch)
    total_balance = get_total_balance(state, active_validator_indices)

    # Compute `total_penalties`
    total_at_start = state.latest_slashed_balances[(current_epoch + 1) % LATEST_SLASHED_EXIT_LENGTH]
    total_at_end = state.latest_slashed_balances[current_epoch % LATEST_SLASHED_EXIT_LENGTH]
    total_penalties = total_at_end - total_at_start

    for index, validator in enumerate(state.validator_registry):
        if validator.slashed and current_epoch == validator.withdrawable_epoch - LATEST_SLASHED_EXIT_LENGTH // 2:
            penalty = max(
                get_effective_balance(state, index) * min(total_penalties * 3, total_balance) // total_balance,
                get_effective_balance(state, index) // MIN_PENALTY_QUOTIENT
            )
            decrease_balance(state, index, penalty)
```

#### Final updates

Run the following function:

```python
def finish_epoch_update(state: BeaconState) -> None:
    current_epoch = get_current_epoch(state)
    next_epoch = current_epoch + 1
    # Set active index root
    index_root_position = (next_epoch + ACTIVATION_EXIT_DELAY) % LATEST_ACTIVE_INDEX_ROOTS_LENGTH
    state.latest_active_index_roots[index_root_position] = hash_tree_root(
        get_active_validator_indices(state.validator_registry, next_epoch + ACTIVATION_EXIT_DELAY)
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

### Per-slot processing

At every `slot > GENESIS_SLOT` run the following function:

```python
def advance_slot(state: BeaconState) -> None:
    state.slot += 1
```

### Per-block processing

For every `block` except the genesis block, run `process_block_header(state, block)`, `process_randao(state, block)` and `process_eth1_data(state, block)`.

#### Block header

```python
def process_block_header(state: BeaconState, block: BeaconBlock) -> None:
    # Verify that the slots match
    assert block.slot == state.slot
    # Verify that the parent matches
    assert block.previous_block_root == signing_root(state.latest_block_header)
    # Save current block as the new latest block
    state.latest_block_header = get_temporary_block_header(block)
    # Verify proposer is not slashed
    proposer = state.validator_registry[get_beacon_proposer_index(state, state.slot)]
    assert not proposer.slashed
    # Verify proposer signature
    assert bls_verify(
        pubkey=proposer.pubkey,
        message_hash=signing_root(block),
        signature=block.signature,
        domain=get_domain(state.fork, get_current_epoch(state), DOMAIN_BEACON_BLOCK)
    )
```

#### RANDAO

```python
def process_randao(state: BeaconState, block: BeaconBlock) -> None:
    proposer = state.validator_registry[get_beacon_proposer_index(state, state.slot)]
    # Verify that the provided randao value is valid
    assert bls_verify(
        pubkey=proposer.pubkey,
        message_hash=hash_tree_root(get_current_epoch(state)),
        signature=block.body.randao_reveal,
        domain=get_domain(state.fork, get_current_epoch(state), DOMAIN_RANDAO)
    )
    # Mix it in
    state.latest_randao_mixes[get_current_epoch(state) % LATEST_RANDAO_MIXES_LENGTH] = (
        xor(get_randao_mix(state, get_current_epoch(state)),
            hash(block.body.randao_reveal))
    )
```

#### Eth1 data

```python
def process_eth1_data(state: BeaconState, block: BeaconBlock) -> None:
    for eth1_data_vote in state.eth1_data_votes:
        # If someone else has already voted for the same hash, add to its counter
        if eth1_data_vote.eth1_data == block.body.eth1_data:
            eth1_data_vote.vote_count += 1
            return
    # If we're seeing this hash for the first time, make a new counter
    state.eth1_data_votes.append(Eth1DataVote(eth1_data=block.body.eth1_data, vote_count=1))
```

#### Operations

##### Proposer slashings

Verify that `len(block.body.proposer_slashings) <= MAX_PROPOSER_SLASHINGS`.

For each `proposer_slashing` in `block.body.proposer_slashings`, run the following function:

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
        assert bls_verify(
            pubkey=proposer.pubkey,
            message_hash=signing_root(header),
            signature=header.signature,
            domain=get_domain(state.fork, slot_to_epoch(header.slot), DOMAIN_BEACON_BLOCK)
        )
    slash_validator(state, proposer_slashing.proposer_index)
```

##### Attester slashings

Verify that `len(block.body.attester_slashings) <= MAX_ATTESTER_SLASHINGS`.

For each `attester_slashing` in `block.body.attester_slashings`, run the following function:

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

Verify that `len(block.body.attestations) <= MAX_ATTESTATIONS`.

For each `attestation` in `block.body.attestations`, run the following function:

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    """
    Process ``Attestation`` operation.
    Note that this function mutates ``state``.
    """
    assert max(GENESIS_SLOT, state.slot - SLOTS_PER_EPOCH) <= attestation.data.slot
    assert attestation.data.slot <= state.slot - MIN_ATTESTATION_INCLUSION_DELAY

    # Check target epoch, source epoch, and source root
    target_epoch = slot_to_epoch(attestation.data.slot)
    assert (target_epoch, attestation.data.source_epoch, attestation.data.source_root) in {
        (get_current_epoch(state), state.current_justified_epoch, state.current_justified_root),
        (get_previous_epoch(state), state.previous_justified_epoch, state.previous_justified_root),
    }

    # Check crosslink data
    assert attestation.data.crosslink_data_root == ZERO_HASH  # [to be removed in phase 1]
    assert state.latest_crosslinks[attestation.data.shard] in {
        attestation.data.previous_crosslink,  # Case 1: latest crosslink matches previous crosslink
        Crosslink(                            # Case 2: latest crosslink matches current crosslink
            crosslink_data_root=attestation.data.crosslink_data_root,
            epoch=min(slot_to_epoch(attestation.data.slot),
                      attestation.data.previous_crosslink.epoch + MAX_CROSSLINK_EPOCHS)
        ),
    }

    # Check signature and bitfields
    assert verify_indexed_attestation(state, convert_to_indexed(state, attestation))

    # Cache pending attestation
    pending_attestation = PendingAttestation(
        data=attestation.data,
        aggregation_bitfield=attestation.aggregation_bitfield,
        custody_bitfield=attestation.custody_bitfield,
        inclusion_slot=state.slot
    )
    if target_epoch == get_current_epoch(state):
        state.current_epoch_attestations.append(pending_attestation)
    else:
        state.previous_epoch_attestations.append(pending_attestation)
```

##### Deposits

Verify that `len(block.body.deposits) == min(MAX_DEPOSITS, latest_eth1_data.deposit_count - state.deposit_index)`.

For each `deposit` in `block.body.deposits`, run the following function:

```python
def process_deposit(state: BeaconState, deposit: Deposit) -> None:
    """
    Process a deposit from Ethereum 1.0.
    Used to add a validator or top up an existing validator's
    balance by some ``deposit`` amount.

    Note that this function mutates ``state``.
    """
    # Deposits must be processed in order
    assert deposit.index == state.deposit_index

    # Verify the Merkle branch
    merkle_branch_is_valid = verify_merkle_branch(
        leaf=hash(serialize(deposit.data)),  # 48 + 32 + 8 + 96 = 184 bytes serialization
        proof=deposit.proof,
        depth=DEPOSIT_CONTRACT_TREE_DEPTH,
        index=deposit.index,
        root=state.latest_eth1_data.deposit_root,
    )
    assert merkle_branch_is_valid

    # Increment the next deposit index we are expecting. Note that this
    # needs to be done here because while the deposit contract will never
    # create an invalid Merkle branch, it may admit an invalid deposit
    # object, and we need to be able to skip over it
    state.deposit_index += 1

    validator_pubkeys = [v.pubkey for v in state.validator_registry]
    pubkey = deposit.data.pubkey
    amount = deposit.data.amount

    if pubkey not in validator_pubkeys:
        # Verify the proof of possession
        proof_is_valid = bls_verify(
            pubkey=pubkey,
            message_hash=signing_root(deposit.data),
            signature=deposit.data.proof_of_possession,
            domain=get_domain(
                state.fork,
                get_current_epoch(state),
                DOMAIN_DEPOSIT,
            )
        )
        if not proof_is_valid:
            return

        # Add new validator
        validator = Validator(
            pubkey=pubkey,
            withdrawal_credentials=deposit.data.withdrawal_credentials,
            activation_eligibility_epoch=FAR_FUTURE_EPOCH,
            activation_epoch=FAR_FUTURE_EPOCH,
            exit_epoch=FAR_FUTURE_EPOCH,
            withdrawable_epoch=FAR_FUTURE_EPOCH,
            initiated_exit=False,
            slashed=False,
            high_balance=0
        )

        # Note: In phase 2 registry indices that have been withdrawn for a long time will be recycled.
        state.validator_registry.append(validator)
        state.balances.append(0)
        set_balance(state, len(state.validator_registry) - 1, amount)
    else:
        # Increase balance by deposit amount
        index = validator_pubkeys.index(pubkey)
        increase_balance(state, index, amount)
```

##### Voluntary exits

Verify that `len(block.body.voluntary_exits) <= MAX_VOLUNTARY_EXITS`.

For each `exit` in `block.body.voluntary_exits`, run the following function:

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
    assert bls_verify(
        pubkey=validator.pubkey,
        message_hash=signing_root(exit),
        signature=exit.signature,
        domain=get_domain(state.fork, exit.epoch, DOMAIN_VOLUNTARY_EXIT)
    )
    # Initiate exit
    initiate_validator_exit(state, exit.validator_index)
```

##### Transfers

Note: Transfers are a temporary functionality for phases 0 and 1, to be removed in phase 2.

Verify that `len(block.body.transfers) <= MAX_TRANSFERS` and that all transfers are distinct.

For each `transfer` in `block.body.transfers`, run the following function:

```python
def process_transfer(state: BeaconState, transfer: Transfer) -> None:
    """
    Process ``Transfer`` operation.
    Note that this function mutates ``state``.
    """
    # Verify the amount and fee aren't individually too big (for anti-overflow purposes)
    assert get_balance(state, transfer.sender) >= max(transfer.amount, transfer.fee)
    # Verify that we have enough ETH to send, and that after the transfer the balance will be either
    # exactly zero or at least MIN_DEPOSIT_AMOUNT
    assert (
        get_balance(state, transfer.sender) == transfer.amount + transfer.fee or
        get_balance(state, transfer.sender) >= transfer.amount + transfer.fee + MIN_DEPOSIT_AMOUNT
    )
    # A transfer is valid in only one slot
    assert state.slot == transfer.slot
    # Only withdrawn or not-yet-deposited accounts can transfer
    assert (
        get_current_epoch(state) >= state.validator_registry[transfer.sender].withdrawable_epoch or
        state.validator_registry[transfer.sender].activation_epoch == FAR_FUTURE_EPOCH
    )
    # Verify that the pubkey is valid
    assert (
        state.validator_registry[transfer.sender].withdrawal_credentials ==
        BLS_WITHDRAWAL_PREFIX_BYTE + hash(transfer.pubkey)[1:]
    )
    # Verify that the signature is valid
    assert bls_verify(
        pubkey=transfer.pubkey,
        message_hash=signing_root(transfer),
        signature=transfer.signature,
        domain=get_domain(state.fork, slot_to_epoch(transfer.slot), DOMAIN_TRANSFER)
    )
    # Process the transfer
    decrease_balance(state, transfer.sender, transfer.amount + transfer.fee)
    increase_balance(state, transfer.recipient, transfer.amount)
    increase_balance(state, get_beacon_proposer_index(state, state.slot), transfer.fee)
```

#### State root verification

Verify the block's `state_root` by running the following function:

```python
def verify_block_state_root(state: BeaconState, block: BeaconBlock) -> None:
    assert block.state_root == hash_tree_root(state)
```
