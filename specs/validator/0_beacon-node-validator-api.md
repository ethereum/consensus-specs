# Ethereum 2.0 Phase 0 -- Beacon Node API for Validator

__NOTICE__: This document is a work-in-progress for researchers and implementers. This is an accompanying document to [Ethereum 2.0 Phase 0 -- Honest Validator](0_beacon-chain-validator.md) that describes an API exposed by the beacon node, which enables the validator client to participate in the Ethereum 2.0 protocol.

## Table of Contents

<!-- TOC -->

<!-- /TOC -->

## Outline

This document outlines a minimal application programming interface (API) which is exposed by a `BeaconNode` for use by a `ValidatorClient` which aims to facilitate [_phase 0_](../../README.md#phase-0) of Ethereum 2.0.

The API is a REST interface, accessed via HTTP, designed for use as a local communications protocol between binaries.

###  Background
The beacon node maintains the state of the beacon chain by communicating with other beacon nodes in the Ethereum Serenity network. Conceptually, it does not maintain keypairs that participate with the beacon chain.

The validator client is a conceptually separate entity which utilises private keys to perform validator related tasks on the beacon chain, which we call validator "duties". These duties includes the production of beacon blocks and signing of attestations.

Since it is recommended to separate these concerns in the client implementations, we must clearly define the communication between them.

The goal of this specification is to promote interoperability between beacon nodes and validator clients derived from different projects. For example, the validator client from Lighthouse, could communicate with a running instance of the beacon node from Prysm.

This specification is derived from a proposal and discussion on Issues [#1011](https://github.com/ethereum/eth2.0-specs/issues/1011) and [#1012](https://github.com/ethereum/eth2.0-specs/issues/1012)


## Specification 

### Entities 
The following are the two entities that participate in this protocol:
 - **`BeaconNode`**:
 A beacon node instance, run with a `--rpc` flag to enable the RPC interface. Runs stand-alone.

 - **`ValidatorClient`**:
A validator client instance, which must connect to at least one instance of `BeaconNode`.


### Endpoints
This section summarises API endpoints which are published by an instance of `BeaconNode`, for the exclusive use of `ValidatorClient` implementations.
 
This proposal is a minimum set of messages necessary to enable effective communication, without any extra features. Anything extra is beyond the scope of this document.

#### Summary Table
| Name      | Type | Parameters |  Returns |  
| --------  | ---  | -----      |  -----   | 
| [`get_client_version`](#get_client_version) | GET | N/A        |  `client_version` | 
| [`get_genesis_time`](#get_genesis_time) | GET | N/A        |  `genesis_time` | 
| [`get_syncing_status`](#get_syncing_status) | GET | N/A        |  `syncing_status` | 
| [`get_duties`](#get_duties) | GET | `validator_pubkeys` |  `syncing_status`, `current_version`, [`ValidatorDuty`]| 
| [`produce_block`](#produce_block) | GET | `slot`, `randao_reveal` | `beacon_block` | 
| [`publish_block`](#publish_block) | POST |  `beacon_block` |  N/A  | 
| [`produce_attestation`](#produce_attestation) | GET | `slot`, `shard` |  `indexed_attestation` | 
| [`publish_attestation`](#publish_attestation) | POST | `indexed_attestation` | N/A | Publishes the IndexedAttestation after having been signed by the ValidatorClient |

#### Status Codes
For each of these endpoints the underlying transport protocol should provide status codes. Assuming this will be based on HTTP, one of the following standard status codes will always be included as part of a response:

| Code | Meaning |
| ---  | ---     |
| `200`  | The API call succeeded. |
| `40X`  | The request was malformed.   |
| `500`  | The `BeaconNode` cannot complete the request due to an internal error. |
| `503`  | The `BeaconNode` is currently syncing, try again later. _A call can be made to `get_syncing_status` to in order to find out how much has been synchronised._ |

#### `get_client_version`
Requests that the `BeaconNode` identify information about its implementation in a format similar to a [HTTP User-Agent](https://tools.ietf.org/html/rfc7231#section-5.5.3) field.

 - **Parameters**: N/A
 - **Returns**:
 
 | Name         | Type          | Description |
 | ---          | ---              | --- |
 | `client_version`  | bytes32 | An ASCII-encoded hex string which uniquely defines the implementation of the `BeaconNode` and its current software version. |
 
 **Note**: _Unlike most other endpoints, `get_client_version` does not return an error `503` while the `BeaconNode` is syncing, but instead returns status code `200`._


#### `get_genesis_time`
 Requests the `genesis_time` parameter from the `BeaconNode`, which should be consistent across all `BeaconNodes` that follow the same beacon chain.
 
 - **Parameters**: N/A
 - **Returns**:
 
 | Name         | Type          | Description |
 | ---          | ---              | --- |
 | `genesis_time`  | uint64 | The [`genesis_time`](https://github.com/ethereum/eth2.0-specs/blob/dev/specs/core/0_beacon-chain.md#on-genesis), which is a fairly static configuration option for the `BeaconNode`. |
 
 **Note**: _Unlike most other endpoints, `get_genesis_time` does not return an error `503` while the `BeaconNode` is syncing, but instead returns status code `200`._


#### `get_syncing_status`
 Requests the `BeaconNode` to describe if it's currently syncing or not, and if it is, what block it is up to. This is modelled after the Eth1.0 JSON-RPC [`eth_syncing`](https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_syncing) call.
  - **Parameters**: N/A
 - **Returns**:
 
 | Name         | Type          | Description |
 | ---          | ---              | --- |
 | `syncing`  | `false` OR `SyncingStatus` | Either `false` if the node is not syncing, or a [`SyncingStatus`](#SyncingStatus) object if it is. |
 
  **Note**: _Unlike most other endpoints, `get_syncing_status` does not return an error `503` while the `BeaconNode` is syncing, but instead returns status code `200` with the `SyncingStatus` object._
 

#### `get_duties`
  Requests the BeaconNode to provide a set of “duties”, which are actions that should be performed by ValidatorClients. This API call should be polled at every slot, to ensure that any chain reorganisations are catered for, and to ensure that the currently connected `BeaconNode` is properly synchronised.
  
 - **Parameters**: 
 
 | Name                 | Type      | Description   | 
 | ---                  | ---       |  ---          |
 | `validator_pubkeys`  | [bytes48] | A list of unique validator public keys, where each item is a `0x` encoded hex string. |
 
 - **Returns**:
 
 | Name                 | Type              | Description   |
 | ---                  | ---               | ---           |
 | `current_version`    | bytes4            | The `current_version`, as described by the current [`Fork`](#Fork). |
 | `validator_duties`   | [`ValidatorDuty`] | A list where each item is a custom [`ValidatorDuty`](#ValidatorDuty) object. |
 
 
 #### `produce_block`
 Requests a `BeaconNode` to produce a valid block, which can then be signed by a ValidatorClient.
 
 - **Parameters**: 
 
 | Name             | Type      | Description |
 | ---              | ---       | --- |
 | `slot`           | uint64    | The slot for which the block should be proposed. |
 | `randao_reveal`  | bytes     | The ValidatorClient's randao reveal value. |
 
 - **Returns**:
 
 | Name             | Type          | Description |
 | ---              | ---           | --- |
 | `beacon_block`   | `BeaconBlock` | A proposed [`BeaconBlock`](#BeaconBlock) object, but with the `signature` field left blank.
 
 
 #### `publish_block`
 Instructs the `BeaconNode` to publish a newly signed beacon block to the beacon network, to be included in the beacon chain.
 - **Parameters**: 
 
 | Name             | Type      | Description |
 | ---              | ---       | --- |
 | `beacon_block`   | `BeaconBlock` | The [`BeaconBlock`](#BeaconBlock) object, as sent from the `BeaconNode` originally, but now with the `signature` field completed.
 
 - **Returns**: N/A
 
 
 ####  `produce_attestation`
 Requests that the `BeaconNode` produce an `IndexedAttestation`, with a blank `signature` field, which the `ValidatorClient` will then sign.
 
 - **Parameters**: 
 
 | Name             | Type      | Description |
 | ---              | ---       | --- |
 | `slot`           | uint64    | The slot for which the attestation should be proposed. |
 | `shard`          | uint64    | The shard number for which the attestation is to be proposed. |
 
 - **Returns**:
 
 | Name             | Type          | Description |
 | ---              | ---           | --- |
 | `indexed_attestation`   | `IndexedAttestation` | An [`IndexedAttestation`](#IndexedAttestation) structure with the `signature` field left blank. |
 
 #### `publish_attestation`
 Instructs the `BeaconNode` to publish a newly signed `IndexedAttestation` object, to be incorporated into the beacon chain.
 
 - **Parameters**: 
 
 | Name             | Type          | Description |
 | ---              | ---           | --- |
 | `indexed_attestation`   | `IndexedAttestation` | An [`IndexedAttestation`](#IndexedAttestation) structure, as originally provided by the `BeaconNode`, but now with the `signature` field completed. |
  - **Returns**: N/A
 


 -----

### Data Structures
Two new data objects are proposed for the sake of implementation, and several other data objects from the Eth2.0 specs are referenced.

The `bytes` data types are encoded hex strings, with `0x` preceeding them. `uint64` are decimal encoded integers, and `None` may be `null`, which is distinct from `0`.

#### `ValidatorDuty`
```asm
{
    
    # The validator's public key, uniquely identifying them
    'validator_pubkey': 'bytes48',
    # The index of the validator in the committee
    'committee_index': 'uint64',
    # The slot at which the validator must attest.
    'attestation_slot': 'uint64',
    # The shard in which the validator must attest
    'attestation_shard': 'uint64',
    # The slot in which a validator must propose a block. This field can also be None.
    'block_production_slot': 'uint64' or None
}
```

#### `SyncingStatus`
As described by the [Eth1.0 JSON-RPC](https://github.com/ethereum/wiki/wiki/JSON-RPC#eth_syncing).:
```asm
{
    # The block at which syncing started (will only be reset, after the sync reached his head)
    'startingBlock': 'uint64',
    # The current block
    'currentBlock': 'uint64',
    # The estimated highest block, or current target block number
    'highestBlock': 'uint64'    
}
```

#### `Fork`
As described by [Fork](https://github.com/ethereum/eth2.0-specs/blob/dev/specs/core/0_beacon-chain.md#Fork) in the Eth2.0 specs.

#### `BeaconBlock`
As described by [BeaconBlock](https://github.com/ethereum/eth2.0-specs/blob/dev/specs/core/0_beacon-chain.md#BeaconBlock) in the Eth2.0 specs.

#### `IndexedAttestation`
As described by [IndexedAttestation](https://github.com/ethereum/eth2.0-specs/blob/dev/specs/core/0_beacon-chain.md#IndexedAttestation) in the Eth2.0 specs.
  
  
 
  
## Optional Extras

#### Endpoint: `get_fork`
 Requests the `BeaconNode` to provide which fork version it is currently on.
 - **Parameters**: N/A
 - **Returns**:
 
 | Name         | Type          | Description |
 | ---          | ---              | --- |
 | `fork`  | [`Fork`](#Fork) | Provides the current version information for the fork which the `BeaconNode` is currently following. |
 | `chain_id` | uint64  | Sometimes called the network id, this number discerns the active chain for the `BeaconNode`. Analagous to Eth1.0 JSON-RPC [`net_version`](https://github.com/ethereum/wiki/wiki/JSON-RPC#net_version). |
  
