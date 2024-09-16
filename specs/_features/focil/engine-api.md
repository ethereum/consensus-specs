# Engine API -- FOCIL

Engine API changes introduced in FOCIL.

This specification is based on and extends [Engine API - Prague](./prague.md) specification.

Warning: This file should be placed in https://github.com/ethereum/execution-apis but I'm placing it here for convenience of reviewing.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Constants](#constants)
- [Structures](#structures)
  - [InclusionListSummaryV1](#inclusionlistsummaryv1)
  - [InclusionListSummaryListV1](#inclusionlistsummarylistv1)
  - [InclusionListStatusV1](#inclusionliststatusv1)
- [Methods](#methods)
  - [engine_newPayloadV5](#engine_newpayloadv5)
    - [Request](#request)
    - [Response](#response)
    - [Specification](#specification)
  - [engine_newInclusionListV1](#engine_newinclusionlistv1)
    - [Request](#request-1)
    - [Response](#response-1)
    - [Specification](#specification-1)
  - [engine_getInclusionListV1](#engine_getinclusionlistv1)
    - [Request](#request-2)
    - [Response](#response-2)
    - [Specification](#specification-2)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Constants

| Name | Value |
| - | - |
| `INCLUSION_LIST_MAX_GAS` |  `uint64(4194304) = 2**22` |

## Structures 

### InclusionListSummaryV1

This structure contains the details of each inclusion summary.

- `address` : `DATA`, 20 Bytes
- `nonce` : `QUANTITY`, 64 Bits
- `gas_limit` : `QUANTITY`, 64 Bits

### InclusionListSummaryListV1

This structure contains the inclusion summary.

- `summary`: `Array of InclusionListSummaryV1`, Array of summaries that must be satisfied.

### InclusionListStatusV1

This structure contains the result of processing an inclusion list. The fields are encoded as follows:

- `status`: `enum` - `"VALID" | "INVALID" | "SYNCING" | "ACCEPTED"`
- `validationError`: `String|null` - a message providing additional details on the validation error if the payload is classified as `INVALID`.

## Methods

### engine_newPayloadV5

The request of this method is updated with [`ExecutionPayloadV5`](#ExecutionPayloadV5).

#### Request

* method: `engine_newPayloadV5`
* params:
  1. `executionPayload`: [`ExecutionPayloadV4`](#ExecutionPayloadV4).
  2. `expectedBlobVersionedHashes`: `Array of DATA`, 32 Bytes - Array of expected blob versioned hashes to validate.
  3. `parentBeaconBlockRoot`: `DATA`, 32 Bytes - Root of the parent beacon block.
  4. `inclusionListSummaryList`: [`InclusionListSummaryListV1`](#InclusionListSummaryListV1).

#### Response

Refer to the response for [`engine_newPayloadV3`](./cancun.md#engine_newpayloadv3).

#### Specification

This method follows the same specification as [`engine_newPayloadV3`](./cancun.md#engine_newpayloadv3) with the following changes:

1. Client software **MUST** return `-38005: Unsupported fork` error if the `timestamp` of the payload does not fall within the time frame of the Prague fork.

### engine_newInclusionListV1

#### Request

* method: `engine_newInclusionListV1`
* params:
  1. `parent_hash`: `DATA`, 32 Bytes - parent hash which this inclusion list is built upon.
  2. `inclusionListSummaryList`: `InclusionListSummaryListV1` - Summary.
  3. `inclusionListTransactions`: `Array of DATA` - Array of transaction objects, each object is a byte list (`DATA`) representing `TransactionType || TransactionPayload` or `LegacyTransaction` as defined in [EIP-2718](https://eips.ethereum.org/EIPS/eip-2718)
* timeout: 1s

#### Response

* result: [`InclusionListStatusV1`](./#inclusionliststatusv1).
* error: code and message set in case an exception happens while processing the inclusion list.

#### Specification

1. Client software **MUST** validate the inclusion list transactions are valid (correct nonce and sufficient base fee) given the parent block hash specified. If the parent block is not available, return false.
2. Client software **MUST** validate that the sum of inclusion list transactions gas does not exceed `INCLUSION_LIST_MAX_GAS`.   
3. Client software **MUST** validate that the summary and transactions are the same length.
4. Client software **MUST** validate that the order of the summary entries matches the order of the transactions.

### engine_getInclusionListV1

#### Request

* method: `engine_getInclusionListV1`
* params:
  1. `parent_hash`: `DATA`, 32 Bytes - parent hash which returned inclusion list should be built upon.
* timeout: 1s

#### Response

* result: `object`
  - `inclusionListSummaryList`: `InclusionListSummaryListV1` - Summary.
  - `inclusionListTransactions`: `Array of DATA` - Array of transaction objects, each object is a byte list (`DATA`) representing `TransactionType || TransactionPayload` or `LegacyTransaction` as defined in [EIP-2718](https://eips.ethereum.org/EIPS/eip-2718)
* error: code and message set in case an exception happens while getting the inclusion list.

#### Specification

1. Client software **MUST** provide a list of transactions for the inclusion list based on local view of the mempool and according to the config specifications.
2. Client software **MUST** broadcast their inclusion list in addition to the full beacon block during their block proposal.