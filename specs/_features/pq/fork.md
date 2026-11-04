# PQ -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configs](#configs)
- [Helpers](#helpers)
  - [New `upgrade_pq_registrations_to_pq`](#new-upgrade_pq_registrations_to_pq)
  - [New `get_pq_data_pubkeys`](#new-get_pq_data_pubkeys)
- [Fork to PQ](#fork-to-pq)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the PQ upgrade.

Validators and builders register their XMSS public key and VRF data before the
fork, as the `pq_data` of a [Prereg](../prereg/beacon-chain.md) registration. At
the fork, each registration becomes an entry in `state.pq_data`. Validators and
builders keep their BLS public keys, which identify their entries.

A validator or builder without an entry for its role has its exit initiated.
Prereg ignores a registration whose XMSS public key is already registered, so
every XMSS public key is unique.

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

### New `upgrade_pq_registrations_to_pq`

```python
def upgrade_pq_registrations_to_pq(pre: prereg.BeaconState) -> PQDataList:
    pq_data = PQDataList()
    for registration in pre.pq_registrations:
        pq_data.append(
            PQData(
                role=registration.role,
                bls_pubkey=registration.pubkey,
                xmss_pubkey=XMSSPubkey(registration.pq_data[:32]),
                vrf_data=Bytes32(registration.pq_data[32:]),
            )
        )
    return pq_data
```

### New `get_pq_data_pubkeys`

```python
def get_pq_data_pubkeys(state: BeaconState, role: Uint8) -> set[BLSPubkey]:
    """
    Return the BLS public keys with an entry in ``state.pq_data`` for ``role``.
    """
    return {entry.bls_pubkey for entry in state.pq_data if entry.role == role}
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
def upgrade_to_pq(pre: prereg.BeaconState) -> BeaconState:
    epoch = prereg.get_current_epoch(pre)

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
        # Removed `pq_registrations`
        # [New in PQ]
        pq_data=upgrade_pq_registrations_to_pq(pre),
    )

    # [New in PQ]
    registered_pubkeys = get_pq_data_pubkeys(post, PQ_REGISTRATION_ROLE_VALIDATOR)
    for index, validator in enumerate(post.validators):
        if validator.pubkey not in registered_pubkeys:
            initiate_validator_exit(post, ValidatorIndex(index))

    # [New in PQ]
    registered_builder_pubkeys = get_pq_data_pubkeys(post, PQ_REGISTRATION_ROLE_BUILDER)
    for builder_index, builder in enumerate(post.builders):
        is_registered = builder.pubkey in registered_builder_pubkeys
        if not is_registered and builder.withdrawable_epoch == FAR_FUTURE_EPOCH:
            initiate_builder_exit(post, BuilderIndex(builder_index))

    return post
```
