# The Merge -- Client Settings

**Notice**: This document is a work-in-progress for researchers and implementers.

This document specifies configurable settings that clients must implement for the Merge.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [The Merge -- Client Settings](#the-merge----client-settings)
    - [Override terminal total difficulty](#override-terminal-total-difficulty)
    - [Override terminal block hash](#override-terminal-block-hash)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

### Override terminal total difficulty

To coordinate manual overrides to [`terminal_total_difficulty`](./fork-choice.md#transitionstore), clients
must provide `--terminal-total-difficulty-override` as a configurable setting.

If `TransitionStore` has already [been initialized](./fork.md#initializing-transition-store), this alters the previously initialized value of
`TransitionStore.terminal_total_difficulty`, otherwise this setting initializes `TransitionStore` with the specified `terminal_total_difficulty`, bypassing `compute_terminal_total_difficulty` and the use of an `anchor_pow_block`.

Except under exceptional scenarios, this setting is expected to not be used, and `terminal_total_difficulty` will operate with [default functionality](./fork.md#initializing-transition-store). Sufficient warning to the user about this exceptional configurable setting should be provided.

### Override terminal block hash

In case fork coordination around a specific PoW block hash is necessary, clients must also provide `--terminal-block-hash-override` as a configurable setting.

If `TransitionStore` has already [been initialized](./fork.md#initializing-transition-store), this alters the previously initialized value of
`TransitionStore.terminal_block_hash`, otherwise this setting initializes `TransitionStore` with the specified `terminal_block_hash`.

As with `--terminal-total-difficulty-override`, this setting is not expected to be used unless under exceptional scenarios and sufficient warning to the user about this setting should be provided.
