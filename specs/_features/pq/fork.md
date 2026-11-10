# PQ -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configs](#configs)
- [Helpers](#helpers)
  - [New `compute_validators`](#new-compute_validators)
  - [New `compute_builders`](#new-compute_builders)
  - [New `compute_pending_deposits`](#new-compute_pending_deposits)
  - [New `compute_builder_pending_withdrawals`](#new-compute_builder_pending_withdrawals)
  - [New `compute_builder_pending_payments`](#new-compute_builder_pending_payments)
- [Fork to PQ](#fork-to-pq)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the PQ upgrade.

Before the fork, validators register their XMSS public key and VRF root, and
builders their XMSS public key, through [EIP-8483](../eip8483/beacon-chain.md)
registrations. At the fork, each validator and builder that registered takes its
XMSS public key in place of its BLS public key, and each validator its VRF root.
Validators and builders keep their indices.

A validator that did not register takes
`sha256(pubkey + LEGACY_XMSS_PUBKEY_DOMAIN)` of its BLS public key as its XMSS
public key, and `sha256(pubkey + LEGACY_VRF_ROOT_DOMAIN)` as its VRF root. No
signature verifies against that key. The validator becomes exited and
withdrawable at the fork, so the validator sweep withdraws its balance. A
slashed validator instead keeps its withdrawable epoch, so `process_slashings`
still applies its slashing penalty before the sweep. A validator with `0x00`
withdrawal credentials has no withdrawal address, so its balance stays locked
until a later upgrade adds a quantum-safe way to set one.

A builder that did not register takes
`sha256(pubkey + LEGACY_XMSS_PUBKEY_DOMAIN)` of its BLS public key as its XMSS
public key, as a validator does, so a legacy deposit for it still tops it up. It
becomes withdrawable at the fork. Builder withdrawals pay its settled builder
payments to their fee recipients, and the builder sweep then withdraws the rest
of its balance to its execution address. Its unsettled payments are settled at
the fork if they have reached the payment quorum, and dropped otherwise.

Pending deposits name their validator by BLS public key. The fork renames a
pending deposit for an existing validator to 16 zero bytes followed by that
validator's XMSS public key, so it still tops up that validator. A top-up for a
validator that did not register does not consume churn, since the validator is
withdrawable, and the validator sweep withdraws it.

A pending deposit for a new validator is kept as is. It names a BLS public key,
so it is a legacy deposit. Its validator takes the XMSS public key and VRF root
that a validator that did not register takes, and it is exited at once, so the
validator sweep refunds its balance after the withdrawability delay.

The proposer lookahead and the PTC window are kept, so the slots and votes they
assign to validators that did not register are missed.

## Configs

Warning: this configuration is not definitive.

| Name              | Value                                 |
| ----------------- | ------------------------------------- |
| `PQ_FORK_VERSION` | `Version("0xe0000000")`               |
| `PQ_FORK_EPOCH`   | `Epoch(18446744073709551615)` **TBD** |

## Helpers

### New `compute_validators`

```python
def compute_validators(pre: eip8483.BeaconState) -> Validators:
    epoch = eip8483.get_current_epoch(pre)
    registered = {
        registration.validator_index: registration.pq_data
        for registration in pre.validator_pq_registrations
    }
    validators = Validators()
    for index, validator in enumerate(pre.validators):
        if ValidatorIndex(index) in registered:
            pq_data = registered[ValidatorIndex(index)]
            pubkey = XMSSPubkey(pq_data[:32])
            vrf_root = Root(pq_data[32:])
            exit_epoch = validator.exit_epoch
            withdrawable_epoch = validator.withdrawable_epoch
        else:
            pubkey = XMSSPubkey(sha256(validator.pubkey + LEGACY_XMSS_PUBKEY_DOMAIN))
            vrf_root = Root(sha256(validator.pubkey + LEGACY_VRF_ROOT_DOMAIN))
            exit_epoch = min(validator.exit_epoch, epoch)
            # A slashed validator must still receive its slashing penalty
            if validator.slashed:
                withdrawable_epoch = validator.withdrawable_epoch
            else:
                withdrawable_epoch = min(validator.withdrawable_epoch, epoch)
        validators.append(
            Validator(
                pubkey=pubkey,
                vrf_root=vrf_root,
                withdrawal_credentials=validator.withdrawal_credentials,
                effective_balance=validator.effective_balance,
                slashed=validator.slashed,
                activation_eligibility_epoch=validator.activation_eligibility_epoch,
                activation_epoch=validator.activation_epoch,
                exit_epoch=exit_epoch,
                withdrawable_epoch=withdrawable_epoch,
            )
        )
    return validators
```

### New `compute_builders`

```python
def compute_builders(pre: eip8483.BeaconState) -> Builders:
    epoch = eip8483.get_current_epoch(pre)
    registered = {
        registration.builder_pubkey: registration.pq_data
        for registration in pre.builder_pq_registrations
    }
    builders = Builders()
    for builder in pre.builders:
        if builder.pubkey in registered:
            pubkey = XMSSPubkey(registered[builder.pubkey])
            withdrawable_epoch = builder.withdrawable_epoch
        else:
            pubkey = XMSSPubkey(sha256(builder.pubkey + LEGACY_XMSS_PUBKEY_DOMAIN))
            withdrawable_epoch = min(builder.withdrawable_epoch, epoch)
        builders.append(
            Builder(
                pubkey=pubkey,
                version=builder.version,
                execution_address=builder.execution_address,
                balance=builder.balance,
                deposit_epoch=builder.deposit_epoch,
                withdrawable_epoch=withdrawable_epoch,
            )
        )
    return builders
```

### New `compute_pending_deposits`

```python
def compute_pending_deposits(pre: eip8483.BeaconState, validators: Validators) -> PendingDeposits:
    validator_pubkeys = [validator.pubkey for validator in pre.validators]
    pending_deposits = PendingDeposits()
    for deposit in pre.pending_deposits:
        if deposit.pubkey in validator_pubkeys:
            validator = validators[validator_pubkeys.index(deposit.pubkey)]
            pubkey = Bytes48(XMSS_DEPOSIT_PREFIX + validator.pubkey)
        else:
            pubkey = deposit.pubkey
        pending_deposits.append(
            PendingDeposit(
                pubkey=pubkey,
                withdrawal_credentials=deposit.withdrawal_credentials,
                amount=deposit.amount,
                signature=deposit.signature,
                slot=deposit.slot,
            )
        )
    return pending_deposits
```

### New `compute_builder_pending_withdrawals`

```python
def compute_builder_pending_withdrawals(
    pre: eip8483.BeaconState,
) -> BuilderPendingWithdrawals:
    builder_pubkeys = [registration.builder_pubkey for registration in pre.builder_pq_registrations]
    quorum = eip8483.get_builder_payment_quorum_threshold(pre)
    withdrawals = pre.builder_pending_withdrawals.copy()
    for payment in pre.builder_pending_payments:
        builder = pre.builders[payment.withdrawal.builder_index]
        if (
            payment.withdrawal.amount > 0
            and builder.pubkey not in builder_pubkeys
            and payment.weight >= quorum
        ):
            withdrawals.append(payment.withdrawal)
    return withdrawals
```

### New `compute_builder_pending_payments`

```python
def compute_builder_pending_payments(pre: eip8483.BeaconState) -> BuilderPendingPayments:
    builder_pubkeys = [registration.builder_pubkey for registration in pre.builder_pq_registrations]
    payments = []
    for payment in pre.builder_pending_payments:
        builder = pre.builders[payment.withdrawal.builder_index]
        if payment.withdrawal.amount > 0 and builder.pubkey not in builder_pubkeys:
            payments.append(BuilderPendingPayment.empty())
        else:
            payments.append(payment)
    return BuilderPendingPayments(data=payments)
```

## Fork to PQ

### Fork trigger

The fork is triggered at epoch `PQ_FORK_EPOCH`.

### Upgrading the state

If `state.slot % SLOTS_PER_EPOCH == 0` and
`compute_epoch_at_slot(state.slot) == PQ_FORK_EPOCH`, an irregular state change
is made to upgrade to PQ.

*Note*: `latest_execution_payload_bid` keeps its `execution_requests_root`,
which may commit to the pre-fork `ExecutionRequests` type, whose root differs
from the PQ type even for identical content. The upgrade cannot recompute it
because the state stores only the commitment.

```python
def upgrade_to_pq(pre: eip8483.BeaconState) -> BeaconState:
    epoch = eip8483.get_current_epoch(pre)
    validators = compute_validators(pre)

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
        pending_deposits=compute_pending_deposits(pre, validators),
        pending_partial_withdrawals=pre.pending_partial_withdrawals,
        pending_consolidations=pre.pending_consolidations,
        proposer_lookahead=pre.proposer_lookahead,
        # [Modified in PQ]
        builders=compute_builders(pre),
        next_withdrawal_builder_index=pre.next_withdrawal_builder_index,
        execution_payload_availability=pre.execution_payload_availability,
        # [Modified in PQ]
        builder_pending_payments=compute_builder_pending_payments(pre),
        # [Modified in PQ]
        builder_pending_withdrawals=compute_builder_pending_withdrawals(pre),
        latest_execution_payload_bid=pre.latest_execution_payload_bid,
        payload_expected_withdrawals=pre.payload_expected_withdrawals,
        ptc_window=pre.ptc_window,
        # [Modified in PQ]
        # Removed `validator_pq_registrations`
        # [Modified in PQ]
        # Removed `builder_pq_registrations`
        # [New in EIP8205]
        validator_preregistrations=ValidatorPreregistrations(),
    )

    return post
```
