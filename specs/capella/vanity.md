# Capella -- Vanity Art

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [ANSI art](#ansi-art)
- [Theme](#theme)
- [Display triggers](#display-triggers)
  - [Fork transition](#fork-transition)
  - [Relevant BLS to Execution change](#relevant-bls-to-execution-change)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes user-visible vanity features for Capella.

Features described in this document are OPTIONAL.

## ANSI art

Implementations MAY display themed ANSI art as part of their logs when certain criteria are met.

- Art MUST NOT interfere with validator duties or with node operation.
- Art MAY use ANSI colors or ANSI blink sequences. If used, it MUST be ensured that original formatting settings are restored after the art is displayed. Art SHOULD still be recognizable even when a terminal is not configured to show ANSI escape sequences.
- When logging to a file, a short version MAY be used, for example, a single line with an emoji and a text.

## Theme

The theme for Capella is the owl 🦉.

## Display triggers

### Fork transition

When Capella is triggered, themed art MAY be displayed. This confirms to the user that withdrawals are now available. The condition to check is that `compute_fork_version` for `compute_epoch_at_slot` at the chain head as selected by fork choice transitions from an earlier fork version to `CAPELLA_FORK_VERSION`. Art MAY be displayed repeatedly in case of reorgs around the fork transition.

### Relevant BLS to Execution change

When a block with `BLSToExecutionChange` messages for validators relevant to the user is processed, themed art MAY be displayed. This confirms to the user that they have completed all steps necessary to enable withdrawals. Relevance of a validator is determined in an implementation-defined manner, and can include locally attached validators, validators attached through a validator client, or remote signers. The condition to check is that `has_eth1_withdrawal_credential` for relevant validators at the chain head as selected by fork choice transitions from `False` to `True`. Art MAY be displayed repeatedly in case of reorgs around a BLS to Execution change. Art SHOULD be limited on nodes with a large number of relevant validators, e.g., by only tracking up through 64 relevant validators.
