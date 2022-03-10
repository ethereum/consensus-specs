# EIP-4844 -- Fork Logic

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Configuration](#configuration)
- [Fork to EIP-4844](#fork-to-eip-4844)
  - [Fork trigger](#fork-trigger)
  - [Upgrading the state](#upgrading-the-state)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes the process of EIP-4844 upgrade.

## Configuration

Warning: this configuration is not definitive.

| Name | Value |
| - | - |
| `EIP4844_FORK_VERSION` | `Version('0x03000000')` |
| `EIP4844_FORK_EPOCH` | `Epoch(18446744073709551615)` **TBD** |

## Fork to EIP-4844

### Fork trigger

TBD. This fork is defined for testing purposes, the EIP may be combined with other consensus-layer upgrade.
For now we assume the condition will be triggered at epoch `EIP4844_FORK_EPOCH`.

Note that for the pure EIP-4844 networks, we don't apply `upgrade_to_eip4844` since it starts with EIP-4844 version logic.

### Upgrading the state

The `eip4844.BeaconState` format is equal to the `bellatrix.BeaconState` format, no upgrade has to be performed.

