# PQ -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configs](#configs)
- [Helpers](#helpers)
  - [New `compute_unusable_xmss_pubkey`](#new-compute_unusable_xmss_pubkey)
  - [New `get_registered_xmss_pubkeys`](#new-get_registered_xmss_pubkeys)
  - [New `upgrade_pending_deposits_to_pq`](#new-upgrade_pending_deposits_to_pq)
- [Fork to PQ](#fork-to-pq)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the PQ upgrade.

Validators and builders register their XMSS public key before the fork, as the
`pq_data` of an [EIP-8483](../eip8483/beacon-chain.md) registration. At the
fork, each registered key replaces the BLS public key it was registered for.

A validator or builder without a registration gets a public key that nobody can
sign for, and its exit is initiated. EIP-8483 ignores a registration whose key
is already registered, so every registered key is unique. An exited builder can
register again with an XMSS builder deposit.

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

### New `compute_unusable_xmss_pubkey`

```python
def compute_unusable_xmss_pubkey(bls_pubkey: BLSPubkey) -> XMSSPubkey:
    """
    Return an XMSS public key derived from ``bls_pubkey`` that nobody can sign
    for, since that would require a preimage of the hash.
    """
    return XMSSPubkey(sha256(bls_pubkey))
```

### New `get_registered_xmss_pubkeys`

*Note*: A builder may share a validator's BLS public key, so registrations are
looked up by role.

```python
def get_registered_xmss_pubkeys(
    pre: eip8483.BeaconState, role: Uint8
) -> dict[BLSPubkey, XMSSPubkey]:
    """
    Return the XMSS public key registered for each BLS public key with ``role``.
    """
    registered_pubkeys: dict[BLSPubkey, XMSSPubkey] = {}
    for registration in pre.pq_registrations:
        if registration.role == role:
            registered_pubkeys[registration.pubkey] = XMSSPubkey(registration.pq_data)
    return registered_pubkeys
```

### New `upgrade_pending_deposits_to_pq`

*Note*: A pending deposit for a public key that is not yet in the registry
cannot be applied after the fork, because its proof of possession is a BLS
signature. Such a validator is added to the registry at the fork without a
balance, and its deposit is queued as a top-up. It has no registered key, so its
exit is initiated with the other unregistered validators.

```python
def upgrade_pending_deposits_to_pq(pre: eip8483.BeaconState, post: BeaconState) -> None:
    bls_pubkeys = [validator.pubkey for validator in pre.validators]
    for deposit in pre.pending_deposits:
        if deposit.pubkey not in bls_pubkeys:
            if not eip8483.is_valid_deposit_signature(
                deposit.pubkey, deposit.withdrawal_credentials, deposit.amount, deposit.signature
            ):
                continue
            add_validator_to_registry(
                post,
                compute_unusable_xmss_pubkey(deposit.pubkey),
                deposit.withdrawal_credentials,
                Gwei(0),
            )
            bls_pubkeys.append(deposit.pubkey)

        validator = post.validators[bls_pubkeys.index(deposit.pubkey)]
        post.pending_deposits.append(
            PendingDeposit(
                pubkey=validator.pubkey,
                withdrawal_credentials=deposit.withdrawal_credentials,
                amount=deposit.amount,
                signature=XMSSSignature(),
                slot=deposit.slot,
            )
        )
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
def upgrade_to_pq(pre: eip8483.BeaconState) -> BeaconState:
    epoch = eip8483.get_current_epoch(pre)
    registered_pubkeys = get_registered_xmss_pubkeys(pre, PQ_REGISTRATION_ROLE_VALIDATOR)
    registered_builder_pubkeys = get_registered_xmss_pubkeys(pre, PQ_REGISTRATION_ROLE_BUILDER)

    validators = Validators()
    for pre_validator in pre.validators:
        if pre_validator.pubkey in registered_pubkeys:
            pubkey = registered_pubkeys[pre_validator.pubkey]
        else:
            pubkey = compute_unusable_xmss_pubkey(pre_validator.pubkey)
        validators.append(
            Validator(
                pubkey=pubkey,
                withdrawal_credentials=pre_validator.withdrawal_credentials,
                effective_balance=pre_validator.effective_balance,
                slashed=pre_validator.slashed,
                activation_eligibility_epoch=pre_validator.activation_eligibility_epoch,
                activation_epoch=pre_validator.activation_epoch,
                exit_epoch=pre_validator.exit_epoch,
                withdrawable_epoch=pre_validator.withdrawable_epoch,
            )
        )

    builders = Builders()
    for pre_builder in pre.builders:
        if pre_builder.pubkey in registered_builder_pubkeys:
            builder_pubkey = registered_builder_pubkeys[pre_builder.pubkey]
        else:
            builder_pubkey = compute_unusable_xmss_pubkey(pre_builder.pubkey)
        builders.append(
            Builder(
                pubkey=builder_pubkey,
                version=pre_builder.version,
                execution_address=pre_builder.execution_address,
                balance=pre_builder.balance,
                deposit_epoch=pre_builder.deposit_epoch,
                withdrawable_epoch=pre_builder.withdrawable_epoch,
            )
        )

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
        # [Modified in PQ]
        validators=validators,
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
        # [Modified in PQ]
        pending_deposits=PendingDeposits(),
        pending_partial_withdrawals=pre.pending_partial_withdrawals,
        pending_consolidations=pre.pending_consolidations,
        proposer_lookahead=pre.proposer_lookahead,
        # [Modified in PQ]
        builders=builders,
        next_withdrawal_builder_index=pre.next_withdrawal_builder_index,
        execution_payload_availability=pre.execution_payload_availability,
        builder_pending_payments=pre.builder_pending_payments,
        builder_pending_withdrawals=pre.builder_pending_withdrawals,
        latest_execution_payload_bid=pre.latest_execution_payload_bid,
        payload_expected_withdrawals=pre.payload_expected_withdrawals,
        ptc_window=pre.ptc_window,
        # [Modified in PQ]
        # Removed `pq_registrations`
    )

    # [New in PQ]
    upgrade_pending_deposits_to_pq(pre, post)

    # [New in PQ]
    validator_xmss_pubkeys = set(registered_pubkeys.values())
    for index, validator in enumerate(post.validators):
        if validator.pubkey not in validator_xmss_pubkeys:
            initiate_validator_exit(post, ValidatorIndex(index))

    # [New in PQ]
    builder_xmss_pubkeys = set(registered_builder_pubkeys.values())
    for builder_index, builder in enumerate(post.builders):
        is_registered = builder.pubkey in builder_xmss_pubkeys
        if not is_registered and builder.withdrawable_epoch == FAR_FUTURE_EPOCH:
            initiate_builder_exit(post, BuilderIndex(builder_index))

    return post
```
