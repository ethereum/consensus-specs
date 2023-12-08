from typing import Dict
from .base import BaseSpecBuilder
from ..constants import WHISK


class WhiskSpecBuilder(BaseSpecBuilder):
    fork: str = WHISK

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
            'WHISK_MAX_SHUFFLE_PROOF_SIZE': spec_object.preset_vars['WHISK_MAX_SHUFFLE_PROOF_SIZE'].value,
            'WHISK_MAX_OPENING_PROOF_SIZE': spec_object.preset_vars['WHISK_MAX_OPENING_PROOF_SIZE'].value,
            'WHISK_VALIDATORS_PER_SHUFFLE': spec_object.preset_vars['WHISK_VALIDATORS_PER_SHUFFLE'].value,
            'CURDLEPROOFS_N_BLINDERS': spec_object.preset_vars['CURDLEPROOFS_N_BLINDERS'].value,
        }

    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        constants = {
            'EXECUTION_PAYLOAD_INDEX': 'GeneralizedIndex(41)',
        }
        return {**super().hardcoded_ssz_dep_constants(), **constants}
