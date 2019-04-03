# ETH 2.0 PySpec

The Python executable spec is built from the ETH 2.0 specification, 
 complemented with the necessary helper functions for hashing, BLS, and more.

With this executable spec,
 test-generators can easily create test-vectors for client implementations,
 and the spec itself can be verified to be consistent and coherent, through sanity tests implemented with pytest.

## Building

All the dynamic parts of the spec can be build at once with `make pyspec`.

Alternatively, you can build a sub-set of the pyspec: `make phase0`.

Or, to build a single file, specify the path, e.g. `make test_libs/pyspec/eth2spec/phase0/spec.py`

## Contributing

Contributions are welcome, but consider implementing your idea as part of the spec itself first.
The pyspec is not a replacement.
If you see opportunity to include any of the `pyspec/eth2spec/utils/` code in the spec,
 please submit an issue or PR.

## License

Same as the spec itself, see LICENSE file in spec repository root.
