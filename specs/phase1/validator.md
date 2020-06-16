# Ethereum 2.0 Phase 1 -- Updates to honest validator

**Notice**: This document is a work-in-progress for researchers and implementers. This is so far only a skeleton that describes non-obvious pitfalls so that they won't be forgotten when the full version of the document is prepared

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
- [How to avoid slashing](#how-to-avoid-slashing)
  - [Custody slashing](#custody-slashing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is an update to the [Phase 0 -- Honest validator](../phase0/validator.md) honest validator guide. This will only describe the differences in phase 1. All behaviours in phase 0 remain valid

## How to avoid slashing

### Custody slashing

To avoid custody slashings, the attester must never sign any shard transition for which the custody bit is one. The custody bit is computed using the custody secret:

```python
def get_custody_secret(spec, state, validator_index, epoch=None):
    period = spec.get_custody_period_for_validator(validator_index, epoch if epoch is not None
                                                   else spec.get_current_epoch(state))
    epoch_to_sign = spec.get_randao_epoch_for_custody_period(period, validator_index)
    domain = spec.get_domain(state, spec.DOMAIN_RANDAO, epoch_to_sign)
    signing_root = spec.compute_signing_root(spec.Epoch(epoch_to_sign), domain)
    return bls.Sign(privkeys[validator_index], signing_root)
```

Note that the valid custody secret is always the one for the **attestation target epoch**, not to be confused with the epoch in which the shard block was generated. While they are the same most of the time, getting this wrong at custody epoch boundaries would result in a custody slashing.
