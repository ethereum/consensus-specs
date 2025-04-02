# Release Procedure

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Open a Release Pull Request](#open-a-release-pull-request)
- [Bump the Version](#bump-the-version)
- [Pick a Release Name](#pick-a-release-name)
- [Generate Reference Tests](#generate-reference-tests)
  - [Install Git Large File Storage](#install-git-large-file-storage)
  - [Prepare Tests Repository](#prepare-tests-repository)
  - [Commit Reference Tests](#commit-reference-tests)
  - [Bundle Reference Tests](#bundle-reference-tests)
- [Merge the Release Pull Request](#merge-the-release-pull-request)
- [Create Tests Release](#create-tests-release)
- [Create Specs Release](#create-specs-release)
- [Click the Release Buttons](#click-the-release-buttons)
- [Make an Announcement](#make-an-announcement)

<!-- mdformat-toc end -->

## Introduction

This document describes the necessary steps to produce a consensus-specs release.

## Open a Release Pull Request

> [!NOTE]
> Try to do this at least a few days prior to the release.

First, create a PR which merges `dev` into `master`.

> [!TIP]
> Click on the following link to draft a PR:
> * https://github.com/ethereum/consensus-specs/compare/dev...master?expand=1

Title this PR "Release &lt;version&gt;" (_e.g._, "Release v1.5.0-alpha.10").

In the PR's description, provide a list of items that must be done. At the bottom, list unmerged PRs
which are to be included in the release; this signals to other maintainers and developers that they
should review these PRs soon.

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
> * https://github.com/ethereum/consensus-specs/edit/dev/tests/core/pyspec/eth2spec/VERSION.txt

Next, change the version to the appropriate value and click the "Commit changes..." button.

For the commit message, put "Bump version to &lt;version&gt;" (_e.g._, "Bump version to 1.5.0-alpha.10").

Next, click the "Propose changes" button and proceed to make the PR.

## Pick a Release Name

Generally, names are based on some theme. For example, for Electra, releases are named after
Electric-type Pokemon.

> [!NOTE]
> Please ensure that the name you choose does not have an unwanted meaning in other languages;
use [WordSafety.com](http://wordsafety.com) to check this.

## Generate Reference Tests

### Install Git Large File Storage

The consensus-spec-tests repository uses [Git LFS](https://git-lfs.com) because it contains many
large files. Attempt to install LFS support with the following command. If it does not work, please
refer to the installation directions on their website.

```bash
git lfs install
```

### Prepare Tests Repository

Next, clone the consensus-spec-tests repository.

> [!NOTE]
> Only the single latest commit is needed to make the release. Use `--depth=1` to do this. Please
> note that even this may take some time to checkout, as the combined size of the test vectors is
> multiple gigabytes.

```bash
git clone https://github.com/ethereum/consensus-spec-tests.git --depth=1
cd consensus-spec-tests
```

Next, remove directories which will be overwritten.

```bash
rm -rf configs presets tests
```

### Commit Reference Tests

Next, change directory to outside of the tests repository.

```bash
cd ..
```

Next, clone the consensus-specs repository.

```bash
git clone https://github.com/ethereum/consensus-specs.git
cd consensus-specs
```

Next, copy the presets and configuration files to the tests repository.

```bash
cp -r presets ../consensus-spec-tests
cp -r configs ../consensus-spec-tests
```

Next, use `make gen_all` to generate all the reference tests. The following command will run all
generators in parallel for maximum speed. The console output is saved to a file so we can check for
errors afterwards.

> [!TIP]
> Instead of this, another option is to use the test vectors that are automatically generated each
> night. To download these files, click the following link, then click the latest action run, and
> then download all of the artifacts. Please note, if there has been a change to the dev branch
> after the test vectors were generated, you can manually trigger the action with the "Run workflow"
> button.
>
> * https://github.com/ethereum/consensus-specs/actions/workflows/generate_vectors.yml
>
> After downloading these artifacts, move them to the `consensus-spec-tests` directory. Then unzip
> each, then untar each of the `*.tar.gz` files. Use `unzip <file>.zip` and `tar -xvf <file>.tar.gz`
> to do this. Note that the "Bundle Reference Tests" section can be skipped if this route is taken.

```bash
make --jobs gen_all 2>&1 | tee ../consensustestgen.log
```

Next, check for errors by searching for "ERROR" in test logfile.

```bash
grep "ERROR" ../consensustestgen.log
```

> [!WARNING]
> If there is an error: (1) determine what the issue is, (2) create/merge a PR to fix the issue, and
> (3) restart the release process.

Next, change directory to the consensus-spec-tests repository:

```bash
cd ../consensus-spec-tests
```

Next, check that the differences look sane; that there are no unexpected changes. Sometimes there
are several hundred (if not more) changes per release so use your best judgement when reviewing. One
might ensure that there are no changes to old forks and double check a few reference tests to ensure
they were indeed modified in this release.

```bash
git lfs status
```

Next, after reviewing the changes and are reasonably confident that they are okay, stage the
changes.

```bash
git add .
```

Next, commit the changes.

> [!IMPORTANT]
> Commits to consensus-spec-tests must be signed. Please refer to [Signing
> Commits](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits)
> for instructions on setting this up.

```bash
git commit --gpg-sign --message "release <version> tests"
```

Finally, push the changes.

```bash
git push origin master
```

### Bundle Reference Tests

Next, delete all empty directories.

```bash
find . -type d -empty -delete
```

Finally, tar each group of tests into separate tarballs.

```bash
tar -czvf general.tar.gz tests/general
tar -czvf minimal.tar.gz tests/minimal
tar -czvf mainnet.tar.gz tests/mainnet
```

## Merge the Release Pull Request

After successfully generating the test vectors, we have confidence that the release is fine. We can
now merge the release pull request which brings changes from the development branch into the master
branch. Releases are made from the master branch.

## Create Tests Release

First, begin to draft a new consensus-spec-tests release.

> [!TIP]
> Click on the following link to draft a new release:
> * https://github.com/ethereum/consensus-spec-tests/releases/new

Next, click the "Choose a tag" button to create a new tag. Type in the release version (_e.g._,
"v1.5.0-alpha.10") and click the "Create new tag: &lt;version&gt; on publish" button.

Next, provide a title "Spec tests for &lt;version&gt;" (_e.g._, "Spec tests for v1.5.0-alpha.10").

Next, provide a description. Use the following template:

```markdown
Spec tests for <version>.

Detailed changelog can be found in [<version> specs release](https://github.com/ethereum/consensus-specs/releases/tag/<version>).
```

Next, upload the tarballs from the [Bundle Reference Tests]() section to the release.

> [!NOTE]
> This is expected to take a while if your upload speed is below average. The tarballs are at
> least 1 gigabyte in total. There is a progress bar shown for each artifact.

Next, if this is an alpha/beta release, please select the "Set as a pre-release" checkbox, otherwise
select the "Set as the latest release" checkbox.

> [!IMPORTANT]
> Do no click the release button just yet.

## Create Specs Release

First, begin to draft a new consensus-specs release.

> [!TIP]
> Click on the following link to draft a new release:
> * https://github.com/ethereum/consensus-specs/releases/new

Next, click the "Choose a tag" button to create a new tag. Type in the release version (_e.g._,
"v1.5.0-alpha.10") and click the "Create new tag: &lt;version&gt; on publish" button.

Next, change the target from `dev` to `master`.

> [!IMPORTANT]
> Do not forget this to change the target branch.

Next, provide a title "&lt;release-name&gt;" (_e.g._, "Bellibolt").

Next, provide a description. Use the following template:

```markdown
<version> -- <release-name> -- <short-release-description>

_PR showing full diff can be found here: <this-PR-number>_

## <component-a>

* Add new feature #1234
* Fix problem in old feature #2345

## <component-b>

* Fix bug related to feature #3456

## Testing, repo, etc

* Add new test for feature #4567
* Improve documentation #5678
```

If this is an alpha/beta release, please select the "Set as a pre-release" checkbox, otherwise
select the "Set as the latest release" checkbox.

> [!IMPORTANT]
> Do no click the release button just yet.

## Click the Release Buttons

1. First, click the release button for consensus-specs.

2. Then, click the release button for consensus-spec-tests.

> [!NOTE]
> It should be done in this order because the tests release references the specs release. Also,
> we wait to push these buttons at the same time so their time/date will be approximately the same.

## Make an Announcement

> [!IMPORTANT]
> In order to do this, you must be granted the appropriate access.

Finally, make an announcement to the Eth R&D server on Discord. This should be posted in the
`#announcements` channel. This will notify client developers of the new release and they will begin
to incorporate the new reference tests into their client.

Use the following template for your announcement:

```markdown
Consensus layer specs <version> -- <release-name> -- released!

https://github.com/ethereum/consensus-specs/releases/tag/<version>

Test vectors: https://github.com/ethereum/consensus-spec-tests/releases/tag/<version>
```