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
        - [Gwei values](#gwei-values)
        - [Initial values](#initial-values)
        - [Time parameters](#time-parameters)
        - [State list lengths](#state-list-lengths)
        - [Reward and penalty quotients](#reward-and-penalty-quotients)
        - [Status flags](#status-flags)
        - [Max operations per block](#max-operations-per-block)
        - [Signature domains](#signature-domains)
    - [Data structures](#data-structures)
        - [Beacon chain operations](#beacon-chain-operations)
            - [Proposer slashings](#proposer-slashings)
                - [`ProposerSlashing`](#proposerslashing)
            - [Attester slashings](#attester-slashings)
                - [`AttesterSlashing`](#attesterslashing)
                - [`SlashableAttestation`](#slashableattestation)
            - [Attestations](#attestations)
                - [`Attestation`](#attestation)
                - [`AttestationData`](#attestationdata)
                - [`AttestationDataAndCustodyBit`](#attestationdataandcustodybit)
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
            - [`Validator`](#validator)
            - [`Crosslink`](#crosslink)
            - [`PendingAttestation`](#pendingattestation)
            - [`Fork`](#fork)
            - [`Eth1Data`](#eth1data)
            - [`Eth1DataVote`](#eth1datavote)
    - [Custom Types](#custom-types)
    - [Helper functions](#helper-functions)
        - [`hash`](#hash)
        - [`hash_tree_root`](#hash_tree_root)
        - [`slot_to_epoch`](#slot_to_epoch)
        - [`get_previous_epoch`](#get_previous_epoch)
        - [`get_current_epoch`](#get_current_epoch)
        - [`get_epoch_start_slot`](#get_epoch_start_slot)
        - [`is_active_validator`](#is_active_validator)
        - [`get_active_validator_indices`](#get_active_validator_indices)
        - [`get_permuted_index`](#get_permuted_index)
        - [`split`](#split)
        - [`get_epoch_committee_count`](#get_epoch_committee_count)
        - [`get_shuffling`](#get_shuffling)
        - [`get_previous_epoch_committee_count`](#get_previous_epoch_committee_count)
        - [`get_current_epoch_committee_count`](#get_current_epoch_committee_count)
        - [`get_next_epoch_committee_count`](#get_next_epoch_committee_count)
        - [`get_crosslink_committees_at_slot`](#get_crosslink_committees_at_slot)
        - [`get_block_root`](#get_block_root)
        - [`get_randao_mix`](#get_randao_mix)
        - [`get_active_index_root`](#get_active_index_root)
        - [`generate_seed`](#generate_seed)
        - [`get_beacon_proposer_index`](#get_beacon_proposer_index)
        - [`merkle_root`](#merkle_root)
        - [`get_attestation_participants`](#get_attestation_participants)
        - [`is_power_of_two`](#is_power_of_two)
        - [`int_to_bytes1`, `int_to_bytes2`, ...](#int_to_bytes1-int_to_bytes2-)
        - [`bytes_to_int`](#bytes_to_int)
        - [`get_effective_balance`](#get_effective_balance)
        - [`get_total_balance`](#get_total_balance)
        - [`get_fork_version`](#get_fork_version)
        - [`get_domain`](#get_domain)
        - [`get_bitfield_bit`](#get_bitfield_bit)
        - [`verify_bitfield`](#verify_bitfield)
        - [`verify_slashable_attestation`](#verify_slashable_attestation)
        - [`is_double_vote`](#is_double_vote)
        - [`is_surround_vote`](#is_surround_vote)
        - [`integer_squareroot`](#integer_squareroot)
        - [`get_entry_exit_effect_epoch`](#get_entry_exit_effect_epoch)
        - [`bls_verify`](#bls_verify)
        - [`bls_verify_multiple`](#bls_verify_multiple)
        - [`bls_aggregate_pubkeys`](#bls_aggregate_pubkeys)
        - [`validate_proof_of_possession`](#validate_proof_of_possession)
        - [`process_deposit`](#process_deposit)
        - [Routines for updating validator status](#routines-for-updating-validator-status)
            - [`activate_validator`](#activate_validator)
            - [`initiate_validator_exit`](#initiate_validator_exit)
            - [`exit_validator`](#exit_validator)
            - [`penalize_validator`](#penalize_validator)
            - [`prepare_validator_for_withdrawal`](#prepare_validator_for_withdrawal)
    - [Ethereum 1.0 deposit contract](#ethereum-10-deposit-contract)
        - [Deposit arguments](#deposit-arguments)
        - [Withdrawal credentials](#withdrawal-credentials)
        - [`Deposit` logs](#deposit-logs)
        - [`ChainStart` log](#chainstart-log)
        - [Vyper code](#vyper-code)
    - [On startup](#on-startup)
    - [Beacon chain processing](#beacon-chain-processing)
        - [Beacon chain fork choice rule](#beacon-chain-fork-choice-rule)
    - [Beacon chain state transition function](#beacon-chain-state-transition-function)
        - [Per-slot processing](#per-slot-processing)
            - [Slot](#slot)
            - [Block roots](#block-roots)
        - [Per-block processing](#per-block-processing)
            - [Slot](#slot-1)
            - [Proposer signature](#proposer-signature)
            - [RANDAO](#randao)
            - [Eth1 data](#eth1-data)
            - [Operations](#operations)
                - [Proposer slashings](#proposer-slashings-1)
                - [Attester slashings](#attester-slashings-1)
                - [Attestations](#attestations-1)
                - [Deposits](#deposits-1)
                - [Exits](#exits-1)
        - [Per-epoch processing](#per-epoch-processing)
            - [Helpers](#helpers)
            - [Eth1 data](#eth1-data-1)
            - [Justification](#justification)
            - [Crosslinks](#crosslinks)
            - [Rewards and penalties](#rewards-and-penalties)
                - [Justification and finalization](#justification-and-finalization)
                - [Attestation inclusion](#attestation-inclusion)
                - [Crosslinks](#crosslinks-1)
            - [Ejections](#ejections)
            - [Validator registry and shuffling seed data](#validator-registry-and-shuffling-seed-data)
            - [Final updates](#final-updates)
        - [State root verification](#state-root-verification)
- [References](#references)
    - [Normative](#normative)
    - [Informative](#informative)
- [Copyright](#copyright)

<!-- /TOC -->

## Introduction

This document represents the specification for Phase 0 of Ethereum 2.0 -- The Beacon Chain.

At the core of Ethereum 2.0 is a system chain called the "beacon chain". The beacon chain stores and manages the registry of [validators](#dfn-validator). In the initial deployment phases of Ethereum 2.0 the only mechanism to become a [validator](#dfn-validator) is to make a one-way ETH transaction to a deposit contract on Ethereum 1.0. Activation as a [validator](#dfn-validator) happens when Ethereum 1.0 deposit receipts are processed by the beacon chain, the activation balance is reached, and after a queuing process. Exit is either voluntary or done forcibly as a penalty for misbehavior.

The primary source of load on the beacon chain is "attestations". Attestations are availability votes for a shard block, and simultaneously proof of stake votes for a beacon block. A sufficient number of attestations for the same shard block create a "crosslink", confirming the shard segment up to that shard block into the beacon chain. Crosslinks also serve as infrastructure for asynchronous cross-shard communication.

## Notation

Code snippets appearing in `this style` are to be interpreted as Python code. Beacon blocks that trigger unhandled Python exceptions (e.g. out-of-range list accesses) and failed asserts are considered invalid.

## Terminology

* **Validator** <a id="dfn-validator"></a> - a registered participant in the beacon chain. You can become one by sending Ether into the Ethereum 1.0 deposit contract.
* **Active validator** <a id="dfn-active-validator"></a> - an active participant in the Ethereum 2.0 consensus invited to, among other things, propose and attest to blocks and vote for crosslinks.
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
| `TARGET_COMMITTEE_SIZE` | `2**7` (= 128) | [validators](#dfn-validator) |
| `MAX_BALANCE_CHURN_QUOTIENT` | `2**5` (= 32) | - |
| `BEACON_CHAIN_SHARD_NUMBER` | `2**64 - 1` | - |
| `MAX_INDICES_PER_SLASHABLE_VOTE` | `2**12` (= 4,096) | votes |
| `MAX_WITHDRAWALS_PER_EPOCH` | `2**2` (= 4) | withdrawals |
| `SHUFFLE_ROUND_COUNT` | 90 | - |

* For the safety of crosslinks `TARGET_COMMITTEE_SIZE` exceeds [the recommended minimum committee size of 111](https://vitalik.ca/files/Ithaca201807_Sharding.pdf); with sufficient active validators (at least `EPOCH_LENGTH * TARGET_COMMITTEE_SIZE`), the shuffling algorithm ensures committee sizes at least `TARGET_COMMITTEE_SIZE`. (Unbiasable randomness with a Verifiable Delay Function (VDF) will improve committee robustness and lower the safe minimum committee size.)

### Deposit contract

| Name | Value |
| - | - |
| `DEPOSIT_CONTRACT_ADDRESS` | **TBD** |
| `DEPOSIT_CONTRACT_TREE_DEPTH` | `2**5` (= 32) |

### Gwei values

| Name | Value | Unit |
| - | - | :-: |
| `MIN_DEPOSIT_AMOUNT` | `2**0 * 1e9` (= 1,000,000,000) | Gwei |
| `MAX_DEPOSIT_AMOUNT` | `2**5 * 1e9` (= 32,000,000,000) | Gwei |
| `FORK_CHOICE_BALANCE_INCREMENT` | `2**0 * 1e9` (= 1,000,000,000) | Gwei |
| `EJECTION_BALANCE` | `2**4 * 1e9` (= 16,000,000,000) | Gwei |

### Initial values

| Name | Value |
| - | - |
| `GENESIS_FORK_VERSION` | `0` |
| `GENESIS_SLOT` | `2**63` |
| `GENESIS_EPOCH` | `slot_to_epoch(GENESIS_SLOT)` |
| `GENESIS_START_SHARD` | `0` |
| `FAR_FUTURE_EPOCH` | `2**64 - 1` |
| `ZERO_HASH` | `int_to_bytes32(0)` |
| `EMPTY_SIGNATURE` | `int_to_bytes96(0)` |
| `BLS_WITHDRAWAL_PREFIX_BYTE` | `int_to_bytes1(0)` |

* `GENESIS_SLOT` should be at least as large in terms of time as the largest of the time parameters or state list lengths below (ie. it should be at least as large as any value measured in slots, and at least `EPOCH_LENGTH` times as large as any value measured in epochs).

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SLOT_DURATION` | `6` | seconds | 6 seconds |
| `MIN_ATTESTATION_INCLUSION_DELAY` | `2**2` (= 4) | slots | 24 seconds |
| `EPOCH_LENGTH` | `2**6` (= 64) | slots | 6.4 minutes |
| `SEED_LOOKAHEAD` | `2**0` (= 1) | epochs | 6.4 minutes |
| `ENTRY_EXIT_DELAY` | `2**2` (= 4) | epochs | 25.6 minutes |
| `ETH1_DATA_VOTING_PERIOD` | `2**4` (= 16) | epochs | ~1.7 hours |
| `MIN_VALIDATOR_WITHDRAWAL_EPOCHS` | `2**8` (= 256) | epochs | ~27 hours |

### State list lengths

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `LATEST_BLOCK_ROOTS_LENGTH` | `2**13` (= 8,192) | slots | ~13 hours |
| `LATEST_RANDAO_MIXES_LENGTH` | `2**13` (= 8,192) | epochs | ~36 days |
| `LATEST_INDEX_ROOTS_LENGTH` | `2**13` (= 8,192) | epochs | ~36 days |
| `LATEST_PENALIZED_EXIT_LENGTH` | `2**13` (= 8,192) | epochs | ~36 days |

### Reward and penalty quotients

| Name | Value |
| - | - |
| `BASE_REWARD_QUOTIENT` | `2**5` (= 32) |
| `WHISTLEBLOWER_REWARD_QUOTIENT` | `2**9` (= 512) |
| `INCLUDER_REWARD_QUOTIENT` | `2**3` (= 8) |
| `INACTIVITY_PENALTY_QUOTIENT` | `2**24` (= 16,777,216) |

* The `BASE_REWARD_QUOTIENT` parameter dictates the per-epoch reward. It corresponds to ~2.54% annual interest assuming 10 million participating ETH in every epoch.
* The `INACTIVITY_PENALTY_QUOTIENT` equals `INVERSE_SQRT_E_DROP_TIME**2` where `INVERSE_SQRT_E_DROP_TIME := 2**12 epochs` (~18 days) is the time it takes the inactivity penalty to reduce the balance of non-participating [validators](#dfn-validator) to about `1/sqrt(e) ~= 60.6%`. Indeed, the balance retained by offline [validators](#dfn-validator) after `n` epochs is about `(1-1/INACTIVITY_PENALTY_QUOTIENT)**(n**2/2)` so after `INVERSE_SQRT_E_DROP_TIME` epochs it is roughly `(1-1/INACTIVITY_PENALTY_QUOTIENT)**(INACTIVITY_PENALTY_QUOTIENT/2) ~= 1/sqrt(e)`.

### Status flags

| Name | Value |
| - | - |
| `INITIATED_EXIT` | `2**0` (= 1) |
| `WITHDRAWABLE` | `2**1` (= 2) |

### Max operations per block

| Name | Value |
| - | - |
| `MAX_PROPOSER_SLASHINGS` | `2**4` (= 16) |
| `MAX_ATTESTER_SLASHINGS` | `2**0` (= 1) |
| `MAX_ATTESTATIONS` | `2**7` (= 128) |
| `MAX_DEPOSITS` | `2**4` (= 16) |
| `MAX_EXITS` | `2**4` (= 16) |

### Signature domains

| Name | Value |
| - | - |
| `DOMAIN_DEPOSIT` | `0` |
| `DOMAIN_ATTESTATION` | `1` |
| `DOMAIN_PROPOSAL` | `2` |
| `DOMAIN_EXIT` | `3` |
| `DOMAIN_RANDAO` | `4` |

## Data structures

The following data structures are defined as [SimpleSerialize (SSZ)](https://github.com/ethereum/eth2.0-specs/blob/master/specs/simple-serialize.md) objects.

### Beacon chain operations

#### Proposer slashings

##### `ProposerSlashing`

```python
{
    # Proposer index
    'proposer_index': 'uint64',
    # First proposal data
    'proposal_data_1': ProposalSignedData,
    # First proposal signature
    'proposal_signature_1': 'bytes96',
    # Second proposal data
    'proposal_data_2': ProposalSignedData,
    # Second proposal signature
    'proposal_signature_2': 'bytes96',
}
```

#### Attester slashings

##### `AttesterSlashing`

```python
{
    # First slashable attestation
    'slashable_attestation_1': SlashableAttestation,
    # Second slashable attestation
    'slashable_attestation_2': SlashableAttestation,
}
```

##### `SlashableAttestation`

```python
{
    # Validator indices
    'validator_indices': ['uint64'],
    # Attestation data
    'data': AttestationData,
    # Custody bitfield
    'custody_bitfield': 'bytes',
    # Aggregate signature
    'aggregate_signature': 'bytes96',
}
```

#### Attestations

##### `Attestation`

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

##### `AttestationData`

```python
{
    # Slot number
    'slot': 'uint64',
    # Shard number
    'shard': 'uint64',
    # Hash of root of the signed beacon block
    'beacon_block_root': 'bytes32',
    # Hash of root of the ancestor at the epoch boundary
    'epoch_boundary_root': 'bytes32',
    # Shard block's hash of root
    'shard_block_root': 'bytes32',
    # Last crosslink
    'latest_crosslink': Crosslink,
    # Last justified epoch in the beacon state
    'justified_epoch': 'uint64',
    # Hash of the last justified beacon block
    'justified_block_root': 'bytes32',
}
```

##### `AttestationDataAndCustodyBit`

```python
{
    # Attestation data
    'data': AttestationData,
    # Custody bit
    'custody_bit': 'bool',
}
```

#### Deposits

##### `Deposit`

```python
{
    # Branch in the deposit tree
    'branch': ['bytes32'],
    # Index in the deposit tree
    'index': 'uint64',
    # Data
    'deposit_data': DepositData,
}
```

##### `DepositData`

```python
{
    # Amount in Gwei
    'amount': 'uint64',
    # Timestamp from deposit contract
    'timestamp': 'uint64',
    # Deposit input
    'deposit_input': DepositInput,
}
```

##### `DepositInput`

```python
{
    # BLS pubkey
    'pubkey': 'bytes48',
    # Withdrawal credentials
    'withdrawal_credentials': 'bytes32',
    # A BLS signature of this `DepositInput`
    'proof_of_possession': 'bytes96',
}
```

#### Exits

##### `Exit`

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

### Beacon chain blocks

#### `BeaconBlock`

```python
{
    ## Header ##
    'slot': 'uint64',
    'parent_root': 'bytes32',
    'state_root': 'bytes32',
    'randao_reveal': 'bytes96',
    'eth1_data': Eth1Data,
    'signature': 'bytes96',

    ## Body ##
    'body': BeaconBlockBody,
}
```

#### `BeaconBlockBody`

```python
{
    'proposer_slashings': [ProposerSlashing],
    'attester_slashings': [AttesterSlashing],
    'attestations': [Attestation],
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
    'block_root': 'bytes32',
}
```

### Beacon chain state

#### `BeaconState`

```python
{
    # Misc
    'slot': 'uint64',
    'genesis_time': 'uint64',
    'fork': Fork,  # For versioning hard forks

    # Validator registry
    'validator_registry': [Validator],
    'validator_balances': ['uint64'],
    'validator_registry_update_epoch': 'uint64',

    # Randomness and committees
    'latest_randao_mixes': ['bytes32'],
    'previous_epoch_start_shard': 'uint64',
    'current_epoch_start_shard': 'uint64',
    'previous_calculation_epoch': 'uint64',
    'current_calculation_epoch': 'uint64',
    'previous_epoch_seed': 'bytes32',
    'current_epoch_seed': 'bytes32',

    # Finality
    'previous_justified_epoch': 'uint64',
    'justified_epoch': 'uint64',
    'justification_bitfield': 'uint64',
    'finalized_epoch': 'uint64',

    # Recent state
    'latest_crosslinks': [Crosslink],
    'latest_block_roots': ['bytes32'],
    'latest_index_roots': ['bytes32'],
    'latest_penalized_balances': ['uint64'],  # Balances penalized at every withdrawal period
    'latest_attestations': [PendingAttestation],
    'batched_block_roots': ['bytes32'],

    # Ethereum 1.0 chain data
    'latest_eth1_data': Eth1Data,
    'eth1_data_votes': [Eth1DataVote],
}
```

#### `Validator`

```python
{
    # BLS public key
    'pubkey': 'bytes48',
    # Withdrawal credentials
    'withdrawal_credentials': 'bytes32',
    # Epoch when validator activated
    'activation_epoch': 'uint64',
    # Epoch when validator exited
    'exit_epoch': 'uint64',
    # Epoch when validator withdrew
    'withdrawal_epoch': 'uint64',
    # Epoch when validator was penalized
    'penalized_epoch': 'uint64',
    # Status flags
    'status_flags': 'uint64',
}
```

#### `Crosslink`

```python
{
    # Epoch number
    'epoch': 'uint64',
    # Shard block root
    'shard_block_root': 'bytes32',
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

#### `Fork`

```python
{
    # Previous fork version
    'previous_version': 'uint64',
    # Current fork version
    'current_version': 'uint64',
    # Fork epoch number
    'epoch': 'uint64',
}
```

#### `Eth1Data`

```python
{
    # Root of the deposit tree
    'deposit_root': 'bytes32',
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

## Custom Types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `SlotNumber` | `uint64` | a slot number |
| `EpochNumber` | `uint64` | an epoch number |
| `ShardNumber` | `uint64` | a shard number |
| `ValidatorIndex` | `uint64` | an index in the validator registry |
| `Gwei` | `uint64` | an amount in Gwei |
| `Bytes32` | `bytes32` | 32 bytes of binary data |
| `BLSPubkey` | `bytes48` | a BLS public key |
| `BLSSignature` | `bytes96` | a BLS signature |

## Helper functions

Note: The definitions below are for specification purposes and are not necessarily optimal implementations.

### `hash`

The hash function is denoted by `hash`. In Phase 0 the beacon chain is deployed with the same hash function as Ethereum 1.0, i.e. Keccak-256 (also incorrectly known as SHA3).

Note: We aim to migrate to a S[T/N]ARK-friendly hash function in a future Ethereum 2.0 deployment phase.

### `hash_tree_root`

`def hash_tree_root(object: SSZSerializable) -> Bytes32` is a function for hashing objects into a single root utilizing a hash tree structure. `hash_tree_root` is defined in the [SimpleSerialize spec](https://github.com/ethereum/eth2.0-specs/blob/master/specs/simple-serialize.md#tree-hash).

### `slot_to_epoch`

```python
def slot_to_epoch(slot: SlotNumber) -> EpochNumber:
    """
    Return the epoch number of the given ``slot``.
    """
    return slot // EPOCH_LENGTH
```

### `get_previous_epoch`

```python
def get_previous_epoch(state: BeaconState) -> EpochNumber:
    """`
    Return the previous epoch of the given ``state``.
    If the current epoch is  ``GENESIS_EPOCH``, return ``GENESIS_EPOCH``.
    """
    current_epoch = get_current_epoch(state)
    if current_epoch == GENESIS_EPOCH:
        return GENESIS_EPOCH
    return current_epoch - 1
```

### `get_current_epoch`

```python
def get_current_epoch(state: BeaconState) -> EpochNumber:
    """
    Return the current epoch of the given ``state``.
    """
    return slot_to_epoch(state.slot)
```

### `get_epoch_start_slot`

```python
def get_epoch_start_slot(epoch: EpochNumber) -> SlotNumber:
    """
    Return the starting slot of the given ``epoch``.
    """
    return epoch * EPOCH_LENGTH
```

### `is_active_validator`
```python
def is_active_validator(validator: Validator, epoch: EpochNumber) -> bool:
    """
    Check if ``validator`` is active.
    """
    return validator.activation_epoch <= epoch < validator.exit_epoch
```

### `get_active_validator_indices`

```python
def get_active_validator_indices(validators: List[Validator], epoch: EpochNumber) -> List[ValidatorIndex]:
    """
    Get indices of active validators from ``validators``.
    """
    return [i for i, v in enumerate(validators) if is_active_validator(v, epoch)]
```

### `get_permuted_index`

```python
def get_permuted_index(index: int, list_size: int, seed: Bytes32) -> int:
    """
    Return `p(index)` in a pseudorandom permutation `p` of `0...list_size-1` with ``seed`` as entropy.

    Utilizes 'swap or not' shuffling found in
    https://link.springer.com/content/pdf/10.1007%2F978-3-642-32009-5_1.pdf
    See the 'generalized domain' algorithm on page 3.
    """
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

### `split`

```python
def split(values: List[Any], split_count: int) -> List[List[Any]]:
    """
    Splits ``values`` into ``split_count`` pieces.
    """
    list_length = len(values)
    return [
        values[(list_length * i // split_count): (list_length * (i + 1) // split_count)]
        for i in range(split_count)
    ]
```

### `get_epoch_committee_count`

```python
def get_epoch_committee_count(active_validator_count: int) -> int:
    """
    Return the number of committees in one epoch.
    """
    return max(
        1,
        min(
            SHARD_COUNT // EPOCH_LENGTH,
            active_validator_count // EPOCH_LENGTH // TARGET_COMMITTEE_SIZE,
        )
    ) * EPOCH_LENGTH
```

### `get_shuffling`

```python
def get_shuffling(seed: Bytes32,
                  validators: List[Validator],
                  epoch: EpochNumber) -> List[List[ValidatorIndex]]
    """
    Shuffle ``validators`` into crosslink committees seeded by ``seed`` and ``epoch``.
    Return a list of ``committees_per_epoch`` committees where each
    committee is itself a list of validator indices.
    """

    active_validator_indices = get_active_validator_indices(validators, epoch)

    committees_per_epoch = get_epoch_committee_count(len(active_validator_indices))

    # Shuffle
    shuffled_active_validator_indices = [
        active_validator_indices[get_permuted_index(i, len(active_validator_indices), seed)]
        for i in active_validator_indices
    ]

    # Split the shuffled list into committees_per_epoch pieces
    return split(shuffled_active_validator_indices, committees_per_epoch)
```

**Invariant**: if `get_shuffling(seed, validators, epoch)` returns some value `x` for some `epoch <= get_current_epoch(state) + ENTRY_EXIT_DELAY`, it should return the same value `x` for the same `seed` and `epoch` and possible future modifications of `validators` forever in phase 0, and until the ~1 year deletion delay in phase 2 and in the future.

**Note**: this definition and the next few definitions make heavy use of repetitive computing. Production implementations are expected to appropriately use caching/memoization to avoid redoing work.

### `get_previous_epoch_committee_count`

```python
def get_previous_epoch_committee_count(state: BeaconState) -> int:
    """
    Return the number of committees in the previous epoch of the given ``state``.
    """
    previous_active_validators = get_active_validator_indices(
        state.validator_registry,
        state.previous_calculation_epoch,
    )
    return get_epoch_committee_count(len(previous_active_validators))
```

### `get_current_epoch_committee_count`

```python
def get_current_epoch_committee_count(state: BeaconState) -> int:
    """
    Return the number of committees in the current epoch of the given ``state``.
    """
    current_active_validators = get_active_validator_indices(
        state.validator_registry,
        state.current_calculation_epoch,
    )
    return get_epoch_committee_count(len(current_active_validators))
```

### `get_next_epoch_committee_count`

```python
def get_next_epoch_committee_count(state: BeaconState) -> int:
    """
    Return the number of committees in the next epoch of the given ``state``.
    """
    next_active_validators = get_active_validator_indices(
        state.validator_registry,
        get_current_epoch(state) + 1,
    )
    return get_epoch_committee_count(len(next_active_validators))
```

### `get_crosslink_committees_at_slot`

```python
def get_crosslink_committees_at_slot(state: BeaconState,
                                     slot: SlotNumber,
                                     registry_change: bool=False) -> List[Tuple[List[ValidatorIndex], ShardNumber]]:
    """
    Return the list of ``(committee, shard)`` tuples for the ``slot``.

    Note: There are two possible shufflings for crosslink committees for a
    ``slot`` in the next epoch -- with and without a `registry_change`
    """
    epoch = slot_to_epoch(slot)
    current_epoch = get_current_epoch(state)
    previous_epoch = get_previous_epoch(state)
    next_epoch = current_epoch + 1

    assert previous_epoch <= epoch <= next_epoch

    if epoch == previous_epoch:
        committees_per_epoch = get_previous_epoch_committee_count(state)
        seed = state.previous_epoch_seed
        shuffling_epoch = state.previous_calculation_epoch
        shuffling_start_shard = state.previous_epoch_start_shard
    elif epoch == current_epoch:
        committees_per_epoch = get_current_epoch_committee_count(state)
        seed = state.current_epoch_seed
        shuffling_epoch = state.current_calculation_epoch
        shuffling_start_shard = state.current_epoch_start_shard
    elif epoch == next_epoch:
        current_committees_per_epoch = get_current_epoch_committee_count(state)
        committees_per_epoch = get_next_epoch_committee_count(state)
        shuffling_epoch = next_epoch

        epochs_since_last_registry_update = current_epoch - state.validator_registry_update_epoch
        if registry_change:
            seed = generate_seed(state, next_epoch)
            shuffling_start_shard = (state.current_epoch_start_shard + current_committees_per_epoch) % SHARD_COUNT
        elif epochs_since_last_registry_update > 1 and is_power_of_two(epochs_since_last_registry_update):
            seed = generate_seed(state, next_epoch)
            shuffling_start_shard = state.current_epoch_start_shard
        else:
            seed = state.current_epoch_seed
            shuffling_start_shard = state.current_epoch_start_shard

    shuffling = get_shuffling(
        seed,
        state.validator_registry,
        shuffling_epoch,
    )
    offset = slot % EPOCH_LENGTH
    committees_per_slot = committees_per_epoch // EPOCH_LENGTH
    slot_start_shard = (shuffling_start_shard + committees_per_slot * offset) % SHARD_COUNT

    return [
        (
            shuffling[committees_per_slot * offset + i],
            (slot_start_shard + i) % SHARD_COUNT,
        )
        for i in range(committees_per_slot)
    ]
```

### `get_block_root`

```python
def get_block_root(state: BeaconState,
                   slot: SlotNumber) -> Bytes32:
    """
    Return the block root at a recent ``slot``.
    """
    assert state.slot <= slot + LATEST_BLOCK_ROOTS_LENGTH
    assert slot < state.slot
    return state.latest_block_roots[slot % LATEST_BLOCK_ROOTS_LENGTH]
```

`get_block_root(_, s)` should always return `hash_tree_root` of the block in the beacon chain at slot `s`, and `get_crosslink_committees_at_slot(_, s)` should not change unless the [validator](#dfn-validator) registry changes.

### `get_randao_mix`

```python
def get_randao_mix(state: BeaconState,
                   epoch: EpochNumber) -> Bytes32:
    """
    Return the randao mix at a recent ``epoch``.
    """
    assert get_current_epoch(state) - LATEST_RANDAO_MIXES_LENGTH < epoch <= get_current_epoch(state)
    return state.latest_randao_mixes[epoch % LATEST_RANDAO_MIXES_LENGTH]
```

### `get_active_index_root`

```python
def get_active_index_root(state: BeaconState,
                          epoch: EpochNumber) -> Bytes32:
    """
    Return the index root at a recent ``epoch``.
    """
    assert get_current_epoch(state) - LATEST_INDEX_ROOTS_LENGTH + ENTRY_EXIT_DELAY < epoch <= get_current_epoch(state) + ENTRY_EXIT_DELAY
    return state.latest_index_roots[epoch % LATEST_INDEX_ROOTS_LENGTH]
```

### `generate_seed`

```python
def generate_seed(state: BeaconState,
                  epoch: EpochNumber) -> Bytes32:
    """
    Generate a seed for the given ``epoch``.
    """
    return hash(
        get_randao_mix(state, epoch - SEED_LOOKAHEAD) +
        get_active_index_root(state, epoch) +
        int_to_bytes32(epoch)
    )
```

### `get_beacon_proposer_index`

```python
def get_beacon_proposer_index(state: BeaconState,
                              slot: SlotNumber) -> ValidatorIndex:
    """
    Return the beacon proposer index for the ``slot``.
    """
    first_committee, _ = get_crosslink_committees_at_slot(state, slot)[0]
    return first_committee[slot % len(first_committee)]
```

### `merkle_root`

```python
def merkle_root(values: List[Bytes32]) -> Bytes32:
    """
    Merkleize ``values`` (where ``len(values)`` is a power of two) and return the Merkle root.
    """
    o = [0] * len(values) + values
    for i in range(len(values) - 1, 0, -1):
        o[i] = hash(o[i * 2] + o[i * 2 + 1])
    return o[1]
```

### `get_attestation_participants`

```python
def get_attestation_participants(state: BeaconState,
                                 attestation_data: AttestationData,
                                 bitfield: bytes) -> List[ValidatorIndex]:
    """
    Return the participant indices at for the ``attestation_data`` and ``bitfield``.
    """
    # Find the committee in the list with the desired shard
    crosslink_committees = get_crosslink_committees_at_slot(state, attestation_data.slot)

    assert attestation_data.shard in [shard for _, shard in crosslink_committees]
    crosslink_committee = [committee for committee, shard in crosslink_committees if shard == attestation_data.shard][0]

    assert verify_bitfield(bitfield, len(crosslink_committee))

    # Find the participating attesters in the committee
    participants = []
    for i, validator_index in enumerate(crosslink_committee):
        aggregation_bit = get_bitfield_bit(bitfield, i)
        if aggregation_bit == 0b1:
            participants.append(validator_index)
    return participants
```

### `is_power_of_two`

```python
def is_power_of_two(value: int) -> bool:
    """
    Check if ``value`` is a power of two integer.
    """
    if value == 0:
        return False
    else:
        return 2**int(math.log2(value)) == value
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
def get_effective_balance(state: State, index: ValidatorIndex) -> Gwei:
    """
    Return the effective balance (also known as "balance at stake") for a validator with the given ``index``.
    """
    return min(state.validator_balances[index], MAX_DEPOSIT_AMOUNT)
```

### `get_total_balance`

```python
def get_total_balance(state: BeaconState, validators: List[ValidatorIndex]) -> Gwei:
    """
    Return the combined effective balance of an array of validators.
    """
    return sum([get_effective_balance(state, i) for i in validators])
```

### `get_fork_version`

```python
def get_fork_version(fork: Fork,
                     epoch: EpochNumber) -> int:
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
               epoch: EpochNumber,
               domain_type: int) -> int:
    """
    Get the domain number that represents the fork meta and signature domain.
    """
    fork_version = get_fork_version(fork, epoch)
    return fork_version * 2**32 + domain_type
```

### `get_bitfield_bit`

```python
def get_bitfield_bit(bitfield: bytes, i: int) -> int:
    """
    Extract the bit in ``bitfield`` at position ``i``.
    """
    return (bitfield[i // 8] >> (7 - (i % 8))) % 2
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

### `verify_slashable_attestation`

```python
def verify_slashable_attestation(state: BeaconState, slashable_attestation: SlashableAttestation) -> bool:
    """
    Verify validity of ``slashable_attestation`` fields.
    """
    if slashable_attestation.custody_bitfield != b'\x00' * len(slashable_attestation.custody_bitfield):  # [TO BE REMOVED IN PHASE 1]
        return False

    if len(slashable_attestation.validator_indices) == 0:
        return False

    for i in range(len(slashable_attestation.validator_indices) - 1):
        if slashable_attestation.validator_indices[i] >= slashable_attestation.validator_indices[i + 1]:
            return False

    if not verify_bitfield(slashable_attestation.custody_bitfield, len(slashable_attestation.validator_indices)):
        return False

    if len(slashable_attestation.validator_indices) > MAX_INDICES_PER_SLASHABLE_VOTE:
        return False

    custody_bit_0_indices = []
    custody_bit_1_indices = []
    for i, validator_index in enumerate(slashable_attestation.validator_indices):
        if get_bitfield_bit(slashable_attestation.custody_bitfield, i) == 0b0:
            custody_bit_0_indices.append(validator_index)
        else:
            custody_bit_1_indices.append(validator_index)

    return bls_verify_multiple(
        pubkeys=[
            bls_aggregate_pubkeys([state.validator_registry[i].pubkey for i in custody_bit_0_indices]),
            bls_aggregate_pubkeys([state.validator_registry[i].pubkey for i in custody_bit_1_indices]),
        ],
        message_hashes=[
            hash_tree_root(AttestationDataAndCustodyBit(data=slashable_attestation.data, custody_bit=0b0)),
            hash_tree_root(AttestationDataAndCustodyBit(data=slashable_attestation.data, custody_bit=0b1)),
        ],
        signature=slashable_attestation.aggregate_signature,
        domain=get_domain(state.fork, slot_to_epoch(vote_data.data.slot), DOMAIN_ATTESTATION),
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
    source_epoch_1 = attestation_data_1.justified_epoch
    source_epoch_2 = attestation_data_2.justified_epoch
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

### `get_entry_exit_effect_epoch`

```python
def get_entry_exit_effect_epoch(epoch: EpochNumber) -> EpochNumber:
    """
    An entry or exit triggered in the ``epoch`` given by the input takes effect at
    the epoch given by the output.
    """
    return epoch + 1 + ENTRY_EXIT_DELAY
```

### `bls_verify`

`bls_verify` is a function for verifying a BLS signature, defined in the [BLS Signature spec](https://github.com/ethereum/eth2.0-specs/blob/master/specs/bls_signature.md#bls_verify).

### `bls_verify_multiple`

`bls_verify_multiple` is a function for verifying a BLS signature constructed from multiple messages, defined in the [BLS Signature spec](https://github.com/ethereum/eth2.0-specs/blob/master/specs/bls_signature.md#bls_verify_multiple).

### `bls_aggregate_pubkeys`

`bls_aggregate_pubkeys` is a function for aggregating multiple BLS public keys into a single aggregate key, defined in the [BLS Signature spec](https://github.com/ethereum/eth2.0-specs/blob/master/specs/bls_signature.md#bls_aggregate_pubkeys).

### `validate_proof_of_possession`

```python
def validate_proof_of_possession(state: BeaconState,
                                 pubkey: BLSPubkey,
                                 proof_of_possession: BLSSignature,
                                 withdrawal_credentials: Bytes32) -> bool:
    """
    Verify the given ``proof_of_possession``.
    """
    proof_of_possession_data = DepositInput(
        pubkey=pubkey,
        withdrawal_credentials=withdrawal_credentials,
        proof_of_possession=EMPTY_SIGNATURE,
    )

    return bls_verify(
        pubkey=pubkey,
        message_hash=hash_tree_root(proof_of_possession_data),
        signature=proof_of_possession,
        domain=get_domain(
            state.fork,
            get_current_epoch(state),
            DOMAIN_DEPOSIT,
        )
    )
```

### `process_deposit`

Used to add a [validator](#dfn-validator) or top up an existing [validator](#dfn-validator)'s balance by some `deposit` amount:

```python
def process_deposit(state: BeaconState,
                    pubkey: BLSPubkey,
                    amount: Gwei,
                    proof_of_possession: BLSSignature,
                    withdrawal_credentials: Bytes32) -> None:
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
    )

    validator_pubkeys = [v.pubkey for v in state.validator_registry]

    if pubkey not in validator_pubkeys:
        # Add new validator
        validator = Validator(
            pubkey=pubkey,
            withdrawal_credentials=withdrawal_credentials,
            activation_epoch=FAR_FUTURE_EPOCH,
            exit_epoch=FAR_FUTURE_EPOCH,
            withdrawal_epoch=FAR_FUTURE_EPOCH,
            penalized_epoch=FAR_FUTURE_EPOCH,
            status_flags=0,
        )

        # Note: In phase 2 registry indices that have been withdrawn for a long time will be recycled.
        state.validator_registry.append(validator)
        state.validator_balances.append(amount)
    else:
        # Increase balance by deposit amount
        index = validator_pubkeys.index(pubkey)
        assert state.validator_registry[index].withdrawal_credentials == withdrawal_credentials

        state.validator_balances[index] += amount
```

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

    validator.activation_epoch = GENESIS_EPOCH if is_genesis else get_entry_exit_effect_epoch(get_current_epoch(state))
```

#### `initiate_validator_exit`

```python
def initiate_validator_exit(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Initiate the validator of the given ``index``.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[index]
    validator.status_flags |= INITIATED_EXIT
```

#### `exit_validator`

```python
def exit_validator(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Exit the validator of the given ``index``.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[index]

    # The following updates only occur if not previous exited
    if validator.exit_epoch <= get_entry_exit_effect_epoch(get_current_epoch(state)):
        return

    validator.exit_epoch = get_entry_exit_effect_epoch(get_current_epoch(state))
```

#### `penalize_validator`

```python
def penalize_validator(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Penalize the validator of the given ``index``.
    Note that this function mutates ``state``.
    """
    exit_validator(state, index)
    validator = state.validator_registry[index]
    state.latest_penalized_balances[get_current_epoch(state) % LATEST_PENALIZED_EXIT_LENGTH] += get_effective_balance(state, index)

    whistleblower_index = get_beacon_proposer_index(state, state.slot)
    whistleblower_reward = get_effective_balance(state, index) // WHISTLEBLOWER_REWARD_QUOTIENT
    state.validator_balances[whistleblower_index] += whistleblower_reward
    state.validator_balances[index] -= whistleblower_reward
    validator.penalized_epoch = get_current_epoch(state)
```

#### `prepare_validator_for_withdrawal`

```python
def prepare_validator_for_withdrawal(state: BeaconState, index: ValidatorIndex) -> None:
    """
    Set the validator with the given ``index`` with ``WITHDRAWABLE`` flag.
    Note that this function mutates ``state``.
    """
    validator = state.validator_registry[index]
    validator.status_flags |= WITHDRAWABLE
```

## Ethereum 1.0 deposit contract

The initial deployment phases of Ethereum 2.0 are implemented without consensus changes to Ethereum 1.0. A deposit contract at address `DEPOSIT_CONTRACT_ADDRESS` is added to Ethereum 1.0 for deposits of ETH to the beacon chain. Validator balances will be withdrawable to the shards in phase 2, i.e. when the EVM2.0 is deployed and the shards have state.

### Deposit arguments

The deposit contract has a single `deposit` function which takes as argument a SimpleSerialize'd `DepositInput`.

### Withdrawal credentials

One of the `DepositInput` fields is `withdrawal_credentials`. It is a commitment to credentials for withdrawals to shards. The first byte of `withdrawal_credentials` is a version number. As of now the only expected format is as follows:

* `withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX_BYTE`
* `withdrawal_credentials[1:] == hash(withdrawal_pubkey)[1:]` where `withdrawal_pubkey` is a BLS pubkey

The private key corresponding to `withdrawal_pubkey` will be required to initiate a withdrawal. It can be stored separately until a withdrawal is required, e.g. in cold storage.

### `Deposit` logs

Every Ethereum 1.0 deposit, of size between `MIN_DEPOSIT_AMOUNT` and `MAX_DEPOSIT_AMOUNT`, emits a `Deposit` log for consumption by the beacon chain. The deposit contract does little validation, pushing most of the validator onboarding logic to the beacon chain. In particular, the proof of possession (a BLS12 signature) is not verified by the deposit contract.

### `ChainStart` log

When sufficiently many full deposits have been made the deposit contract emits the `ChainStart` log. The beacon chain state may then be initialized by calling the `get_initial_beacon_state` function (defined below) where:

* `genesis_time` equals `time` in the `ChainStart` log
* `latest_eth1_data.deposit_root` equals `deposit_root` in the `ChainStart` log, and `latest_eth1_data.block_hash` equals the hash of the block that included the log
* `initial_validator_deposits` is a list of `Deposit` objects built according to the `Deposit` logs up to the deposit that triggered the `ChainStart` log, processed in the order in which they were emitted (oldest to newest)

### Vyper code

The source for the Vyper contract lives in a [separate repository](https://github.com/ethereum/deposit_contract) at [https://github.com/ethereum/deposit_contract/blob/master/deposit_contract/contracts/validator_registration.v.py](https://github.com/ethereum/deposit_contract/blob/master/deposit_contract/contracts/validator_registration.v.py).

Note: to save ~10x on gas this contract uses a somewhat unintuitive progressive Merkle root calculation algo that requires only O(log(n)) storage. See https://github.com/ethereum/research/blob/master/beacon_chain_impl/progressive_merkle_tree.py for an implementation of the same algo in python tested for correctness.

For convenience, we provide the interface to the contract here:

* `__init__()`: initializes the contract
* `get_deposit_root() -> bytes32`: returns the current root of the deposit tree
* `deposit(bytes[512])`: adds a deposit instance to the deposit tree, incorporating the input argument and the value transferred in the given call. Note: the amount of value transferred *must* be within `MIN_DEPOSIT_AMOUNT` and `MAX_DEPOSIT_AMOUNT`, inclusive. Each of these constants are specified in units of Gwei.

## On startup

A valid block with slot `GENESIS_SLOT` (a "genesis block") has the following values. Other validity rules (e.g. requiring a signature) do not apply.

```python
{
    slot=GENESIS_SLOT,
    parent_root=ZERO_HASH,
    state_root=STARTUP_STATE_ROOT,
    randao_reveal=EMPTY_SIGNATURE,
    eth1_data=Eth1Data(
        deposit_root=ZERO_HASH,
        block_hash=ZERO_HASH
    ),
    signature=EMPTY_SIGNATURE,
    body=BeaconBlockBody(
        proposer_slashings=[],
        attester_slashings=[],
        attestations=[],
        deposits=[],
        exits=[],
    ),
}
```

`STARTUP_STATE_ROOT` (in the above "genesis block") is generated from the `get_initial_beacon_state` function below. When enough full deposits have been made to the deposit contract and the `ChainStart` log has been emitted, `get_initial_beacon_state` will execute to compute the `hash_tree_root` of `BeaconState`.

```python
def get_initial_beacon_state(initial_validator_deposits: List[Deposit],
                             genesis_time: int,
                             latest_eth1_data: Eth1Data) -> BeaconState:
    """
    Get the initial ``BeaconState``.
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
        validator_balances=[],
        validator_registry_update_epoch=GENESIS_EPOCH,

        # Randomness and committees
        latest_randao_mixes=[ZERO_HASH for _ in range(LATEST_RANDAO_MIXES_LENGTH)],
        previous_epoch_start_shard=GENESIS_START_SHARD,
        current_epoch_start_shard=GENESIS_START_SHARD,
        previous_calculation_epoch=GENESIS_EPOCH,
        current_calculation_epoch=GENESIS_EPOCH,
        previous_epoch_seed=ZERO_HASH,
        current_epoch_seed=ZERO_HASH,

        # Finality
        previous_justified_epoch=GENESIS_EPOCH,
        justified_epoch=GENESIS_EPOCH,
        justification_bitfield=0,
        finalized_epoch=GENESIS_EPOCH,

        # Recent state
        latest_crosslinks=[Crosslink(epoch=GENESIS_EPOCH, shard_block_root=ZERO_HASH) for _ in range(SHARD_COUNT)],
        latest_block_roots=[ZERO_HASH for _ in range(LATEST_BLOCK_ROOTS_LENGTH)],
        latest_index_roots=[ZERO_HASH for _ in range(LATEST_INDEX_ROOTS_LENGTH)],
        latest_penalized_balances=[0 for _ in range(LATEST_PENALIZED_EXIT_LENGTH)],
        latest_attestations=[],
        batched_block_roots=[],

        # Ethereum 1.0 chain data
        latest_eth1_data=latest_eth1_data,
        eth1_data_votes=[],
    )

    # Process initial deposits
    for deposit in initial_validator_deposits:
        process_deposit(
            state=state,
            pubkey=deposit.deposit_data.deposit_input.pubkey,
            amount=deposit.deposit_data.amount,
            proof_of_possession=deposit.deposit_data.deposit_input.proof_of_possession,
            withdrawal_credentials=deposit.deposit_data.deposit_input.withdrawal_credentials,
        )

    # Process initial activations
    for validator_index, _ in enumerate(state.validator_registry):
        if get_effective_balance(state, validator_index) >= MAX_DEPOSIT_AMOUNT:
            activate_validator(state, validator_index, is_genesis=True)

    genesis_active_index_root = hash_tree_root(get_active_validator_indices(state.validator_registry, GENESIS_EPOCH))
    for index in range(LATEST_INDEX_ROOTS_LENGTH):
        state.latest_index_roots[index] = genesis_active_index_root
    state.current_epoch_seed = generate_seed(state, GENESIS_EPOCH)

    return state
```

## Beacon chain processing

The beacon chain is the system chain for Ethereum 2.0. The main responsibilities of the beacon chain are:

* Store and maintain the registry of [validators](#dfn-validator)
* Process crosslinks (see above)
* Process its per-block consensus, as well as the finality gadget

Processing the beacon chain is similar to processing the Ethereum 1.0 chain. Clients download and process blocks, and maintain a view of what is the current "canonical chain", terminating at the current "head". However, because of the beacon chain's relationship with Ethereum 1.0, and because it is a proof-of-stake chain, there are differences.

For a beacon chain block, `block`, to be processed by a node, the following conditions must be met:

* The parent block with root `block.parent_root` has been processed and accepted.
* An Ethereum 1.0 block pointed to by the `state.latest_eth1_data.block_hash` has been processed and accepted.
* The node's local clock time is greater than or equal to `state.genesis_time + block.slot * SLOT_DURATION`.

If these conditions are not met, the client should delay processing the beacon block until the conditions are all satisfied.

Beacon block production is significantly different because of the proof of stake mechanism. A client simply checks what it thinks is the canonical chain when it should create a block, and looks up what its slot number is; when the slot arrives, it either proposes or attests to a block as required. Note that this requires each node to have a clock that is roughly (i.e. within `SLOT_DURATION` seconds) synchronized with the other nodes.

### Beacon chain fork choice rule

The beacon chain fork choice rule is a hybrid that combines justification and finality with Latest Message Driven (LMD) Greediest Heaviest Observed SubTree (GHOST). At any point in time a [validator](#dfn-validator) `v` subjectively calculates the beacon chain head as follows.

* Abstractly define `Store` as the type of storage object for the chain data and `store` be the set of attestations and blocks that the [validator](#dfn-validator) `v` has observed and verified (in particular, block ancestors must be recursively verified). Attestations not yet included in any chain are still included in `store`.
* Let `finalized_head` be the finalized block with the highest epoch. (A block `B` is finalized if there is a descendant of `B` in `store` the processing of which sets `B` as finalized.)
* Let `justified_head` be the descendant of `finalized_head` with the highest epoch that has been justified for at least 1 epoch. (A block `B` is justified if there is a descendant of `B` in `store` the processing of which sets `B` as justified.) If no such descendant exists set `justified_head` to `finalized_head`.
* Let `get_ancestor(store: Store, block: BeaconBlock, slot: SlotNumber) -> BeaconBlock` be the ancestor of `block` with slot number `slot`. The `get_ancestor` function can be defined recursively as:

```python
def get_ancestor(store: Store, block: BeaconBlock, slot: SlotNumber) -> BeaconBlock:
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
    active_validator_indices = get_active_validator_indices(validators, start_state.slot)
    attestation_targets = [
        (validator_index, get_latest_attestation_target(store, validator_index))
        for validator_index in active_validator_indices
    ]

    def get_vote_count(block: BeaconBlock) -> int:
        return sum(
            get_effective_balance(start_state.validator_balances[validator_index]) // FORK_CHOICE_BALANCE_INCREMENT
            for validator_index, target in attestation_targets
            if get_ancestor(store, target, block.slot) == block
        )

    head = start_block
    while 1:
        children = get_children(store, head)
        if len(children) == 0:
            return head
        head = max(children, key=get_vote_count)
```

## Beacon chain state transition function

We now define the state transition function. At a high level the state transition is made up of three parts:

1. The per-slot transitions, which happens at the start of every slot.
2. The per-block transitions, which happens at every block.
3. The per-epoch transitions, which happens at the end of the last slot of every epoch (i.e. `(state.slot + 1) % EPOCH_LENGTH == 0`).

The per-slot transitions focus on the slot counter and block roots records updates; the per-block transitions generally focus on verifying aggregate signatures and saving temporary records relating to the per-block activity in the `BeaconState`; the per-epoch transitions focus on the [validator](#dfn-validator) registry, including adjusting balances and activating and exiting [validators](#dfn-validator), as well as processing crosslinks and managing block justification/finalization.

_Note_: If there are skipped slots between a block and its parent block, run the steps in the [per-slot](#per-slot-processing) and [per-epoch](#per-epoch-processing) sections once for each skipped slot and then once for the slot containing the new block.

### Per-slot processing

Below are the processing steps that happen at every slot.

#### Slot

* Set `state.slot += 1`.

#### Block roots

* Let `previous_block_root` be the `hash_tree_root` of the previous beacon block processed in the chain.
* Set `state.latest_block_roots[(state.slot - 1) % LATEST_BLOCK_ROOTS_LENGTH] = previous_block_root`.
* If `state.slot % LATEST_BLOCK_ROOTS_LENGTH == 0` append `merkle_root(state.latest_block_roots)` to `state.batched_block_roots`.

### Per-block processing

Below are the processing steps that happen at every `block`.

#### Slot

* Verify that `block.slot == state.slot`.

#### Proposer signature

* Let `block_without_signature_root` be the `hash_tree_root` of `block` where `block.signature` is set to `EMPTY_SIGNATURE`.
* Let `proposal_root = hash_tree_root(ProposalSignedData(state.slot, BEACON_CHAIN_SHARD_NUMBER, block_without_signature_root))`.
* Verify that `bls_verify(pubkey=state.validator_registry[get_beacon_proposer_index(state, state.slot)].pubkey, message_hash=proposal_root, signature=block.signature, domain=get_domain(state.fork, get_current_epoch(state), DOMAIN_PROPOSAL))`.

#### RANDAO

* Let `proposer = state.validator_registry[get_beacon_proposer_index(state, state.slot)]`.
* Verify that `bls_verify(pubkey=proposer.pubkey, message_hash=int_to_bytes32(get_current_epoch(state)), signature=block.randao_reveal, domain=get_domain(state.fork, get_current_epoch(state), DOMAIN_RANDAO))`.
* Set `state.latest_randao_mixes[get_current_epoch(state) % LATEST_RANDAO_MIXES_LENGTH] = xor(get_randao_mix(state, get_current_epoch(state)), hash(block.randao_reveal))`.

#### Eth1 data

* If there exists an `eth1_data_vote` in `states.eth1_data_votes` for which `eth1_data_vote.eth1_data == block.eth1_data` (there will be at most one), set `eth1_data_vote.vote_count += 1`.
* Otherwise, append to `state.eth1_data_votes` a new `Eth1DataVote(eth1_data=block.eth1_data, vote_count=1)`.

#### Operations

##### Proposer slashings

Verify that `len(block.body.proposer_slashings) <= MAX_PROPOSER_SLASHINGS`.

For each `proposer_slashing` in `block.body.proposer_slashings`:

* Let `proposer = state.validator_registry[proposer_slashing.proposer_index]`.
* Verify that `proposer_slashing.proposal_data_1.slot == proposer_slashing.proposal_data_2.slot`.
* Verify that `proposer_slashing.proposal_data_1.shard == proposer_slashing.proposal_data_2.shard`.
* Verify that `proposer_slashing.proposal_data_1.block_root != proposer_slashing.proposal_data_2.block_root`.
* Verify that `proposer.penalized_epoch > get_current_epoch(state)`.
* Verify that `bls_verify(pubkey=proposer.pubkey, message_hash=hash_tree_root(proposer_slashing.proposal_data_1), signature=proposer_slashing.proposal_signature_1, domain=get_domain(state.fork, slot_to_epoch(proposer_slashing.proposal_data_1.slot), DOMAIN_PROPOSAL))`.
* Verify that `bls_verify(pubkey=proposer.pubkey, message_hash=hash_tree_root(proposer_slashing.proposal_data_2), signature=proposer_slashing.proposal_signature_2, domain=get_domain(state.fork, slot_to_epoch(proposer_slashing.proposal_data_2.slot), DOMAIN_PROPOSAL))`.
* Run `penalize_validator(state, proposer_slashing.proposer_index)`.

##### Attester slashings

Verify that `len(block.body.attester_slashings) <= MAX_ATTESTER_SLASHINGS`.

For each `attester_slashing` in `block.body.attester_slashings`:

* Let `slashable_attestation_1 = attester_slashing.slashable_attestation_1`.
* Let `slashable_attestation_2 = attester_slashing.slashable_attestation_2`.
* Verify that `slashable_attestation_1.data != slashable_attestation_2.data`.
* Verify that `is_double_vote(slashable_attestation_1.data, slashable_attestation_2.data)` or `is_surround_vote(slashable_attestation_1.data, slashable_attestation_2.data)`.
* Verify that `verify_slashable_attestation(state, slashable_attestation_1)`.
* Verify that `verify_slashable_attestation(state, slashable_attestation_2)`.
* Let `slashable_indices = [index for index in slashable_attestation_1.validator_indices if index in slashable_attestation_2.validator_indices and state.validator_registry[index].penalized_epoch > get_current_epoch(state)]`.
* Verify that `len(slashable_indices) >= 1`.
* Run `penalize_validator(state, index)` for each `index` in `slashable_indices`.

##### Attestations

Verify that `len(block.body.attestations) <= MAX_ATTESTATIONS`.

For each `attestation` in `block.body.attestations`:

* Verify that `attestation.data.slot <= state.slot - MIN_ATTESTATION_INCLUSION_DELAY < attestation.data.slot + EPOCH_LENGTH`.
* Verify that `attestation.data.justified_epoch` is equal to `state.justified_epoch if attestation.data.slot >= get_epoch_start_slot(get_current_epoch(state)) else state.previous_justified_epoch`.
* Verify that `attestation.data.justified_block_root` is equal to `get_block_root(state, get_epoch_start_slot(attestation.data.justified_epoch))`.
* Verify that either (i) `state.latest_crosslinks[attestation.data.shard] == attestation.data.latest_crosslink` or (ii) `state.latest_crosslinks[attestation.data.shard] == Crosslink(shard_block_root=attestation.data.shard_block_root, epoch=slot_to_epoch(attestation.data.slot))`.
* Verify bitfields and aggregate signature:

```python
    assert attestation.custody_bitfield == b'\x00' * len(attestation.custody_bitfield)  # [TO BE REMOVED IN PHASE 1]
    assert attestation.aggregation_bitfield != b'\x00' * len(attestation.aggregation_bitfield)

    crosslink_committee = [
        committee for committee, shard in get_crosslink_committees_at_slot(state, attestation.data.slot)
        if shard == attestation.data.shard
    ][0]
    for i in range(len(crosslink_committee)):
        if get_bitfield_bit(attestation.aggregation_bitfield, i) == 0b0:
            assert get_bitfield_bit(attestation.custody_bitfield, i) == 0b0

    participants = get_attestation_participants(state, attestation.data, attestation.aggregation_bitfield)
    custody_bit_1_participants = get_attestation_participants(state, attestation.data, attestation.custody_bitfield)
    custody_bit_0_participants = [i in participants for i not in custody_bit_1_participants]

    assert bls_verify_multiple(
        pubkeys=[
            bls_aggregate_pubkeys([state.validator_registry[i].pubkey for i in custody_bit_0_participants]),
            bls_aggregate_pubkeys([state.validator_registry[i].pubkey for i in custody_bit_1_participants]),
        ],
        messages=[
            hash_tree_root(AttestationDataAndCustodyBit(data=attestation.data, custody_bit=0b0)),
            hash_tree_root(AttestationDataAndCustodyBit(data=attestation.data, custody_bit=0b1)),
        ],
        signature=attestation.aggregate_signature,
        domain=get_domain(state.fork, slot_to_epoch(attestation.data.slot), DOMAIN_ATTESTATION),
    )
```

* [TO BE REMOVED IN PHASE 1] Verify that `attestation.data.shard_block_root == ZERO_HASH`.
* Append `PendingAttestation(data=attestation.data, aggregation_bitfield=attestation.aggregation_bitfield, custody_bitfield=attestation.custody_bitfield, inclusion_slot=state.slot)` to `state.latest_attestations`.

##### Deposits

Verify that `len(block.body.deposits) <= MAX_DEPOSITS`.

[TODO: add logic to ensure that deposits from 1.0 chain are processed in order]
[TODO: update the call to `verify_merkle_branch` below if it needs to change after we process deposits in order]

For each `deposit` in `block.body.deposits`:

* Let `serialized_deposit_data` be the serialized form of `deposit.deposit_data`. It should be 8 bytes for `deposit_data.amount` followed by 8 bytes for `deposit_data.timestamp` and then the `DepositInput` bytes. That is, it should match `deposit_data` in the [Ethereum 1.0 deposit contract](#ethereum-10-deposit-contract) of which the hash was placed into the Merkle tree.
* Verify that `verify_merkle_branch(hash(serialized_deposit_data), deposit.branch, DEPOSIT_CONTRACT_TREE_DEPTH, deposit.index, state.latest_eth1_data.deposit_root)` is `True`.

```python
def verify_merkle_branch(leaf: Bytes32, branch: List[Bytes32], depth: int, index: int, root: Bytes32) -> bool:
    """
    Verify that the given ``leaf`` is on the merkle branch ``branch``.
    """
    value = leaf
    for i in range(depth):
        if index // (2**i) % 2:
            value = hash(branch[i] + value)
        else:
            value = hash(value + branch[i])
    return value == root
```

* Run the following:

```python
process_deposit(
    state=state,
    pubkey=deposit.deposit_data.deposit_input.pubkey,
    amount=deposit.deposit_data.amount,
    proof_of_possession=deposit.deposit_data.deposit_input.proof_of_possession,
    withdrawal_credentials=deposit.deposit_data.deposit_input.withdrawal_credentials,
)
```

##### Exits

Verify that `len(block.body.exits) <= MAX_EXITS`.

For each `exit` in `block.body.exits`:

* Let `validator = state.validator_registry[exit.validator_index]`.
* Verify that `validator.exit_epoch > get_entry_exit_effect_epoch(get_current_epoch(state))`.
* Verify that `get_current_epoch(state) >= exit.epoch`.
* Let `exit_message = hash_tree_root(Exit(epoch=exit.epoch, validator_index=exit.validator_index, signature=EMPTY_SIGNATURE))`.
* Verify that `bls_verify(pubkey=validator.pubkey, message_hash=exit_message, signature=exit.signature, domain=get_domain(state.fork, exit.epoch, DOMAIN_EXIT))`.
* Run `initiate_validator_exit(state, exit.validator_index)`.

### Per-epoch processing

The steps below happen when `(state.slot + 1) % EPOCH_LENGTH == 0`.

#### Helpers

* Let `current_epoch = get_current_epoch(state)`.
* Let `previous_epoch = get_previous_epoch(state)`.
* Let `next_epoch = current_epoch + 1`.

[Validators](#dfn-Validator) attesting during the current epoch:

* Let `current_total_balance = get_total_balance(state, get_active_validator_indices(state.validator_registry, current_epoch))`.
* Let `current_epoch_attestations = [a for a in state.latest_attestations if current_epoch == slot_to_epoch(a.data.slot)]`. (Note: this is the set of attestations of slots in the epoch `current_epoch`, _not_ attestations that got included in the chain during the epoch `current_epoch`.)
* Validators justifying the epoch boundary block at the start of the current epoch:
  * Let `current_epoch_boundary_attestations = [a for a in current_epoch_attestations if a.data.epoch_boundary_root == get_block_root(state, get_epoch_start_slot(current_epoch)) and a.data.justified_epoch == state.justified_epoch]`.
  * Let `current_epoch_boundary_attester_indices` be the union of the [validator](#dfn-validator) index sets given by `[get_attestation_participants(state, a.data, a.aggregation_bitfield) for a in current_epoch_boundary_attestations]`.
  * Let `current_epoch_boundary_attesting_balance = get_total_balance(state, current_epoch_boundary_attester_indices)`.

[Validators](#dfn-Validator) attesting during the previous epoch:

* Let `previous_total_balance = get_total_balance(state, get_active_validator_indices(state.validator_registry, previous_epoch))`.
* Validators that made an attestation during the previous epoch:
  * Let `previous_epoch_attestations = [a for a in state.latest_attestations if previous_epoch == slot_to_epoch(a.data.slot)]`.
  * Let `previous_epoch_attester_indices` be the union of the validator index sets given by `[get_attestation_participants(state, a.data, a.aggregation_bitfield) for a in previous_epoch_attestations]`.
* Validators targeting the previous justified slot:
  * Let `previous_epoch_justified_attestations = [a for a in current_epoch_attestations + previous_epoch_attestations if a.data.justified_epoch == state.previous_justified_epoch]`.
  * Let `previous_epoch_justified_attester_indices` be the union of the validator index sets given by `[get_attestation_participants(state, a.data, a.aggregation_bitfield) for a in previous_epoch_justified_attestations]`.
  * Let `previous_epoch_justified_attesting_balance = get_total_balance(state, previous_epoch_justified_attester_indices)`.
* Validators justifying the epoch boundary block at the start of the previous epoch:
  * Let `previous_epoch_boundary_attestations = [a for a in previous_epoch_justified_attestations if a.data.epoch_boundary_root == get_block_root(state, get_epoch_start_slot(previous_epoch))]`.
  * Let `previous_epoch_boundary_attester_indices` be the union of the validator index sets given by `[get_attestation_participants(state, a.data, a.aggregation_bitfield) for a in previous_epoch_boundary_attestations]`.
  * Let `previous_epoch_boundary_attesting_balance = get_total_balance(state, previous_epoch_boundary_attester_indices)`.
* Validators attesting to the expected beacon chain head during the previous epoch:
  * Let `previous_epoch_head_attestations = [a for a in previous_epoch_attestations if a.data.beacon_block_root == get_block_root(state, a.data.slot)]`.
  * Let `previous_epoch_head_attester_indices` be the union of the validator index sets given by `[get_attestation_participants(state, a.data, a.aggregation_bitfield) for a in previous_epoch_head_attestations]`.
  * Let `previous_epoch_head_attesting_balance = get_total_balance(state, previous_epoch_head_attester_indices)`.

**Note**: `previous_total_balance` and `previous_epoch_boundary_attesting_balance` balance might be marginally different than the actual balances during previous epoch transition. Due to the tight bound on validator churn each epoch and small per-epoch rewards/penalties, the potential balance difference is very low and only marginally affects consensus safety.

For every `slot in range(get_epoch_start_slot(previous_epoch), get_epoch_start_slot(next_epoch))`, let `crosslink_committees_at_slot = get_crosslink_committees_at_slot(state, slot)`. For every `(crosslink_committee, shard)` in `crosslink_committees_at_slot`, compute:

* Let `shard_block_root` be `state.latest_crosslinks[shard].shard_block_root`
* Let `attesting_validator_indices(crosslink_committee, shard_block_root)` be the union of the [validator](#dfn-validator) index sets given by `[get_attestation_participants(state, a.data, a.aggregation_bitfield) for a in current_epoch_attestations + previous_epoch_attestations if a.data.shard == shard and a.data.shard_block_root == shard_block_root]`.
* Let `winning_root(crosslink_committee)` be equal to the value of `shard_block_root` such that `get_total_balance(state, attesting_validator_indices(crosslink_committee, shard_block_root))` is maximized (ties broken by favoring lower `shard_block_root` values).
* Let `attesting_validators(crosslink_committee)` be equal to `attesting_validator_indices(crosslink_committee, winning_root(crosslink_committee))` for convenience.
* Let `total_attesting_balance(crosslink_committee) = get_total_balance(state, attesting_validators(crosslink_committee))`.

Define the following helpers to process attestation inclusion rewards and inclusion distance reward/penalty. For every attestation `a` in `previous_epoch_attestations`:

* Let `inclusion_slot(state, index) = a.inclusion_slot` for the attestation `a` where `index` is in `get_attestation_participants(state, a.data, a.aggregation_bitfield)`. If multiple attestations are applicable, the attestation with lowest `inclusion_slot` is considered.
* Let `inclusion_distance(state, index) = a.inclusion_slot - a.data.slot` where `a` is the above attestation.

#### Eth1 data

If `next_epoch % ETH1_DATA_VOTING_PERIOD == 0`:

* If `eth1_data_vote.vote_count * 2 > ETH1_DATA_VOTING_PERIOD * EPOCH_LENGTH` for some `eth1_data_vote` in `state.eth1_data_votes` (ie. more than half the votes in this voting period were for that value), set `state.latest_eth1_data = eth1_data_vote.eth1_data`.
* Set `state.eth1_data_votes = []`.

#### Justification

First, update the justification bitfield:

* Let `new_justified_epoch = state.justified_epoch`.
* Set `state.justification_bitfield = state.justification_bitfield << 1`.
* Set `state.justification_bitfield |= 2` and `new_justified_epoch = previous_epoch` if `3 * previous_epoch_boundary_attesting_balance >= 2 * previous_total_balance`.
* Set `state.justification_bitfield |= 1` and `new_justified_epoch = current_epoch` if `3 * current_epoch_boundary_attesting_balance >= 2 * current_total_balance`.

Next, update last finalized epoch if possible:

* Set `state.finalized_epoch = state.previous_justified_epoch` if `(state.justification_bitfield >> 1) % 8 == 0b111 and state.previous_justified_epoch == previous_epoch - 2`.
* Set `state.finalized_epoch = state.previous_justified_epoch` if `(state.justification_bitfield >> 1) % 4 == 0b11 and state.previous_justified_epoch == previous_epoch - 1`.
* Set `state.finalized_epoch = state.justified_epoch` if `(state.justification_bitfield >> 0) % 8 == 0b111 and state.justified_epoch == previous_epoch - 1`.
* Set `state.finalized_epoch = state.justified_epoch` if `(state.justification_bitfield >> 0) % 4 == 0b11 and state.justified_epoch == previous_epoch`.

Finally, update the following:

* Set `state.previous_justified_epoch = state.justified_epoch`.
* Set `state.justified_epoch = new_justified_epoch`.

#### Crosslinks

For every `slot in range(get_epoch_start_slot(previous_epoch), get_epoch_start_slot(next_epoch))`, let `crosslink_committees_at_slot = get_crosslink_committees_at_slot(state, slot)`. For every `(crosslink_committee, shard)` in `crosslink_committees_at_slot`, compute:

* Set `state.latest_crosslinks[shard] = Crosslink(epoch=slot_to_epoch(slot), shard_block_root=winning_root(crosslink_committee))` if `3 * total_attesting_balance(crosslink_committee) >= 2 * get_total_balance(crosslink_committee)`.

#### Rewards and penalties

First, we define some additional helpers:

* Let `base_reward_quotient = integer_squareroot(previous_total_balance) // BASE_REWARD_QUOTIENT`.
* Let `base_reward(state, index) = get_effective_balance(state, index) // base_reward_quotient // 5` for any validator with the given `index`.
* Let `inactivity_penalty(state, index, epochs_since_finality) = base_reward(state, index) + get_effective_balance(state, index) * epochs_since_finality // INACTIVITY_PENALTY_QUOTIENT // 2` for any validator with the given `index`.

##### Justification and finalization

Note: When applying penalties in the following balance recalculations implementers should make sure the `uint64` does not underflow.

* Let `epochs_since_finality = next_epoch - state.finalized_epoch`.

Case 1: `epochs_since_finality <= 4`:

* Expected FFG source:
  * Any [validator](#dfn-validator) `index` in `previous_epoch_justified_attester_indices` gains `base_reward(state, index) * previous_epoch_justified_attesting_balance // previous_total_balance`.
  * Any [active validator](#dfn-active-validator) `index` not in `previous_epoch_justified_attester_indices` loses `base_reward(state, index)`.
* Expected FFG target:
  * Any [validator](#dfn-validator) `index` in `previous_epoch_boundary_attester_indices` gains `base_reward(state, index) * previous_epoch_boundary_attesting_balance // previous_total_balance`.
  * Any [active validator](#dfn-active-validator) `index` not in `previous_epoch_boundary_attester_indices` loses `base_reward(state, index)`.
* Expected beacon chain head:
  * Any [validator](#dfn-validator) `index` in `previous_epoch_head_attester_indices` gains `base_reward(state, index) * previous_epoch_head_attesting_balance // previous_total_balance)`.
  * Any [active validator](#dfn-active-validator) `index` not in `previous_epoch_head_attester_indices` loses `base_reward(state, index)`.
* Inclusion distance:
  * Any [validator](#dfn-validator) `index` in `previous_epoch_attester_indices` gains `base_reward(state, index) * MIN_ATTESTATION_INCLUSION_DELAY // inclusion_distance(state, index)`

Case 2: `epochs_since_finality > 4`:

* Any [active validator](#dfn-active-validator) `index` not in `previous_epoch_justified_attester_indices`, loses `inactivity_penalty(state, index, epochs_since_finality)`.
* Any [active validator](#dfn-active-validator) `index` not in `previous_epoch_boundary_attester_indices`, loses `inactivity_penalty(state, index, epochs_since_finality)`.
* Any [active validator](#dfn-active-validator) `index` not in `previous_epoch_head_attester_indices`, loses `base_reward(state, index)`.
* Any [active_validator](#dfn-active-validator) `index` with `validator.penalized_epoch <= current_epoch`, loses `2 * inactivity_penalty(state, index, epochs_since_finality) + base_reward(state, index)`.
* Any [validator](#dfn-validator) `index` in `previous_epoch_attester_indices` loses `base_reward(state, index) - base_reward(state, index) * MIN_ATTESTATION_INCLUSION_DELAY // inclusion_distance(state, index)`

##### Attestation inclusion

For each `index` in `previous_epoch_attester_indices`, we determine the proposer `proposer_index = get_beacon_proposer_index(state, inclusion_slot(state, index))` and set `state.validator_balances[proposer_index] += base_reward(state, index) // INCLUDER_REWARD_QUOTIENT`.

##### Crosslinks

For every `slot in range(get_epoch_start_slot(previous_epoch), get_epoch_start_slot(current_epoch))`:

* Let `crosslink_committees_at_slot = get_crosslink_committees_at_slot(state, slot)`.
* For every `(crosslink_committee, shard)` in `crosslink_committees_at_slot`:
    * If `index in attesting_validators(crosslink_committee)`, `state.validator_balances[index] += base_reward(state, index) * total_attesting_balance(crosslink_committee) // get_total_balance(state, crosslink_committee))`.
    * If `index not in attesting_validators(crosslink_committee)`, `state.validator_balances[index] -= base_reward(state, index)`.

#### Ejections

* Run `process_ejections(state)`.

```python
def process_ejections(state: BeaconState) -> None:
    """
    Iterate through the validator registry
    and eject active validators with balance below ``EJECTION_BALANCE``.
    """
    for index in get_active_validator_indices(state.validator_registry, current_epoch(state)):
        if state.validator_balances[index] < EJECTION_BALANCE:
            exit_validator(state, index)
```

#### Validator registry and shuffling seed data

First, update the following:

* Set `state.previous_calculation_epoch = state.current_calculation_epoch`.
* Set `state.previous_epoch_start_shard = state.current_epoch_start_shard`.
* Set `state.previous_epoch_seed = state.current_epoch_seed`.

If the following are satisfied:

* `state.finalized_epoch > state.validator_registry_update_epoch`
* `state.latest_crosslinks[shard].epoch > state.validator_registry_update_epoch` for every shard number `shard` in `[(state.current_epoch_start_shard + i) % SHARD_COUNT for i in range(get_current_epoch_committee_count(state))]` (that is, for every shard in the current committees)

update the validator registry and associated fields by running

```python
def update_validator_registry(state: BeaconState) -> None:
    """
    Update validator registry.
    Note that this function mutates ``state``.
    """
    current_epoch = get_current_epoch(state)
    # The active validators
    active_validator_indices = get_active_validator_indices(state.validator_registry, current_epoch)
    # The total effective balance of active validators
    total_balance = get_total_balance(state, active_validator_indices)

    # The maximum balance churn in Gwei (for deposits and exits separately)
    max_balance_churn = max(
        MAX_DEPOSIT_AMOUNT,
        total_balance // (2 * MAX_BALANCE_CHURN_QUOTIENT)
    )

    # Activate validators within the allowable balance churn
    balance_churn = 0
    for index, validator in enumerate(state.validator_registry):
        if validator.activation_epoch > get_entry_exit_effect_epoch(current_epoch) and state.validator_balances[index] >= MAX_DEPOSIT_AMOUNT:
            # Check the balance churn would be within the allowance
            balance_churn += get_effective_balance(state, index)
            if balance_churn > max_balance_churn:
                break

            # Activate validator
            activate_validator(state, index, is_genesis=False)

    # Exit validators within the allowable balance churn
    balance_churn = 0
    for index, validator in enumerate(state.validator_registry):
        if validator.exit_epoch > get_entry_exit_effect_epoch(current_epoch) and validator.status_flags & INITIATED_EXIT:
            # Check the balance churn would be within the allowance
            balance_churn += get_effective_balance(state, index)
            if balance_churn > max_balance_churn:
                break

            # Exit validator
            exit_validator(state, index)

    state.validator_registry_update_epoch = current_epoch
```

and perform the following updates:

* Set `state.current_calculation_epoch = next_epoch`
* Set `state.current_epoch_start_shard = (state.current_epoch_start_shard + get_current_epoch_committee_count(state)) % SHARD_COUNT`
* Set `state.current_epoch_seed = generate_seed(state, state.current_calculation_epoch)`

If a validator registry update does _not_ happen do the following:

* Let `epochs_since_last_registry_update = current_epoch - state.validator_registry_update_epoch`.
* If `epochs_since_last_registry_update > 1` and `is_power_of_two(epochs_since_last_registry_update)`:
    * Set `state.current_calculation_epoch = next_epoch`.
    * Set `state.current_epoch_seed = generate_seed(state, state.current_calculation_epoch)`
    * _Note_ that `state.current_epoch_start_shard` is left unchanged.

**Invariant**: the active index root that is hashed into the shuffling seed actually is the `hash_tree_root` of the validator set that is used for that epoch.

Regardless of whether or not a validator set change happens, run the following:

```python
def process_penalties_and_exits(state: BeaconState) -> None:
    """
    Process the penalties and prepare the validators who are eligible to withdrawal.
    Note that this function mutates ``state``.
    """
    current_epoch = get_current_epoch(state)
    # The active validators
    active_validator_indices = get_active_validator_indices(state.validator_registry, current_epoch)
    # The total effective balance of active validators
    total_balance = sum(get_effective_balance(state, i) for i in active_validator_indices)

    for index, validator in enumerate(state.validator_registry):
        if current_epoch == validator.penalized_epoch + LATEST_PENALIZED_EXIT_LENGTH // 2:
            epoch_index = current_epoch % LATEST_PENALIZED_EXIT_LENGTH
            total_at_start = state.latest_penalized_balances[(epoch_index + 1) % LATEST_PENALIZED_EXIT_LENGTH]
            total_at_end = state.latest_penalized_balances[epoch_index]
            total_penalties = total_at_end - total_at_start
            penalty = get_effective_balance(state, index) * min(total_penalties * 3, total_balance) // total_balance
            state.validator_balances[index] -= penalty

    def eligible(index):
        validator = state.validator_registry[index]
        if validator.penalized_epoch <= current_epoch:
            penalized_withdrawal_epochs = LATEST_PENALIZED_EXIT_LENGTH // 2
            return current_epoch >= validator.penalized_epoch + penalized_withdrawal_epochs
        else:
            return current_epoch >= validator.exit_epoch + MIN_VALIDATOR_WITHDRAWAL_EPOCHS

    all_indices = list(range(len(state.validator_registry)))
    eligible_indices = filter(eligible, all_indices)
    # Sort in order of exit epoch, and validators that exit within the same epoch exit in order of validator index
    sorted_indices = sorted(eligible_indices, key=lambda index: state.validator_registry[index].exit_epoch)
    withdrawn_so_far = 0
    for index in sorted_indices:
        prepare_validator_for_withdrawal(state, index)
        withdrawn_so_far += 1
        if withdrawn_so_far >= MAX_WITHDRAWALS_PER_EPOCH:
            break
```

#### Final updates

* Set `state.latest_index_roots[(next_epoch + ENTRY_EXIT_DELAY) % LATEST_INDEX_ROOTS_LENGTH] = hash_tree_root(get_active_validator_indices(state, next_epoch + ENTRY_EXIT_DELAY))`.
* Set `state.latest_penalized_balances[(next_epoch) % LATEST_PENALIZED_EXIT_LENGTH] = state.latest_penalized_balances[current_epoch % LATEST_PENALIZED_EXIT_LENGTH]`.
* Set `state.latest_randao_mixes[next_epoch % LATEST_RANDAO_MIXES_LENGTH] = get_randao_mix(state, current_epoch)`.
* Remove any `attestation` in `state.latest_attestations` such that `slot_to_epoch(attestation.data.slot) < current_epoch`.

### State root verification

Verify `block.state_root == hash_tree_root(state)` if there exists a `block` for the slot being processed.

# References

This section is divided into Normative and Informative references.  Normative references are those that must be read in order to implement this specification, while Informative references are merely that, information.  An example of the former might be the details of a required consensus algorithm, and an example of the latter might be a pointer to research that demonstrates why a particular consensus algorithm might be better suited for inclusion in the standard than another.

## Normative

## Informative
<a id="ref-casper-ffg"></a> _**casper-ffg**_ </br> &nbsp; _Casper the Friendly Finality Gadget_. V. Buterin and V. Griffith. URL: https://arxiv.org/abs/1710.09437

<a id="ref-python-poc"></a> _**python-poc**_ </br> &nbsp; _Python proof-of-concept implementation_. Ethereum Foundation. URL: https://github.com/ethereum/beacon_chain

# Copyright
Copyright and related rights waived via [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
