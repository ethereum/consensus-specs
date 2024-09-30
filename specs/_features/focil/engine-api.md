# Engine API -- FOCIL

Engine API changes introduced in FOCIL.

This specification is based on and extends [Engine API - Prague](./prague.md) specification.

Warning: This file should be placed in https://github.com/ethereum/execution-apis but I'm placing it here for convenience of reviewing.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Constants](#constants)
  - [PayloadStatusV2](#payloadstatusv2)
- [Methods](#methods)
  - [engine_newPayloadV5](#engine_newpayloadv5)
    - [Request](#request)
    - [Response](#response)
    - [Specification](#specification)
  - [engine_updateBlockWithInclusionListV1](#engine_updateblockwithinclusionlistv1)
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
| `LOCAL_INCLUSION_LIST_MAX_GAS` |  `uint64(4194304) = 2**22` |

### PayloadStatusV2

This structure contains the result of processing a payload. The fields are encoded as follows:

- `status`: `enum` - `"VALID" | "INVALID" | "SYNCING" | "ACCEPTED" | "INVALID_BLOCK_HASH" | "INVALID_INCLUSION_LIST"`
- `latestValidHash`: `DATA|null`, 32 Bytes - the hash of the most recent *valid* block in the branch defined by payload and its ancestors
- `validationError`: `String|null` - a message providing additional details on the validation error if the payload is classified as `INVALID` or `INVALID_BLOCK_HASH`.

## Methods

### engine_newPayloadV5

The request of this method is updated with [`ExecutionPayloadV5`](#ExecutionPayloadV5).

#### Request

* method: `engine_newPayloadV5`
* params:
  1. `executionPayload`: [`ExecutionPayloadV4`](#ExecutionPayloadV4).
  2. `expectedBlobVersionedHashes`: `Array of DATA`, 32 Bytes - Array of expected blob versioned hashes to validate.
  3. `parentBeaconBlockRoot`: `DATA`, 32 Bytes - Root of the parent beacon block.
  4. `inclusionListTransactions`: `Array of DATA` - Array of transaction objects, each object is a byte list (`DATA`) representing `TransactionType || TransactionPayload` or `LegacyTransaction` as defined in [EIP-2718](https://eips.ethereum.org/EIPS/eip-2718)

#### Response

* result: [`PayloadStatusV2`](#PayloadStatusV2)

#### Specification

1. Client software **MUST** respond to this method call in the following way:
  * `{status: INVALID_INCLUSION_LISTING, latestValidHash: null, validationError: null}` if there are any leftover `inclusionListTransactions` that are not part of the `executionPayload`, they can be processed at the end of the `executionPayload`.

### engine_updateBlockWithInclusionListV1

#### Request

* method: `engine_updateBlockWithInclusionListV1`
* params:
  1. `payloadId`: `DATA`, 8 Bytes - Identifier of the payload build process
  2. `inclusionListTransactions`: `Array of DATA` - Array of transaction objects, each object is a byte list (`DATA`) representing `TransactionType || TransactionPayload` or `LegacyTransaction` as defined in [EIP-2718](https://eips.ethereum.org/EIPS/eip-2718)
* timeout: 1s

#### Response

#### Specification

1. Given the `payloadId` client software **MUST** update payload build process building with a list of `inclusionListTransactions`. The transactions must be part of the execution payload unless it fails to be included at the end of the execution block.

* error: code and message set in case an exception happens while getting the payload.

### engine_getInclusionListV1

#### Request

* method: `engine_getInclusionListV1`
* params:
  1. `parent_hash`: `DATA`, 32 Bytes - parent hash which returned inclusion list should be built upon.
* timeout: 1s

#### Response

* result: `object`
  - `inclusionListTransactions`: `Array of DATA` - Array of transaction objects, each object is a byte list (`DATA`) representing `TransactionType || TransactionPayload` or `LegacyTransaction` as defined in [EIP-2718](https://eips.ethereum.org/EIPS/eip-2718)
* error: code and message set in case an exception happens while getting the inclusion list.

#### Specification

1. Client software **MUST** provide a list of transactions for the inclusion list based on local view of the mempool and according to the config specifications.