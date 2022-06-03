# EIP-4844 -- The Beacon Chain

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
  - [Blob](#blob)
  - [Crypto](#crypto)
  - [Domain types](#domain-types)
- [Preset](#preset)
  - [Trusted setup](#trusted-setup)
  - [Execution](#execution)
- [Configuration](#configuration)
- [Containers](#containers)
  - [Extended containers](#extended-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
- [Helper functions](#helper-functions)
  - [KZG core](#kzg-core)
    - [`blob_to_kzg`](#blob_to_kzg)
    - [`kzg_to_versioned_hash`](#kzg_to_versioned_hash)
  - [Misc](#misc)
    - [`tx_peek_blob_versioned_hashes`](#tx_peek_blob_versioned_hashes)
    - [`verify_kzgs_against_transactions`](#verify_kzgs_against_transactions)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Blob KZGs](#blob-kzgs)
- [Testing](#testing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This upgrade adds blobs to the beacon chain as part of EIP-4844.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `BLSFieldElement` | `uint256` | `x < BLS_MODULUS` |
| `Blob` | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_BLOB]` | |
| `VersionedHash` | `Bytes32` | |
| `KZGCommitment` | `Bytes48` | Same as BLS standard "is valid pubkey" check but also allows `0x00..00` for point-at-infinity |
| `G2Point` | `Bytes96` | |

## Constants

### Blob

| Name | Value |
| - | - |
| `BLOB_TX_TYPE` | `uint8(0x05)` |
| `FIELD_ELEMENTS_PER_BLOB` | `uint64(4096)` |
| `BLOB_COMMITMENT_VERSION_KZG` | `Bytes1(0x01)` | 

### Crypto

| Name | Value |
| - | - |
| `BLS_MODULUS` | `52435875175126190479447740508185965837690552500527637822603658699938581184513` |

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_BLOBS_SIDECAR` | `DomainType('0x0a000000')` |

## Preset

### Trusted setup

The trusted setup is part of the preset: during testing a `minimal` insecure variant may be used,
but reusing the `mainnet` settings in public networks is a critical security requirement.

| Name | Value |
| - | - |
| `KZG_SETUP_G2` | `Vector[G2Point, FIELD_ELEMENTS_PER_BLOB]`, contents TBD |
| `KZG_SETUP_LAGRANGE` | `Vector[KZGCommitment, FIELD_ELEMENTS_PER_BLOB]`, contents TBD |

### Execution

| Name | Value |
| - | - |
| `MAX_BLOBS_PER_BLOCK` | `uint64(2**4)` (= 16) |

## Configuration


## Containers

### Extended containers

#### `BeaconBlockBody`

Note: `BeaconBlock` and `SignedBeaconBlock` types are updated indirectly.

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
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    # Execution
    execution_payload: ExecutionPayload 
    blob_kzgs: List[KZGCommitment, MAX_BLOBS_PER_BLOCK]  # [New in EIP-4844]
```

## Helper functions

### KZG core

KZG core functions. These are also defined in EIP-4844 execution specs.

#### `blob_to_kzg`

```python
def blob_to_kzg(blob: Blob) -> KZGCommitment:
    computed_kzg = bls.Z1
    for value, point_kzg in zip(blob, KZG_SETUP_LAGRANGE):
        assert value < BLS_MODULUS
        computed_kzg = bls.add(
            computed_kzg,
            bls.multiply(point_kzg, value)
        )
    return computed_kzg
```

#### `kzg_to_versioned_hash`

```python
def kzg_to_versioned_hash(kzg: KZGCommitment) -> VersionedHash:
    return BLOB_COMMITMENT_VERSION_KZG + hash(kzg)[1:]
```

### Misc

#### `tx_peek_blob_versioned_hashes`

This function retrieves the hashes from the `SignedBlobTransaction` as defined in EIP-4844, using SSZ offsets.
Offsets are little-endian `uint32` values, as defined in the [SSZ specification](../../ssz/simple-serialize.md).

```python
def tx_peek_blob_versioned_hashes(opaque_tx: Transaction) -> Sequence[VersionedHash]:
    assert opaque_tx[0] == BLOB_TX_TYPE
    message_offset = 1 + uint32.decode_bytes(opaque_tx[1:5])
    # field offset: 32 + 8 + 32 + 32 + 8 + 4 + 32 + 4 + 4 = 156
    blob_versioned_hashes_offset = uint32.decode_bytes(opaque_tx[(message_offset + 156):(message_offset + 160)])
    return [VersionedHash(opaque_tx[x:(x + 32)]) for x in range(blob_versioned_hashes_offset, len(opaque_tx), 32)]
```

#### `verify_kzgs_against_transactions`

```python
def verify_kzgs_against_transactions(transactions: Sequence[Transaction], blob_kzgs: Sequence[KZGCommitment]) -> bool:
    all_versioned_hashes = []
    for tx in transactions:
        if tx[0] == BLOB_TX_TYPE:
            all_versioned_hashes.extend(tx_peek_blob_versioned_hashes(tx))
    return all_versioned_hashes == [kzg_to_versioned_hash(kzg) for kzg in blob_kzgs]
```

## Beacon chain state transition function

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    if is_execution_enabled(state, block.body):
        process_execution_payload(state, block.body.execution_payload, EXECUTION_ENGINE)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    process_sync_aggregate(state, block.body.sync_aggregate)
    process_blob_kzgs(state, block.body)  # [New in EIP-4844]
```

#### Blob KZGs

```python
def process_blob_kzgs(state: BeaconState, body: BeaconBlockBody):
    assert verify_kzgs_against_transactions(body.execution_payload.transactions, body.blob_kzgs)
```

## Testing

*Note*: The function `initialize_beacon_state_from_eth1` is modified for pure EIP-4844 testing only.

The `BeaconState` initialization is unchanged, except for the use of the updated `eip4844.BeaconBlockBody` type 
when initializing the first body-root.

```python
def initialize_beacon_state_from_eth1(eth1_block_hash: Hash32,
                                      eth1_timestamp: uint64,
                                      deposits: Sequence[Deposit],
                                      execution_payload_header: ExecutionPayloadHeader=ExecutionPayloadHeader()
                                      ) -> BeaconState:
    fork = Fork(
        previous_version=EIP4844_FORK_VERSION,  # [Modified in EIP-4844] for testing only
        current_version=EIP4844_FORK_VERSION,  # [Modified in EIP-4844]
        epoch=GENESIS_EPOCH,
    )
    state = BeaconState(
        genesis_time=eth1_timestamp + GENESIS_DELAY,
        fork=fork,
        eth1_data=Eth1Data(block_hash=eth1_block_hash, deposit_count=uint64(len(deposits))),
        latest_block_header=BeaconBlockHeader(body_root=hash_tree_root(BeaconBlockBody())),
        randao_mixes=[eth1_block_hash] * EPOCHS_PER_HISTORICAL_VECTOR,  # Seed RANDAO with Eth1 entropy
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

    # Set genesis validators root for domain separation and chain versioning
    state.genesis_validators_root = hash_tree_root(state.validators)

    # Fill in sync committees
    # Note: A duplicate committee is assigned for the current and next committee at genesis
    state.current_sync_committee = get_next_sync_committee(state)
    state.next_sync_committee = get_next_sync_committee(state)

    # Initialize the execution payload header
    # If empty, will initialize a chain that has not yet gone through the Merge transition
    state.latest_execution_payload_header = execution_payload_header

    return state
```
