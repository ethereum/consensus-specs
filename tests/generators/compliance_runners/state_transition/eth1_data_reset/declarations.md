# ETH1 data reset: declaration sketch

Proposed Python syntax only. These constructors are not implemented, and the
working target remains in `target.py`.

The specification declares the attributes it needs, defines factors over them,
and selects their interactions. Attribute expressions build a declarative model;
they do not read a state or execute the handler.

```python
next_epoch = attribute("next_epoch", Integer(min=1))
epochs_per_eth1_voting_period = constant("epochs_per_eth1_voting_period", Integer(min=1))
vote_count = attribute("vote_count", Integer(min=0))

reset = aspect(
    "reset",
    factor(
        "at_reset_boundary",
        next_epoch % epochs_per_eth1_voting_period == 0,
        description="The handler reaches the end of the ETH1 voting period.",
    ),
    factor(
        "votes_nonempty",
        vote_count > 0,
        description="Resetting a populated list has an observable effect.",
    ),
)

coverage = coverage_spec(
    "eth1_data_reset",
    focus="process_eth1_data_reset: reset guard and vote-list occupancy",
    record="one vector",
    constants=(epochs_per_eth1_voting_period,),
    attributes=(next_epoch, vote_count),
    aspects=(reset,),
    profiles={
        "smoke": reset.nwise(1),
        "normal": reset.exhaustive(),
        "standard": reset.exhaustive(),
    },
)
```

Both factors are boolean. Their expressions deliberately do not request
three-way or five-way comparison abstraction. Both are unconditional:
`votes_nonempty` matters on either side of the reset guard, so it has no `when=`
clause.

The exhaustive profiles require these four combinations:

| at_reset_boundary | votes_nonempty |
| ----------------- | -------------- |
| false             | false          |
| false             | true           |
| true              | false          |
| true              | true           |

The adapter in `observation.py` returns only `next_epoch` and `vote_count`. A
separate binding supplies the constant from a fixed spec:

```python
TARGET = bind(
    coverage,
    constants={
        epochs_per_eth1_voting_period: int(spec.EPOCHS_PER_ETH1_VOTING_PERIOD),
    },
    observe_attributes=observe_attributes,
)
```

The period is supplied by the selected spec/preset, not chosen freely by a
materializer. Its positive integer domain describes valid observations;
generation must bind its concrete configured value. Likewise, `next_epoch` is
the current epoch plus one. That extraction relationship stays in the adapter,
while the coverage choices stay visible here.

The working capture DSL expresses this distinction with `CConstant[int]` and
`Target.constants`, whose binding functions receive only the spec. Bindings are
resolved for each observation's spec so a target can be reused across presets
without retaining stale values. Constants are kept separately from observed
attributes and cannot be passed or overridden by a capture call. The explicit
declaration constructors above, including domain validation, remain a sketch.
