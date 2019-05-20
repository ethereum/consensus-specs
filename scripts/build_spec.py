import sys
import re
import function_puller
from argparse import ArgumentParser
from typing import Tuple, List


PHASE0_IMPORTS = '''from typing import (
    Any,
    Dict,
    List,
    NewType,
    Tuple,
)

from eth2spec.utils.minimal_ssz import (
    SSZType,
    hash_tree_root,
    signing_root,
)

from eth2spec.utils.bls_stub import (
    bls_aggregate_pubkeys,
    bls_verify,
    bls_verify_multiple,
)

from eth2spec.utils.hash_function import hash
'''
PHASE1_IMPORTS = '''from typing import (
    Any,
    Dict,
    List,
    NewType,
    Tuple,
)

from eth2spec.utils.minimal_ssz import (
    SSZType,
    hash_tree_root,
    signing_root,
    type_of,
    empty,
)

from eth2spec.utils.bls_stub import (
    bls_aggregate_pubkeys,
    bls_verify,
    bls_verify_multiple,
)

from eth2spec.utils.hash_function import hash
import math
'''
NEW_TYPES = {
    'Slot': 'int',
    'Epoch': 'int',
    'Shard': 'int',
    'ValidatorIndex': 'int',
    'Gwei': 'int',
    'Bytes32': 'bytes',
    'BLSPubkey': 'bytes',
    'BLSSignature': 'bytes',
    'Store': 'None',
    'Hash': 'bytes'
}
SUNDRY_FUNCTIONS = '''
# Monkey patch validator compute committee code
_compute_committee = compute_committee
committee_cache = {}


def compute_committee(indices: List[ValidatorIndex], seed: Bytes32, index: int, count: int) -> List[ValidatorIndex]:
    param_hash = (hash_tree_root(indices), seed, index, count)

    if param_hash in committee_cache:
        return committee_cache[param_hash]
    else:
        ret = _compute_committee(indices, seed, index, count)
        committee_cache[param_hash] = ret
        return ret


# Monkey patch hash cache
_hash = hash
hash_cache = {}


def hash(x):
    if x in hash_cache:
        return hash_cache[x]
    else:
        ret = _hash(x)
        hash_cache[x] = ret
        return ret


# Access to overwrite spec constants based on configuration
def apply_constants_preset(preset: Dict[str, Any]):
    global_vars = globals()
    for k, v in preset.items():
        global_vars[k] = v

    # Deal with derived constants
    global_vars['GENESIS_EPOCH'] = slot_to_epoch(GENESIS_SLOT)

    # Initialize SSZ types again, to account for changed lengths
    init_SSZ_types()
'''


def objects_to_spec(functions, constants, ssz_objects, imports):
    new_type_definitions = '\n'.join(['''%s = NewType('%s', %s)''' % (key, key, value) for key, value in NEW_TYPES.items()])
    functions_spec = '\n\n'.join(functions.values())
    constants_spec = '\n'.join(map(lambda x: '%s = %s' % (x, constants[x]),constants))
    ssz_objects_instantiation_spec = '\n'.join(map(lambda x: '%s = SSZType(%s)' % (x, ssz_objects[x][:-1]), ssz_objects))
    ssz_objects_reinitialization_spec = '\n'.join(
        map(lambda x: '    global_vars[%s] = SSZType(%s    })' % (x, re.sub('( ){4}', ' '*8, ssz_objects[x][:-2])), ssz_objects))
    ssz_objects_reinitialization_spec = (
        'def init_SSZ_types():\n    global_vars = globals()\n' 
        + ssz_objects_reinitialization_spec
    )
    return (
        imports
        + '\n' + new_type_definitions
        + '\n\n' + constants_spec
        + '\n\n' + ssz_objects_instantiation_spec
        + '\n\n\n' + functions_spec
        + '\n' + SUNDRY_FUNCTIONS
        + '\n\n' + ssz_objects_reinitialization_spec
        + '\n'
    )

def combine_functions(old_funcitons, new_functions):
    for key, value in new_functions.items():
        old_funcitons[key] = value
    # TODO: Add insert functionality
    return old_funcitons


def combine_constants(old_constants, new_constants):
    for key, value in new_constants.items():
        old_constants[key] = value
    return old_constants


def dependency_order_ssz_objects(objects):
    items = list(objects.items())
    for key, value in items:
        dependencies = re.findall(r'(: [\[]*[A-Z][a-z][\w]+)', value)
        dependencies = map(lambda x: re.sub(r'\W', '', x), dependencies)
        for dep in dependencies:
            if dep in NEW_TYPES:
                continue
            key_list = list(objects.keys())
            for item in [dep, key] + key_list[key_list.index(dep)+1:]:
                objects[item] = objects.pop(item)


def combine_ssz_objects(old_objects, new_objects):
    for key, value in new_objects.items():
        # remove leading "{" and trailing "\n}"
        old_objects[key] = old_objects.get(key, '')[1:-3]
        # remove leading "{"
        value = value[1:]
        old_objects[key] = '{' + old_objects.get(key, '') + value
    dependency_order_ssz_objects(old_objects)
    return old_objects


def build_phase0_spec(sourcefile, outfile=None):
    functions, constants, ssz_objects = function_puller.get_spec(sourcefile)
    spec = objects_to_spec(functions, constants, ssz_objects, PHASE0_IMPORTS)
    if outfile is not None:
        with open(outfile, 'w') as out:
            out.write(spec)
    else:
        return spec


def build_phase1_spec(phase0_sourcefile, phase1_sourcefile, outfile=None):
    phase0_functions, phase0_constants, phase0_ssz_objects = function_puller.get_spec(phase0_sourcefile)
    phase1_functions, phase1_constants, phase1_ssz_objects = function_puller.get_spec(phase1_sourcefile)
    functions = combine_functions(phase0_functions, phase1_functions)
    constants = combine_constants(phase0_constants, phase1_constants)
    ssz_objects = combine_ssz_objects(phase0_ssz_objects, phase1_ssz_objects)
    spec = objects_to_spec(functions, constants, ssz_objects, PHASE1_IMPORTS)
    if outfile is not None:
        with open(outfile, 'w') as out:
            out.write(spec)
    else:
        return spec


if __name__ == '__main__':
    description = '''
Build the specs from the md docs.
If building phase 0:
    1st argument is input spec.md
    2nd argument is output spec.py

If building phase 1:
    1st argument is input spec_phase0.md
    2nd argument is input spec_phase1.md
    3rd argument is output spec.py
'''
    parser = ArgumentParser(description=description)
    parser.add_argument("-p", "--phase", dest="phase", type=int, default=0, help="Build for phase #")
    parser.add_argument(dest="files", help="Input and output files", nargs="+")

    args = parser.parse_args()
    if args.phase == 0:
        build_phase0_spec(*args.files)
    elif args.phase == 1:
        if len(args.files) == 3:
            build_phase1_spec(*args.files)
        else:
            print(" Phase 1 requires an output as well as 2 input files (phase0.md and phase1.md)")
    else:
        print("Invalid phase: {0}".format(args.phase))
