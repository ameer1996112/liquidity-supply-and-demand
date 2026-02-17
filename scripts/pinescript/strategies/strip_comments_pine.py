#!/usr/bin/env python3
"""Strip // and /* */ comments from Pine Script. Preserves strings (single, double)."""
import re
import sys

def strip_comments(content: str) -> str:
    out = []
    i = 0
    n = len(content)
    in_single = False
    in_double = False
    in_block = False
    block_start = -1
    line_start = True
    strip_rest_of_line = False

    while i < n:
        if in_block:
            if content[i:i+2] == '*/':
                in_block = False
                i += 2
                continue
            i += 1
            continue

        if in_single:
            if content[i] == "'" and (i == 0 or content[i-1] != '\\'):
                in_single = False
            out.append(content[i])
            i += 1
            continue

        if in_double:
            if content[i] == '"' and (i == 0 or content[i-1] != '\\'):
                in_double = False
            out.append(content[i])
            i += 1
            continue

        if content[i:i+2] == '/*':
            in_block = True
            while len(out) and out[-1] in ' \t':
                out.pop()
            i += 2
            continue

        if content[i:i+2] == '//':
            strip_rest_of_line = True
            while len(out) and out[-1] in ' \t':
                out.pop()
            i += 2
            while i < n and content[i] != '\n':
                i += 1
            if i < n:
                out.append('\n')
                i += 1
            strip_rest_of_line = False
            continue

        if content[i] == "'" and (i == 0 or content[i-1] != '\\'):
            in_single = True
            out.append(content[i])
            i += 1
            continue

        if content[i] == '"' and (i == 0 or content[i-1] != '\\'):
            in_double = True
            out.append(content[i])
            i += 1
            continue

        out.append(content[i])
        if content[i] == '\n':
            line_start = True
        else:
            line_start = False
        i += 1

    result = ''.join(out)
    result = re.sub(r'\n{4,}', '\n\n\n', result)
    return result

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if not path:
        print("Usage: strip_comments_pine.py <file.pine>", file=sys.stderr)
        sys.exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    cleaned = strip_comments(content)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(cleaned)
    print("Done. Comments stripped.")

if __name__ == '__main__':
    main()
