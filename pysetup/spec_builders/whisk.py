from .base import BaseSpecBuilder
from ..constants import WHISK


class WhiskSpecBuilder(BaseSpecBuilder):
    fork: str = WHISK

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.capella import {preset_name} as capella
'''

    @classmethod
    def hardcoded_custom_type_dep_constants(cls, spec_object) -> str:
        # Necessary for custom types `WhiskShuffleProof` and `WhiskTrackerProof`
        return {
            'WHISK_MAX_SHUFFLE_PROOF_SIZE': spec_object.preset_vars['WHISK_MAX_SHUFFLE_PROOF_SIZE'].value,
            'WHISK_MAX_OPENING_PROOF_SIZE': spec_object.preset_vars['WHISK_MAX_OPENING_PROOF_SIZE'].value,
        }
