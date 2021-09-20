<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [The Merge -- Client Settings](#the-merge----client-settings)
    - [Override terminal total difficulty](#override-terminal-total-difficulty)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# The Merge -- Client Settings

**Notice**: This document is a work-in-progress for researchers and implementers.

This document specifies configurable settings that clients must implement for the Merge.

### Override terminal total difficulty

To coordinate manual overrides to [`TERMINAL_TOTAL_DIFFICULTY`](./beacon-chain.md#Transition-settings) parameter, clients must provide `--terminal-total-difficulty-override` as a configurable setting. The value provided by this setting must take precedence over pre-configured `TERMINAL_TOTAL_DIFFICULTY` parameter.

Except under exceptional scenarios, this setting is expected to not be used. Sufficient warning to the user about this exceptional configurable setting should be provided.

