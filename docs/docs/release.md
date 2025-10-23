# Release Procedure

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Bump the Version](#bump-the-version)
- [Tag the Release](#tag-the-release)
- [Make an Announcement](#make-an-announcement)

<!-- mdformat-toc end -->

## Introduction

This document describes the necessary steps to produce a consensus-specs
release.

## Bump the Version

Next, update the `VERSION.txt` file which contains the eth2spec version.

> [!TIP]
> Click on the following link to open the GitHub editor for this file:
>
> - https://github.com/ethereum/consensus-specs/edit/master/tests/core/pyspec/eth2spec/VERSION.txt

Next, change the version to the appropriate value and click the "Commit
changes..." button.

For the commit message, put "Bump version to \<version>" (_e.g._, "Bump version
to 1.5.0-alpha.10").

Next, click the "Propose changes" button and proceed to make the PR.

## Tag the Release

Next, tag the latest commit to master. This will trigger the
[automated release process](../../.github/workflows/release.yml).

```bash
git clone git@github.com:ethereum/consensus-specs.git
cd consensus-specs
git tag <version>
git push origin <version>
```

Several hours later, the consensus-specs release will be automatically published
on GitHub.

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
