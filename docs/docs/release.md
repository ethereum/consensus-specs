# Release Procedure

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Open a Release Pull Request](#open-a-release-pull-request)
- [Bump the Version](#bump-the-version)
- [Merge the Release Pull Request](#merge-the-release-pull-request)
- [Tag the Release](#tag-the-release)
- [Make an Announcement](#make-an-announcement)

<!-- mdformat-toc end -->

## Introduction

This document describes the necessary steps to produce a consensus-specs
release.

## Open a Release Pull Request

> [!NOTE]
> Try to do this at least a few days prior to the release.

First, create a PR which merges `dev` into `master`.

> [!TIP]
> Click on the following link to draft a PR:
>
> - https://github.com/ethereum/consensus-specs/compare/dev...master?expand=1

Title this PR "Release \<version>" (_e.g._, "Release v1.5.0-alpha.10").

In the PR's description, provide a list of items that must be done. At the
bottom, list unmerged PRs which are to be included in the release; this signals
to other maintainers and developers that they should review these PRs soon.

```markdown
- [ ] testgen
- [ ] version bump
- [ ] #1234
- [ ] #2345
- [ ] #3456
```

## Bump the Version

Next, update the `VERSION.txt` file which contains the eth2spec version.

> [!TIP]
> Click on the following link to open the GitHub editor for this file:
>
> - https://github.com/ethereum/consensus-specs/edit/dev/tests/core/pyspec/eth2spec/VERSION.txt

Next, change the version to the appropriate value and click the "Commit
changes..." button.

For the commit message, put "Bump version to \<version>" (_e.g._, "Bump version
to 1.5.0-alpha.10").

Next, click the "Propose changes" button and proceed to make the PR.

## Merge the Release Pull Request

> [!IMPORTANT]
> Be sure to merge this using the "Create a merge commit" method.

After all PRs have been merged/addressed, merge the release PR.

## Tag the Release

Next, tag the latest commit to master. This will trigger the
[automated release process](../../.github/workflows/release.yml).

```bash
git clone git@github.com:ethereum/consensus-specs.git
cd consensus-specs
git tag <version>
git push origin <version>
```

Approximately 12 hours later, the releases for consensus-specs and
consensus-spec-tests will be available on GitHub.

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

Test vectors: https://github.com/ethereum/consensus-spec-tests/releases/tag/<version>
```
