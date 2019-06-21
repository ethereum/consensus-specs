import re
from typing import Dict, Tuple, NewType


FUNCTION_REGEX = r'^def [\w_]*'
BEGIN_INSERT_REGEX = r'# begin insert '
END_INSERT_REGEX = r'# end insert'

SpecObject = NewType('SpecObjects', Tuple[Dict[str, str], Dict[str, str], Dict[str, str], Dict[str, str]])


def get_spec(file_name: str) -> SpecObject:
    """
    Takes in the file name of a spec.md file, opens it and returns the following objects:
    functions = {function_name: function_code}
    constants= {constant_name: constant_code}
    ssz_objects= {object_name: object}
    inserts= {insert_tag: code to be inserted}

    Note: This function makes heavy use of the inherent ordering of dicts,
    if this is not supported by your python version, it will not work.
    """
    pulling_from = None  # line number of start of latest object
    current_name = None  # most recent section title
    insert_name = None  # stores the label of the current insert object
    functions = {}
    constants = {}
    ssz_objects = {}
    inserts = {}
    function_matcher = re.compile(FUNCTION_REGEX)
    inserts_matcher = re.compile(BEGIN_INSERT_REGEX)
    custom_types = {}
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
            # Find @insert names
            insert_name = re.search(r'@[\w]*', line).group(0)
        elif insert_name is not None:
            # In insert mode, either the next line is more code, or the end of the insert
            if re.match(END_INSERT_REGEX, line) is not None:
                insert_name = None
            else:
                inserts[insert_name] = inserts.get(insert_name, '') + line + '\n'
        else:
            # Handle function definitions & ssz_objects
            if pulling_from is not None:
                # SSZ Object
                if len(line) > 18 and line[:6] == 'class ' and line[-12:] == '(Container):':
                    name = line[6:-12]
                    # Check consistency with markdown header
                    assert name == current_name
                    is_ssz = True
                # function definition
                elif function_matcher.match(line) is not None:
                    current_name = function_matcher.match(line).group(0)
                    is_ssz = False
                if is_ssz:
                    ssz_objects[current_name] = ssz_objects.get(current_name, '') + line + '\n'
                else:
                    functions[current_name] = functions.get(current_name, '') + line + '\n'
            # Handle constant and custom types table entries
            elif pulling_from is None and len(line) > 0 and line[0] == '|':
                row = line[1:].split('|')
                if len(row) >= 2:
                    for i in range(2):
                        row[i] = row[i].strip().strip('`')
                        if '`' in row[i]:
                            row[i] = row[i][:row[i].find('`')]
                    if row[1].startswith('uint') or row[1].startswith('Bytes'):
                        custom_types[row[0]] = row[1]
                    else:
                        eligible = True
                        if row[0][0] not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_':
                            eligible = False
                        for c in row[0]:
                            if c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789':
                                eligible = False
                        if eligible:
                            constants[row[0]] = row[1].replace('**TBD**', '0x1234567890123456789012345678901234567890')
    return functions, custom_types, constants, ssz_objects, inserts
