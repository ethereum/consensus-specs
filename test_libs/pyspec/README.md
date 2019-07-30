# Eth 2.0 Executable Python Spec (PySpec)

The executable Python spec is built from the Eth 2.0 specification, 
 complemented with the necessary helper functions for hashing, BLS, and more.

With this executable spec,
 test-generators can easily create test-vectors for client implementations,
 and the spec itself can be verified to be consistent and coherent through sanity tests implemented with pytest.


## Building

All the dynamic parts of the spec can be build at once with `make pyspec`.

Alternatively, you can build a sub-set of the pyspec: `make phase0`.

Or, to build a single file, specify the path, e.g. `make test_libs/pyspec/eth2spec/phase0/spec.py`.


## Py-tests

After building, you can install the dependencies for running the `pyspec` tests with `make install_test`.

These tests are not intended for client-consumption.
These tests are sanity tests, to verify if the spec itself is consistent.

### How to run tests

#### Automated

Run `make test` from the root of the specs repository (after running `make install_test` if have not before).

#### Manual

From within the `pyspec` folder:

Install dependencies:
```bash
python3 -m venv venv
. venv/bin/activate
pip3 install -r requirements-testing.txt
```
*Note*: Make sure to run `make -B pyspec` from the root of the specs repository,
 to build the parts of the pyspec module derived from the markdown specs.
The `-B` flag may be helpful to force-overwrite the `pyspec` output after you made a change to the markdown source files.

Run the tests:
```
pytest --config=minimal eth2spec
```
Note the package-name, this is to locate the tests.

### How to view code coverage report

Run `make open_cov` from the root of the specs repository after running `make test` to open the html code coverage report.


## Contributing

Contributions are welcome, but consider implementing your idea as part of the spec itself first.
The pyspec is not a replacement.


## License

Same as the spec itself; see [LICENSE](../../LICENSE) file in the specs repository root.
