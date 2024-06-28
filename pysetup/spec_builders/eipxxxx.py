from typing import Dict

from .base import BaseSpecBuilder
from ..constants import EIPXXXX


class EIPXXXXSpecBuilder(BaseSpecBuilder):
    fork: str = EIPXXXX

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.eipxxxx import {preset_name} as eipxxxx
'''

    @classmethod
    def hardcoded_custom_type_dep_constants(cls, spec_object) -> Dict[str, str]:
        return {
            'PTC_SIZE': spec_object.preset_vars['PTC_SIZE'].value,
            'MAX_PAYLOAD_ATTESTATIONS': spec_object.preset_vars['MAX_PAYLOAD_ATTESTATIONS'].value,
        }