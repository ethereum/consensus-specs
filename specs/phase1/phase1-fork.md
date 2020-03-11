<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Ethereum 2.0 Phase 1 -- From Phase 0 to Phase 1](#ethereum-20-phase-1----from-phase-0-to-phase-1)
  - [Table of contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Configuration](#configuration)
  - [Fork to Phase 1](#fork-to-phase-1)
    - [Fork trigger.](#fork-trigger)
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
| `INITIAL_ACTIVE_SHARDS` | `2**6` (= 64) |
| `INITIAL_GASPRICE` | `Gwei(10)` |

## Fork to Phase 1

### Fork trigger.

TBD. Social consensus, along with state conditions such as epoch boundary, finality, deposits, active validator count, etc. may be part of the decision process to trigger the fork.

### Upgrading the state

After `process_slots` of Phase 0 finishes, but before the first Phase 1 block is processed, an irregular state change is made to upgrade to Phase 1.

```python
def upgrade_to_phase1(pre: phase0.BeaconState) -> BeaconState:
    epoch = get_current_epoch(pre)
    post = BeaconState(
        genesis_time=pre.genesis_time,
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
                max_reveal_lateness=0,  # TODO custody refactor. Outdated? 
            ) for i, phase0_validator in enumerate(pre.validators)
        ),
        balances=pre.balances,
        # Randomness
        randao_mixes=pre.randao_mixes,
        # Slashings
        slashings=pre.slashings,
        # Attestations
        # previous_epoch_attestations is cleared on upgrade. 
        previous_epoch_attestations=List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH](),
        # empty in pre state, since the upgrade is performed just after an epoch boundary.
        current_epoch_attestations=List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH](),
        # Finality
        justification_bits=pre.justification_bits,
        previous_justified_checkpoint=pre.previous_justified_checkpoint,
        current_justified_checkpoint=pre.current_justified_checkpoint,
        finalized_checkpoint=pre.finalized_checkpoint,
        # Phase 1
        shard_states=List[ShardState, MAX_SHARDS](
            ShardState(
                slot=pre.slot,
                gasprice=INITIAL_GASPRICE,
                data=Root(),
                latest_block_root=Root(),
            ) for i in range(INITIAL_ACTIVE_SHARDS)
        ),
        online_countdown=[ONLINE_PERIOD] * len(pre.validators),  # all online
        current_light_committee=CompactCommittee(),  # computed after state creation
        next_light_committee=CompactCommittee(),
        # Custody game
        custody_challenge_index=0,
        # exposed_derived_secrets will fully default to zeroes
    )
    next_epoch = Epoch(epoch + 1)
    post.current_light_committee = committee_to_compact_committee(post, get_light_client_committee(post, epoch))
    post.next_light_committee = committee_to_compact_committee(post, get_light_client_committee(post, next_epoch))
    return post
```
