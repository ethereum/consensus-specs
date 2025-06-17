# Fork choice compliance test generator

Fork Choice test generator intended to produce tests to validate conformance to the specs of various Fork Choice implementations.

Implementation of the approach described in the [Fork Choice compliance testing framework](https://hackmd.io/@ericsson49/fork-choice-implementation-vs-spec-testing).

Preliminary research has been also performed in this [repo](https://github.com/txrx-research/fork_choice_test_generation/tree/main).

To simplify adoption of the tests, we follow the test format described in the [fork choice test formats documentation](../../../formats/fork_choice/README.md), with a minor exception (new check added).

This work was supported by a grant from the Ethereum Foundation.

# Pre-requisites

Install pyspec using the top-level Makefile, this will install necessary pre-requiesites.

```
> make pyspec
```

# Generating tests

From the root directory:

```
> python -m tests.generators.compliance_runners.fork_choice.test_gen -o ${test_dir} --fc-gen-config ${config}
```
where `config` can be either: `tiny`, `small` or `standard.

Or specify path to the configuration file directrly:

```
> python -m tests.generators.compliance_runners.fork_choice.test_gen -o ${test_dir} --fc-gen-config-path ${config_path}
```

There are three configurations in the repo: [tiny](tiny/), [small](small/) and [standard](standard/).

# Running tests

From the root directory:

```
> python -m tests.generators.compliance_runners.fork_choice.test_run -i ${test_dir}
```

# Generating configurations

Files in [tiny](tiny/), [small](small/) and [standard](standard/) are generated with [generate_test_instances.py](generate_test_instances.py), e.g.
```
> python -m tests.generators.compliance_runners.fork_choice.generate_test_instances
```

But one normally doesn't need to generate them.
