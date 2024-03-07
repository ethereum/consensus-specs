from typing import Dict

from .base import BaseSpecBuilder
from ..constants import CAPELLA


class CapellaSpecBuilder(BaseSpecBuilder):
    fork: str = CAPELLA

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.bellatrix import {preset_name} as bellatrix
'''

    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        return {
            'EXECUTION_PAYLOAD_GINDEX': 'GeneralizedIndex(25)',
        }
