"""Registry and orchestration for state-transition test providers."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TYPE_CHECKING

import snappy
from ruamel.yaml import YAML

from .catalog import HANDLERS, Provider, PROVIDERS, RUNNERS
from .materializer import SUITE_NAME

if TYPE_CHECKING:
    from collections.abc import Callable


PROFILES = ("all", "smoke", "normal", "exceptional", "standard")
_YAML = YAML(typ="safe")


@dataclass
class Check:
    dimension: str
    claimed: Any
    actual: Any
    status: str


def check_dimensions(claimed: dict, actual: dict) -> list[Check]:
    return [
        Check(
            name,
            value,
            actual.get(name, "<none>"),
            "ok" if actual.get(name, "<none>") == value else "mismatch",
        )
        for name, value in claimed.items()
    ]


def decode(path: Path, sedes: Any) -> Any:
    return sedes.decode_bytes(snappy.decompress(path.read_bytes()))


RUNNER_BY_HANDLER = {
    handler: runner for runner, handlers in RUNNERS.items() for handler in handlers
}


def _spec_for_case(case_dir: Path) -> Any:
    """Load the preset encoded by a generated case's directory layout."""
    for parent in case_dir.parents:
        if parent.name in ("minimal", "mainnet"):
            return import_module(f"eth_consensus_specs.gloas.{parent.name}")
    raise ValueError(f"could not determine preset for case: {case_dir}")


def validate_cases(
    test_dir: Path,
    handler: str,
    validate_case: Callable[..., Any] | dict[str, Callable[..., Any]],
    selected_cases: set[str] | None = None,
) -> int:
    """Run a handler validator over its materialized reference-test cases."""
    phase = RUNNER_BY_HANDLER[handler]
    case_dirs = sorted(test_dir.glob(f"**/{phase}/{handler}/{SUITE_NAME}/case_*"))
    if selected_cases is not None:
        case_dirs = [case_dir for case_dir in case_dirs if case_dir.name in selected_cases]
    if not case_dirs:
        suffix = " matching the requested cases" if selected_cases is not None else ""
        print(f"No cases found under {test_dir}{suffix}")
        return 1

    total_mm = total_err = 0
    for case_dir in case_dirs:
        case_spec = _spec_for_case(case_dir)
        dimensions = _YAML.load((case_dir / "dimensions.yaml").read_text())
        test_provider = dimensions.get("test_provider")
        if isinstance(validate_case, dict):
            if test_provider not in validate_case:
                print(f"{case_dir.name}: FAIL  [unknown test provider {test_provider!r}]")
                total_err += 1
                continue
            case_validate = validate_case[test_provider]
        else:
            case_validate = validate_case
        # Validators historically imported the minimal spec at module scope.
        # Replace that binding so validation follows each case's preset.
        case_validate.__globals__["spec"] = case_spec
        result = case_validate(case_dir)
        if isinstance(result, tuple):
            checks, errors = result
        else:
            checks, errors = result, []
        mismatches = [check for check in checks if check.status == "mismatch"]
        total_mm += len(mismatches)
        total_err += len(errors)
        status = "OK" if not mismatches and not errors else "FAIL"
        outcome = next((check.claimed for check in checks if check.dimension == "outcome"), "?")
        print(f"{case_dir.name}: {status}  [{outcome}]")
        for check in mismatches:
            print(f"    dim {check.dimension}: claimed={check.claimed!r} actual={check.actual!r}")
        for error in errors:
            print(f"    oracle: {error}")

    print()
    if total_mm or total_err:
        print(f"FAILED: {total_mm} dimension mismatch(es), {total_err} oracle error(s)")
        return 1
    print(f"PASSED: {len(case_dirs)} cases, all dimensions consistent")
    return 0


def discover_handlers(test_dir: Path) -> list[str]:
    candidates = []
    for phase in ("operations", "epoch_processing"):
        for handler in HANDLERS:
            if list(test_dir.glob(f"**/{phase}/{handler}/**/case_*")):
                candidates.append((phase, handler))
    if not candidates:
        raise ValueError(f"could not discover a state-transition handler under {test_dir}")
    return [handler for _, handler in candidates]


def providers_for(handler: str) -> tuple[Provider, ...]:
    """Return all providers registered for ``handler``."""
    providers = tuple(provider for provider in PROVIDERS if provider.handler == handler)
    if not providers:
        raise ValueError(f"no providers registered for handler: {handler}")
    return providers


def _generated_count(generated: int | tuple[int, int]) -> int:
    """Normalize provider return values to the generated case count."""
    return generated[0] if isinstance(generated, tuple) else generated


def _materialize_provider(
    provider: Provider,
    profile: str,
    output_dir: Path,
    case_offset: int,
    clean: bool,
    spec: Any,
    preset_name: str,
) -> tuple[Any, int]:
    module = import_module(f".{provider.module}", __package__)
    _, chosen = module.build_profile(profile)
    reps = [SimpleNamespace(**record) for record in chosen]
    materializer = module.MATERIALIZER(spec, preset_name=preset_name)
    materializer.test_provider = provider.name
    if materializer.runner_name != provider.runner or materializer.handler_name != provider.handler:
        raise ValueError(f"provider metadata does not match materializer: {provider.name}")
    generated = materializer.materialize_reps(
        output_dir, reps, case_offset=case_offset, clean=clean
    )
    return module.validate_case, _generated_count(generated)


def materialize_handler(
    handler: str,
    profile: str,
    output_dir: Path,
    spec: Any | None = None,
    preset_name: str = "minimal",
) -> int:
    """Materialize and validate all providers registered for ``handler``."""
    if spec is None:
        spec = import_module(f"eth_consensus_specs.gloas.{preset_name}")
    providers = providers_for(handler)
    case_offset = 0
    for provider_index, provider in enumerate(providers):
        print(f"Materializing '{profile}' test vectors for '{handler}' from '{provider.name}'")
        validate_case, generated = _materialize_provider(
            provider,
            profile,
            output_dir,
            case_offset,
            clean=provider_index == 0,
            spec=spec,
            preset_name=preset_name,
        )
        selected_cases = {
            f"case_{index:04d}" for index in range(case_offset, case_offset + generated)
        }
        case_offset += generated
        print(f"Validating cases from '{provider.name}'")
        if validate_cases(output_dir, handler, validate_case, selected_cases=selected_cases):
            raise RuntimeError(f"validation failed for provider: {provider.name}")
    return case_offset


def validate_handler(
    test_dir: Path,
    handler: str,
    selected_cases: set[str] | None = None,
) -> int:
    """Validate all providers registered for ``handler``."""
    validators = {}
    for provider in providers_for(handler):
        module = import_module(f".{provider.module}", __package__)
        validators[provider.name] = module.validate_case
    return validate_cases(test_dir, handler, validators, selected_cases)


def run(
    handler: str,
    comptests_output: Path | None = None,
    profile: str = "standard",
    preset_name: str = "minimal",
) -> int:
    spec = import_module(f"eth_consensus_specs.gloas.{preset_name}")
    handlers = HANDLERS if handler == "all" else (handler,)
    for current_handler in handlers:
        output_dir = (
            comptests_output
            if comptests_output is not None
            else Path(__file__).parent / current_handler / "reftests"
        )
        materialize_handler(current_handler, profile, output_dir, spec, preset_name)
    return 0
