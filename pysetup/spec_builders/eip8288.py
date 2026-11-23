from pysetup.constants import EIP8288

from .base import BaseSpecBuilder


class EIP8288SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8288

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.heze import {preset_name} as heze
"""

    @classmethod
    def deprecate_config_vars(cls) -> set[str]:
        return {
            "MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS",
        }
