# Ethereum 2.0 Phase 0 -- Deposit Contract

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->

- [Ethereum 2.0 Phase 0 -- Deposit Contract](#ethereum-20-phase-0----deposit-contract)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Constants](#constants)
        - [Contract](#contract)
    - [Ethereum 1.0 deposit contract](#ethereum-10-deposit-contract)
        - [Arguments](#arguments)
            - [Withdrawal credentials](#withdrawal-credentials)
            - [Amount](#amount)
    - [Event logs](#event-logs)
        - [`Deposit` logs](#deposit-logs)
    - [Vyper code](#vyper-code)

<!-- /TOC -->

## Introduction

This document represents the specification for the beacon chain deposit contract, part of Ethereum 2.0 Phase 0.

## Constants

### Contract

| Name | Value |
| - | - |
| `DEPOSIT_CONTRACT_ADDRESS` | **TBD** |
| `DEPOSIT_CONTRACT_TREE_DEPTH` | `2**5` (= 32) |

## Ethereum 1.0 deposit contract

The initial deployment phases of Ethereum 2.0 are implemented without consensus changes to Ethereum 1.0. A deposit contract at address `DEPOSIT_CONTRACT_ADDRESS` is added to Ethereum 1.0 for deposits of ETH to the beacon chain. Validator balances will be withdrawable to the shards in Phase 2 (i.e. when the EVM 2.0 is deployed and the shards have state).

### Arguments

The deposit contract has a `deposit` function which takes the amount in Ethereum 1.0 transaction, and arguments `pubkey: bytes[48], withdrawal_credentials: bytes[32], signature: bytes[96]` corresponding to `DepositData`.

#### Withdrawal credentials

One of the `DepositData` fields is `withdrawal_credentials`. It is a commitment to credentials for withdrawals to shards. The first byte of `withdrawal_credentials` is a version number. As of now, the only expected format is as follows:

* `withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX_BYTE`
* `withdrawal_credentials[1:] == hash(withdrawal_pubkey)[1:]` where `withdrawal_pubkey` is a BLS pubkey

The private key corresponding to `withdrawal_pubkey` will be required to initiate a withdrawal. It can be stored separately until a withdrawal is required, e.g. in cold storage.

#### Amount

* A valid deposit amount should be at least `MIN_DEPOSIT_AMOUNT` in Gwei.

## Event logs

### `Deposit` logs

Every Ethereum 1.0 deposit, of size at least `MIN_DEPOSIT_AMOUNT`, emits a `Deposit` log for consumption by the beacon chain. The deposit contract does little validation, pushing most of the validator onboarding logic to the beacon chain. In particular, the proof of possession (a BLS12-381 signature) is not verified by the deposit contract.

## Vyper code

The source for the Vyper contract lives in a [separate repository](https://github.com/ethereum/deposit_contract) at [https://github.com/ethereum/deposit_contract/blob/master/deposit_contract/contracts/validator_registration.v.py](https://github.com/ethereum/deposit_contract/blob/master/deposit_contract/contracts/validator_registration.v.py).

*Note*: To save ~10x on gas, this contract uses a somewhat unintuitive progressive Merkle root calculation algo that requires only O(log(n)) storage. See https://github.com/ethereum/research/blob/master/beacon_chain_impl/progressive_merkle_tree.py for an implementation of the same algo in Python tested for correctness.

For convenience, we provide the interface to the contract here:

* `__init__()`: initializes the contract
* `get_deposit_root() -> bytes32`: returns the current root of the deposit tree
* `deposit(pubkey: bytes[48], withdrawal_credentials: bytes[32], signature: bytes[96])`: adds a deposit instance to the deposit tree, incorporating the input arguments and the value transferred in the given call. *Note*: The amount of value transferred *must* be at least `MIN_DEPOSIT_AMOUNT`. Each of these constants are specified in units of Gwei.
