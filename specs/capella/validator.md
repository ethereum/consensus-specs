# Capella -- Honest Validator

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Helpers](#helpers)
  - [Modified `GetPayloadResponse`](#modified-getpayloadresponse)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [Modified `get_payload`](#modified-get_payload)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [ExecutionPayload](#executionpayload)
      - [BLS to execution changes](#bls-to-execution-changes)
- [Enabling validator withdrawals](#enabling-validator-withdrawals)
  - [Changing from BLS to execution withdrawal credentials](#changing-from-bls-to-execution-withdrawal-credentials)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement the Capella upgrade.

## Prerequisites

This document is an extension of the [Bellatrix -- Honest Validator](../bellatrix/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [Capella](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Helpers

### Modified `GetPayloadResponse`

```python
@dataclass
class GetPayloadResponse(object):
    execution_payload: ExecutionPayload
    block_value: uint256
```

## Protocols

### `ExecutionEngine`

#### Modified `get_payload`

`get_payload` returns the upgraded Capella `ExecutionPayload` type.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Block proposal

#### Constructing the `BeaconBlockBody`

##### ExecutionPayload

`ExecutionPayload`s are constructed as they were in Bellatrix, except that the
expected withdrawals for the slot must be gathered from the `state` (utilizing the
helper `get_expected_withdrawals`) and passed into the `ExecutionEngine` within `prepare_execution_payload`.

*Note*: In this section, `state` is the state of the slot for the block proposal _without_ the block yet applied.
That is, `state` is the `previous_state` processed through any empty slots up to the assigned slot using `process_slots(previous_state, slot)`.

*Note*: The only change made to `prepare_execution_payload` is to call
`get_expected_withdrawals()` to set the new `withdrawals` field of `PayloadAttributes`.

```python
def prepare_execution_payload(state: BeaconState,
                              safe_block_hash: Hash32,
                              finalized_block_hash: Hash32,
                              suggested_fee_recipient: ExecutionAddress,
                              execution_engine: ExecutionEngine) -> Optional[PayloadId]:
    # [Modified in Capella] Removed `is_merge_transition_complete` check in Capella
    parent_hash = state.latest_execution_payload_header.block_hash

    # Set the forkchoice head and initiate the payload build process
    payload_attributes = PayloadAttributes(
        timestamp=compute_timestamp_at_slot(state, state.slot),
        prev_randao=get_randao_mix(state, get_current_epoch(state)),
        suggested_fee_recipient=suggested_fee_recipient,
        withdrawals=get_expected_withdrawals(state),  # [New in Capella]
    )
    return execution_engine.notify_forkchoice_updated(
        head_block_hash=parent_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
    )
```

##### BLS to execution changes

Up to `MAX_BLS_TO_EXECUTION_CHANGES`, [`BLSToExecutionChange`](./beacon-chain.md#blstoexecutionchange) objects can be included in the `block`. The BLS to execution changes must satisfy the verification conditions found in [BLS to execution change processing](./beacon-chain.md#new-process_bls_to_execution_change).

## Enabling validator withdrawals

Validator balances are withdrawn periodically via an automatic process. For exited validators, the full balance is withdrawn. For active validators, the balance in excess of `MAX_EFFECTIVE_BALANCE` is withdrawn.

There is one prerequisite for this automated process:
the validator's withdrawal credentials pointing to an execution layer address, i.e. having an `ETH1_ADDRESS_WITHDRAWAL_PREFIX`.

If a validator has a `BLS_WITHDRAWAL_PREFIX` withdrawal credential prefix, to participate in withdrawals the validator must
create a one-time message to change their withdrawal credential from the version authenticated with a BLS key to the
version compatible with the execution layer. This message -- a `BLSToExecutionChange` -- is available starting in Capella

Validators who wish to enable withdrawals **MUST** assemble, sign, and broadcast this message so that it is accepted
on the beacon chain. Validators who do not want to enable withdrawals and have the `BLS_WITHDRAWAL_PREFIX` version of
withdrawal credentials can delay creating this message until they are ready to enable withdrawals.

### Changing from BLS to execution withdrawal credentials

First, the validator must construct a valid [`BLSToExecutionChange`](./beacon-chain.md#blstoexecutionchange) `message`.
This `message` contains the `validator_index` for the validator who wishes to change their credentials, the `from_bls_pubkey` -- the BLS public key corresponding to the **withdrawal BLS secret key** used to form the `BLS_WITHDRAWAL_PREFIX` withdrawal credential, and the `to_execution_address` specifying the execution layer address to which the validator's balances will be withdrawn.

*Note*: The withdrawal key pair used to construct the `BLS_WITHDRAWAL_PREFIX` withdrawal credential should be distinct from the signing key pair used to operate the validator under typical circumstances. Consult your validator deposit tooling documentation for further details if you are not aware of the difference.

*Warning*: This message can only be included on-chain once and is
irreversible so ensure the correctness and accessibility to `to_execution_address`.

Next, the validator signs the assembled `message: BLSToExecutionChange` with the **withdrawal BLS secret key** and this
`signature` is placed into a `SignedBLSToExecutionChange` message along with the inner `BLSToExecutionChange` `message`.
Note that the `SignedBLSToExecutionChange` message should pass all of the validations in [`process_bls_to_execution_change`](./beacon-chain.md#new-process_bls_to_execution_change).

The `SignedBLSToExecutionChange` message should then be submitted to the consensus layer network. Once included on-chain,
the withdrawal credential change takes effect. No further action is required for a validator to enter into the automated
withdrawal process.

*Note*: A node *should* prioritize locally received `BLSToExecutionChange` operations to ensure these changes make it on-chain
through self published blocks even if the rest of the network censors.
