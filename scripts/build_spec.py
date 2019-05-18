import sys
import re
import function_puller
from argparse import ArgumentParser
from typing import Tuple, List


IMPORTS = '''from typing import (
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
NEW_TYPE_DEFINITIONS = '''
Slot = NewType('Slot', int)  # uint64
Epoch = NewType('Epoch', int)  # uint64
Shard = NewType('Shard', int)  # uint64
ValidatorIndex = NewType('ValidatorIndex', int)  # uint64
Gwei = NewType('Gwei', int)  # uint64
Bytes32 = NewType('Bytes32', bytes)  # bytes32
BLSPubkey = NewType('BLSPubkey', bytes)  # bytes48
BLSSignature = NewType('BLSSignature', bytes)  # bytes96
Store = None
'''
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

def split_and_label(regex_pattern: str, text: str) -> List[str]:
    '''
    Splits a string based on regex, but down not remove the matched text.
    It subsequently labels the matches with their match
    '''
    find_pattern = r'''%s.*?(?=%s|$)''' % (regex_pattern, regex_pattern)
    matches = re.findall(find_pattern, text, re.DOTALL)
    return list(map(lambda x: [re.match(regex_pattern, x).group(0), x], matches))


def inserter(oldfile: str, newfile: str) -> Tuple[str, str]:
    '''
    Searches for occurrences of @LabelName in oldfile and replaces them with instances of code wraped as follows:
    # begin insert @LabelName
    def foo(bar):
        return bar
    # end insert @LabelName
    '''
    new_insert_objects = re.split(r"(# begin insert |# end insert @[\w\d_]*\n)", newfile)
    # Retrieve label from insert objects
    def get_labeled_object(labeled_text):
        label = re.match(r"@[\w\d_]*\n", labeled_text)
        if label is not None:
            label = label.group(0)
            labeled_text = re.sub(label, '', labeled_text)
        return {'label': label, 'text': labeled_text}
    new_insert_objects = map(get_labeled_object, new_insert_objects)
    # Find and replace labels
    newfile = ""
    for item in new_insert_objects:
        if item['label'] is not None:
            oldfile, insertions = re.subn('# %s' % item['label'], item['text'], oldfile)
            if insertions == 0:
                newfile.join('# begin insert %s/n%s# end insert %s' % (item['label'], item['text'], item['label']))
        elif re.match(r"(# begin insert |# end insert )", item['text']) is None:
            newfile += item['text']
    return oldfile, newfile


def merger(oldfile:str, newfile:str) -> str:
    '''
    Seeks out functions and objects in new and old files.
    Replaces old objects with new ones if they exist.
    '''
    object_regex = r'''(?:\n[@\w]+[\s\w]*[='" "\.\w]*)|(?:\s{4}global_vars\["\w+"\])'''
    ssz_object_regex = r'''(?:\w+|\s{4}global_vars\["\w+"\]) = SSZType\(\{\n'''
    old_objects = split_and_label(object_regex, oldfile)
    new_objects = split_and_label(object_regex, newfile)
    for new_item in new_objects:
        found_old = False
        for index, old_item in enumerate(old_objects):
            if old_item[0] == new_item[0]:
                ssz_object_match = re.match(ssz_object_regex, new_item[1])
                if ssz_object_match is not None:
                    new_item[1] = re.sub(ssz_object_regex, '', new_item[1])
                    old_item[1] = re.sub(r'\n\w*\}\)', '', old_item[1])
                    old_item[1] += new_item[1]
                else:
                    old_item[1] = new_item[1]
                found_old = True
                old_objects[index] = old_item
                break
        if not found_old:
            old_objects.append(new_item)
    return ''.join(elem for elem in map(lambda x: x[1], old_objects))


def objects_to_spec(functions, constants, ssz_objects):
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
        IMPORTS
        + '\n' + NEW_TYPE_DEFINITIONS
        + '\n' + constants_spec
        + '\n' + ssz_objects_instantiation_spec
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

def combine_ssz_objects(old_objects, new_objects):
    remove_encasing = lambda x: x[1:-1]
    old_objects = map(remove_encasing, old_objects)
    new_objects = map(remove_encasing, new_objects)
    for key, value in new_objects.items():
        old_objects[key] += value
    reapply_encasing = lambda x: '{%s}' %x
    return map(reapply_encasing, old_objects) 


def build_phase0_spec(sourcefile, outfile=None):
    functions, constants, ssz_objects = function_puller.get_spec(sourcefile)
    spec = objects_to_spec(functions, constants, ssz_objects)
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
    ssz_objects = combine_functions(phase0_ssz_objects, phase1_ssz_objects)
    spec = objects_to_spec(functions, constants, ssz_objects)
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
