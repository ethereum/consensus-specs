# Decoupled Consensus -- Fork Logic

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configs](#configs)

<!-- mdformat-toc end -->

## Introduction

This document describes the process of the DC upgrade.

*Note*: The upgrade function, which sets the initial state of the finality
gadget, is not yet specified.

## Configs

Warning: this configuration is not definitive.

| Name              | Value                                 |
| ----------------- | ------------------------------------- |
| `DC_FORK_VERSION` | `Version("0xdc000000")`               |
| `DC_FORK_EPOCH`   | `Epoch(18446744073709551615)` **TBD** |
