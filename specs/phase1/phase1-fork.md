<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Ethereum 2.0 Phase 1 -- From Phase 0 to Phase 1](#ethereum-20-phase-1----from-phase-0-to-phase-1)
  - [Table of contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Configuration](#configuration)
  - [Fork to Phase 1](#fork-to-phase-1)
    - [Fork trigger](#fork-trigger)
    - [Upgrading the state](#upgrading-the-state)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Ethereum 2.0 Phase 1 -- From Phase 0 to Phase 1

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

 TODO

<!-- /TOC -->

## Introduction

This document describes the process of moving from Phase 0 to Phase 1 of Ethereum 2.0.

## Configuration

Warning: this configuration is not definitive.

| Name | Value |
| - | - |
| `PHASE_1_FORK_VERSION` | `Version('0x01000000')` |
| `PHASE_1_FORK_SLOT` | `Slot(0)` **TBD** |

## Fork to Phase 1

### Fork trigger

TBD. Social consensus, along with state conditions such as epoch boundary, finality, deposits, active validator count, etc. may be part of the decision process to trigger the fork. For now we assume the condition will be triggered at slot `PHASE_1_FORK_SLOT`, where `PHASE_1_FORK_SLOT % SLOTS_PER_EPOCH == 0`.

### Upgrading the state

After `process_slots` of Phase 0 finishes, if `state.slot == PHASE_1_FORK_SLOT`, an irregular state change is made to upgrade to Phase 1.

```python
def upgrade_to_phase1(pre: phase0.BeaconState) -> BeaconState:
    epoch = get_current_epoch(pre)
    post = BeaconState(
        genesis_time=pre.genesis_time,
        genesis_validators_root=pre.genesis_validators_root,
        slot=pre.slot,
        fork=Fork(
            previous_version=pre.fork.current_version,
            current_version=PHASE_1_FORK_VERSION,
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
        validators=List[Validator, VALIDATOR_REGISTRY_LIMIT](
            Validator(
                pubkey=phase0_validator.pubkey,
                withdrawal_credentials=phase0_validator.withdrawal_credentials,
                effective_balance=phase0_validator.effective_balance,
                slashed=phase0_validator.slashed,
                activation_eligibility_epoch=phase0_validator.activation_eligibility_epoch,
                activation_epoch=phase0_validator.activation_eligibility_epoch,
                exit_epoch=phase0_validator.exit_epoch,
                withdrawable_epoch=phase0_validator.withdrawable_epoch,
                next_custody_secret_to_reveal=get_custody_period_for_validator(ValidatorIndex(i), epoch),
                all_custody_secrets_revealed_epoch=FAR_FUTURE_EPOCH,
            ) for i, phase0_validator in enumerate(pre.validators)
        ),
        balances=pre.balances,
        # Randomness
        randao_mixes=pre.randao_mixes,
        # Slashings
        slashings=pre.slashings,
        # Finality
        justification_bits=pre.justification_bits,
        previous_justified_checkpoint=pre.previous_justified_checkpoint,
        current_justified_checkpoint=pre.current_justified_checkpoint,
        finalized_checkpoint=pre.finalized_checkpoint,
        # Phase 1
        current_epoch_start_shard=Shard(0),
        shard_states=List[ShardState, MAX_SHARDS](
            ShardState(
                slot=compute_previous_slot(pre.slot),
                gasprice=MIN_GASPRICE,
                latest_block_root=Root(),
            ) for i in range(INITIAL_ACTIVE_SHARDS)
        ),
        online_countdown=[ONLINE_PERIOD] * len(pre.validators),  # all online
        current_light_committee=CompactCommittee(),  # computed after state creation
        next_light_committee=CompactCommittee(),
        current_shard_transition_candidates=List[ShardTransitionCandidate, MAX_ATTESTATIONS * SLOTS_PER_EPOCH](),
        previous_shard_transition_candidates=List[ShardTransitionCandidate, MAX_ATTESTATIONS * SLOTS_PER_EPOCH](),
        current_epoch_reward_flags=List[Bitvector[8], MAX_ACTIVE_VALIDATORS](
            Bitvector[8]() for _ in get_active_validator_indices(pre, get_current_epoch(pre))
        ),
        previous_epoch_reward_flags=List[Bitvector[8], MAX_ACTIVE_VALIDATORS](
            Bitvector[8]() for _ in get_active_validator_indices(pre, get_previous_epoch(pre))
        ),
        # Custody game
        exposed_derived_secrets=[()] * EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS,
        # exposed_derived_secrets will fully default to zeroes
    )
    next_epoch = Epoch(epoch + 1)
    post.current_light_committee = committee_to_compact_committee(post, get_light_client_committee(post, epoch))
    post.next_light_committee = committee_to_compact_committee(post, get_light_client_committee(post, next_epoch))
    return post
```
