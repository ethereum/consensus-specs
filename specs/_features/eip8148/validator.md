# EIP-8148 -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Execution requests](#execution-requests)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement EIP-8148.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Block and sidecar proposal

#### Constructing the `BeaconBlockBody`

##### Execution requests

*Note*: The function `get_execution_requests` is modified to parse the sweep
threshold requests.

```python
def get_execution_requests(execution_requests_list: Sequence[bytes]) -> ExecutionRequests:
    deposits = []
    withdrawals = []
    consolidations = []
    builder_deposits = []
    builder_exits = []
    # [New in EIP8148]
    sweep_thresholds = []

    request_types = [
        DEPOSIT_REQUEST_TYPE,
        WITHDRAWAL_REQUEST_TYPE,
        CONSOLIDATION_REQUEST_TYPE,
        BUILDER_DEPOSIT_REQUEST_TYPE,
        BUILDER_EXIT_REQUEST_TYPE,
        # [New in EIP8148]
        SWEEP_THRESHOLD_REQUEST_TYPE,
    ]

    prev_request_type = None
    for request in execution_requests_list:
        request_type, request_data = request[0:1], request[1:]

        # Check that the request type is valid
        assert request_type in request_types
        # Check that the request data is not empty
        assert len(request_data) != 0
        # Check that requests are in strictly ascending order
        # Each successive type must be greater than the last with no duplicates
        assert prev_request_type is None or prev_request_type < request_type
        prev_request_type = request_type

        if request_type == DEPOSIT_REQUEST_TYPE:
            deposits = ssz_deserialize(DepositRequests, request_data)
        elif request_type == WITHDRAWAL_REQUEST_TYPE:
            withdrawals = ssz_deserialize(WithdrawalRequests, request_data)
        elif request_type == CONSOLIDATION_REQUEST_TYPE:
            consolidations = ssz_deserialize(ConsolidationRequests, request_data)
        elif request_type == BUILDER_DEPOSIT_REQUEST_TYPE:
            builder_deposits = ssz_deserialize(BuilderDepositRequests, request_data)
        elif request_type == BUILDER_EXIT_REQUEST_TYPE:
            builder_exits = ssz_deserialize(BuilderExitRequests, request_data)
        # [New in EIP8148]
        elif request_type == SWEEP_THRESHOLD_REQUEST_TYPE:
            sweep_thresholds = ssz_deserialize(SweepThresholdRequests, request_data)

    return ExecutionRequests(
        deposits=deposits,
        withdrawals=withdrawals,
        consolidations=consolidations,
        builder_deposits=builder_deposits,
        builder_exits=builder_exits,
        # [New in EIP8148]
        sweep_thresholds=sweep_thresholds,
    )
```
