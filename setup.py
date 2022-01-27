from setuptools import setup, find_packages, Command
from setuptools.command.build_py import build_py
from distutils import dir_util
from distutils.util import convert_path
from pathlib import Path
import os
import re
import string
import textwrap
from typing import Dict, NamedTuple, List, Sequence, Optional, TypeVar
from abc import ABC, abstractmethod
import ast
import subprocess
import sys

# NOTE: have to programmatically include third-party dependencies in `setup.py`.
def installPackage(package: str):
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])

RUAMEL_YAML_VERSION = "ruamel.yaml==0.16.5"
try:
    import ruamel.yaml
except ImportError:
    installPackage(RUAMEL_YAML_VERSION)

from ruamel.yaml import YAML

MARKO_VERSION = "marko==1.0.2"
try:
    import marko
except ImportError:
    installPackage(MARKO_VERSION)

from marko.block import Heading, FencedCode, LinkRefDef, BlankLine
from marko.inline import CodeSpan
from marko.ext.gfm import gfm
from marko.ext.gfm.elements import Table


# Definitions in context.py
PHASE0 = 'phase0'
ALTAIR = 'altair'
BELLATRIX = 'bellatrix'

# The helper functions that are used when defining constants
CONSTANT_DEP_SUNDRY_CONSTANTS_FUNCTIONS = '''
def ceillog2(x: int) -> uint64:
    if x < 1:
        raise ValueError(f"ceillog2 accepts only positive values, x={x}")
    return uint64((x - 1).bit_length())


def floorlog2(x: int) -> uint64:
    if x < 1:
        raise ValueError(f"floorlog2 accepts only positive values, x={x}")
    return uint64(x.bit_length() - 1)
'''


OPTIMIZED_BLS_AGGREGATE_PUBKEYS = '''
def eth_aggregate_pubkeys(pubkeys: Sequence[BLSPubkey]) -> BLSPubkey:
    return bls.AggregatePKs(pubkeys)
'''


class ProtocolDefinition(NamedTuple):
    # just function definitions currently. May expand with configuration vars in future.
    functions: Dict[str, str]


class VariableDefinition(NamedTuple):
    type_name: Optional[str]
    value: str
    comment: Optional[str]  # e.g. "noqa: E501"


class SpecObject(NamedTuple):
    functions: Dict[str, str]
    protocols: Dict[str, ProtocolDefinition]
    custom_types: Dict[str, str]
    constant_vars: Dict[str, VariableDefinition]
    preset_vars: Dict[str, VariableDefinition]
    config_vars: Dict[str, VariableDefinition]
    ssz_dep_constants: Dict[str, str]  # the constants that depend on ssz_objects
    ssz_objects: Dict[str, str]
    dataclasses: Dict[str, str]


def _get_name_from_heading(heading: Heading) -> Optional[str]:
    last_child = heading.children[-1]
    if isinstance(last_child, CodeSpan):
        return last_child.children
    return None


def _get_source_from_code_block(block: FencedCode) -> str:
    return block.children[0].children.strip()


def _get_function_name_from_source(source: str) -> str:
    fn = ast.parse(source).body[0]
    return fn.name


def _get_self_type_from_source(source: str) -> Optional[str]:
    fn = ast.parse(source).body[0]
    args = fn.args.args
    if len(args) == 0:
        return None
    if args[0].arg != 'self':
        return None
    if args[0].annotation is None:
        return None
    return args[0].annotation.id


def _get_class_info_from_source(source: str) -> (str, Optional[str]):
    class_def = ast.parse(source).body[0]
    base = class_def.bases[0]
    if isinstance(base, ast.Name):
        parent_class = base.id
    else:
        # NOTE: SSZ definition derives from earlier phase...
        # e.g. `phase0.SignedBeaconBlock`
        # TODO: check for consistency with other phases
        parent_class = None
    return class_def.name, parent_class


def _is_constant_id(name: str) -> bool:
    if name[0] not in string.ascii_uppercase + '_':
        return False
    return all(map(lambda c: c in string.ascii_uppercase + '_' + string.digits, name[1:]))


ETH2_SPEC_COMMENT_PREFIX = "eth2spec:"


def _get_eth2_spec_comment(child: LinkRefDef) -> Optional[str]:
    _, _, title = child._parse_info
    if not (title[0] == "(" and title[len(title)-1] == ")"):
        return None
    title = title[1:len(title)-1]
    if not title.startswith(ETH2_SPEC_COMMENT_PREFIX):
        return None
    return title[len(ETH2_SPEC_COMMENT_PREFIX):].strip()


def _parse_value(name: str, typed_value: str) -> VariableDefinition:
    comment = None
    if name == "BLS12_381_Q":
        comment = "noqa: E501"

    typed_value = typed_value.strip()
    if '(' not in typed_value:
        return VariableDefinition(type_name=None, value=typed_value, comment=comment)
    i = typed_value.index('(')
    type_name = typed_value[:i]

    return VariableDefinition(type_name=type_name, value=typed_value[i+1:-1], comment=comment)


def get_spec(file_name: Path, preset: Dict[str, str], config: Dict[str, str]) -> SpecObject:
    functions: Dict[str, str] = {}
    protocols: Dict[str, ProtocolDefinition] = {}
    constant_vars: Dict[str, VariableDefinition] = {}
    preset_vars: Dict[str, VariableDefinition] = {}
    config_vars: Dict[str, VariableDefinition] = {}
    ssz_dep_constants: Dict[str, str] = {}
    ssz_objects: Dict[str, str] = {}
    dataclasses: Dict[str, str] = {}
    custom_types: Dict[str, str] = {}

    with open(file_name) as source_file:
        document = gfm.parse(source_file.read())

    current_name = None
    should_skip = False
    for child in document.children:
        if isinstance(child, BlankLine):
            continue
        if should_skip:
            should_skip = False
            continue
        if isinstance(child, Heading):
            current_name = _get_name_from_heading(child)
        elif isinstance(child, FencedCode):
            if child.lang != "python":
                continue
            source = _get_source_from_code_block(child)
            if source.startswith("def"):
                current_name = _get_function_name_from_source(source)
                self_type_name = _get_self_type_from_source(source)
                function_def = "\n".join(line.rstrip() for line in source.splitlines())
                if self_type_name is None:
                    functions[current_name] = function_def
                else:
                    if self_type_name not in protocols:
                        protocols[self_type_name] = ProtocolDefinition(functions={})
                    protocols[self_type_name].functions[current_name] = function_def
            elif source.startswith("@dataclass"):
                dataclasses[current_name] = "\n".join(line.rstrip() for line in source.splitlines())
            elif source.startswith("class"):
                class_name, parent_class = _get_class_info_from_source(source)
                # check consistency with spec
                assert class_name == current_name
                if parent_class:
                    assert parent_class == "Container"
                # NOTE: trim whitespace from spec
                ssz_objects[current_name] = "\n".join(line.rstrip() for line in source.splitlines())
            else:
                raise Exception("unrecognized python code element: " + source)
        elif isinstance(child, Table):
            for row in child.children:
                cells = row.children
                if len(cells) >= 2:
                    name_cell = cells[0]
                    name = name_cell.children[0].children

                    value_cell = cells[1]
                    value = value_cell.children[0].children
                    if isinstance(value, list):
                        # marko parses `**X**` as a list containing a X
                        value = value[0].children

                    if not _is_constant_id(name):
                        # Check for short type declarations
                        if value.startswith(("uint", "Bytes", "ByteList", "Union")):
                            custom_types[name] = value
                        continue

                    if value.startswith("get_generalized_index"):
                        ssz_dep_constants[name] = value
                        continue

                    value_def = _parse_value(name, value)
                    if name in preset:
                        preset_vars[name] = VariableDefinition(value_def.type_name, preset[name], value_def.comment)
                    elif name in config:
                        config_vars[name] = VariableDefinition(value_def.type_name, config[name], value_def.comment)
                    else:
                        constant_vars[name] = value_def

        elif isinstance(child, LinkRefDef):
            comment = _get_eth2_spec_comment(child)
            if comment == "skip":
                should_skip = True

    return SpecObject(
        functions=functions,
        protocols=protocols,
        custom_types=custom_types,
        constant_vars=constant_vars,
        preset_vars=preset_vars,
        config_vars=config_vars,
        ssz_dep_constants=ssz_dep_constants,
        ssz_objects=ssz_objects,
        dataclasses=dataclasses,
    )


class SpecBuilder(ABC):
    @property
    @abstractmethod
    def fork(self) -> str:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def imports(cls, preset_name: str) -> str:
        """
        Import objects from other libraries.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def preparations(cls) -> str:
        """
        Define special types/constants for building pyspec or call functions.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def sundry_functions(cls) -> str:
        """
        The functions that are (1) defined abstractly in specs or (2) adjusted for getting better performance.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        """
        The constants that are required for SSZ objects.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def hardcoded_custom_type_dep_constants(cls) -> Dict[str, str]:  # TODO
        """
        The constants that are required for custom types.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def implement_optimizations(cls, functions: Dict[str, str]) -> Dict[str, str]:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def build_spec(cls, preset_name: str,
                   source_files: List[Path], preset_files: Sequence[Path], config_file: Path) -> str:
        raise NotImplementedError()


#
# Phase0SpecBuilder
#
class Phase0SpecBuilder(SpecBuilder):
    fork: str = PHASE0

    @classmethod
    def imports(cls, preset_name: str) -> str:
        return '''from lru import LRU
from dataclasses import (
    dataclass,
    field,
)
from typing import (
    Any, Callable, Dict, Set, Sequence, Tuple, Optional, TypeVar, NamedTuple
)

from eth2spec.utils.ssz.ssz_impl import hash_tree_root, copy, uint_to_bytes
from eth2spec.utils.ssz.ssz_typing import (
    View, boolean, Container, List, Vector, uint8, uint32, uint64,
    Bytes1, Bytes4, Bytes32, Bytes48, Bytes96, Bitlist)
from eth2spec.utils.ssz.ssz_typing import Bitvector  # noqa: F401
from eth2spec.utils import bls
from eth2spec.utils.hash_function import hash
'''

    @classmethod
    def preparations(cls) -> str:
        return  '''
SSZObject = TypeVar('SSZObject', bound=View)
'''

    @classmethod
    def sundry_functions(cls) -> str:
        return '''
def get_eth1_data(block: Eth1Block) -> Eth1Data:
    """
    A stub function return mocking Eth1Data.
    """
    return Eth1Data(
        deposit_root=block.deposit_root,
        deposit_count=block.deposit_count,
        block_hash=hash_tree_root(block))


def cache_this(key_fn, value_fn, lru_size):  # type: ignore
    cache_dict = LRU(size=lru_size)

    def wrapper(*args, **kw):  # type: ignore
        key = key_fn(*args, **kw)
        nonlocal cache_dict
        if key not in cache_dict:
            cache_dict[key] = value_fn(*args, **kw)
        return cache_dict[key]
    return wrapper


_compute_shuffled_index = compute_shuffled_index
compute_shuffled_index = cache_this(
    lambda index, index_count, seed: (index, index_count, seed),
    _compute_shuffled_index, lru_size=SLOTS_PER_EPOCH * 3)

_get_total_active_balance = get_total_active_balance
get_total_active_balance = cache_this(
    lambda state: (state.validators.hash_tree_root(), compute_epoch_at_slot(state.slot)),
    _get_total_active_balance, lru_size=10)

_get_base_reward = get_base_reward
get_base_reward = cache_this(
    lambda state, index: (state.validators.hash_tree_root(), state.slot, index),
    _get_base_reward, lru_size=2048)

_get_committee_count_per_slot = get_committee_count_per_slot
get_committee_count_per_slot = cache_this(
    lambda state, epoch: (state.validators.hash_tree_root(), epoch),
    _get_committee_count_per_slot, lru_size=SLOTS_PER_EPOCH * 3)

_get_active_validator_indices = get_active_validator_indices
get_active_validator_indices = cache_this(
    lambda state, epoch: (state.validators.hash_tree_root(), epoch),
    _get_active_validator_indices, lru_size=3)

_get_beacon_committee = get_beacon_committee
get_beacon_committee = cache_this(
    lambda state, slot, index: (state.validators.hash_tree_root(), state.randao_mixes.hash_tree_root(), slot, index),
    _get_beacon_committee, lru_size=SLOTS_PER_EPOCH * MAX_COMMITTEES_PER_SLOT * 3)

_get_matching_target_attestations = get_matching_target_attestations
get_matching_target_attestations = cache_this(
    lambda state, epoch: (state.hash_tree_root(), epoch),
    _get_matching_target_attestations, lru_size=10)

_get_matching_head_attestations = get_matching_head_attestations
get_matching_head_attestations = cache_this(
    lambda state, epoch: (state.hash_tree_root(), epoch),
    _get_matching_head_attestations, lru_size=10)

_get_attesting_indices = get_attesting_indices
get_attesting_indices = cache_this(
    lambda state, data, bits: (
        state.randao_mixes.hash_tree_root(),
        state.validators.hash_tree_root(), data.hash_tree_root(), bits.hash_tree_root()
    ),
    _get_attesting_indices, lru_size=SLOTS_PER_EPOCH * MAX_COMMITTEES_PER_SLOT * 3)'''

    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        return {}

    @classmethod
    def hardcoded_custom_type_dep_constants(cls) -> Dict[str, str]:
        return {}

    @classmethod
    def implement_optimizations(cls, functions: Dict[str, str]) -> Dict[str, str]:
        return functions

    @classmethod
    def build_spec(cls, preset_name: str,
                   source_files: Sequence[Path], preset_files: Sequence[Path], config_file: Path) -> str:
        return _build_spec(preset_name, cls.fork, source_files, preset_files, config_file)


#
# AltairSpecBuilder
#
class AltairSpecBuilder(Phase0SpecBuilder):
    fork: str = ALTAIR

    @classmethod
    def imports(cls, preset_name: str) -> str:
        return super().imports(preset_name) + '\n' + f'''
from typing import NewType, Union as PyUnion

from eth2spec.phase0 import {preset_name} as phase0
from eth2spec.utils.ssz.ssz_typing import Path
'''

    @classmethod
    def preparations(cls):
        return super().preparations() + '\n' + '''
SSZVariableName = str
GeneralizedIndex = NewType('GeneralizedIndex', int)
'''

    @classmethod
    def sundry_functions(cls) -> str:
        return super().sundry_functions() + '\n\n' + '''
def get_generalized_index(ssz_class: Any, *path: Sequence[PyUnion[int, SSZVariableName]]) -> GeneralizedIndex:
    ssz_path = Path(ssz_class)
    for item in path:
        ssz_path = ssz_path / item
    return GeneralizedIndex(ssz_path.gindex())'''


    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        constants = {
            'FINALIZED_ROOT_INDEX': 'GeneralizedIndex(105)',
            'NEXT_SYNC_COMMITTEE_INDEX': 'GeneralizedIndex(55)',
        }
        return {**super().hardcoded_ssz_dep_constants(), **constants}

    @classmethod
    def implement_optimizations(cls, functions: Dict[str, str]) -> Dict[str, str]:
        if "eth_aggregate_pubkeys" in functions:
            functions["eth_aggregate_pubkeys"] = OPTIMIZED_BLS_AGGREGATE_PUBKEYS.strip()
        return super().implement_optimizations(functions)

#
# BellatrixSpecBuilder
#
class BellatrixSpecBuilder(AltairSpecBuilder):
    fork: str = BELLATRIX

    @classmethod
    def imports(cls, preset_name: str):
        return super().imports(preset_name) + f'''
from typing import Protocol
from eth2spec.altair import {preset_name} as altair
from eth2spec.utils.ssz.ssz_typing import Bytes8, Bytes20, ByteList, ByteVector, uint256
'''

    @classmethod
    def preparations(cls):
        return super().preparations()

    @classmethod
    def sundry_functions(cls) -> str:
        return super().sundry_functions() + '\n\n' + """
ExecutionState = Any


def get_pow_block(hash: Bytes32) -> Optional[PowBlock]:
    return PowBlock(block_hash=hash, parent_hash=Bytes32(), total_difficulty=uint256(0))


def get_execution_state(_execution_state_root: Bytes32) -> ExecutionState:
    pass


def get_pow_chain_head() -> PowBlock:
    pass


class NoopExecutionEngine(ExecutionEngine):

    def notify_new_payload(self: ExecutionEngine, execution_payload: ExecutionPayload) -> bool:
        return True

    def notify_forkchoice_updated(self: ExecutionEngine,
                                  head_block_hash: Hash32,
                                  finalized_block_hash: Hash32,
                                  payload_attributes: Optional[PayloadAttributes]) -> Optional[PayloadId]:
        pass

    def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> ExecutionPayload:
        raise NotImplementedError("no default block production")


EXECUTION_ENGINE = NoopExecutionEngine()"""


    @classmethod
    def hardcoded_custom_type_dep_constants(cls) -> str:
        constants = {
            'MAX_BYTES_PER_TRANSACTION': 'uint64(2**30)',
        }
        return {**super().hardcoded_custom_type_dep_constants(), **constants}


spec_builders = {
    builder.fork: builder
    for builder in (Phase0SpecBuilder, AltairSpecBuilder, BellatrixSpecBuilder)
}


def is_spec_defined_type(value: str) -> bool:
    return value.startswith('ByteList') or value.startswith('Union')


def objects_to_spec(preset_name: str,
                    spec_object: SpecObject,
                    builder: SpecBuilder,
                    ordered_class_objects: Dict[str, str]) -> str:
    """
    Given all the objects that constitute a spec, combine them into a single pyfile.
    """
    new_type_definitions = (
        '\n\n'.join(
            [
                f"class {key}({value}):\n    pass\n"
                for key, value in spec_object.custom_types.items()
                if not is_spec_defined_type(value)
            ]
        )
        + ('\n\n' if len([key for key, value in spec_object.custom_types.items() if is_spec_defined_type(value)]) > 0 else '')
        + '\n\n'.join(
            [
                f"{key} = {value}\n"
                for key, value in spec_object.custom_types.items()
                if is_spec_defined_type(value)
            ]
        )
    )

    def format_protocol(protocol_name: str, protocol_def: ProtocolDefinition) -> str:
        protocol = f"class {protocol_name}(Protocol):"
        for fn_source in protocol_def.functions.values():
            fn_source = fn_source.replace("self: "+protocol_name, "self")
            protocol += "\n\n" + textwrap.indent(fn_source, "    ")
        return protocol

    protocols_spec = '\n\n\n'.join(format_protocol(k, v) for k, v in spec_object.protocols.items())
    for k in list(spec_object.functions):
        if "ceillog2" in k or "floorlog2" in k:
            del spec_object.functions[k]
    functions = builder.implement_optimizations(spec_object.functions)
    functions_spec = '\n\n\n'.join(functions.values())

    # Access global dict of config vars for runtime configurables
    for name in spec_object.config_vars.keys():
        functions_spec = re.sub(r"\b%s\b" % name, 'config.' + name, functions_spec)

    def format_config_var(name: str, vardef: VariableDefinition) -> str:
        if vardef.type_name is None:
            out = f'{name}={vardef.value},'
        else:
            out = f'{name}={vardef.type_name}({vardef.value}),'
        if vardef.comment is not None:
            out += f'  # {vardef.comment}'
        return out

    config_spec = 'class Configuration(NamedTuple):\n'
    config_spec += '    PRESET_BASE: str\n'
    config_spec += '\n'.join(f'    {k}: {v.type_name if v.type_name is not None else "int"}'
                             for k, v in spec_object.config_vars.items())
    config_spec += '\n\n\nconfig = Configuration(\n'
    config_spec += f'    PRESET_BASE="{preset_name}",\n'
    config_spec += '\n'.join('    ' + format_config_var(k, v) for k, v in spec_object.config_vars.items())
    config_spec += '\n)\n'

    def format_constant(name: str, vardef: VariableDefinition) -> str:
        if vardef.type_name is None:
            out = f'{name} = {vardef.value}'
        else:
            out = f'{name} = {vardef.type_name}({vardef.value})'
        if vardef.comment is not None:
            out += f'  # {vardef.comment}'
        return out

    constant_vars_spec = '# Constant vars\n' + '\n'.join(format_constant(k, v) for k, v in spec_object.constant_vars.items())
    preset_vars_spec = '# Preset vars\n' + '\n'.join(format_constant(k, v) for k, v in spec_object.preset_vars.items())
    ordered_class_objects_spec = '\n\n\n'.join(ordered_class_objects.values())
    ssz_dep_constants = '\n'.join(map(lambda x: '%s = %s' % (x, builder.hardcoded_ssz_dep_constants()[x]), builder.hardcoded_ssz_dep_constants()))
    ssz_dep_constants_verification = '\n'.join(map(lambda x: 'assert %s == %s' % (x, spec_object.ssz_dep_constants[x]), builder.hardcoded_ssz_dep_constants()))
    custom_type_dep_constants = '\n'.join(map(lambda x: '%s = %s' % (x, builder.hardcoded_custom_type_dep_constants()[x]), builder.hardcoded_custom_type_dep_constants()))
    spec = (
            builder.imports(preset_name)
            + builder.preparations()
            + '\n\n' + f"fork = \'{builder.fork}\'\n"
            # The constants that some SSZ containers require. Need to be defined before `new_type_definitions`
            + ('\n\n' + custom_type_dep_constants + '\n' if custom_type_dep_constants != '' else '')
            + '\n\n' + new_type_definitions
            + '\n' + CONSTANT_DEP_SUNDRY_CONSTANTS_FUNCTIONS
            # The constants that some SSZ containers require. Need to be defined before `constants_spec`
            + ('\n\n' + ssz_dep_constants if ssz_dep_constants != '' else '')
            + '\n\n' + constant_vars_spec
            + '\n\n' + preset_vars_spec
            + '\n\n\n' + config_spec
            + '\n\n' + ordered_class_objects_spec
            + ('\n\n\n' + protocols_spec if protocols_spec != '' else '')
            + '\n\n\n' + functions_spec
            + '\n\n' + builder.sundry_functions()
            # Since some constants are hardcoded in setup.py, the following assertions verify that the hardcoded constants are
            # as same as the spec definition.
            + ('\n\n\n' + ssz_dep_constants_verification if ssz_dep_constants_verification != '' else '')
            + '\n'
    )
    return spec


def combine_protocols(old_protocols: Dict[str, ProtocolDefinition],
                      new_protocols: Dict[str, ProtocolDefinition]) -> Dict[str, ProtocolDefinition]:
    for key, value in new_protocols.items():
        if key not in old_protocols:
            old_protocols[key] = value
        else:
            functions = combine_dicts(old_protocols[key].functions, value.functions)
            old_protocols[key] = ProtocolDefinition(functions=functions)
    return old_protocols


T = TypeVar('T')


def combine_dicts(old_dict: Dict[str, T], new_dict: Dict[str, T]) -> Dict[str, T]:
    return {**old_dict, **new_dict}


ignored_dependencies = [
    'bit', 'boolean', 'Vector', 'List', 'Container', 'BLSPubkey', 'BLSSignature',
    'Bytes1', 'Bytes4', 'Bytes8', 'Bytes20', 'Bytes32', 'Bytes48', 'Bytes96', 'Bitlist', 'Bitvector',
    'uint8', 'uint16', 'uint32', 'uint64', 'uint128', 'uint256',
    'bytes', 'byte', 'ByteList', 'ByteVector',
    'Dict', 'dict', 'field', 'ceillog2', 'floorlog2', 'Set',
    'Optional',
]


def dependency_order_class_objects(objects: Dict[str, str], custom_types: Dict[str, str]) -> None:
    """
    Determines which SSZ Object is dependent on which other and orders them appropriately
    """
    items = list(objects.items())
    for key, value in items:
        dependencies = []
        for line in value.split('\n'):
            if not re.match(r'\s+\w+: .+', line):
                continue  # skip whitespace etc.
            line = line[line.index(':') + 1:]  # strip of field name
            if '#' in line:
                line = line[:line.index('#')]  # strip of comment
            dependencies.extend(re.findall(r'(\w+)', line))  # catch all legible words, potential dependencies
        dependencies = filter(lambda x: '_' not in x and x.upper() != x, dependencies)  # filter out constants
        dependencies = filter(lambda x: x not in ignored_dependencies, dependencies)
        dependencies = filter(lambda x: x not in custom_types, dependencies)
        for dep in dependencies:
            key_list = list(objects.keys())
            for item in [dep, key] + key_list[key_list.index(dep)+1:]:
                objects[item] = objects.pop(item)


def combine_ssz_objects(old_objects: Dict[str, str], new_objects: Dict[str, str], custom_types) -> Dict[str, str]:
    """
    Takes in old spec and new spec ssz objects, combines them,
    and returns the newer versions of the objects in dependency order.
    """
    for key, value in new_objects.items():
        old_objects[key] = value
    return old_objects


def combine_spec_objects(spec0: SpecObject, spec1: SpecObject) -> SpecObject:
    """
    Takes in two spec variants (as tuples of their objects) and combines them using the appropriate combiner function.
    """
    protocols = combine_protocols(spec0.protocols, spec1.protocols)
    functions = combine_dicts(spec0.functions, spec1.functions)
    custom_types = combine_dicts(spec0.custom_types, spec1.custom_types)
    constant_vars = combine_dicts(spec0.constant_vars, spec1.constant_vars)
    preset_vars = combine_dicts(spec0.preset_vars, spec1.preset_vars)
    config_vars = combine_dicts(spec0.config_vars, spec1.config_vars)
    ssz_dep_constants = combine_dicts(spec0.ssz_dep_constants, spec1.ssz_dep_constants)
    ssz_objects = combine_ssz_objects(spec0.ssz_objects, spec1.ssz_objects, custom_types)
    dataclasses = combine_dicts(spec0.dataclasses, spec1.dataclasses)
    return SpecObject(
        functions=functions,
        protocols=protocols,
        custom_types=custom_types,
        constant_vars=constant_vars,
        preset_vars=preset_vars,
        config_vars=config_vars,
        ssz_dep_constants=ssz_dep_constants,
        ssz_objects=ssz_objects,
        dataclasses=dataclasses,
    )


def parse_config_vars(conf: Dict[str, str]) -> Dict[str, str]:
    """
    Parses a dict of basic str/int/list types into a dict for insertion into the spec code.
    """
    out: Dict[str, str] = dict()
    for k, v in conf.items():
        if isinstance(v, str) and (v.startswith("0x") or k == 'PRESET_BASE' or k == 'CONFIG_NAME'):
            # Represent byte data with string, to avoid misinterpretation as big-endian int.
            # Everything is either byte data or an integer, with PRESET_BASE as one exception.
            out[k] = f"'{v}'"
        else:
            out[k] = str(int(v))
    return out


def load_preset(preset_files: Sequence[Path]) -> Dict[str, str]:
    """
    Loads the a directory of preset files, merges the result into one preset.
    """
    preset = {}
    for fork_file in preset_files:
        yaml = YAML(typ='base')
        fork_preset: dict = yaml.load(fork_file)
        if fork_preset is None:  # for empty YAML files
            continue
        if not set(fork_preset.keys()).isdisjoint(preset.keys()):
            duplicates = set(fork_preset.keys()).intersection(set(preset.keys()))
            raise Exception(f"duplicate config var(s) in preset files: {', '.join(duplicates)}")
        preset.update(fork_preset)
    assert preset != {}
    return parse_config_vars(preset)


def load_config(config_path: Path) -> Dict[str, str]:
    """
    Loads the given configuration file.
    """
    yaml = YAML(typ='base')
    config_data = yaml.load(config_path)
    return parse_config_vars(config_data)


def _build_spec(preset_name: str, fork: str,
                source_files: Sequence[Path], preset_files: Sequence[Path], config_file: Path) -> str:
    preset = load_preset(preset_files)
    config = load_config(config_file)
    all_specs = [get_spec(spec, preset, config) for spec in source_files]

    spec_object = all_specs[0]
    for value in all_specs[1:]:
        spec_object = combine_spec_objects(spec_object, value)

    class_objects = {**spec_object.ssz_objects, **spec_object.dataclasses}
    dependency_order_class_objects(class_objects, spec_object.custom_types)

    return objects_to_spec(preset_name, spec_object, spec_builders[fork], class_objects)


class BuildTarget(NamedTuple):
    name: str
    preset_paths: List[Path]
    config_path: Path


class PySpecCommand(Command):
    """Convert spec markdown files to a spec python file"""

    description = "Convert spec markdown files to a spec python file"

    spec_fork: str
    md_doc_paths: str
    parsed_md_doc_paths: List[str]
    build_targets: str
    parsed_build_targets: List[BuildTarget]
    out_dir: str

    # The format is (long option, short option, description).
    user_options = [
        ('spec-fork=', None, "Spec fork to tag build with. Used to select md-docs defaults."),
        ('md-doc-paths=', None, "List of paths of markdown files to build spec with"),
        ('build-targets=', None, "Names, directory paths of compile-time presets, and default config paths."),
        ('out-dir=', None, "Output directory to write spec package to")
    ]

    def initialize_options(self):
        """Set default values for options."""
        # Each user option must be listed here with their default value.
        self.spec_fork = PHASE0
        self.md_doc_paths = ''
        self.out_dir = 'pyspec_output'
        self.build_targets = """
                minimal:presets/minimal:configs/minimal.yaml
                mainnet:presets/mainnet:configs/mainnet.yaml
        """

    def finalize_options(self):
        """Post-process options."""
        if len(self.md_doc_paths) == 0:
            print("no paths were specified, using default markdown file paths for pyspec"
                  " build (spec fork: %s)" % self.spec_fork)
            if self.spec_fork in (PHASE0, ALTAIR, BELLATRIX):
                self.md_doc_paths = """
                    specs/phase0/beacon-chain.md
                    specs/phase0/fork-choice.md
                    specs/phase0/validator.md
                    specs/phase0/weak-subjectivity.md
                """
            if self.spec_fork in (ALTAIR, BELLATRIX):
                self.md_doc_paths += """
                    specs/altair/beacon-chain.md
                    specs/altair/bls.md
                    specs/altair/fork.md
                    specs/altair/validator.md
                    specs/altair/p2p-interface.md
                    specs/altair/sync-protocol.md
                """
            if self.spec_fork == BELLATRIX:
                self.md_doc_paths += """
                    specs/bellatrix/beacon-chain.md
                    specs/bellatrix/fork.md
                    specs/bellatrix/fork-choice.md
                    specs/bellatrix/validator.md
                    sync/optimistic.md
                """
            if len(self.md_doc_paths) == 0:
                raise Exception('no markdown files specified, and spec fork "%s" is unknown', self.spec_fork)

        self.parsed_md_doc_paths = self.md_doc_paths.split()

        for filename in self.parsed_md_doc_paths:
            if not os.path.exists(filename):
                raise Exception('Pyspec markdown input file "%s" does not exist.' % filename)

        self.parsed_build_targets = []
        for target in self.build_targets.split():
            target = target.strip()
            data = target.split(':')
            if len(data) != 3:
                raise Exception('invalid target, expected "name:preset_dir:config_file" format, but got: %s' % target)
            name, preset_dir_path, config_path = data
            if any((c not in string.digits + string.ascii_letters) for c in name):
                raise Exception('invalid target name: "%s"' % name)
            if not os.path.exists(preset_dir_path):
                raise Exception('Preset dir "%s" does not exist' % preset_dir_path)
            _, _, preset_file_names = next(os.walk(preset_dir_path))
            preset_paths = [(Path(preset_dir_path) / name) for name in preset_file_names]

            if not os.path.exists(config_path):
                raise Exception('Config file "%s" does not exist' % config_path)
            self.parsed_build_targets.append(BuildTarget(name, preset_paths, Path(config_path)))

    def run(self):
        if not self.dry_run:
            dir_util.mkpath(self.out_dir)

        for (name, preset_paths, config_path) in self.parsed_build_targets:
            spec_str = spec_builders[self.spec_fork].build_spec(
                name, self.parsed_md_doc_paths, preset_paths, config_path)
            if self.dry_run:
                self.announce('dry run successfully prepared contents for spec.'
                              f' out dir: "{self.out_dir}", spec fork: "{self.spec_fork}", build target: "{name}"')
                self.debug_print(spec_str)
            else:
                with open(os.path.join(self.out_dir, name+'.py'), 'w') as out:
                    out.write(spec_str)

        if not self.dry_run:
            with open(os.path.join(self.out_dir, '__init__.py'), 'w') as out:
                # `mainnet` is the default spec.
                out.write("from . import mainnet as spec  # noqa:F401\n")


class BuildPyCommand(build_py):
    """Customize the build command to run the spec-builder on setup.py build"""

    def initialize_options(self):
        super(BuildPyCommand, self).initialize_options()

    def run_pyspec_cmd(self, spec_fork: str, **opts):
        cmd_obj: PySpecCommand = self.distribution.reinitialize_command("pyspec")
        cmd_obj.spec_fork = spec_fork
        cmd_obj.out_dir = os.path.join(self.build_lib, 'eth2spec', spec_fork)
        for k, v in opts.items():
            setattr(cmd_obj, k, v)
        self.run_command('pyspec')

    def run(self):
        for spec_fork in spec_builders:
            self.run_pyspec_cmd(spec_fork=spec_fork)

        super(BuildPyCommand, self).run()


class PyspecDevCommand(Command):
    """Build the markdown files in-place to their source location for testing."""
    description = "Build the markdown files in-place to their source location for testing."
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run_pyspec_cmd(self, spec_fork: str, **opts):
        cmd_obj: PySpecCommand = self.distribution.reinitialize_command("pyspec")
        cmd_obj.spec_fork = spec_fork
        eth2spec_dir = convert_path(self.distribution.package_dir['eth2spec'])
        cmd_obj.out_dir = os.path.join(eth2spec_dir, spec_fork)
        for k, v in opts.items():
            setattr(cmd_obj, k, v)
        self.run_command('pyspec')

    def run(self):
        print("running build_py command")
        for spec_fork in spec_builders:
            self.run_pyspec_cmd(spec_fork=spec_fork)

commands = {
    'pyspec': PySpecCommand,
    'build_py': BuildPyCommand,
    'pyspecdev': PyspecDevCommand,
}

with open("README.md", "rt", encoding="utf8") as f:
    readme = f.read()

# How to use "VERSION.txt" file:
# - dev branch contains "X.Y.Z.dev", where "X.Y.Z" is the target version to release dev into.
#    -> Changed as part of 'master' backport to 'dev'
# - master branch contains "X.Y.Z", where "X.Y.Z" is the current version.
#    -> Changed as part of 'dev' release (or other branch) into 'master'
#    -> In case of a commit on master without git tag, target the next version
#        with ".postN" (release candidate, numbered) suffixed.
# See https://www.python.org/dev/peps/pep-0440/#public-version-identifiers
with open(os.path.join('tests', 'core', 'pyspec', 'eth2spec', 'VERSION.txt')) as f:
    spec_version = f.read().strip()

setup(
    name='eth2spec',
    version=spec_version,
    description="Eth2 spec, provided as Python package for tooling and testing",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="ethereum",
    url="https://github.com/ethereum/eth2.0-specs",
    include_package_data=False,
    package_data={'configs': ['*.yaml'],
                  'presets': ['*.yaml'],
                  'specs': ['**/*.md'],
                  'eth2spec': ['VERSION.txt']},
    package_dir={
        "eth2spec": "tests/core/pyspec/eth2spec",
        "configs": "configs",
        "presets": "presets",
        "specs": "specs",
    },
    packages=find_packages(where='tests/core/pyspec') + ['configs', 'specs'],
    py_modules=["eth2spec"],
    cmdclass=commands,
    python_requires=">=3.8, <4",
    extras_require={
        "test": ["pytest>=4.4", "pytest-cov", "pytest-xdist"],
        "lint": ["flake8==3.7.7", "mypy==0.812", "pylint==2.12.2"],
        "generator": ["python-snappy==0.5.4"],
    },
    install_requires=[
        "eth-utils>=1.3.0,<2",
        "eth-typing>=2.1.0,<3.0.0",
        "pycryptodome==3.9.4",
        "py_ecc==5.2.0",
        "milagro_bls_binding==1.6.3",
        "dataclasses==0.6",
        "remerkleable==0.1.24",
        RUAMEL_YAML_VERSION,
        "lru-dict==1.1.6",
        MARKO_VERSION,
    ]
)
