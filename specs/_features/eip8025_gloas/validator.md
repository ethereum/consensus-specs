# EIP-8025 (Gloas) -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Validator behavior](#validator-behavior)

<!-- mdformat-toc end -->

## Introduction

This document provides guidance for validators in the EIP-8025 network on Gloas.

*Note*: This specification is built upon [Gloas](../../gloas/validator.md) and
imports proof types from
[eip8025_fulu/proof-engine.md](../eip8025_fulu/proof-engine.md).

## Validator behavior

In EIP-8025 on Gloas, execution proof generation is handled by builders and
whitelisted provers. Validators inherit all behaviors from the Gloas
specification except where overridden by this document.

Validators are not required to generate execution proofs themselves. Instead,
they rely on builders (who produce the execution payloads) and provers (either
standalone provers or prover relays) to generate and broadcast execution proofs.
