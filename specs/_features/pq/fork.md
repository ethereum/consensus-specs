# PQ -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configs](#configs)
- [Helpers](#helpers)
  - [New `get_registered_validator_pq_data`](#new-get_registered_validator_pq_data)
  - [New `get_registered_builder_pq_data`](#new-get_registered_builder_pq_data)
  - [New `compute_pq_validators`](#new-compute_pq_validators)
  - [New `compute_pq_builders`](#new-compute_pq_builders)
- [Fork to PQ](#fork-to-pq)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the PQ upgrade.

Before the fork, validators register their XMSS public key and VRF data, and
builders their XMSS public key, through [PQReg](../pqreg/beacon-chain.md)
registrations. At the fork, every validator is copied into `state.pq_validators`
and every builder into `state.pq_builders`, at the same index, with its
registered material. `state.validators` and `state.builders` are frozen from
then on, and only pending deposits still find a validator by BLS public key in
`state.validators`.

A validator or builder without a registration gets the empty XMSS public key,
which no signature verifies against, and has its exit initiated. PQReg ignores a
registration whose XMSS public key is already registered by another validator,
or by another builder, so no two validators and no two builders share an XMSS
public key.

*Note*: A validator with `0x00` withdrawal credentials has no withdrawal address
to register from, so it is exited. `BLSToExecutionChange` is disabled in PQ, so
its balance stays locked until a later upgrade adds a quantum-safe way to change
its credentials.

## Configs

Warning: this configuration is not definitive.

| Name              | Value                                 |
| ----------------- | ------------------------------------- |
| `PQ_FORK_VERSION` | `Version("0xe0000000")`               |
| `PQ_FORK_EPOCH`   | `Epoch(18446744073709551615)` **TBD** |

## Helpers

### New `get_registered_validator_pq_data`

```python
def get_registered_validator_pq_data(pre: pqreg.BeaconState) -> dict[ValidatorIndex, Bytes64]:
    """
    Return the PQ material registered for each validator index.
    """
    registered: dict[ValidatorIndex, Bytes64] = {}
    for registration in pre.validator_pq_registrations:
        registered[registration.validator_index] = registration.pq_data
    return registered
```

### New `get_registered_builder_pq_data`

```python
def get_registered_builder_pq_data(pre: pqreg.BeaconState) -> dict[BLSPubkey, Bytes32]:
    """
    Return the PQ material registered for each builder public key.
    """
    registered: dict[BLSPubkey, Bytes32] = {}
    for registration in pre.builder_pq_registrations:
        registered[registration.builder_pubkey] = registration.pq_data
    return registered
```

### New `compute_pq_validators`

```python
def compute_pq_validators(pre: pqreg.BeaconState) -> PQValidators:
    registered = get_registered_validator_pq_data(pre)
    pq_validators = PQValidators()
    for index, validator in enumerate(pre.validators):
        pq_data = registered.get(ValidatorIndex(index), Bytes64())
        pq_validators.append(
            PQValidator(
                pubkey=XMSSPubkey(pq_data[:32]),
                vrf_data=Root(pq_data[32:]),
                withdrawal_credentials=validator.withdrawal_credentials,
                effective_balance=validator.effective_balance,
                slashed=validator.slashed,
                activation_eligibility_epoch=validator.activation_eligibility_epoch,
                activation_epoch=validator.activation_epoch,
                exit_epoch=validator.exit_epoch,
                withdrawable_epoch=validator.withdrawable_epoch,
            )
        )
    return pq_validators
```

### New `compute_pq_builders`

```python
def compute_pq_builders(pre: pqreg.BeaconState) -> PQBuilders:
    registered = get_registered_builder_pq_data(pre)
    pq_builders = PQBuilders()
    for builder in pre.builders:
        pq_builders.append(
            PQBuilder(
                pubkey=XMSSPubkey(registered.get(builder.pubkey, Bytes32())),
                version=builder.version,
                execution_address=builder.execution_address,
                balance=builder.balance,
                deposit_epoch=builder.deposit_epoch,
                withdrawable_epoch=builder.withdrawable_epoch,
            )
        )
    return pq_builders
```

## Fork to PQ

### Fork trigger

The fork is triggered at epoch `PQ_FORK_EPOCH`.

### Upgrading the state

If `state.slot % SLOTS_PER_EPOCH == 0` and
`compute_epoch_at_slot(state.slot) == PQ_FORK_EPOCH`, an irregular state change
is made to upgrade to PQ.

*Note*: Exits are initiated through the exit churn, so unregistered validators
remain in the active set, unable to sign, until their exit epoch.

*Note*: `latest_execution_payload_bid` is copied unchanged. Its
`execution_requests_root` may commit to the pre-fork `ExecutionRequests` type,
whose root differs from the PQ type even for identical content. The upgrade
cannot recompute it because the state stores only the commitment.

```python
def upgrade_to_pq(pre: pqreg.BeaconState) -> BeaconState:
    epoch = pqreg.get_current_epoch(pre)

    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            # [Modified in PQ]
            current_version=PQ_FORK_VERSION,
            epoch=epoch,
        ),
        latest_block_header=pre.latest_block_header,
        block_roots=pre.block_roots,
        state_roots=pre.state_roots,
        historical_roots=pre.historical_roots,
        eth1_data=pre.eth1_data,
        eth1_data_votes=pre.eth1_data_votes,
        eth1_deposit_index=pre.eth1_deposit_index,
        validators=pre.validators,
        balances=pre.balances,
        randao_mixes=pre.randao_mixes,
        slashings=pre.slashings,
        previous_epoch_participation=pre.previous_epoch_participation,
        current_epoch_participation=pre.current_epoch_participation,
        justification_bits=pre.justification_bits,
        previous_justified_checkpoint=pre.previous_justified_checkpoint,
        current_justified_checkpoint=pre.current_justified_checkpoint,
        finalized_checkpoint=pre.finalized_checkpoint,
        inactivity_scores=pre.inactivity_scores,
        # [Modified in PQ]
        # Removed `current_sync_committee`
        # [Modified in PQ]
        # Removed `next_sync_committee`
        latest_block_hash=pre.latest_block_hash,
        next_withdrawal_index=pre.next_withdrawal_index,
        next_withdrawal_validator_index=pre.next_withdrawal_validator_index,
        historical_summaries=pre.historical_summaries,
        deposit_requests_start_index=pre.deposit_requests_start_index,
        deposit_balance_to_consume=pre.deposit_balance_to_consume,
        exit_balance_to_consume=pre.exit_balance_to_consume,
        earliest_exit_epoch=pre.earliest_exit_epoch,
        consolidation_balance_to_consume=pre.consolidation_balance_to_consume,
        earliest_consolidation_epoch=pre.earliest_consolidation_epoch,
        pending_deposits=pre.pending_deposits,
        pending_partial_withdrawals=pre.pending_partial_withdrawals,
        pending_consolidations=pre.pending_consolidations,
        proposer_lookahead=pre.proposer_lookahead,
        builders=pre.builders,
        next_withdrawal_builder_index=pre.next_withdrawal_builder_index,
        execution_payload_availability=pre.execution_payload_availability,
        builder_pending_payments=pre.builder_pending_payments,
        builder_pending_withdrawals=pre.builder_pending_withdrawals,
        latest_execution_payload_bid=pre.latest_execution_payload_bid,
        payload_expected_withdrawals=pre.payload_expected_withdrawals,
        ptc_window=pre.ptc_window,
        # [Modified in PQ]
        # Removed `validator_pq_registrations`
        # [Modified in PQ]
        # Removed `builder_pq_registrations`
        # [New in PQ]
        pq_validators=compute_pq_validators(pre),
        # [New in PQ]
        pq_builders=compute_pq_builders(pre),
    )

    # [New in PQ]
    for index, validator in enumerate(post.pq_validators):
        if validator.pubkey == XMSSPubkey():
            initiate_validator_exit(post, ValidatorIndex(index))

    # [New in PQ]
    for builder_index, builder in enumerate(post.pq_builders):
        is_registered = builder.pubkey != XMSSPubkey()
        if not is_registered and builder.withdrawable_epoch == FAR_FUTURE_EPOCH:
            initiate_builder_exit(post, BuilderIndex(builder_index))

    return post
```
