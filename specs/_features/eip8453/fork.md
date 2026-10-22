# EIP-8453 -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configs](#configs)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the EIP-8453 upgrade.

*Note*: The upgrade function, which sets the initial state of the finality
gadget, is not yet specified.

## Configs

Warning: this configuration is not definitive.

| Name                   | Value                                 |
| ---------------------- | ------------------------------------- |
| `EIP8453_FORK_VERSION` | `Version("0xe8453000")`               |
| `EIP8453_FORK_EPOCH`   | `Epoch(18446744073709551615)` **TBD** |
