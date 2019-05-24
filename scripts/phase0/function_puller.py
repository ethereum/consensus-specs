import sys
from typing import List


def get_spec(file_name: str) -> List[str]:
    code_lines = []
    pulling_from = None
    current_name = None
    current_typedef = None
    type_defs = []
    for linenum, line in enumerate(open(sys.argv[1]).readlines()):
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
                if current_typedef is not None:
                    assert code_lines[-1] == '}'
                    code_lines[-1] = ''
                    code_lines.append('')
                pulling_from = None
                current_typedef = None
        else:
            if pulling_from == linenum and line == '{':
                code_lines.append('class %s(SSZContainer):' % current_name)
                current_typedef = current_name
                type_defs.append(current_name)
            elif pulling_from is not None:
                # Add some whitespace between functions
                if line[:3] == 'def':
                    code_lines.append('')
                    code_lines.append('')
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
    for ssz_type_name in type_defs:
        code_lines.append(f'    {ssz_type_name},\n')
    code_lines.append(']')
    code_lines.append('\n')
    code_lines.append('def get_ssz_type_by_name(name: str) -> SSZType:')
    code_lines.append('    return globals()[name]')
    code_lines.append('')
    return code_lines
