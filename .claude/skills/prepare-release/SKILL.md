---
name: prepare-release
description: >-
  Prepare for a new release. Perform checks to ensure that the release action
  can be started. Use when the user asks for help with a new release.
compatibility: Requires git and gh
---

# Prepare for a release

The release process is mostly automated via the release
[action](https://github.com/ethereum/consensus-specs/actions/workflows/release.yml)
on GitHub, which is started manually by a maintainer. Before starting this
action there is a checklist which must be handled. Feel free to ask the user for
information that you are unable to obtain yourself. When performing these
checks, do not make any modifications to the repository. These steps apply to
`ethereum/consensus-specs@master` on GitHub, not the working tree or the local
`master` branch (which may belong to a fork).

## Check the version

The current version can be found in
`tests/core/pyspec/eth_consensus_specs/VERSION.txt`. It follows the standard
`major.minor.patch` format and does not contain a leading `v` letter. The major
version number is unlikely to change. The minor number corresponds to the
upgrade sequence. After an upgrade goes live on mainnet, the minor number is
incremented to reflect that work on the next upgrade has started. The patch
number is incremented for releases after the stable release for an upgrade is
made but before the upgrade goes live on mainnet. In the devnet testing phase,
use the alpha qualifier. In the testnet testing phase, use the beta qualifier.
Only after the last testnet is upgraded and the upgrade is scheduled can the
pre-release qualifier be removed.

## Compare version to last release

Check that the current version does not already exist as a release or tag. If it
does, this probably means that the version number has not been updated. Ensure
that the new version is logically sequential to the previous release version.

### Review PR titles since the last release

The release notes are generated from PRs and their titles should be normalized.
Review the PRs since the last release and provide a list of recommendations to
the user. If necessary, the user will manually update PR titles prior to
starting the release action. Titles must be written in the imperative mood.
Titles must not have component prefixes like the "conventional commit" style.
Titles should use sentence case, not title case. Titles must be fewer than 68
characters long. Titles should not be too vague. Words that are clearly code
(functions, classes, etc) must be wrapped in backticks. There must be no
terminal punctuation and ideally no punctuation at all. Titles must not contain
double spaces, leading whitespace, or trailing whitespace. Ignore PRs with the
dependencies label.
