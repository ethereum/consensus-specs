from enum import Enum, auto
from setuptools import setup, find_packages, Command
from setuptools.command.build_py import build_py
from distutils import dir_util
from distutils.util import convert_path
import os
import re
from typing import Dict, NamedTuple, List

FUNCTION_REGEX = r'^def [\w_]*'


class SpecObject(NamedTuple):
    functions: Dict[str, str]
    custom_types: Dict[str, str]
    constants: Dict[str, str]
    ssz_objects: Dict[str, str]
    dataclasses: Dict[str, str]


class CodeBlockType(Enum):
    SSZ = auto()
    DATACLASS = auto()
    FUNCTION = auto()


def get_spec(file_name: str) -> SpecObject:
    """
    Takes in the file name of a spec.md file, opens it and returns a parsed spec object.

    Note: This function makes heavy use of the inherent ordering of dicts,
    if this is not supported by your python version, it will not work.
    """
    pulling_from = None  # line number of start of latest object
    current_name = None  # most recent section title
    functions: Dict[str, str] = {}
    constants: Dict[str, str] = {}
    ssz_objects: Dict[str, str] = {}
    dataclasses: Dict[str, str] = {}
    function_matcher = re.compile(FUNCTION_REGEX)
    block_type = CodeBlockType.FUNCTION
    custom_types: Dict[str, str] = {}
    for linenum, line in enumerate(open(file_name).readlines()):
        line = line.rstrip()
        if pulling_from is None and len(line) > 0 and line[0] == '#' and line[-1] == '`':
            current_name = line[line[:-1].rfind('`') + 1: -1]
        if line[:9] == '```python':
            assert pulling_from is None
            pulling_from = linenum + 1
        elif line[:3] == '```':
            pulling_from = None
        else:
            # Handle function definitions & ssz_objects
            if pulling_from is not None:
                if len(line) > 18 and line[:6] == 'class ' and (line[-12:] == '(Container):' or '(phase' in line):
                    end = -12 if line[-12:] == '(Container):' else line.find('(')
                    name = line[6:end]
                    # Check consistency with markdown header
                    assert name == current_name
                    block_type = CodeBlockType.SSZ
                elif line[:10] == '@dataclass':
                    block_type = CodeBlockType.DATACLASS
                elif function_matcher.match(line) is not None:
                    current_name = function_matcher.match(line).group(0)
                    block_type = CodeBlockType.FUNCTION

                if block_type == CodeBlockType.SSZ:
                    ssz_objects[current_name] = ssz_objects.get(current_name, '') + line + '\n'
                elif block_type == CodeBlockType.DATACLASS:
                    dataclasses[current_name] = dataclasses.get(current_name, '') + line + '\n'
                elif block_type == CodeBlockType.FUNCTION:
                    functions[current_name] = functions.get(current_name, '') + line + '\n'
                else:
                    pass

            # Handle constant and custom types table entries
            elif pulling_from is None and len(line) > 0 and line[0] == '|':
                row = line[1:].split('|')
                if len(row) >= 2:
                    for i in range(2):
                        row[i] = row[i].strip().strip('`')
                        if '`' in row[i]:
                            row[i] = row[i][:row[i].find('`')]
                    is_constant_def = True
                    if row[0][0] not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_':
                        is_constant_def = False
                    for c in row[0]:
                        if c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789':
                            is_constant_def = False
                    if is_constant_def:
                        constants[row[0]] = row[1].replace('**TBD**', '2**32')
                    elif row[1].startswith('uint') or row[1].startswith('Bytes'):
                        custom_types[row[0]] = row[1]
    return SpecObject(functions, custom_types, constants, ssz_objects, dataclasses)


CONFIG_LOADER = '''
apply_constants_config(globals())
'''

PHASE0_IMPORTS = '''from eth2spec.config.config_util import apply_constants_config
from typing import (
    Any, Callable, Dict, Set, Sequence, Tuple, Optional, TypeVar
)

from dataclasses import (
    dataclass,
    field,
)

from lru import LRU

from eth2spec.utils.ssz.ssz_impl import hash_tree_root, copy, uint_to_bytes
from eth2spec.utils.ssz.ssz_typing import (
    View, boolean, Container, List, Vector, uint8, uint32, uint64,
    Bytes1, Bytes4, Bytes32, Bytes48, Bytes96, Bitlist, Bitvector,
)
from eth2spec.utils import bls

from eth2spec.utils.hash_function import hash

SSZObject = TypeVar('SSZObject', bound=View)

CONFIG_NAME = 'mainnet'
'''
PHASE1_IMPORTS = '''from eth2spec.phase0 import spec as phase0
from eth2spec.config.config_util import apply_constants_config
from typing import (
    Any, Dict, Set, Sequence, NewType, Tuple, TypeVar, Callable, Optional
)
from typing import List as PyList

from dataclasses import (
    dataclass,
    field,
)

from lru import LRU

from eth2spec.utils.ssz.ssz_impl import hash_tree_root, copy, uint_to_bytes
from eth2spec.utils.ssz.ssz_typing import (
    View, boolean, Container, List, Vector, uint8, uint32, uint64, bit,
    ByteList, ByteVector, Bytes1, Bytes4, Bytes32, Bytes48, Bytes96, Bitlist, Bitvector,
)
from eth2spec.utils import bls

from eth2spec.utils.hash_function import hash

# Whenever phase 1 is loaded, make sure we have the latest phase0
from importlib import reload
reload(phase0)


SSZVariableName = str
GeneralizedIndex = NewType('GeneralizedIndex', int)
SSZObject = TypeVar('SSZObject', bound=View)

CONFIG_NAME = 'mainnet'
'''
LIGHTCLIENT_IMPORT = '''from eth2spec.phase0 import spec as phase0
from eth2spec.config.config_util import apply_constants_config
from typing import (
    Any, Dict, Set, Sequence, NewType, Tuple, TypeVar, Callable, Optional
)

from dataclasses import (
    dataclass,
    field,
)

from lru import LRU

from eth2spec.utils.ssz.ssz_impl import hash_tree_root, copy, uint_to_bytes
from eth2spec.utils.ssz.ssz_typing import (
    View, boolean, Container, List, Vector, uint8, uint32, uint64,
    Bytes1, Bytes4, Bytes32, Bytes48, Bytes96, Bitlist, Bitvector,
)
from eth2spec.utils import bls

from eth2spec.utils.hash_function import hash

# Whenever lightclient is loaded, make sure we have the latest phase0
from importlib import reload
reload(phase0)


SSZVariableName = str
GeneralizedIndex = NewType('GeneralizedIndex', int)
SSZObject = TypeVar('SSZObject', bound=View)

CONFIG_NAME = 'mainnet'
'''

SUNDRY_CONSTANTS_FUNCTIONS = '''
def ceillog2(x: int) -> uint64:
    if x < 1:
        raise ValueError(f"ceillog2 accepts only positive values, x={x}")
    return uint64((x - 1).bit_length())
'''
PHASE0_SUNDRY_FUNCTIONS = '''
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


PHASE1_SUNDRY_FUNCTIONS = '''

_get_start_shard = get_start_shard
get_start_shard = cache_this(
    lambda state, slot: (state.validators.hash_tree_root(), slot),
    _get_start_shard, lru_size=SLOTS_PER_EPOCH * 3)'''


def objects_to_spec(spec_object: SpecObject, imports: str, fork: str, ordered_class_objects: Dict[str, str]) -> str:
    """
    Given all the objects that constitute a spec, combine them into a single pyfile.
    """
    new_type_definitions = (
        '\n\n'.join(
            [
                f"class {key}({value}):\n    pass\n"
                for key, value in spec_object.custom_types.items()
            ]
        )
    )
    for k in list(spec_object.functions):
        if "ceillog2" in k:
            del spec_object.functions[k]
    functions_spec = '\n\n'.join(spec_object.functions.values())
    for k in list(spec_object.constants.keys()):
        if k == "BLS12_381_Q":
            spec_object.constants[k] += "  # noqa: E501"
    constants_spec = '\n'.join(map(lambda x: '%s = %s' % (x, spec_object.constants[x]), spec_object.constants))
    ordered_class_objects_spec = '\n\n'.join(ordered_class_objects.values())
    spec = (
            imports
            + '\n\n' + f"fork = \'{fork}\'\n"
            + '\n\n' + new_type_definitions
            + '\n' + SUNDRY_CONSTANTS_FUNCTIONS
            + '\n\n' + constants_spec
            + '\n\n' + CONFIG_LOADER
            + '\n\n' + ordered_class_objects_spec
            + '\n\n' + functions_spec
            + '\n' + PHASE0_SUNDRY_FUNCTIONS
    )
    if fork == 'phase1':
        spec += '\n' + PHASE1_SUNDRY_FUNCTIONS
    spec += '\n'
    return spec


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
    'Bytes1', 'Bytes4', 'Bytes32', 'Bytes48', 'Bytes96', 'Bitlist', 'Bitvector',
    'uint8', 'uint16', 'uint32', 'uint64', 'uint128', 'uint256',
    'bytes', 'byte', 'ByteList', 'ByteVector',
    'Dict', 'dict', 'field',
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
    functions0, custom_types0, constants0, ssz_objects0, dataclasses0 = spec0
    functions1, custom_types1, constants1, ssz_objects1, dataclasses1 = spec1
    functions = combine_functions(functions0, functions1)
    custom_types = combine_constants(custom_types0, custom_types1)
    constants = combine_constants(constants0, constants1)
    ssz_objects = combine_ssz_objects(ssz_objects0, ssz_objects1, custom_types)
    dataclasses = combine_functions(dataclasses0, dataclasses1)
    return SpecObject(functions, custom_types, constants, ssz_objects, dataclasses)


fork_imports = {
    'phase0': PHASE0_IMPORTS,
    'phase1': PHASE1_IMPORTS,
    'lightclient_patch': LIGHTCLIENT_IMPORT,
}


def build_spec(fork: str, source_files: List[str]) -> str:
    all_specs = [get_spec(spec) for spec in source_files]

    spec_object = all_specs[0]
    for value in all_specs[1:]:
        spec_object = combine_spec_objects(spec_object, value)

    class_objects = {**spec_object.ssz_objects, **spec_object.dataclasses}
    dependency_order_class_objects(class_objects, spec_object.custom_types)

    return objects_to_spec(spec_object, fork_imports[fork], fork, class_objects)


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
        self.spec_fork = 'phase0'
        self.md_doc_paths = ''
        self.out_dir = 'pyspec_output'

    def finalize_options(self):
        """Post-process options."""
        if len(self.md_doc_paths) == 0:
            print("no paths were specified, using default markdown file paths for pyspec"
                  " build (spec fork: %s)" % self.spec_fork)
            if self.spec_fork == "phase0":
                self.md_doc_paths = """
                    specs/phase0/beacon-chain.md
                    specs/phase0/fork-choice.md
                    specs/phase0/validator.md
                    specs/phase0/weak-subjectivity.md
                """
            elif self.spec_fork == "phase1":
                self.md_doc_paths = """
                    specs/phase0/beacon-chain.md
                    specs/phase0/fork-choice.md
                    specs/phase0/validator.md
                    specs/phase0/weak-subjectivity.md
                    specs/phase1/custody-game.md
                    specs/phase1/beacon-chain.md
                    specs/phase1/shard-transition.md
                    specs/phase1/fork-choice.md
                    specs/phase1/phase1-fork.md
                    specs/phase1/shard-fork-choice.md
                    specs/phase1/validator.md
                """
            elif self.spec_fork == "lightclient_patch":
                self.md_doc_paths = """
                    specs/phase0/beacon-chain.md
                    specs/phase0/fork-choice.md
                    specs/phase0/validator.md
                    specs/phase0/weak-subjectivity.md
                    specs/lightclient/beacon-chain.md
                    specs/lightclient/lightclient-fork.md
                """
                # TODO: add specs/lightclient/sync-protocol.md back when the GeneralizedIndex helpers are included.
            else:
                raise Exception('no markdown files specified, and spec fork "%s" is unknown', self.spec_fork)

        self.parsed_md_doc_paths = self.md_doc_paths.split()

        for filename in self.parsed_md_doc_paths:
            if not os.path.exists(filename):
                raise Exception('Pyspec markdown input file "%s" does not exist.' % filename)

    def run(self):
        spec_str = build_spec(self.spec_fork, self.parsed_md_doc_paths)
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
        for spec_fork in fork_imports:
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
        for spec_fork in fork_imports:
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
    },
    install_requires=[
        "eth-utils>=1.3.0,<2",
        "eth-typing>=2.1.0,<3.0.0",
        "pycryptodome==3.9.4",
        "py_ecc==5.1.0",
        "milagro_bls_binding==1.6.3",
        "dataclasses==0.6",
        "remerkleable==0.1.18",
        "ruamel.yaml==0.16.5",
        "lru-dict==1.1.6"
    ]
)
