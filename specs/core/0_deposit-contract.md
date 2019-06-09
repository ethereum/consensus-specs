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
        - [`deposit` function](#deposit-function)
            - [Deposit amount](#deposit-amount)
            - [Withdrawal credentials](#withdrawal-credentials)
            - [`Deposit` log](#deposit-log)
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

### `deposit` function

The deposit contract has a public `deposit` function to make deposits. It takes as arguments `pubkey: bytes[48], withdrawal_credentials: bytes[32], signature: bytes[96]` corresponding to a `DepositData` object.

#### Deposit amount

The ETH sent to the deposit contract, i.e. the deposit amount, is burnt on Ethereum 1.0. The minimum deposit amount is `MIN_DEPOSIT_AMOUNT` Gwei.

#### Withdrawal credentials

One of the `DepositData` fields is `withdrawal_credentials`. It is a commitment to credentials for withdrawing validator balance (e.g. to another validator, or to shards). The first byte of `withdrawal_credentials` is a version number. As of now, the only expected format is as follows:

* `withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX_BYTE`
* `withdrawal_credentials[1:] == hash(withdrawal_pubkey)[1:]` where `withdrawal_pubkey` is a BLS pubkey

The private key corresponding to `withdrawal_pubkey` will be required to initiate a withdrawal. It can be stored separately until a withdrawal is required, e.g. in cold storage.

#### `Deposit` log

Every Ethereum 1.0 deposit emits a `Deposit` log for consumption by the beacon chain. The deposit contract does little validation, pushing most of the validator onboarding logic to the beacon chain. In particular, the proof of possession (a BLS12-381 signature) is not verified by the deposit contract.

## Vyper code

The deposit contract source code, written in Vyper, is available [here](https://github.com/ethereum/eth2.0-specs/blob/dev/deposit_contract/contracts/validator_registration.v.py).

*Note*: To save on gas the deposit contract uses a progressive Merkle root calculation algorithm that requires only O(log(n)) storage. See [here](https://github.com/ethereum/research/blob/master/beacon_chain_impl/progressive_merkle_tree.py) for a Python implementation, and [here](https://github.com/runtimeverification/verified-smart-contracts/blob/master/deposit/formal-incremental-merkle-tree-algorithm.pdf) for a formal correctness proof.
