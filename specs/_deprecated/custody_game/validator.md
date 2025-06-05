# Custody Game -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Becoming a validator](#becoming-a-validator)
- [Beacon chain validator assignments](#beacon-chain-validator-assignments)
  - [Custody slashings](#custody-slashings)
  - [Custody key reveals](#custody-key-reveals)
  - [Early derived secret reveals](#early-derived-secret-reveals)
  - [Construct attestation](#construct-attestation)
- [How to avoid slashing](#how-to-avoid-slashing)
  - [Custody slashing](#custody-slashing)

<!-- mdformat-toc end -->

## Introduction

This is an accompanying document to
[Custody Game -- The Beacon Chain](./beacon-chain.md), which describes the
expected actions of a "validator" participating in the shard data Custody Game.

## Prerequisites

This document is an extension of the
[Sharding -- Validator](../sharding/validator.md). All behaviors and definitions
defined in the Sharding doc carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the
[Custody Game -- The Beacon Chain](./beacon-chain.md) docs are requisite for
this document and used throughout. Please see the Custody Game docs before
continuing and use them as a reference throughout.

## Becoming a validator

Becoming a validator in Custody Game is unchanged from Phase 0. See the
[Phase 0 validator guide](../../phase0/validator.md#becoming-a-validator) for
details.

## Beacon chain validator assignments

Beacon chain validator assignments to beacon committees and beacon block
proposal are unchanged from Phase 0. See the
[Phase 0 validator guide](../../phase0/validator.md#validator-assignments) for
details.

##### Custody slashings

Up to `MAX_CUSTODY_SLASHINGS`,
[`CustodySlashing`](./beacon-chain.md#custodyslashing) objects can be included
in the `block`. The custody slashings must satisfy the verification conditions
found in [custody slashings processing](beacon-chain.md#custody-slashings). The
validator receives a small "whistleblower" reward for each custody slashing
included (THIS IS NOT CURRENTLY THE CASE BUT PROBABLY SHOULD BE).

##### Custody key reveals

Up to `MAX_CUSTODY_KEY_REVEALS`,
[`CustodyKeyReveal`](./beacon-chain.md#custodykeyreveal) objects can be included
in the `block`. The custody key reveals must satisfy the verification conditions
found in [custody key reveal processing](beacon-chain.md#custody-key-reveals).
The validator receives a small reward for each custody key reveal included.

##### Early derived secret reveals

Up to `MAX_EARLY_DERIVED_SECRET_REVEALS`,
[`EarlyDerivedSecretReveal`](./beacon-chain.md#earlyderivedsecretreveal) objects
can be included in the `block`. The early derived secret reveals must satisfy
the verification conditions found in
[early derived secret reveal processing](beacon-chain.md#custody-key-reveals).
The validator receives a small "whistleblower" reward for each early derived
secret reveal included.

#### Construct attestation

`attestation.data`, `attestation.aggregation_bits`, and `attestation.signature`
are unchanged from Phase 0. But safety/validity in signing the message is
premised upon calculation of the "custody bit" [TODO].

## How to avoid slashing

Proposer and Attester slashings described in Phase 0 remain in place with the
addition of the following.

### Custody slashing

To avoid custody slashings, the attester must never sign any shard transition
for which the custody bit is one. The custody bit is computed using the custody
secret:

```python
def get_custody_secret(
    state: BeaconState, validator_index: ValidatorIndex, privkey: int, epoch: Epoch = None
) -> BLSSignature:
    if epoch is None:
        epoch = get_current_epoch(state)
    period = get_custody_period_for_validator(validator_index, epoch)
    epoch_to_sign = get_randao_epoch_for_custody_period(period, validator_index)
    domain = get_domain(state, DOMAIN_RANDAO, epoch_to_sign)
    signing_root = compute_signing_root(Epoch(epoch_to_sign), domain)
    return bls.Sign(privkey, signing_root)
```

Note that the valid custody secret is always the one for the **attestation
target epoch**, not to be confused with the epoch in which the shard block was
generated. While they are the same most of the time, getting this wrong at
custody epoch boundaries would result in a custody slashing.
