# EIP-7547 -- Honest Validator

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Helpers](#helpers)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Inclusion list validation](#inclusion-list-validation)
  - [Inclusion list proposal](#inclusion-list-proposal)
    - [Constructing the inclusion list](#constructing-the-inclusion-list)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement EIP-7547.

## Prerequisites

This document is an extension of the [Deneb -- Honest Validator](../../deneb/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [EIP-7547](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Helpers

## Protocols

### `ExecutionEngine`

*Note*: `engine_getInclusionListV1` and `engine_newInclusionListV1` functions are added to the `ExecutionEngine` protocol for use as a validator.

The body of these function is implementation dependent. The Engine API may be used to implement it with an external execution engine. 

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.

### Inclusion list validation

When receiving a new block, the validator must verify the inclusion list by calling `engine_newInclusionListV1` after verifying the signature. The execution layer will process inclusion list transactions to ensure they are valid. Once the inclusion list validity is asserted, the validator must check the block by calling `engine_newPayloadV3`.

### Inclusion list proposal

EIP7547 introduces forward inclusion list. The detail design is described in this [post](https://ethresear.ch/t/no-free-lunch-a-new-inclusion-list-design/16389).

Proposer must construct and broadcast `SignedBeaconBlockAndInclusionList` along with the beacon block.

#### Constructing the inclusion list

To obtain an inclusion list, a block proposer building a block on top of a `state` must take the following actions:

1. Retrieve `SignedInclusionList` from execution layer by calling `engine_getInclusionListV1`.
2. Publish the `SignedBeaconBlockAndInclusionList` over the `beacon_block` topic.


