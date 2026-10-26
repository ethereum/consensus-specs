# EIP-8453 -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configs](#configs)
- [Helpers](#helpers)
  - [New `initialize_head_vote_committee_window`](#new-initialize_head_vote_committee_window)
- [Fork to EIP-8453](#fork-to-eip-8453)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the EIP-8453 upgrade.

## Configs

| Name                   | Value                   |
| ---------------------- | ----------------------- |
| `EIP8453_FORK_VERSION` | `Version("0xe8453000")` |
| `EIP8453_FORK_EPOCH`   | `FAR_FUTURE_EPOCH`      |

## Helpers

### New `initialize_head_vote_committee_window`

```python
def initialize_head_vote_committee_window(state: BeaconState) -> HeadVoteCommitteeWindow:
    """
    Return the head vote committee window starting from the current epoch.
    """
    committees = [HeadVoteCommittee() for _ in range(SLOTS_PER_EPOCH)]
    current_epoch = get_current_epoch(state)
    start_slot = compute_start_slot_at_epoch(current_epoch)
    end_slot = compute_start_slot_at_epoch(current_epoch + MIN_SEED_LOOKAHEAD + 1)
    for slot in range(start_slot, end_slot):
        committees.append(compute_head_vote_committee(state, Slot(slot)))
    return HeadVoteCommitteeWindow(data=committees)
```

## Fork to EIP-8453

### Fork trigger

The fork is triggered at epoch `EIP8453_FORK_EPOCH`.

### Upgrading the state

If `state.slot % SLOTS_PER_EPOCH == 0` and
`compute_epoch_at_slot(state.slot) == EIP8453_FORK_EPOCH`, an irregular state
change is made to upgrade to EIP-8453.

*Note*: The finality gadget starts at height 0 from the last finalized Casper
FFG checkpoint, and the target of height 1 is the latest block before the
upgrade. Participation in the last epoch before the upgrade is not rewarded.

```python
def upgrade_to_eip8453(pre: heze.BeaconState) -> BeaconState:
    epoch = heze.get_current_epoch(pre)

    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            # [Modified in EIP8453]
            current_version=EIP8453_FORK_VERSION,
            epoch=epoch,
        ),
        latest_block_header=pre.latest_block_header,
        block_roots=pre.block_roots,
        state_roots=pre.state_roots,
        historical_roots=pre.historical_roots,
        validators=pre.validators,
        balances=pre.balances,
        randao_mixes=pre.randao_mixes,
        slashings=pre.slashings,
        # [Modified in EIP8453]
        # Removed `previous_epoch_participation`
        # [Modified in EIP8453]
        # Removed `current_epoch_participation`
        # [Modified in EIP8453]
        # Removed `justification_bits`
        # [Modified in EIP8453]
        # Removed `previous_justified_checkpoint`
        # [Modified in EIP8453]
        # Removed `current_justified_checkpoint`
        # [Modified in EIP8453]
        # Removed `finalized_checkpoint`
        inactivity_scores=pre.inactivity_scores,
        current_sync_committee=pre.current_sync_committee,
        next_sync_committee=pre.next_sync_committee,
        latest_block_hash=pre.latest_block_hash,
        next_withdrawal_index=pre.next_withdrawal_index,
        next_withdrawal_validator_index=pre.next_withdrawal_validator_index,
        historical_summaries=pre.historical_summaries,
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
        # [New in EIP8453]
        target_checkpoint=HeightCheckpoint(
            height=Height(1),
            root=hash_tree_root(pre.latest_block_header),
        ),
        # [New in EIP8453]
        justified_checkpoint=HeightCheckpoint(
            height=Height(0),
            root=pre.finalized_checkpoint.root,
        ),
        # [New in EIP8453]
        finalized_checkpoint=HeightCheckpoint(
            height=Height(0),
            root=pre.finalized_checkpoint.root,
        ),
        # [New in EIP8453]
        target_slot=pre.latest_block_header.slot,
        # [New in EIP8453]
        finalized_slot=compute_start_slot_at_epoch(pre.finalized_checkpoint.epoch),
        # [New in EIP8453]
        target_participation=HeightParticipation(data=[Boolean(False)] * len(pre.validators)),
        # [New in EIP8453]
        progress_participation=HeightParticipation(data=[Boolean(False)] * len(pre.validators)),
        # [New in EIP8453]
        round_participation=RoundParticipation(data=[ParticipationFlags(0)] * len(pre.validators)),
        # [New in EIP8453]
        pending_finality=PendingFinalities(),
        # [New in EIP8453]
        head_vote_participation=HeadVoteParticipation(),
        # [New in EIP8453]
        head_vote_committee_window=HeadVoteCommitteeWindow(),
    )

    # [New in EIP8453]
    post.head_vote_committee_window = initialize_head_vote_committee_window(post)

    return post
```
