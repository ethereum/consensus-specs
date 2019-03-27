import sys


def get_lines(file_name):
    code_lines = []
    pulling_from = None
    current_name = None
    processing_typedef = False
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
                if processing_typedef:
                    assert code_lines[-1] == '}'
                    code_lines[-1] = '})'
                pulling_from = None
                processing_typedef = False
        else:
            if pulling_from == linenum and line == '{':
                code_lines.append('%s = SSZType({' % current_name)
                processing_typedef = True
            elif pulling_from is not None:
                # Add some whitespace between functions
                if line[:3] == 'def':
                    code_lines.append("")
                    code_lines.append("")
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
                        code_lines.append(row[0] + ' = ' + (row[1].replace('**TBD**', '0x1234567890123567890123456789012357890')))
    return code_lines
