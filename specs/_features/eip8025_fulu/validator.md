# EIP-8025 (Fulu) -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Validator behavior](#validator-behavior)

<!-- mdformat-toc end -->

## Introduction

This document provides guidance for validators in the EIP-8025 network on Fulu.

*Note*: This specification is built upon [Fulu](../../fulu/validator.md) and
imports proof types from [proof-engine.md](./proof-engine.md).

## Validator behavior

In EIP-8025 on Fulu, execution proof generation is handled by whitelisted
provers. Validators inherit all behaviors from the Fulu specification except
where overridden by this document.

Validators are not required to generate execution proofs themselves. Instead,
they rely on provers (either standalone provers or prover relays) to generate
and broadcast execution proofs for the payloads they produce.
