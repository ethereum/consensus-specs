# Altair -- Fork Logic

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [`compute_fork_version`](#compute_fork_version)
- [Fork to Altair](#fork-to-altair)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the first upgrade of the beacon chain:
the Altair hard fork, introducing light client support and other improvements.

## Configuration

| Name                  | Value                                         |
| --------------------- | --------------------------------------------- |
| `ALTAIR_FORK_VERSION` | `Version('0x01000000')`                       |
| `ALTAIR_FORK_EPOCH`   | `Epoch(74240)` (Oct 27, 2021, 10:56:23am UTC) |

## Helper functions

### Misc

#### `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

## Fork to Altair

### Fork trigger

The fork is triggered at epoch `ALTAIR_FORK_EPOCH`.

Note that for the pure Altair networks, we don't apply `upgrade_to_altair` since
it starts with Altair version logic.

### Upgrading the state

If `state.slot % SLOTS_PER_EPOCH == 0` and
`compute_epoch_at_slot(state.slot) == ALTAIR_FORK_EPOCH`, an irregular state
change is made to upgrade to Altair.

The upgrade occurs after the completion of the inner loop of `process_slots`
that sets `state.slot` equal to `ALTAIR_FORK_EPOCH * SLOTS_PER_EPOCH`. Care must
be taken when transitioning through the fork boundary as implementations will
need a modified
[state transition function](../phase0/beacon-chain.md#beacon-chain-state-transition-function)
that deviates from the Phase 0 document. In particular, the outer
`state_transition` function defined in the Phase 0 document will not expose the
precise fork slot to execute the upgrade in the presence of skipped slots at the
fork boundary. Instead the logic must be within `process_slots`.

```python
def translate_participation(state: BeaconState, pending_attestations: Sequence[phase0.PendingAttestation]) -> None:
    for attestation in pending_attestations:
        data = attestation.data
        inclusion_delay = attestation.inclusion_delay
        # Translate attestation inclusion info to flag indices
        participation_flag_indices = get_attestation_participation_flag_indices(state, data, inclusion_delay)

        # Apply flags to all attesting validators
        epoch_participation = state.previous_epoch_participation
        for index in get_attesting_indices(state, attestation):
            for flag_index in participation_flag_indices:
                epoch_participation[index] = add_flag(epoch_participation[index], flag_index)


def upgrade_to_altair(pre: phase0.BeaconState) -> BeaconState:
    epoch = phase0.get_current_epoch(pre)
    post = BeaconState(
        # Versioning
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=ALTAIR_FORK_VERSION,
            epoch=epoch,
        ),
        # History
        latest_block_header=pre.latest_block_header,
        block_roots=pre.block_roots,
        state_roots=pre.state_roots,
        historical_roots=pre.historical_roots,
        # Eth1
        eth1_data=pre.eth1_data,
        eth1_data_votes=pre.eth1_data_votes,
        eth1_deposit_index=pre.eth1_deposit_index,
        # Registry
        validators=pre.validators,
        balances=pre.balances,
        # Randomness
        randao_mixes=pre.randao_mixes,
        # Slashings
        slashings=pre.slashings,
        # Participation
        previous_epoch_participation=[ParticipationFlags(0b0000_0000) for _ in range(len(pre.validators))],
        current_epoch_participation=[ParticipationFlags(0b0000_0000) for _ in range(len(pre.validators))],
        # Finality
        justification_bits=pre.justification_bits,
        previous_justified_checkpoint=pre.previous_justified_checkpoint,
        current_justified_checkpoint=pre.current_justified_checkpoint,
        finalized_checkpoint=pre.finalized_checkpoint,
        # Inactivity
        inactivity_scores=[uint64(0) for _ in range(len(pre.validators))],
    )
    # Fill in previous epoch participation from the pre state's pending attestations
    translate_participation(post, pre.previous_epoch_attestations)

    # Fill in sync committees
    # Note: A duplicate committee is assigned for the current and next committee at the fork boundary
    post.current_sync_committee = get_next_sync_committee(post)
    post.next_sync_committee = get_next_sync_committee(post)
    return post
```
