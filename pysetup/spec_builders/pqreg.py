from pysetup.constants import PQREG

from .base import BaseSpecBuilder


class PQRegSpecBuilder(BaseSpecBuilder):
    fork: str = PQREG

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
