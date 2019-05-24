import re
from typing import Dict, Tuple


FUNCTION_REGEX = r'^def [\w_]*'
BEGIN_INSERT_REGEX = r'# begin insert '
END_INSERT_REGEX = r'# end insert'


def get_spec(file_name: str) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str]]:
    pulling_from = None  # line number of start of latest object
    current_name = None  # most recent section title
    insert_name = None  # stores the label of the current insert object
    functions = {}
    constants = {}
    ssz_objects = {}
    inserts = {}
    function_matcher = re.compile(FUNCTION_REGEX)
    inserts_matcher = re.compile(BEGIN_INSERT_REGEX)
    for linenum, line in enumerate(open(file_name).readlines()):
        line = line.rstrip()
        if pulling_from is None and len(line) > 0 and line[0] == '#' and line[-1] == '`':
            current_name = line[line[:-1].rfind('`') + 1: -1]
        if line[:9] == '```python':
            assert pulling_from is None
            pulling_from = linenum + 1
        elif line[:3] == '```':
            pulling_from = None
        elif inserts_matcher.match(line) is not None:
            insert_name = re.search(r'@[\w]*', line).group(0)
        elif insert_name is not None:
            if re.match(END_INSERT_REGEX, line) is not None:
                insert_name = None
            else:
                inserts[insert_name] = inserts.get(insert_name, '') + line + '\n'
        else:
            # Handle function definitions
            if pulling_from is not None:
                func_match = function_matcher.match(line)
                if func_match is not None:
                    current_name = func_match.group(0)
                if function_matcher.match(current_name) is None:
                    ssz_objects[current_name] = ssz_objects.get(current_name, '') + line + '\n'
                else:
                    functions[current_name] = functions.get(current_name, '') + line + '\n'
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
    return functions, constants, ssz_objects, inserts
