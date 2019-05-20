import sys
import re
from typing import List
from collections import defaultdict


FUNCTION_REGEX = r'^def [\w_]*'


def get_spec(file_name: str):
    code_lines = []
    pulling_from = None # line number of start of latest object
    current_name = None # most recent section title
    functions = defaultdict(str)
    constants = {}
    ssz_objects = defaultdict(str)
    function_matcher = re.compile(FUNCTION_REGEX)
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
            # Handle function definitions
            if pulling_from is not None:
                match = function_matcher.match(line)
                if match is not None:
                    current_name = match.group(0)
                if function_matcher.match(current_name) is None:
                    ssz_objects[current_name] += line + '\n'
                else:
                    functions[current_name] += line + '\n'
            # Handle constant table entries
            elif pulling_from is None and len(line) > 0 and line[0] == '|':
                row = line[1:].split('|')
                if len(row) >= 2:
                    for i in range(2):
                        row[i] = row[i].strip().strip('`')
                        if '`' in row[i]:
                            row[i] = row[i][:row[i].find('`')]
                    eligible = True
                    if row[0][0] not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_':
                        eligible = False
                    for c in row[0]:
                        if c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789':
                            eligible = False
                    if eligible:
                        constants[row[0]] = row[1].replace('**TBD**', '0x1234567890123456789012345678901234567890')
    return functions, constants, ssz_objects
