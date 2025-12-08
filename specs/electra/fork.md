# Electra -- Fork Logic

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Fork to Electra](#fork-to-electra)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the Electra upgrade.

## Configuration

Warning: this configuration is not definitive.

| Name                   | Value                                         |
| ---------------------- | --------------------------------------------- |
| `ELECTRA_FORK_VERSION` | `Version('0x05000000')`                       |
| `ELECTRA_FORK_EPOCH`   | `Epoch(364032)` (May 7, 2025, 10:05:11am UTC) |

## Fork to Electra

### Fork trigger

The fork is triggered at epoch `ELECTRA_FORK_EPOCH`.

*Note*: For the pure Electra networks, the `upgrade_to_electra` function is
applied to transition the genesis state to this fork.

### Upgrading the state

If `state.slot % SLOTS_PER_EPOCH == 0` and
`compute_epoch_at_slot(state.slot) == ELECTRA_FORK_EPOCH`, an irregular state
change is made to upgrade to Electra.

```python
def upgrade_to_electra(pre: deneb.BeaconState) -> BeaconState:
    epoch = deneb.get_current_epoch(pre)

    earliest_exit_epoch = compute_activation_exit_epoch(get_current_epoch(pre))
    for validator in pre.validators:
        if validator.exit_epoch != FAR_FUTURE_EPOCH:
            if validator.exit_epoch > earliest_exit_epoch:
                earliest_exit_epoch = validator.exit_epoch
    earliest_exit_epoch += Epoch(1)

    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            # [Modified in Electra]
            current_version=ELECTRA_FORK_VERSION,
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
        current_sync_committee=pre.current_sync_committee,
        next_sync_committee=pre.next_sync_committee,
        latest_execution_payload_header=pre.latest_execution_payload_header,
        next_withdrawal_index=pre.next_withdrawal_index,
        next_withdrawal_validator_index=pre.next_withdrawal_validator_index,
        historical_summaries=pre.historical_summaries,
        # [New in Electra:EIP6110]
        deposit_requests_start_index=UNSET_DEPOSIT_REQUESTS_START_INDEX,
        # [New in Electra:EIP7251]
        deposit_balance_to_consume=0,
        # [New in Electra:EIP7251]
        exit_balance_to_consume=0,
        # [New in Electra:EIP7251]
        earliest_exit_epoch=earliest_exit_epoch,
        # [New in Electra:EIP7251]
        consolidation_balance_to_consume=0,
        # [New in Electra:EIP7251]
        earliest_consolidation_epoch=compute_activation_exit_epoch(get_current_epoch(pre)),
        # [New in Electra:EIP7251]
        pending_deposits=[],
        # [New in Electra:EIP7251]
        pending_partial_withdrawals=[],
        # [New in Electra:EIP7251]
        pending_consolidations=[],
    )

    post.exit_balance_to_consume = get_activation_exit_churn_limit(post)
    post.consolidation_balance_to_consume = get_consolidation_churn_limit(post)

    # [New in Electra:EIP7251]
    # add validators that are not yet active to pending balance deposits
    pre_activation = sorted(
        [
            index
            for index, validator in enumerate(post.validators)
            if validator.activation_epoch == FAR_FUTURE_EPOCH
        ],
        key=lambda index: (post.validators[index].activation_eligibility_epoch, index),
    )

    for index in pre_activation:
        balance = post.balances[index]
        post.balances[index] = 0
        validator = post.validators[index]
        validator.effective_balance = 0
        validator.activation_eligibility_epoch = FAR_FUTURE_EPOCH
        # Use bls.G2_POINT_AT_INFINITY as a signature field placeholder
        # and GENESIS_SLOT to distinguish from a pending deposit request
        post.pending_deposits.append(
            PendingDeposit(
                pubkey=validator.pubkey,
                withdrawal_credentials=validator.withdrawal_credentials,
                amount=balance,
                signature=bls.G2_POINT_AT_INFINITY,
                slot=GENESIS_SLOT,
            )
        )

    # Ensure early adopters of compounding credentials go through the activation churn
    for index, validator in enumerate(post.validators):
        if has_compounding_withdrawal_credential(validator):
            queue_excess_active_balance(post, ValidatorIndex(index))

    return post
```
