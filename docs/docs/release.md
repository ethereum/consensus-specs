# Release Procedure

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Bump the Version](#bump-the-version)
- [Publish the Release](#publish-the-release)
- [Make an Announcement](#make-an-announcement)

<!-- mdformat-toc end -->

## Introduction

This document describes the necessary steps to produce a consensus-specs
release.

## Bump the Version

First, update the `VERSION.txt` file which contains the eth2spec version.

> [!TIP]
> Click on the following link to open the GitHub editor for this file:
>
> - https://github.com/ethereum/consensus-specs/edit/master/tests/core/pyspec/eth2spec/VERSION.txt

Next, change the version to the appropriate value and click the "Commit
changes..." button.

For the commit message, put "Bump version to \<version>" (_e.g._, "Bump version
to 1.5.0-alpha.10").

Next, click the "Propose changes" button and proceed to make the PR.

## Publish the Release

First, go to
[Actions > Release](https://github.com/ethereum/consensus-specs/actions/workflows/release.yml).

Next, click the "Run workflow" dropdown box at the top right-hand corner.

Next, click the green "Run workflow" button.

> [!NOTE]
> The release workflow will create a tag from `VERSION.txt` and fail if the tag
> already exists. Many hours later, if successful, the consensus-specs release
> will be automatically published on GitHub. The release action can take up to
> 24 hours to run.

> [!TIP]
> If the release fails, delete the tag, fix the issue, and re-run the release
> workflow.

## Make an Announcement

> [!IMPORTANT]
> In order to do this, you must be granted the appropriate access.

Finally, make an announcement to the Eth R&D server on Discord. This should be
posted in the `#announcements` channel. This will notify client developers of
the new release and they will begin to incorporate the new reference tests into
their client.

Use the following template for your announcement:

```markdown
Consensus layer specs <version> -- <release-name> -- released!

https://github.com/ethereum/consensus-specs/releases/tag/<version>
```
