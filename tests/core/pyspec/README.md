# Executable Python Spec (PySpec)

The executable Python spec is built from the consensus specifications,
 complemented with the necessary helper functions for hashing, BLS, and more.

With this executable spec,
 test-generators can easily create test-vectors for client implementations,
 and the spec itself can be verified to be consistent and coherent through sanity tests implemented with pytest.

## Dev Install

First, create a `venv` and install the developer dependencies (`test` and `lint` extras):

```shell
make install_test
```

All the dynamic parts of the spec are built with:

```shell
(venv) python setup.py pyspecdev
```

Unlike the regular install, this outputs spec files to their intended source location,
to enable debuggers to navigate between packages and generated code, without fragile directory linking.

By default, when installing the `eth2spec` as package in non-develop mode,
the distutils implementation of the `setup` runs `build`, which is extended to run the same `pyspec` work,
but outputs into the standard `./build/lib` output.
This enables the `consensus-specs` repository to be installed like any other python package.


## Py-tests

These tests are not intended for client-consumption.
These tests are testing the spec itself, to verify consistency and provide feedback on modifications of the spec.
However, most of the tests can be run in generator-mode, to output test vectors for client-consumption.

### How to run tests

#### Automated

Run `make test` from the root of the specs repository (after running `make install_test` if have not before).

Note that the `make` commands run through the build steps: it runs the `build` output, not the local package source files.

#### Manual

See `Dev install` for test pre-requisites.

Tests are built for `pytest`.

Caveats:
- Working directory must be `./tests/core/pyspec`. The work-directory is important to locate eth2 configuration files.
- Run `pytest` as module. It avoids environment differences, and the behavior is different too:
  `pytest` as module adds the current directory to the `sys.path`

Full test usage, with explicit configuration for illustration of options usage:
```shell
(venv) python -m pytest --preset=minimal eth2spec
```

Or, to run a specific test file, specify the full path:
```shell
(venv) python -m pytest --preset=minimal ./eth2spec/test/phase0/block_processing/test_process_attestation.py
```

Or, to run a specific test function (specify the `eth2spec` module, or the script path if the keyword is ambiguous):
```shell
(venv) python -m pytest --preset=minimal -k test_success_multi_proposer_index_iterations eth2spec
```

Options:
- `--preset`, to change the preset (compile-time configurables). Defaults to `minimal`, can be set to `mainnet`.
  Use `@spec_configured_state_test({config here...}` to override runtime configurables on a per-test basis.
- `--disable-bls`, to disable BLS (only for tests that can run without)
- `--bls-type`, `milagro` or `py_ecc` (default)

### How to view code coverage report

Run `make open_cov` from the root of the specs repository after running `make test` to open the html code coverage report.

### Advanced

Building spec files from any markdown sources, to a custom location:
```bash
(venv) python setup.py pyspec --spec-fork=phase0 --md-doc-paths="specs/phase0/beacon-chain.md specs/phase0/fork-choice.md" --out-dir=my_spec_dir
```

## Contributing

Contributions are welcome, but consider implementing your idea as part of the spec itself first.
The pyspec is not a replacement.


## License

Same as the spec itself; see [LICENSE](../../../LICENSE) file in the specs repository root.
