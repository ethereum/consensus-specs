from typing import Dict
from .base import BaseSpecBuilder
from ..constants import EIP7441


class EIP7441SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7441

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.capella import {preset_name} as capella
import curdleproofs
import json
'''

    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        constants = {
            'EXECUTION_PAYLOAD_GINDEX': 'GeneralizedIndex(41)',
        }
        return {**super().hardcoded_ssz_dep_constants(), **constants}
