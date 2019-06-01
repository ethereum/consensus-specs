from typing import List


def get_spec(file_name: str) -> List[str]:
    code_lines = []
    pulling_from = None
    current_name = None
    # list of current type definition being parsed, or None otherwise
    current_typedef = None
    # list of (name, definition lines list) tuples.
    type_defs = []
    for linenum, line in enumerate(open(file_name).readlines()):
        line = line.rstrip()
        if pulling_from is None and len(line) > 0 and line[0] == '#' and line[-1] == '`':
            current_name = line[line[:-1].rfind('`') + 1: -1]
        if line[:9] == '```python':
            assert pulling_from is None
            pulling_from = linenum + 1
        elif line[:3] == '```':
            if pulling_from is None:
                pulling_from = linenum
            else:
                pulling_from = None
                if current_typedef is not None:
                    type_defs.append((current_name, current_typedef))
                    current_typedef = None
        else:
            if pulling_from is not None:
                # Add some whitespace between functions
                if line[:3] == 'def' or line[:5] == 'class':
                    code_lines.append('')
                    code_lines.append('')
                # Check for SSZ type definitions
                if len(line) > 18 and line[:6] == 'class ' and line[-12:] == '(Container):':
                    name = line[6:-12]
                    # Check consistency with markdown header
                    assert name == current_name
                    current_typedef = []
                if current_typedef is not None:
                    current_typedef.append(line)
                code_lines.append(line)
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
                        code_lines.append(row[0] + ' = ' + (row[1].replace('**TBD**', '0x1234567890123456789012345678901234567890')))
    # Build type-def re-initialization
    code_lines.append('\n')
    code_lines.append('ssz_types = [\n')
    for (ssz_type_name, _) in type_defs:
        code_lines.append(f'    {ssz_type_name},')
    code_lines.append(']')
    code_lines.append('\n')
    code_lines.append('def init_SSZ_types():')
    code_lines.append('    global_vars = globals()')
    for ssz_type_name, ssz_type in type_defs:
        code_lines.append('')
        for type_line in ssz_type:
            if len(type_line) > 0:
                code_lines.append('    ' + type_line)
    code_lines.append('')
    for (ssz_type_name, _) in type_defs:
        code_lines.append(f'    global_vars["{ssz_type_name}"] = {ssz_type_name}')
    code_lines.append('    global_vars["ssz_types"] = [')
    for (ssz_type_name, _) in type_defs:
        code_lines.append(f'        "{ssz_type_name}",')
    code_lines.append('    ]')
    code_lines.append('\n')
    code_lines.append('def get_ssz_type_by_name(name: str) -> Container:')
    code_lines.append('    return globals()[name]')
    code_lines.append('')
    return code_lines
