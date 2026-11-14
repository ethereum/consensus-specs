"""Dispatch scenarios are inferred from vectors, independently of solver claims."""

from shutil import copytree
from types import SimpleNamespace

import pytest
from ruamel.yaml import YAML

from eth_consensus_specs.test.context import get_copy_of_spec, spec_with_config_overrides
from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    validate_record,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    load_observations,
    score,
)
from tests.generators.compliance_runners.state_transition.provider import load_provider

from .materializer import MATERIALIZER
from .target import TARGET

build_profile = load_provider("operations_dispatch").build_profile
validate_case = load_provider("operations_dispatch").validate_case


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_profiles_and_case_validation_cover_all_scenarios(preset, tmp_path):
    spec, _ = spec_with_config_overrides(
        get_copy_of_spec(spec_targets[preset]["gloas"]), {"GLOAS_FORK_EPOCH": 0}
    )
    records = build_profile("max", spec=spec)
    assert len(records) == 5
    assert {r["scenario"] for r in records} == {
        "all_lists",
        "slash_before_exit",
        "invalid_payload_attestation",
        "parent_slot_matches",
        "parent_slot_mismatches",
    }
    materializer = MATERIALIZER(spec, preset_name=preset, seed=124)
    materializer.test_provider = "process_operations_dispatch"
    assert materializer.materialize_reps(tmp_path, [SimpleNamespace(**r) for r in records]) == 5
    for case in sorted(tmp_path.rglob("case_*")):
        assert all(check.status == "ok" for check in validate_case.for_spec(spec, case))
    target = TARGET.for_spec(spec_targets[preset]["gloas"])
    observations = load_observations([tmp_path], target, preset)
    observed = [target.record(o) for o in observations]
    assert {tuple(sorted(r.items())) for r in observed} == {
        tuple(sorted(r.items())) for r in records
    }
    for name, formula in target.profiles.items():
        representatives = build_profile(name, spec=target._bound_spec)
        for selected in (observed, representatives):
            report = score(target, selected, formula)
            assert report.covered == report.total
            assert not report.unexpected
    # The other blocks provider shares the same runner/handler directory.
    # Its vectors must not inflate this fixture-specific scenario audit.
    first_case = next(tmp_path.rglob("case_*"))
    unrelated_case = first_case.with_name("case_9999")
    copytree(first_case, unrelated_case)
    yaml = YAML()
    metadata_path = unrelated_case / "dimensions.yaml"
    metadata = yaml.load(metadata_path.read_text())
    metadata["test_provider"] = "process_operations"
    with metadata_path.open("w") as stream:
        yaml.dump(metadata, stream)
    assert len(load_observations([tmp_path], target, preset)) == 5


@pytest.mark.parametrize("corruption", ["counts", "shared_validator", "payload_root", "head_flag"])
def test_corrupt_scenario_does_not_validate(corruption):
    spec, _ = spec_with_config_overrides(
        get_copy_of_spec(spec_targets["minimal"]["gloas"]), {"GLOAS_FORK_EPOCH": 0}
    )
    scenario = {
        "counts": "all_lists",
        "shared_validator": "slash_before_exit",
        "payload_root": "invalid_payload_attestation",
        "head_flag": "parent_slot_matches",
    }[corruption]
    record = next(r for r in build_profile("max", spec=spec) if r["scenario"] == scenario)
    materializer = MATERIALIZER(spec, seed=7)
    materializer.test_provider = "process_operations_dispatch"
    solution = SimpleNamespace(**record)
    materializer.rng = materializer._rng_for_solution(solution)
    _, parts = materializer.materialize_solution(solution)
    encoded = {name: data for name, _, data in parts}
    pre = spec.BeaconState.decode_bytes(encoded["pre"])
    operation = spec.SignedBeaconBlock.decode_bytes(encoded["blocks_0"])
    post = spec.BeaconState.decode_bytes(encoded["post"]) if "post" in encoded else None
    ctx = Context(spec, pre, operation, post, {})
    assert all(check.status == "ok" for check in validate_record(TARGET, ctx, record))
    body = operation.message.body
    if corruption == "counts":
        body.proposer_slashings.pop()
    elif corruption == "shared_validator":
        body.voluntary_exits[0].message.validator_index = (
            int(body.voluntary_exits[0].message.validator_index) + 1
        ) % len(pre.validators)
    elif corruption == "payload_root":
        body.payload_attestations[0].data.beacon_block_root = operation.message.parent_root
    else:
        for index in spec.get_attesting_indices(post, body.attestations[0]):
            post.current_epoch_participation[index] = spec.ParticipationFlags(0)
    checks = validate_record(TARGET, ctx, record)
    assert any(check.dimension == "scenario" and check.status == "mismatch" for check in checks)
