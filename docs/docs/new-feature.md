# How to add a new feature proposal in consensus-specs

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [A. Make it executable for linter checks](#a-make-it-executable-for-linter-checks)
  - [1. Create a folder under `./specs/_features`](#1-create-a-folder-under-specs_features)
  - [2. Choose the "previous fork" to extend: usually, use the scheduled or the latest mainnet fork version.](#2-choose-the-previous-fork-to-extend-usually-use-the-scheduled-or-the-latest-mainnet-fork-version)
  - [3. Write down your proposed `beacon-chain.md` change](#3-write-down-your-proposed-beacon-chainmd-change)
  - [4. Add `fork.md`](#4-add-forkmd)
  - [5. Make it executable](#5-make-it-executable)
- [B: Make it executable for pytest and test generator](#b-make-it-executable-for-pytest-and-test-generator)
  - [1. [Optional] Add `light-client/*` docs if you updated the content of `BeaconBlock`](#1-optional-add-light-client-docs-if-you-updated-the-content-of-beaconblock)
  - [2. Add the mainnet and minimal presets and update the configs](#2-add-the-mainnet-and-minimal-presets-and-update-the-configs)
  - [3. Update `context.py`](#3-update-contextpy)
  - [4. Update `constants.py`](#4-update-constantspy)
  - [5. Update `genesis.py`:](#5-update-genesispy)
  - [6. Update CI configurations](#6-update-ci-configurations)
- [Others](#others)
  - [Bonus](#bonus)
  - [Need help?](#need-help)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## A. Make it executable for linter checks

### 1. Create a folder under `./specs/_features`

For example, if it's an `EIP-9999` CL spec, you can create a `./specs/_features/eip9999` folder.

### 2. Choose the "previous fork" to extend: usually, use the scheduled or the latest mainnet fork version.

For example, if the latest fork is Capella, use `./specs/capella` content as your "previous fork".

### 3. Write down your proposed `beacon-chain.md` change

- You can either use [Beacon Chain Spec Template](./templates/beacon-chain-template.md), or make a copy of the latest fork content and then edit it.
- Tips:
    - We use [`doctoc`](https://www.npmjs.com/package/doctoc) tool to generate the table of content.
        ```
        cd consensus-specs
        doctoc specs
        ```
    - The differences between "Constants", "Configurations", and "Presets":
        - Constants: The constant that should never be changed.
        - Configurations: The settings that we may change for different networks.
        - Presets: The settings that we may change for testing.
    - Readability and simplicity are more important than efficiency and optimization.
        - Use simple Python rather than the fancy Python dark magic.

### 4. Add `fork.md`

You can refer to the previous fork's `fork.md` file.

### 5. Make it executable

- Update Pyspec [`constants.py`](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/helpers/constants.py) with the new feature name.
- Update helpers for [`setup.py`](https://github.com/ethereum/consensus-specs/blob/dev/setup.py) for building the spec:
    - Update [`pysetup/constants.py`](https://github.com/ethereum/consensus-specs/blob/dev/pysetup/constants.py) with the new feature name as Pyspec `constants.py` defined.
    - Update [`pysetup/spec_builders/__init__.py`](https://github.com/ethereum/consensus-specs/blob/dev/pysetup/spec_builders/__init__.py). Implement a new `<FEATURE_NAME>SpecBuilder` in `pysetup/spec_builders/<FEATURE_NAME>.py` with the new feature name. e.g., `EIP9999SpecBuilder`. Append it to the `spec_builders` list.
    - Update [`pysetup/md_doc_paths.py`](https://github.com/ethereum/consensus-specs/blob/dev/pysetup/md_doc_paths.py): add the path of the new markdown files in `get_md_doc_paths` function if needed.
- Update `PREVIOUS_FORK_OF` setting in both [`test/helpers/constants.py`](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/helpers/constants.py) and [`pysetup/md_doc_paths.py`](https://github.com/ethereum/consensus-specs/blob/dev/pysetup/md_doc_paths.py).
    - NOTE: since these two modules (the pyspec itself and the spec builder tool) must be separate, the fork sequence setting has to be defined again.

## B: Make it executable for pytest and test generator

### 1. [Optional] Add `light-client/*` docs if you updated the content of `BeaconBlock`

- You can refer to the previous fork's `light-client/*` file.
- Add the path of the new markdown files in [`pysetup/md_doc_paths.py`](https://github.com/ethereum/consensus-specs/blob/dev/pysetup/md_doc_paths.py)'s `get_md_doc_paths` function.

### 2. Add the mainnet and minimal presets and update the configs

- Add presets: `presets/mainnet/<new-feature-name>.yaml` and `presets/minimal/<new-feature-name>.yaml`
- Update configs: `configs/mainnet.yaml` and `configs/minimal.yaml`

### 3. Update [`context.py`](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/context.py)

- [Optional] Add `with_<new-feature-name>_and_later` decorator for writing pytest cases. e.g., `with_capella_and_later`.

### 4. Update [`constants.py`](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/helpers/constants.py)

- Add `<NEW_FEATURE>` to `ALL_PHASES` and `TESTGEN_FORKS`

### 5. Update [`genesis.py`](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/helpers/genesis.py):

We use `create_genesis_state` to create the default `state` in tests.

- If the given feature changes `BeaconState` fields, you have to set the initial values by adding:

```python
def create_genesis_state(spec, validator_balances, activation_threshold):
    ...
    if is_post_eip9999(spec):
        state.<NEW_FIELD> = <value>

    return state
```

- If the given feature changes `ExecutionPayload` fields, you have to set the initial values by updating `get_sample_genesis_execution_payload_header` helper.

### 6. Update CI configurations

- Update [GitHub Actions config](https://github.com/ethereum/consensus-specs/blob/dev/.github/workflows/run-tests.yml)
    - Update `pyspec-tests.strategy.matrix.version` list by adding new feature to it

## Others

### Bonus

- Add `validator.md` if honest validator behavior changes with the new feature.

### Need help?

You can tag spec elves for cleaning up your PR. 🧚
