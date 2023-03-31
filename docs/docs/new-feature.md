# How to add a new feature proposal in consensus-specs

### 1. Create a folder under `./specs/_features`

For example, if it's an `EIP-9999` CL spec, you can create a `./specs/_features/eip9999` folder.

### 2. Choose the "previous fork" to extend: usually, use the scheduled or the latest mainnet fork version.

For example, if the latest fork is Capella, use `./specs/capella` content as your "previous fork".

### 3. Write down your proposed `beacon-chain.md` change
- You can either use [Beacon Chain Spec Template](./beacon-chain-template.md), or make a copy of the latest fork content and then edit it.
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
- Update [`constants.py`](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/helpers/constants.py) with the new feature name.
- Update [`setup.py`](https://github.com/ethereum/consensus-specs/blob/dev/setup.py):
    - Add a new `SpecBuilder` with the new feature name constant. e.g., `EIP9999SpecBuilder`
    - Add the new `SpecBuilder` to `spec_builders` list.
    - Add the path of the new markdown files in `finalize_options` function.

### Bonus
- Add `validator.md` if honest validator behavior changes with your change.

### Need help?
You can tag spec elves for cleaning up your PR. 🧚
