import sys
from typing import List


def get_spec(file_name: str, phase:int = 0) -> List[str]:
    code_lines = []
    pulling_from = None
    current_name = None
    current_typedef = None
    is_update_section = False
    update_section_depth = None
    type_defs = []
    for linenum, line in enumerate(open(file_name).readlines()):
        line = line.rstrip()
        if pulling_from is None and len(line) > 0 and line[0] == '#' and line[-1] == '`':
            current_name = line[line[:-1].rfind('`') + 1: -1]
        if pulling_from is None and len(line) > 0 and line[0] == '#' and line.endswith('updates'):
            is_update_section = True
            update_section_depth = max(i for i in range(10) if line.startswith('#' * i))
        elif pulling_from is None and len(line) > 0 and line[0] == '#' and is_update_section:
            section_depth = max(i for i in range(10) if line.startswith('#' * i))
            if section_depth <= update_section_depth:
                is_update_section = False
                update_section_depth = None
        if line[:9] == '```python':
            assert pulling_from is None
            pulling_from = linenum + 1
        elif line[:3] == '```':
            if pulling_from is None:
                pulling_from = linenum
            else:
                if current_typedef is not None:
                    assert code_lines[-1] == '}'
                    code_lines[-1] = '})'
                    current_typedef[-1] = '})'
                    type_defs.append((current_name, current_typedef))
                pulling_from = None
                current_typedef = None
        else:
            if pulling_from == linenum and line == '{':
                if is_update_section:
                    code_lines.append('%s = SSZTypeExtension({' % current_name)
                else:
                    code_lines.append('%s = SSZType({' % current_name)
                current_typedef = ['global_vars["%s"] = SSZType({' % current_name]
            elif pulling_from is not None:
                # Add some whitespace between functions
                if line[:3] == 'def':
                    code_lines.append('')
                    code_lines.append('')
                code_lines.append(line)
                # Remember type def lines
                if current_typedef is not None:
                    current_typedef.append(line)
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
    code_lines.append('')
    code_lines.append('def init_SSZ_types():')
    code_lines.append('    global_vars = globals()')
    for ssz_type_name, ssz_type in type_defs:
        code_lines.append('')
        for type_line in ssz_type:
            code_lines.append('    ' + type_line)
    code_lines.append('\n')
    code_lines.append('ssz_types = [' + ', '.join([f'\'{ssz_type_name}\'' for (ssz_type_name, _) in type_defs]) + ']')
    code_lines.append('\n')
    code_lines.append('def get_ssz_type_by_name(name: str) -> SSZType:')
    code_lines.append('    return globals()[name]')
    code_lines.append('')
    return code_lines
