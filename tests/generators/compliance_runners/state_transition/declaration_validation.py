"""Shared dimension and assertion validation for declaration targets."""

from ruamel.yaml import YAML

from .evaluation.coverage_dsl import Context, NA
from .provider import Check, check_dimensions, decode


def recover_record(target, ctx):
    """Recover metadata independently of claims and solver feasibility."""
    bound = target.for_spec(ctx.spec)
    observed = bound.observation(ctx)
    record = bound.record(observed)
    return bound, record, {n: "NA" if v is NA else v for n, v in record.items()}


def validate_record(target, ctx, claimed):
    bound, record, actual = recover_record(target, ctx)
    summary = bound.assertion_result(record)
    if summary is not None:
        actual["fault_count"] = summary.fault_count
    checks = check_dimensions(claimed, actual)
    assertions = bound.definition.assertions
    if assertions is not None and assertions.observed is not None:
        expected = summary.expected_accepted
        observed = record[assertions.observed.name]
        if expected is not None and (assertions.complete or expected is False):
            checks.append(
                Check(
                    "assertion_outcome",
                    expected,
                    "NA" if observed is NA else observed,
                    "ok" if observed is not NA and expected == observed else "mismatch",
                )
            )
    return checks


def target_validator(target, *, operation_name=None, operation_type=None, spec, require_post=False):
    """Build recovery and on-disk validation using a provider's spec getter.

    Typed operations are decoded from ``<operation_name>.ssz_snappy``. When a
    name is supplied without a type, the operation is read from YAML instead.
    """

    if operation_type is not None and operation_name is None:
        raise ValueError("operation_type requires operation_name")

    def recover(pre, operation, post=None):
        return recover_record(target, Context(spec(), pre, operation, post, {}))[2]

    def validate_file(case_spec, case_dir):
        pre = decode(case_dir / "pre.ssz_snappy", case_spec.BeaconState)
        if operation_name is None:
            operation = None
        elif operation_type is None:
            operation = YAML(typ="safe").load((case_dir / f"{operation_name}.yaml").read_text())
        else:
            operation = decode(
                case_dir / f"{operation_name}.ssz_snappy", getattr(case_spec, operation_type)
            )
        post_path = case_dir / "post.ssz_snappy"
        post_exists = post_path.exists()
        post = decode(post_path, case_spec.BeaconState) if post_exists else None
        metadata = YAML(typ="safe").load((case_dir / "dimensions.yaml").read_text())
        ctx = Context(case_spec, pre, operation, post, metadata)
        checks = validate_record(target, ctx, metadata["claimed"])
        if require_post and not post_exists:
            checks.append(
                Check(
                    "post_state_present",
                    claimed=True,
                    actual=False,
                    status="mismatch",
                )
            )
        return checks

    def validate_case(case_dir):
        return validate_file(spec(), case_dir)

    validate_case.for_spec = validate_file
    return recover, validate_case
