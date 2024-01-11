from typing import Dict

from .base import BaseSpecBuilder
from ..constants import EIP7594


class EIP7594SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7594

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.deneb import {preset_name} as deneb
'''

    @classmethod
    def hardcoded_custom_type_dep_constants(cls, spec_object) -> str:
        return {
            'FIELD_ELEMENTS_PER_CELL': spec_object.preset_vars['FIELD_ELEMENTS_PER_CELL'].value,
            'NUMBER_OF_COLUMNS': spec_object.preset_vars['NUMBER_OF_COLUMNS'].value,
        }

    @classmethod
    def hardcoded_func_dep_presets(cls, spec_object) -> Dict[str, str]:
        return {
            'KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH': spec_object.preset_vars['KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH'].value,
        }
