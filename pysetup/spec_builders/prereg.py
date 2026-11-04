from pysetup.constants import PREREG

from .base import BaseSpecBuilder


class PreregSpecBuilder(BaseSpecBuilder):
    fork: str = PREREG

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.gloas import {preset_name} as gloas
from eth_consensus_specs.utils.ssz.bytes import Bytes64
"""

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "upgrade_to_gloas",
        }
