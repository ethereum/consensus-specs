# How to add a new feature proposal in consensus-specs

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
## Table of Contents

- [A. Make it executable for linter checks](#a-make-it-executable-for-linter-checks)
  - [1. Create a folder under `./specs/_features`](#1-create-a-folder-under-specs_features)
  - [2. Choose the "previous fork" to extend: usually, use the scheduled or the latest mainnet fork version.](#2-choose-the-previous-fork-to-extend-usually-use-the-scheduled-or-the-latest-mainnet-fork-version)
  - [3. Write down your proposed `beacon-chain.md` change](#3-write-down-your-proposed-beacon-chainmd-change)
  - [4. Add `fork.md`](#4-add-forkmd)
  - [5. Make it executable](#5-make-it-executable)
- [B: Make it executable for pytest and test generator](#b-make-it-executable-for-pytest-and-test-generator)
  - [1. Add `light-client/*` docs if you updated the content of `BeaconBlock`](#1-add-light-client-docs-if-you-updated-the-content-of-beaconblock)
  - [2. Add the mainnet and minimal presets and update the configs](#2-add-the-mainnet-and-minimal-presets-and-update-the-configs)
  - [3. Update `context.py`](#3-update-contextpy)
  - [4. Update `constants.py`](#4-update-constantspy)
  - [5. Update `genesis.py`:](#5-update-genesispy)
  - [6. To add fork transition tests, update fork_transition.py](#6-to-add-fork-transition-tests-update-fork_transitionpy)
  - [7. Update CI configurations](#7-update-ci-configurations)
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
    - Update [`pysetup/constants.py`](https://github.com/ethereum/consensus-specs/blob/dev/constants.py) with the new feature name as Pyspec `constants.py` defined.
    - Update [`pysetup/spec_builders/__init__.py`](https://github.com/ethereum/consensus-specs/blob/dev/pysetup/spec_builders/__init__.py). Implement a new `<FEATURE_NAME>SpecBuilder` in `pysetup/spec_builders/<FEATURE_NAME>.py` with the new feature name. e.g., `EIP9999SpecBuilder`. Append it to the `spec_builders` list.
    - Update [`pysetup/md_doc_paths.py`](https://github.com/ethereum/consensus-specs/blob/dev/pysetup/md_doc_paths.py): add the path of the new markdown files in `get_md_doc_paths` function if needed.

## B: Make it executable for pytest and test generator

### 1. [Optional] Add `light-client/*` docs if you updated the content of `BeaconBlock`
- You can refer to the previous fork's `light-client/*` file.
- Add the path of the new markdown files in [`pysetup/md_doc_paths.py`](https://github.com/ethereum/consensus-specs/blob/dev/pysetup/md_doc_paths.py)'s `get_md_doc_paths` function.

### 2. Add the mainnet and minimal presets and update the configs
- Add presets: `presets/mainnet/<new-feature-name>.yaml` and `presets/minimal/<new-feature-name>.yaml`
- Update configs: `configs/mainnet.yaml` and `configs/minimal.yaml`

### 3. Update [`context.py`](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/context.py)
- Update `spec_targets` by adding `<NEW_FEATURE>`

```python
from eth2spec.eip9999 import mainnet as spec_eip9999_mainnet, minimal as spec_eip9999_minimal

...

spec_targets: Dict[PresetBaseName, Dict[SpecForkName, Spec]] = {
    MINIMAL: {
        ...
        EIP9999: spec_eip9999_minimal,
    },
    MAINNET: {
        ...
        EIP9999: spec_eip9999_mainnet
    },
}
```

### 4. Update [`constants.py`](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/helpers/constants.py)
- Add `<NEW_FEATURE>` to `ALL_PHASES` and `TESTGEN_FORKS`

### 5. Update [`genesis.py`](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/helpers/genesis.py):

We use `create_genesis_state` to create the default `state` in tests.

- Update `create_genesis_state` by adding `fork_version` setting:

```python
def create_genesis_state(spec, validator_balances, activation_threshold):
    ...
    if spec.fork == ALTAIR:
        current_version = spec.config.ALTAIR_FORK_VERSION
    ...
    elif spec.fork == EIP9999:
        # Add the previous fork version of given fork
        previous_version = spec.config.<PREVIOUS_FORK_VERSION>
        current_version = spec.config.EIP9999_FORK_VERSION
```

- If the given feature changes `BeaconState` fields, you have to set the initial values by adding:

```python
def create_genesis_state(spec, validator_balances, activation_threshold):
    ...
    if is_post_eip9999(spec):
        state.<NEW_FIELD> = <value>

    return state
```

- If the given feature changes `ExecutionPayload` fields, you have to set the initial values by updating `get_sample_genesis_execution_payload_header` helper.

### 6. To add fork transition tests, update [fork_transition.py](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/helpers/fork_transition.py)

```python
def do_fork(state, spec, post_spec, fork_epoch, with_block=True, sync_aggregate=None, operation_dict=None):
    ...

    if post_spec.fork == ALTAIR:
        state = post_spec.upgrade_to_altair(state)
    ...
    elif post_spec.fork == EIP9999:
        state = post_spec.upgrade_to_eip9999(state)

    ...

    if post_spec.fork == ALTAIR:
        assert state.fork.previous_version == post_spec.config.GENESIS_FORK_VERSION
        assert state.fork.current_version == post_spec.config.ALTAIR_FORK_VERSION
    ...
    elif post_spec.fork == EIP9999:
        assert state.fork.previous_version == post_spec.config.<PREVIOUS_FORK_VERSION>
        assert state.fork.current_version == post_spec.config.EIP9999_FORK_VERSION

    ...
```

### 7. Update CI configurations
- Update [GitHub Actions config](https://github.com/ethereum/consensus-specs/blob/dev/.github/workflows/run-tests.yml)
    - Update `pyspec-tests.strategy.matrix.version` list by adding new feature to it
- Update [CircleCI config](https://github.com/ethereum/consensus-specs/blob/dev/.circleci/config.yml)
    - Add new job to the `workflows.test_spec.jobs`

## Others

### Bonus
- Add `validator.md` if honest validator behavior changes with the new feature.

### Need help?
You can tag spec elves for cleaning up your PR. 🧚
