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
    def hardcoded_custom_type_dep_constants(cls, spec_object) -> str:
        # Necessary for custom types `WhiskShuffleProof` and `WhiskTrackerProof`
        return {
            'MAX_SHUFFLE_PROOF_SIZE': spec_object.preset_vars['MAX_SHUFFLE_PROOF_SIZE'].value,
            'MAX_OPENING_PROOF_SIZE': spec_object.preset_vars['MAX_OPENING_PROOF_SIZE'].value,
            'VALIDATORS_PER_SHUFFLE': spec_object.preset_vars['VALIDATORS_PER_SHUFFLE'].value,
            'CURDLEPROOFS_N_BLINDERS': spec_object.preset_vars['CURDLEPROOFS_N_BLINDERS'].value,
        }

    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        constants = {
            'EXECUTION_PAYLOAD_GINDEX': 'GeneralizedIndex(41)',
        }
        return {**super().hardcoded_ssz_dep_constants(), **constants}
