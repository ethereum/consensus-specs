# The Merge -- Client Settings

**Notice**: This document is a work-in-progress for researchers and implementers.

This document specifies configurable settings that clients must implement for the Merge.

### Override terminal total difficulty

To coordinate manual overrides to [`terminal_total_difficulty`](fork-choice.md#transitionstore), clients
must provide `--terminal-total-difficulty-override` as a configurable setting.

If `TransitionStore` has already [been initialized](./fork.md#initializing-transition-store), this alters the previously initialized value of
`TransitionStore.terminal_total_difficulty`, otherwise this setting initializes `TransitionStore` with the specified, bypassing `compute_terminal_total_difficulty` and the use of an `anchor_pow_block`.
`terminal_total_difficulty`.

Except under exceptional scenarios, this setting is expected to not be used, and `terminal_total_difficulty` will operate with [default functionality](./fork.md#initializing-transition-store). Sufficient warning to the user about this exceptional configurable setting should be provided.
[here](fork.md#initializing-transition-store).
