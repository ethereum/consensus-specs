# Ethereum 2.0 Phase 0 -- Deposit Contract

**NOTICE**: This document is a work in progress for researchers and implementers.

## Table of contents
<!-- TOC -->

- [Ethereum 2.0 Phase 0 -- Deposit Contract](#ethereum-20-phase-0----deposit-contract)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
        - [`Eth2Genesis`](#eth2-genesis)
        - [Genesis state](#genesis-state)
        - [Genesis block](#genesis-block)

<!-- /TOC -->

## Introduction

This document represents is the specification for the beacon chain genesis state and block as part of Ethereum 2.0 phase 0.

## `Eth2Genesis`

When enough full deposits have been made to the deposit contract, an `Eth2Genesis` log is emitted triggering the genesis of the beacon chain. Let:

* `eth2genesis` be the object corresponding to `Eth2Genesis`
* `genesis_eth1_data` be object of type `Eth1Data` where
    * `genesis_eth1_data.deposit_root = eth2genesis.deposit_root`
    * `genesis_eth1_data.deposit_count = eth2genesis.deposit_count`
    * `genesis_eth1_data.block_hash` is the hash of the Ethereum 1.0 block that emitted the `Eth2Genesis` log
* `genesis_deposits` be the object of type `List[Deposit]` with deposits ordered chronologically up to and including the deposit that triggered the `Eth2Genesis` log

## Genesis state

Let `genesis_state = get_genesis_beacon_state(eth2genesis.genesis_time, genesis_eth1_data, genesis_validator_deposits, genesis_deposits)`.

```python
def get_genesis_beacon_state(genesis_time: int, eth1_data: Eth1Data, deposits: List[Deposit]) -> BeaconState:
    state = BeaconState(genesis_time=genesis_time, latest_eth1_data=genesis_eth1_data)

    # Process genesis deposits
    for deposit in deposits:
        process_deposit(state, deposit)

    # Process genesis activations
    for validator in state.validator_registry:
        if validator.effective_balance >= MAX_EFFECTIVE_BALANCE:
            validator.activation_eligibility_epoch = GENESIS_EPOCH
            validator.activation_epoch = GENESIS_EPOCH

    # Populate latest_active_index_roots
    genesis_active_index_root = hash_tree_root(get_active_validator_indices(state, GENESIS_EPOCH))
    for index in range(LATEST_ACTIVE_INDEX_ROOTS_LENGTH):
        state.latest_active_index_roots[index] = genesis_active_index_root

    return state
```

## Genesis block

Let `genesis_block = BeaconBlock(state_root=hash_tree_root(genesis_state))`.
