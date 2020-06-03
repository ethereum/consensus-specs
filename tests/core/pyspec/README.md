# Eth2 Executable Python Spec (PySpec)

The executable Python spec is built from the Eth2 specification, 
 complemented with the necessary helper functions for hashing, BLS, and more.

With this executable spec,
 test-generators can easily create test-vectors for client implementations,
 and the spec itself can be verified to be consistent and coherent through sanity tests implemented with pytest.

## Building

To build the pyspec: `python setup.py build`
 (or `pip install .`, but beware that ignored files will still be copied over to a temporary dir, due to pip issue 2195).
This outputs the build files to the `./build/lib/eth2spec/...` dir, and can't be used for local test running. Instead, use the dev-install as described below. 

## Dev Install

All the dynamic parts of the spec are automatically built with `python setup.py pyspecdev`.
Unlike the regular install, this outputs spec files to their original source location, instead of build output only.

Alternatively, you can build a sub-set of the pyspec with the distutil command: 
```bash
python setup.py pyspec --spec-fork=phase0 --md-doc-paths="specs/phase0/beacon-chain.md specs/phase0/fork-choice.md" --out-dir=my_spec_dir
```

## Py-tests

After installing, you can install the optional dependencies for testing and linting.
With makefile: `make install_test`.
Or manually: run `pip install .[testing]` and `pip install .[linting]`.

These tests are not intended for client-consumption.
These tests are testing the spec itself, to verify consistency and provide feedback on modifications of the spec.
However, most of the tests can be run in generator-mode, to output test vectors for client-consumption.

### How to run tests

#### Automated

Run `make test` from the root of the specs repository (after running `make install_test` if have not before).

#### Manual

From the repository root:

Install venv and install:
```bash
python3 -m venv venv
. venv/bin/activate
python setup.py pyspecdev
```

Run the test command from the `tests/core/pyspec` directory:
```
pytest --config=minimal eth2spec
```

Options:
- `--config`, to change the config. Defaults to `minimal`, can be set to `mainnet`, or other configs from the configs directory.
- `--disable-bls`, to disable BLS (only for tests that can run without)
- `--bls-type`, `milagro` or `py_ecc` (default)

### How to view code coverage report

Run `make open_cov` from the root of the specs repository after running `make test` to open the html code coverage report.


## Contributing

Contributions are welcome, but consider implementing your idea as part of the spec itself first.
The pyspec is not a replacement.


## License

Same as the spec itself; see [LICENSE](../../../LICENSE) file in the specs repository root.
