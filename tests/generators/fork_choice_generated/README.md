# Fork choice compliance test generator

Fork Choice test generator intended to produce tests to validate conformance to the specs of various Fork Choice implementations.

Implementation of the approach described in the [Fork Choice compliance testing framework](https://hackmd.io/@ericsson49/fork-choice-implementation-vs-spec-testing).

Preliminary research has been also performed in this [repo](https://github.com/txrx-research/fork_choice_test_generation/tree/main).

To simplfy adoption of the tests, we follow the test format described in the [fork choice test formats documentation](../../formats/fork_choice/README.md), with a minor exception (new check added).

# Pre-requisites

Install requirements (preferrably, in a dedicated Python environment)

```
> pip install -r requirements.txt
```

In order to run tests, install `tqdm` additionally.
```
> pip install tqdm
```

# Generating tests

```
> python test_gen.py -o ${test_dir} --fc-gen-config ${config_dir}/test_gen.yaml
```

There are three configurations in the repo: [tiny](tiny/), [small](small/) and [standard](standard/).

# Running tests

Install `tqdm` library (to show progress)
```
> pip install tqdm
```

and then
```
> python test_run.py -i ${test_dir}
```

# Generating configurations

Files in [tiny](tiny/), [small](small/) and [standard](standard/) are generated with [generate_test_instances.py](generate_test_instances.py), e.g.
```
> python generate_test_instances.py
```

But one normally doesn't need to generate them.
