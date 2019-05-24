# Ethereum 2.0 Phase 0 -- Beacon Node API for Validator

__NOTICE__: This document is a work-in-progress for researchers and implementers. This is an accompanying document to [Ethereum 2.0 Phase 0 -- Honest Validator](0_beacon-chain-validator.md) that describes an API exposed by the beacon node, which enables the validator client to participate in the Ethereum 2.0 protocol.

## Outline

This document outlines a minimal application programming interface (API) which is exposed by a beacon node for use by a validator client implementation which aims to facilitate [_phase 0_](../../README.md#phase-0) of Ethereum 2.0.

The API is a REST interface, accessed via HTTP, designed for use as a local communications protocol between binaries. The only supported return data type is currently JSON.

###  Background
The beacon node maintains the state of the beacon chain by communicating with other beacon nodes in the Ethereum Serenity network. Conceptually, it does not maintain keypairs that participate with the beacon chain.

The validator client is a conceptually separate entity which utilizes private keys to perform validator related tasks on the beacon chain, which we call validator "duties". These duties include the production of beacon blocks and signing of attestations.

Since it is recommended to separate these concerns in the client implementations, we must clearly define the communication between them.

The goal of this specification is to promote interoperability between beacon nodes and validator clients derived from different projects and to encourage innovation in validator client implementations, independently from beacon node development. For example, the validator client from Lighthouse could communicate with a running instance of the beacon node from Prysm, or a staking pool might create a decentrally managed validator client which utilises the same API.

This specification is derived from a proposal and discussion on Issues [#1011](https://github.com/ethereum/eth2.0-specs/issues/1011) and [#1012](https://github.com/ethereum/eth2.0-specs/issues/1012)


## Specification 

The API specification has been written in [OpenAPI 3.0](https://swagger.io/docs/specification/about/) and is provided in the [beacon_node_oapi.yaml](beacon_node_oapi.yaml) file alongside this document.

For convenience, this specification has been uploaded to [SwaggerHub](https://swagger.io/tools/swaggerhub/) at the following URL:
[https://app.swaggerhub.com/apis/spble/beacon_node_api_for_validator/0.1](https://app.swaggerhub.com/apis/spble/beacon_node_api_for_validator/0.1)
