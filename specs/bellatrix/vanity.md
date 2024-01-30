# Bellatrix -- Vanity Art

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [ANSI art](#ansi-art)
- [Theme](#theme)
- [Display triggers](#display-triggers)
  - [Merge transition](#merge-transition)
  - [Merge finalization](#merge-finalization)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes user-visible vanity features for Bellatrix.

Features described in this document are OPTIONAL.

## ANSI art

Implementations MAY display themed ANSI art as part of their logs when certain criteria are met.

- Art MUST NOT interfere with validator duties or with node operation.
- Art MAY use ANSI colors or ANSI blink sequences. If used, it MUST be ensured that original formatting settings are restored after the art is displayed. Art SHOULD still be recognizable even when a terminal is not configured to show ANSI escape sequences.
- When logging to a file, a short version MAY be used, for example, a single line with an emoji and a text.

## Theme

The theme for Bellatrix is the panda 🐼.

## Display triggers

### Merge transition

When the merge transition completes, themed art MAY be displayed. This confirms to the user that they correctly configured the engine API connection. The condition to check is that `is_merge_transition_complete` at the chain head as selected by fork choice transitions from `False` to `True`. Art MAY be displayed repeatedly in case of reorgs around the merge transition.

### Merge finalization

When the merge transition finalizes, themed art MAY be displayed. This confirms to the user that the Proof-of-Work era is over. The condition to check is that the `execution_payload.block_hash` associated with the `finalized_checkpoint` as selected by fork choice transitions from the zero hash to a non-zero value.
