"""
Generate expected config/spec key-value mappings for the eth/v1/config/spec
beacon API endpoint.

For each (preset, fork) combination, the generator introspects the pyspec
module to collect:

  * Config values (from ``configs/*.yaml``)
  * Preset values (from ``presets/{preset}/*.yaml``)
  * Spec constants (from spec markdown tables)

Every value is serialised to the string representation that the beacon API
must return.
"""

from __future__ import annotations

import importlib
import types
from collections.abc import Iterable

from tests.generators.compliance_runners.gen_base.gen_typing import TestCase

SKIP_NAMES = frozenset(
    {
        "T",
        "EXECUTION_ENGINE",
        "KZG_SETUP_G1_LAGRANGE",
        "KZG_SETUP_G1_MONOMIAL",
        "KZG_SETUP_G2_MONOMIAL",
        # Pure mathematical / implementation constants that are not
        # network-configurable and no client is expected to expose.
        "BLS_MODULUS",
        "PRIMITIVE_ROOT_OF_UNITY",
        "ETH_TO_GWEI",
        "UINT64_MAX",
        "UINT64_MAX_SQRT",
        "UINT256_MAX",
        "SAFETY_DECAY",
        "BASIS_POINTS",
        # KZG internals
        "KZG_ENDIANNESS",
        "KZG_SETUP_G2_LENGTH",
        "FIAT_SHAMIR_PROTOCOL_DOMAIN",
        "RANDOM_CHALLENGE_KZG_BATCH_DOMAIN",
        "RANDOM_CHALLENGE_KZG_CELL_BATCH_DOMAIN",
        # Payload status enum values (implementation detail)
        "PAYLOAD_STATUS_EMPTY",
        "PAYLOAD_STATUS_FULL",
        "PAYLOAD_STATUS_PENDING",
        # Builder index sentinel values (implementation detail)
        "BUILDER_INDEX_FLAG",
        "BUILDER_INDEX_SELF_BUILD",
        # Gossip message domains (p2p layer, not beacon API)
        "MESSAGE_DOMAIN_INVALID_SNAPPY",
        "MESSAGE_DOMAIN_VALID_SNAPPY",
        # G1 point at infinity (implementation constant)
        "G1_POINT_AT_INFINITY",
        "G2_POINT_AT_INFINITY",
    }
)

SKIP_TYPE_NAMES = frozenset(
    {
        "TypeVar",
        "NoopExecutionEngine",
    }
)


def _serialize(value: object) -> str | None:
    """Return the canonical string representation of *value*, or ``None``
    if the value should be skipped."""
    type_name = type(value).__name__

    if type_name in SKIP_TYPE_NAMES:
        return None

    if isinstance(value, bytes):
        return "0x" + value.hex()

    if hasattr(value, "hex") and callable(value.hex):
        return "0x" + value.hex()

    if isinstance(value, int):
        return str(int(value))

    if isinstance(value, str):
        return value

    return None


def _collect_spec_values(spec_module: types.ModuleType) -> dict[str, str]:
    """Extract the complete config/spec mapping from a generated pyspec module."""
    result: dict[str, str] = {}

    for name, value in vars(spec_module).items():
        if not name.isupper() or name.startswith("_"):
            continue
        if name in SKIP_NAMES:
            continue
        if isinstance(value, (type, types.ModuleType, types.FunctionType)):
            continue
        if isinstance(value, (list, tuple)):
            continue

        serialized = _serialize(value)
        if serialized is not None:
            result[name] = serialized

    config = getattr(spec_module, "config", None)
    if config is not None:
        for name, value in config._asdict().items():
            if isinstance(value, (list, tuple)):
                continue
            serialized = _serialize(value)
            if serialized is not None:
                result[name] = serialized

    return result


def _make_case_fn(spec_values: dict[str, str]):
    """Return a callable that yields the test case parts."""

    def case_fn():
        yield "data", "data", dict(sorted(spec_values.items()))

    return case_fn


def enumerate_test_cases(
    forks: list[str],
    presets: list[str],
) -> Iterable[TestCase]:
    """Yield ``TestCase`` objects for every (preset, fork) combination."""
    for preset_name in presets:
        for fork_name in forks:
            module_path = f"eth_consensus_specs.{fork_name}.{preset_name}"
            try:
                spec_module = importlib.import_module(module_path)
            except ModuleNotFoundError:
                continue

            spec_values = _collect_spec_values(spec_module)
            if not spec_values:
                continue

            yield TestCase(
                fork_name=fork_name,
                preset_name=preset_name,
                runner_name="config",
                handler_name="spec",
                suite_name="config_spec",
                case_name=f"{preset_name}_{fork_name}",
                case_fn=_make_case_fn(spec_values),
            )
