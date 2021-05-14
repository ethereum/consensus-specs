from setuptools import setup, find_packages, Command
from setuptools.command.build_py import build_py
from distutils import dir_util
from distutils.util import convert_path
import os
import re
import string
import textwrap
from typing import Dict, NamedTuple, List, Sequence, Optional
from abc import ABC, abstractmethod
import ast


# NOTE: have to programmatically include third-party dependencies in `setup.py`.
MARKO_VERSION = "marko==1.0.2"
try:
    import marko
except ImportError:
    import pip
    pip.main(["install", MARKO_VERSION])

from marko.block import Heading, FencedCode, LinkRefDef, BlankLine
from marko.inline import CodeSpan
from marko.ext.gfm import gfm
from marko.ext.gfm.elements import Table, Paragraph


# Definitions in context.py
PHASE0 = 'phase0'
ALTAIR = 'altair'
MERGE = 'merge'

CONFIG_LOADER = '''
apply_constants_config(globals())
'''

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


class ProtocolDefinition(NamedTuple):
    # just function definitions currently. May expand with configuration vars in future.
    functions: Dict[str, str]


class SpecObject(NamedTuple):
    functions: Dict[str, str]
    protocols: Dict[str, ProtocolDefinition]
    custom_types: Dict[str, str]
    constants: Dict[str, str]
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


def get_spec(file_name: str) -> SpecObject:
    functions: Dict[str, str] = {}
    protocols: Dict[str, ProtocolDefinition] = {}
    constants: Dict[str, str] = {}
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
                raise Exception("unrecognized python code element")
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
                    if _is_constant_id(name):
                        if value.startswith("get_generalized_index"):
                            ssz_dep_constants[name] = value
                        else:
                            constants[name] = value.replace("TBD", "2**32")
                    elif value.startswith("uint") or value.startswith("Bytes") or value.startswith("ByteList"):
                        custom_types[name] = value
        elif isinstance(child, LinkRefDef):
            comment = _get_eth2_spec_comment(child)
            if comment == "skip":
                should_skip = True

    return SpecObject(
        functions=functions,
        protocols=protocols,
        custom_types=custom_types,
        constants=constants,
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
    def imports(cls) -> str:
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
    def hardcoded_custom_type_dep_constants(cls) -> Dict[str, str]:
        """
        The constants that are required for custom types.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def invariant_checks(cls) -> str:
        """
        The invariant checks
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def build_spec(cls, source_files: List[str]) -> str:
        raise NotImplementedError()


#
# Phase0SpecBuilder
#
class Phase0SpecBuilder(SpecBuilder):
    fork: str = PHASE0

    @classmethod
    def imports(cls) -> str:
        return '''from lru import LRU
from dataclasses import (
    dataclass,
    field,
)
from typing import (
    Any, Callable, Dict, Set, Sequence, Tuple, Optional, TypeVar
)

from eth2spec.config.config_util import apply_constants_config
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
CONFIG_NAME = 'mainnet'
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
    def invariant_checks(cls) -> str:
        return ''

    @classmethod
    def build_spec(cls, source_files: Sequence[str]) -> str:
        return _build_spec(cls.fork, source_files)


#
# AltairSpecBuilder
#
class AltairSpecBuilder(Phase0SpecBuilder):
    fork: str = ALTAIR

    @classmethod
    def imports(cls) -> str:
        return super().imports() + '\n' + '''
from typing import NewType, Union
from importlib import reload

from eth2spec.phase0 import spec as phase0
from eth2spec.utils.ssz.ssz_typing import Path
'''

    @classmethod
    def preparations(cls):
        return super().preparations() + '\n' + '''
# Whenever this spec version is loaded, make sure we have the latest phase0
reload(phase0)

SSZVariableName = str
GeneralizedIndex = NewType('GeneralizedIndex', int)
'''

    @classmethod
    def sundry_functions(cls) -> str:
        return super().sundry_functions() + '\n\n' + '''
def get_generalized_index(ssz_class: Any, *path: Sequence[Union[int, SSZVariableName]]) -> GeneralizedIndex:
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
    def invariant_checks(cls) -> str:
        return '''
assert (
    TIMELY_HEAD_WEIGHT + TIMELY_SOURCE_WEIGHT + TIMELY_TARGET_WEIGHT + SYNC_REWARD_WEIGHT + PROPOSER_WEIGHT
) == WEIGHT_DENOMINATOR'''


#
# MergeSpecBuilder
#
class MergeSpecBuilder(Phase0SpecBuilder):
    fork: str = MERGE

    @classmethod
    def imports(cls):
        return super().imports() + '''
from typing import Protocol
from eth2spec.phase0 import spec as phase0
from eth2spec.utils.ssz.ssz_typing import Bytes20, ByteList, ByteVector, uint256
from importlib import reload
'''

    @classmethod
    def preparations(cls):
        return super().preparations() + '\n' + '''
reload(phase0)
'''

    @classmethod
    def sundry_functions(cls) -> str:
        return super().sundry_functions() + '\n\n' + """
ExecutionState = Any


def get_pow_block(hash: Bytes32) -> PowBlock:
    return PowBlock(block_hash=hash, is_valid=True, is_processed=True, total_difficulty=TRANSITION_TOTAL_DIFFICULTY)


def get_execution_state(execution_state_root: Bytes32) -> ExecutionState:
    pass


def get_pow_chain_head() -> PowBlock:
    pass


class NoopExecutionEngine(ExecutionEngine):

    def new_block(self, execution_payload: ExecutionPayload) -> bool:
        return True

    def set_head(self, block_hash: Hash32) -> bool:
        return True

    def finalize_block(self, block_hash: Hash32) -> bool:
        return True

    def assemble_block(self, block_hash: Hash32, timestamp: uint64) -> ExecutionPayload:
        raise NotImplementedError("no default block production")


EXECUTION_ENGINE = NoopExecutionEngine()"""


    @classmethod
    def hardcoded_custom_type_dep_constants(cls) -> str:
        constants = {
            'MAX_BYTES_PER_OPAQUE_TRANSACTION': 'uint64(2**20)',
        }
        return {**super().hardcoded_custom_type_dep_constants(), **constants}


spec_builders = {
    builder.fork: builder
    for builder in (Phase0SpecBuilder, AltairSpecBuilder, MergeSpecBuilder)
}


def objects_to_spec(spec_object: SpecObject, builder: SpecBuilder, ordered_class_objects: Dict[str, str]) -> str:
    """
    Given all the objects that constitute a spec, combine them into a single pyfile.
    """
    new_type_definitions = (
        '\n\n'.join(
            [
                f"class {key}({value}):\n    pass\n"
                for key, value in spec_object.custom_types.items()
                if not value.startswith('ByteList')
            ]
        )
        + ('\n\n' if len([key for key, value in spec_object.custom_types.items() if value.startswith('ByteList')]) > 0 else '')
        + '\n\n'.join(
            [
                f"{key} = {value}\n"
                for key, value in spec_object.custom_types.items()
                if value.startswith('ByteList')
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
    functions_spec = '\n\n\n'.join(spec_object.functions.values())
    for k in list(spec_object.constants.keys()):
        if k == "BLS12_381_Q":
            spec_object.constants[k] += "  # noqa: E501"
    constants_spec = '\n'.join(map(lambda x: '%s = %s' % (x, spec_object.constants[x]), spec_object.constants))
    ordered_class_objects_spec = '\n\n\n'.join(ordered_class_objects.values())
    ssz_dep_constants = '\n'.join(map(lambda x: '%s = %s' % (x, builder.hardcoded_ssz_dep_constants()[x]), builder.hardcoded_ssz_dep_constants()))
    ssz_dep_constants_verification = '\n'.join(map(lambda x: 'assert %s == %s' % (x, spec_object.ssz_dep_constants[x]), builder.hardcoded_ssz_dep_constants()))
    custom_type_dep_constants = '\n'.join(map(lambda x: '%s = %s' % (x, builder.hardcoded_custom_type_dep_constants()[x]), builder.hardcoded_custom_type_dep_constants()))
    spec = (
            builder.imports()
            + builder.preparations()
            + '\n\n' + f"fork = \'{builder.fork}\'\n"
            # The constants that some SSZ containers require. Need to be defined before `new_type_definitions`
            + ('\n\n' + custom_type_dep_constants + '\n' if custom_type_dep_constants != '' else '')
            + '\n\n' + new_type_definitions
            + '\n' + CONSTANT_DEP_SUNDRY_CONSTANTS_FUNCTIONS
            # The constants that some SSZ containers require. Need to be defined before `constants_spec`
            + ('\n\n' + ssz_dep_constants if ssz_dep_constants != '' else '')
            + '\n\n' + constants_spec
            + '\n\n' + CONFIG_LOADER
            + '\n\n' + ordered_class_objects_spec
            + ('\n\n\n' + protocols_spec if protocols_spec != '' else '')
            + '\n\n\n' + functions_spec
            + '\n\n' + builder.sundry_functions()
            # Since some constants are hardcoded in setup.py, the following assertions verify that the hardcoded constants are
            # as same as the spec definition.
            + ('\n\n\n' + ssz_dep_constants_verification if ssz_dep_constants_verification != '' else '')
            + ('\n' + builder.invariant_checks() if builder.invariant_checks() != '' else '')
            + '\n'
    )
    return spec


def combine_protocols(old_protocols: Dict[str, ProtocolDefinition],
                      new_protocols: Dict[str, ProtocolDefinition]) -> Dict[str, ProtocolDefinition]:
    for key, value in new_protocols.items():
        if key not in old_protocols:
            old_protocols[key] = value
        else:
            functions = combine_functions(old_protocols[key].functions, value.functions)
            old_protocols[key] = ProtocolDefinition(functions=functions)
    return old_protocols


def combine_functions(old_functions: Dict[str, str], new_functions: Dict[str, str]) -> Dict[str, str]:
    for key, value in new_functions.items():
        old_functions[key] = value
    return old_functions


def combine_constants(old_constants: Dict[str, str], new_constants: Dict[str, str]) -> Dict[str, str]:
    for key, value in new_constants.items():
        old_constants[key] = value
    return old_constants


ignored_dependencies = [
    'bit', 'boolean', 'Vector', 'List', 'Container', 'BLSPubkey', 'BLSSignature',
    'Bytes1', 'Bytes4', 'Bytes20', 'Bytes32', 'Bytes48', 'Bytes96', 'Bitlist', 'Bitvector',
    'uint8', 'uint16', 'uint32', 'uint64', 'uint128', 'uint256',
    'bytes', 'byte', 'ByteList', 'ByteVector',
    'Dict', 'dict', 'field', 'ceillog2', 'floorlog2', 'Set',
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
    functions0, protocols0, custom_types0, constants0, ssz_dep_constants0, ssz_objects0, dataclasses0 = spec0
    functions1, protocols1, custom_types1, constants1, ssz_dep_constants1, ssz_objects1, dataclasses1 = spec1
    protocols = combine_protocols(protocols0, protocols1)
    functions = combine_functions(functions0, functions1)
    custom_types = combine_constants(custom_types0, custom_types1)
    constants = combine_constants(constants0, constants1)
    ssz_dep_constants = combine_constants(ssz_dep_constants0, ssz_dep_constants1)
    ssz_objects = combine_ssz_objects(ssz_objects0, ssz_objects1, custom_types)
    dataclasses = combine_functions(dataclasses0, dataclasses1)
    return SpecObject(
        functions=functions,
        protocols=protocols,
        custom_types=custom_types,
        constants=constants,
        ssz_dep_constants=ssz_dep_constants,
        ssz_objects=ssz_objects,
        dataclasses=dataclasses,
    )


def _build_spec(fork: str, source_files: Sequence[str]) -> str:
    all_specs = [get_spec(spec) for spec in source_files]

    spec_object = all_specs[0]
    for value in all_specs[1:]:
        spec_object = combine_spec_objects(spec_object, value)

    class_objects = {**spec_object.ssz_objects, **spec_object.dataclasses}
    dependency_order_class_objects(class_objects, spec_object.custom_types)

    return objects_to_spec(spec_object, spec_builders[fork], class_objects)


class PySpecCommand(Command):
    """Convert spec markdown files to a spec python file"""

    description = "Convert spec markdown files to a spec python file"

    spec_fork: str
    md_doc_paths: str
    parsed_md_doc_paths: List[str]
    out_dir: str

    # The format is (long option, short option, description).
    user_options = [
        ('spec-fork=', None, "Spec fork to tag build with. Used to select md-docs defaults."),
        ('md-doc-paths=', None, "List of paths of markdown files to build spec with"),
        ('out-dir=', None, "Output directory to write spec package to")
    ]

    def initialize_options(self):
        """Set default values for options."""
        # Each user option must be listed here with their default value.
        self.spec_fork = PHASE0
        self.md_doc_paths = ''
        self.out_dir = 'pyspec_output'

    def finalize_options(self):
        """Post-process options."""
        if len(self.md_doc_paths) == 0:
            print("no paths were specified, using default markdown file paths for pyspec"
                  " build (spec fork: %s)" % self.spec_fork)
            if self.spec_fork == PHASE0:
                self.md_doc_paths = """
                    specs/phase0/beacon-chain.md
                    specs/phase0/fork-choice.md
                    specs/phase0/validator.md
                    specs/phase0/weak-subjectivity.md
                """
            elif self.spec_fork == ALTAIR:
                self.md_doc_paths = """
                    specs/phase0/beacon-chain.md
                    specs/phase0/fork-choice.md
                    specs/phase0/validator.md
                    specs/phase0/weak-subjectivity.md
                    specs/altair/beacon-chain.md
                    specs/altair/fork.md
                    specs/altair/validator.md
                    specs/altair/p2p-interface.md
                    specs/altair/sync-protocol.md
                """
            elif self.spec_fork == MERGE:
                self.md_doc_paths = """
                    specs/phase0/beacon-chain.md
                    specs/phase0/fork-choice.md
                    specs/phase0/validator.md
                    specs/phase0/weak-subjectivity.md
                    specs/merge/beacon-chain.md
                    specs/merge/fork-choice.md
                    specs/merge/validator.md
                """
            else:
                raise Exception('no markdown files specified, and spec fork "%s" is unknown', self.spec_fork)

        self.parsed_md_doc_paths = self.md_doc_paths.split()

        for filename in self.parsed_md_doc_paths:
            if not os.path.exists(filename):
                raise Exception('Pyspec markdown input file "%s" does not exist.' % filename)

    def run(self):
        spec_str = spec_builders[self.spec_fork].build_spec(self.parsed_md_doc_paths)
        if self.dry_run:
            self.announce('dry run successfully prepared contents for spec.'
                          f' out dir: "{self.out_dir}", spec fork: "{self.spec_fork}"')
            self.debug_print(spec_str)
        else:
            dir_util.mkpath(self.out_dir)
            with open(os.path.join(self.out_dir, 'spec.py'), 'w') as out:
                out.write(spec_str)
            with open(os.path.join(self.out_dir, '__init__.py'), 'w') as out:
                out.write("")


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
                  'specs': ['**/*.md'],
                  'eth2spec': ['VERSION.txt']},
    package_dir={
        "eth2spec": "tests/core/pyspec/eth2spec",
        "configs": "configs",
        "specs": "specs",
    },
    packages=find_packages(where='tests/core/pyspec') + ['configs', 'specs'],
    py_modules=["eth2spec"],
    cmdclass=commands,
    python_requires=">=3.8, <4",
    extras_require={
        "test": ["pytest>=4.4", "pytest-cov", "pytest-xdist"],
        "lint": ["flake8==3.7.7", "mypy==0.750"],
        "generator": ["python-snappy==0.5.4"],
    },
    install_requires=[
        "eth-utils>=1.3.0,<2",
        "eth-typing>=2.1.0,<3.0.0",
        "pycryptodome==3.9.4",
        "py_ecc==5.2.0",
        "milagro_bls_binding==1.6.3",
        "dataclasses==0.6",
        "remerkleable==0.1.19",
        "ruamel.yaml==0.16.5",
        "lru-dict==1.1.6",
        "marko==1.0.2",
    ]
)
