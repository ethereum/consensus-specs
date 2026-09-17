from pysetup.constants import EIP8198

from .base import BaseSpecBuilder


class EIP8198SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8198

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.heze import {preset_name} as heze
"""

    @classmethod
    def deprecate_constants(cls) -> set[str]:
        return {
            "BASIS_POINTS",
        }

    @classmethod
    def deprecate_config_vars(cls) -> set[str]:
        return {
            "SLOT_DURATION_MS",
            "MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS",
        }

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "on_tick_per_slot",
            "get_base_reward",
            "get_base_reward_per_increment",
            "get_slot_component_duration_ms",
        }
