"""The one-slot target distinguishes each ``process_slot`` input branch."""

from itertools import product
from types import SimpleNamespace

import pytest

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    GRANULARITIES,
    NA,
    score,
)

from .target import TARGET


def context(position, *, header_empty, state_populated, block_populated, available, slots=1):
    period = 8
    spec = SimpleNamespace(SLOTS_PER_HISTORICAL_ROOT=period, Bytes32=lambda: bytes(32))
    state_roots = [bytes(32) for _ in range(period)]
    block_roots = [bytes(32) for _ in range(period)]
    state_roots[position] = bytes([1 if state_populated else 0]) * 32
    block_roots[position] = bytes([1 if block_populated else 0]) * 32
    availability = [False] * period
    availability[(position + 1) % period] = available
    state = SimpleNamespace(
        slot=position,
        latest_block_header=SimpleNamespace(state_root=bytes([0 if header_empty else 1]) * 32),
        state_roots=state_roots,
        block_roots=block_roots,
        execution_payload_availability=availability,
    )
    return Context(spec, state, slots, None, {})


@pytest.mark.parametrize("granularity", GRANULARITIES)
def test_observation_and_profiles_cover_the_input_product(granularity):
    records = []
    for position, header_empty, state_populated, block_populated, available in product(
        (0, 3, 7), (False, True), (False, True), (False, True), (False, True)
    ):
        ctx = context(
            position,
            header_empty=header_empty,
            state_populated=state_populated,
            block_populated=block_populated,
            available=available,
        )
        observation = TARGET.observation(ctx)
        record = TARGET.record(observation, granularity)
        assert record == {
            "ring_position": {0: "FIRST", 3: "MIDDLE", 7: "LAST"}[position],
            "header_state_root_empty": header_empty,
            "state_root_destination_populated": state_populated,
            "block_root_destination_populated": block_populated,
            "next_payload_available_before_clear": available,
        }
        records.append(record)

    target = TARGET.for_spec(
        context(
            0,
            header_empty=True,
            state_populated=False,
            block_populated=False,
            available=False,
        ).spec
    )
    for formula in target.profiles.values():
        report = score(target, records, formula, granularity)
        assert report.covered == report.total
        assert report.uncovered == report.unexpected == []
    assert len(target.profiles["standard"].run(granularity)) == 48


def test_multi_slot_vectors_are_outside_this_target():
    observation = TARGET.observation(
        context(
            7,
            header_empty=True,
            state_populated=True,
            block_populated=True,
            available=True,
            slots=2,
        )
    )
    assert all(value is NA for value in TARGET.record(observation, "predicate").values())


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_historical_root_period_is_bound_from_preset(preset):
    spec = spec_targets[preset]["gloas"]
    target = TARGET.for_spec(spec)
    assert target.bound_constants["slots_per_historical_root"] == int(
        spec.SLOTS_PER_HISTORICAL_ROOT
    )
    assert target.profiles["standard"].run("predicate")
