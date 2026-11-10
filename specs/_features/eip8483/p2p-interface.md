# EIP-8483 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `compute_fork_version`](#modified-compute_fork_version)
  - [Modified `verify_execution_requests_limits`](#modified-verify_execution_requests_limits)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-8483.

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite.

## Helpers

### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIP8483_FORK_EPOCH:
        return EIP8483_FORK_VERSION
    if epoch >= GLOAS_FORK_EPOCH:
        return GLOAS_FORK_VERSION
    if epoch >= FULU_FORK_EPOCH:
        return FULU_FORK_VERSION
    if epoch >= ELECTRA_FORK_EPOCH:
        return ELECTRA_FORK_VERSION
    if epoch >= DENEB_FORK_EPOCH:
        return DENEB_FORK_VERSION
    if epoch >= CAPELLA_FORK_EPOCH:
        return CAPELLA_FORK_VERSION
    if epoch >= BELLATRIX_FORK_EPOCH:
        return BELLATRIX_FORK_VERSION
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

### Modified `verify_execution_requests_limits`

*Note*: These checks MAY be performed when deserializing `ExecutionRequests`.

```python
def verify_execution_requests_limits(execution_requests: ExecutionRequests) -> None:
    """
    Verify that each execution request count is within its limit.
    Raises GossipReject on validation failure.
    """
    # [REJECT] The withdrawal request count is within the limit
    if len(execution_requests.withdrawals) > MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many withdrawal requests")

    # [REJECT] The consolidation request count is within the limit
    if len(execution_requests.consolidations) > MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many consolidation requests")

    # [REJECT] The builder deposit request count is within the limit
    if len(execution_requests.builder_deposits) > MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many builder deposit requests")

    # [REJECT] The builder exit request count is within the limit
    if len(execution_requests.builder_exits) > MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many builder exit requests")

    # [New in EIP8483]
    # [REJECT] The validator PQ registration request count is within the limit
    validator_pq_registrations = execution_requests.validator_pq_registrations
    if len(validator_pq_registrations) > MAX_VALIDATOR_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many validator PQ registration requests")

    # [New in EIP8483]
    # [REJECT] The builder PQ registration request count is within the limit
    builder_pq_registrations = execution_requests.builder_pq_registrations
    if len(builder_pq_registrations) > MAX_BUILDER_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD:
        raise GossipReject("too many builder PQ registration requests")
```
