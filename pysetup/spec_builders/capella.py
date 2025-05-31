
from ..constants import CAPELLA
from .base import BaseSpecBuilder


class CapellaSpecBuilder(BaseSpecBuilder):
    fork: str = CAPELLA

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth2spec.bellatrix import {preset_name} as bellatrix
"""

    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> dict[str, str]:
        return {
            "EXECUTION_PAYLOAD_GINDEX": "GeneralizedIndex(25)",
        }
