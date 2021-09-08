# The Merge -- Client Settings

**Notice**: This document is a work-in-progress for researchers and implementers.

This document specifies configurable settings that merge clients are expected to ship with.

### Override terminal total difficulty

To coordinate changes to [`terminal_total_difficulty`](fork-choice.md#transitionstore), clients
should have a setting `--terminal-total-difficulty-override`.

If `TransitionStore` has already been initialized, this just changes the value of
`TransitionStore.terminal_total_difficulty`, otherwise it initializes `TransitionStore` with the specified
`terminal_total_difficulty`.

By default, this setting is expected to not be used and `terminal_total_difficulty` will be set as defined
[here](fork.md#initializing-transition-store).
