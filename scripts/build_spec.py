import sys
import re
import function_puller
from argparse import ArgumentParser
from typing import Tuple, List


def split_retain_delimiter(regex_pattern: str, text: str) -> List[str]:
    '''
    Splits a string based on regex, but down not remove the matched text
    '''
    find_pattern = r'%s.*?(?=%s|$)' % (regex_pattern, regex_pattern)
    return re.findall(find_pattern, text, re.DOTALL)


def inserter(oldfile: str, newfile: str) -> Tuple[str, str]:
    '''
    Searches for occurrences of @LabelName in oldfile and replaces them with instances of code wraped as follows:
    # begin insert @LabelName
    def foo(bar):
        return bar
    # end insert @LabelName
    '''
    new_insert_objects = re.split(r"(# begin insert |# end insert @[a-zA-Z0-9_]*\n)", newfile)
    # Retrieve label from insert objects
    def get_labeled_object(labeled_text):
        label = re.match(r"@[a-zA-Z0-9_]*\n", labeled_text)
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
    old_objects = split_retain_delimiter('\n[a-zA-Z]', oldfile)
    new_objects = split_retain_delimiter('\n[a-zA-Z]', newfile)
    object_regex = r"\n[#@a-zA-Z_0-9]+[\sa-zA-Z_0-9]*[(){}=:'" "]*"
    old_object_tuples = list(map(lambda x: [re.match(object_regex, x).group(0),x], old_objects))
    for new_item in new_objects:
        found_old = False
        for old_item in old_object_tuples:
            if old_item[0] == re.match(object_regex, new_item).group(0):
                old_item[1] = new_item
                found_old = True
                break
        if not found_old:
            old_object_tuples += [[re.match(object_regex, new_item).group(0), new_item]]
    return ''.join(elem for elem in map(lambda x: x[1], old_object_tuples))


def build_phase0_spec(sourcefile, outfile=None):
    code_lines = []
    code_lines.append("""
from typing import (
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


# stub, will get overwritten by real var
SLOTS_PER_EPOCH = 64

Slot = NewType('Slot', int)  # uint64
Epoch = NewType('Epoch', int)  # uint64
Shard = NewType('Shard', int)  # uint64
ValidatorIndex = NewType('ValidatorIndex', int)  # uint64
Gwei = NewType('Gwei', int)  # uint64
Bytes32 = NewType('Bytes32', bytes)  # bytes32
BLSPubkey = NewType('BLSPubkey', bytes)  # bytes48
BLSSignature = NewType('BLSSignature', bytes)  # bytes96
Store = None
""")

    code_lines += function_puller.get_spec(sourcefile)

    code_lines.append("""
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

""")

    if outfile is not None:
        with open(outfile, 'w') as out:
            out.write("\n".join(code_lines))
    else:
        return "\n".join(code_lines)


def build_phase1_spec(phase0_sourcefile, phase1_sourcefile, outfile=None):
    phase0_code = build_phase0_spec(phase0_sourcefile)
    phase1_code = build_phase0_spec(phase1_sourcefile)
    phase0_code, phase1_code = inserter(phase0_code, phase1_code)
    phase1_code = merger(phase0_code, phase1_code)

    if outfile is not None:
        with open(outfile, 'w') as out:
            out.write(phase1_code)
    else:
        return phase1_code


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
