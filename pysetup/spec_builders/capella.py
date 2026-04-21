from ..constants import CAPELLA
from .base import BaseSpecBuilder


class CapellaSpecBuilder(BaseSpecBuilder):
    fork: str = CAPELLA

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.bellatrix import {preset_name} as bellatrix
"""

    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> dict[str, str]:
        return {
            "EXECUTION_PAYLOAD_GINDEX": "GeneralizedIndex(25)",
        }

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return set(
            [
                "get_terminal_pow_block",
                "is_execution_enabled",
                "is_merge_transition_block",
                "is_merge_transition_complete",
                "process_historical_roots_update",
                "upgrade_to_bellatrix",
                "validate_merge_block",
            ]
        )
