from pysetup.constants import DAISUGI

from .base import BaseSpecBuilder


class DaisugiSpecBuilder(BaseSpecBuilder):
    fork: str = DAISUGI

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.electra import {preset_name} as electra
"""

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "upgrade_lc_bootstrap_to_electra",
            "upgrade_lc_finality_update_to_electra",
            "upgrade_lc_header_to_electra",
            "upgrade_lc_optimistic_update_to_electra",
            "upgrade_lc_store_to_electra",
            "upgrade_lc_update_to_electra",
            "upgrade_to_electra",
        }
