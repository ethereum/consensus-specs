# Randomized tests

Randomized tests in the format of `sanity` blocks tests, with randomized operations.

Information on the format of the tests can be found in the [sanity test formats documentation](../../formats/sanity/README.md).

# To generate test sources

```bash
$ make
```

The necessary commands are in the `Makefile`, as the only target.

The generated files are committed to the repo so you should not need to do this.

# To run tests

Use the usual `pytest` mechanics used elsewhere in this repo.

# To generate spec tests (from the generated files)

Run the test generator in the usual way.

E.g. from the root of this repo, you can run:

```bash
$ make gen_random
```
