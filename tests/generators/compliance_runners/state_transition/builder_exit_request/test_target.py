"""Builder-exit declaration profiles survive serialization under both presets."""

from types import SimpleNamespace

import pytest
from ruamel.yaml import YAML

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    recover_record,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    score,
)
from tests.generators.compliance_runners.state_transition.provider import (
    load_provider,
    materialize_handler,
)

from .materializer import MATERIALIZER
from .target import TARGET

build_profile = load_provider("builder_exit_request").build_profile
validate_case = load_provider("builder_exit_request").validate_case


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_max_vectors_preserve_all_signatures_and_profile_coverage(preset, tmp_path):
    spec = spec_targets[preset]["gloas"]
    target = TARGET.for_spec(spec)
    records = build_profile("max", spec=spec)
    assert len(records) == 19
    materializer = MATERIALIZER(spec, preset_name=preset, seed=124)
    materializer.test_provider = "builder_exit_request"
    observations = []
    for record in records:
        solution = SimpleNamespace(**record)
        materializer.rng = materializer._rng_for_solution(solution)
        meta, parts = materializer.materialize_solution(solution)
        encoded = {name: data for name, _, data in parts}
        context = Context(
            spec,
            spec.BeaconState.decode_bytes(encoded["pre"]),
            spec.BuilderExitRequest.decode_bytes(encoded["builder_exit_request"]),
            spec.BeaconState.decode_bytes(encoded["post"]),
            {},
        )
        _, observation, actual = recover_record(TARGET, context)
        assert actual == meta["claimed"] == record
        observations.append(observation)
    for name, profile in target.profiles.items():
        representatives = build_profile(name, spec=spec)
        selected = [{k: v for k, v in r.items() if v != "NA"} for r in representatives]
        for observed in (selected, observations):
            report = score(target, observed, profile)
            assert report.covered == report.total
            assert not report.unexpected
        if name == "normal":
            assert all(r["outcome"] == "EXIT_INITIATED" for r in representatives)
        if name == "exceptional":
            assert len(representatives) == 4
            for record in representatives:
                faults = (
                    1
                    if not record["builder_pubkey_found"]
                    else (
                        int(not record["builder_active"])
                        + int(not record["source_address_matches"])
                        + int(record["builder_has_pending_balance"])
                    )
                )
                assert faults == 1
    assert (
        materialize_handler("builder_exit_request", "smoke", tmp_path, preset_name=preset, seed=7)
        == 5
    )


def test_missing_post_and_corrupt_effect_are_rejected(tmp_path):
    spec = spec_targets["minimal"]["gloas"]
    materializer = MATERIALIZER(spec, seed=7)
    materializer.test_provider = "builder_exit_request"
    record = build_profile("normal", spec=spec)[0]
    materializer.materialize_reps(tmp_path, [SimpleNamespace(**record)])
    case = next(tmp_path.rglob("case_*"))
    assert all(check.status == "ok" for check in validate_case(case))
    post_path = case / "post.ssz_snappy"
    original_post = post_path.read_bytes()
    post_path.write_bytes((case / "pre.ssz_snappy").read_bytes())
    assert any(
        check.dimension == "exit_initiated" and check.status == "mismatch"
        for check in validate_case(case)
    )
    post_path.write_bytes(original_post)
    yaml = YAML()
    dimensions_path = case / "dimensions.yaml"
    metadata = yaml.load(dimensions_path.read_text())
    metadata["claimed"]["exit_initiated"] = False
    with dimensions_path.open("w") as stream:
        yaml.dump(metadata, stream)
    assert any(
        check.dimension == "exit_initiated" and check.status == "mismatch"
        for check in validate_case(case)
    )
    post_path.unlink()
    assert any(
        check.dimension == "post_state_present" and check.status == "mismatch"
        for check in validate_case(case)
    )
