import re
from function_puller import (
    get_spec,
    SpecObject,
)
from argparse import ArgumentParser
from typing import (
    Dict,
    Optional,
)

CONFIG_LOADER = '''
apply_constants_preset(globals())
'''

PHASE0_IMPORTS = '''from eth2spec.config.apply_config import apply_constants_preset
from typing import (
    Any, Callable, Dict, Set, Sequence, Tuple, Optional, TypeVar
)

from dataclasses import (
    dataclass,
    field,
)

from eth2spec.utils.ssz.ssz_impl import hash_tree_root
from eth2spec.utils.ssz.ssz_typing import (
    boolean, Container, List, Vector, uint64, SSZType,
    Bytes1, Bytes4, Bytes8, Bytes32, Bytes48, Bytes96, Bitlist, Bitvector,
)
from eth2spec.utils import bls

from eth2spec.utils.hash_function import hash

SSZObject = TypeVar('SSZObject', bound=SSZType)
'''
PHASE1_IMPORTS = '''from eth2spec.phase0 import spec as phase0
from eth2spec.config.apply_config import apply_constants_preset
from typing import (
    Any, Callable, Dict, Set, Sequence, NewType, Tuple, TypeVar
)

from dataclasses import (
    dataclass,
    field,
)

from eth2spec.utils.ssz.ssz_impl import hash_tree_root
from eth2spec.utils.ssz.ssz_typing import (
    SSZType, Container, List, Vector, ByteList, ByteVector, Bitlist, Bitvector,
    Bytes1, Bytes4, Bytes8, Bytes32, Bytes48, Bytes96,
    uint64, uint8, bit, boolean,
)
from eth2spec.utils import bls

from eth2spec.utils.hash_function import hash


SSZVariableName = str
GeneralizedIndex = NewType('GeneralizedIndex', int)
SSZObject = TypeVar('SSZObject', bound=SSZType)
'''
SUNDRY_CONSTANTS_FUNCTIONS = '''
def ceillog2(x: uint64) -> int:
    return (x - 1).bit_length()
'''
SUNDRY_FUNCTIONS = '''
# Monkey patch hash cache
_hash = hash
hash_cache: Dict[bytes, Bytes32] = {}


def get_eth1_data(distance: uint64) -> Bytes32:
    return hash(distance)


def hash(x: bytes) -> Bytes32:  # type: ignore
    if x not in hash_cache:
        hash_cache[x] = Bytes32(_hash(x))
    return hash_cache[x]


# Monkey patch validator compute committee code
_compute_committee = compute_committee
committee_cache: Dict[Tuple[Bytes32, Bytes32, int, int], Sequence[ValidatorIndex]] = {}


def compute_committee(indices: Sequence[ValidatorIndex],  # type: ignore
                      seed: Bytes32,
                      index: int,
                      count: int) -> Sequence[ValidatorIndex]:
    param_hash = (hash(b''.join(index.to_bytes(length=4, byteorder='little') for index in indices)), seed, index, count)

    if param_hash not in committee_cache:
        committee_cache[param_hash] = _compute_committee(indices, seed, index, count)
    return committee_cache[param_hash]'''


def objects_to_spec(functions: Dict[str, str],
                    custom_types: Dict[str, str],
                    constants: Dict[str, str],
                    ssz_objects: Dict[str, str],
                    imports: Dict[str, str],
                    version: str,
                    ) -> str:
    """
    Given all the objects that constitute a spec, combine them into a single pyfile.
    """
    new_type_definitions = (
        '\n\n'.join(
            [
                f"class {key}({value}):\n    pass\n"
                for key, value in custom_types.items()
            ]
        )
    )
    for k in list(functions):
        if "ceillog2" in k:
            del functions[k]
    functions_spec = '\n\n'.join(functions.values())
    for k in list(constants.keys()):
        if k == "BLS12_381_Q":
            constants[k] += "  # noqa: E501"
    constants_spec = '\n'.join(map(lambda x: '%s = %s' % (x, constants[x]), constants))
    ssz_objects_instantiation_spec = '\n\n'.join(ssz_objects.values())
    spec = (
        imports
        + '\n\n' + f"version = \'{version}\'\n"
        + '\n\n' + new_type_definitions
        + '\n' + SUNDRY_CONSTANTS_FUNCTIONS
        + '\n\n' + constants_spec
        + '\n\n' + CONFIG_LOADER
        + '\n\n' + ssz_objects_instantiation_spec
        + '\n\n' + functions_spec
        + '\n' + SUNDRY_FUNCTIONS
        + '\n'
    )
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
    'bytes', 'byte', 'ByteList', 'ByteVector'
]


def dependency_order_ssz_objects(objects: Dict[str, str], custom_types: Dict[str, str]) -> None:
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
    functions0, custom_types0, constants0, ssz_objects0 = spec0
    functions1, custom_types1, constants1, ssz_objects1 = spec1
    functions = combine_functions(functions0, functions1)
    custom_types = combine_constants(custom_types0, custom_types1)
    constants = combine_constants(constants0, constants1)
    ssz_objects = combine_ssz_objects(ssz_objects0, ssz_objects1, custom_types)
    return functions, custom_types, constants, ssz_objects


def dependency_order_spec(objs: SpecObject):
    functions, custom_types, constants, ssz_objects = objs
    dependency_order_ssz_objects(ssz_objects, custom_types)


def build_phase0_spec(phase0_sourcefile: str, fork_choice_sourcefile: str,
                      v_guide_sourcefile: str, outfile: str=None) -> Optional[str]:
    phase0_spec = get_spec(phase0_sourcefile)
    fork_choice_spec = get_spec(fork_choice_sourcefile)
    v_guide = get_spec(v_guide_sourcefile)
    spec_objects = phase0_spec
    for value in [fork_choice_spec, v_guide]:
        spec_objects = combine_spec_objects(spec_objects, value)
    dependency_order_spec(spec_objects)
    spec = objects_to_spec(*spec_objects, PHASE0_IMPORTS, 'phase0')
    if outfile is not None:
        with open(outfile, 'w') as out:
            out.write(spec)
    return spec


def build_phase1_spec(phase0_beacon_sourcefile: str,
                      phase0_fork_choice_sourcefile: str,
                      phase1_custody_sourcefile: str,
                      phase1_beacon_sourcefile: str,
                      phase1_fraud_sourcefile: str,
                      phase1_fork_sourcefile: str,
                      outfile: str=None) -> Optional[str]:
    all_sourcefiles = (
        phase0_beacon_sourcefile,
        phase0_fork_choice_sourcefile,
        phase1_custody_sourcefile,
        phase1_beacon_sourcefile,
        phase1_fraud_sourcefile,
        phase1_fork_sourcefile,
    )
    all_spescs = [get_spec(spec) for spec in all_sourcefiles]
    spec_objects = all_spescs[0]
    for value in all_spescs[1:]:
        spec_objects = combine_spec_objects(spec_objects, value)
    dependency_order_spec(spec_objects)
    spec = objects_to_spec(*spec_objects, PHASE1_IMPORTS, 'phase1')
    if outfile is not None:
        with open(outfile, 'w') as out:
            out.write(spec)
    return spec


if __name__ == '__main__':
    description = '''
Build the specs from the md docs.
If building phase 0:
    1st argument is input phase0/beacon-chain.md
    2nd argument is input phase0/fork-choice.md
    3rd argument is input phase0/validator.md
    4th argument is output spec.py

If building phase 1:
    1st argument is input phase0/beacon-chain.md
    2nd argument is input phase0/fork-choice.md
    3rd argument is input phase1/custody-game.md
    4th argument is input phase1/beacon-chain.md
    5th argument is input phase1/fraud-proofs.md
    6th argument is input phase1/phase1-fork.md
    7th argument is output spec.py
'''
    parser = ArgumentParser(description=description)
    parser.add_argument("-p", "--phase", dest="phase", type=int, default=0, help="Build for phase #")
    parser.add_argument(dest="files", help="Input and output files", nargs="+")

    args = parser.parse_args()
    if args.phase == 0:
        if len(args.files) == 4:
            build_phase0_spec(*args.files)
        else:
            print(" Phase 0 requires spec, forkchoice, and v-guide inputs as well as an output file.")
    elif args.phase == 1:
        if len(args.files) == 7:
            build_phase1_spec(*args.files)
        else:
            print(
                " Phase 1 requires input files as well as an output file:\n"
                "\t phase0: (beacon-chain.md, fork-choice.md)\n"
                "\t phase1: (custody-game.md, beacon-chain.md, fraud-proofs.md, phase1-fork.md)\n"
                "\t and output.py"
            )
    else:
        print("Invalid phase: {0}".format(args.phase))
