# How to add a new feature proposal in consensus-specs

1. Create a folder under `./specs/features`.
2. Choose the "previous fork" to extend: usually, use the scheduled or the lasted mainnet fork version.
3. Write down your proposed `beacon-chain.md` change:
    - [Beacon Chain Spec Template](./beacon-chain-template.md)
    - Reference to the previous fork content
4. Add `fork.md`: reference to the previous `fork.md` file.
5. Make it executable:
    - Update [`constants.py`](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/helpers/constants.py) with the new feature name.
    - Update [`setup.py`](https://github.com/ethereum/consensus-specs/blob/dev/setup.py):
        - Add a new `SpecBuilder` with the new feature name constant
        - Add the new `SpecBuilder` to `spec_builders`
        - Add the path of the new markdown files in `finalize_options`
6. Bonus:
    - Add `validator.md` if honest validator behavior changes with your change.
7. Need help? Tag spec elves to clean up your PR.
