# Deneb -- Vanity Art

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [ANSI art](#ansi-art)
- [Theme](#theme)
- [Display triggers](#display-triggers)
  - [Fork transition](#fork-transition)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes user-visible vanity features for Deneb.

Features described in this document are OPTIONAL.

## ANSI art

Implementations MAY display themed ANSI art as part of their logs when certain criteria are met.

- Art MUST NOT interfere with validator duties or with node operation.
- Art MAY use ANSI colors or ANSI blink sequences. If used, it MUST be ensured that original formatting settings are restored after the art is displayed. Art SHOULD still be recognizable even when a terminal is not configured to show ANSI escape sequences.
- When logging to a file, a short version MAY be used, for example, a single line with an emoji and a text.

## Theme

The theme for Deneb is the blobfish 🐟.

## Display triggers

### Fork transition

When Deneb is activated, themed art MAY be displayed. This confirms to the user that blob transactions are now available. The condition to check is that `compute_fork_version` for `compute_epoch_at_slot` reports `DENEB_FORK_VERSION` for the chain head, but an earlier fork version for its parent. Art MAY be displayed repeatedly in case of reorgs around the fork transition.
