#!/usr/bin/env python3
"""
extract_strings.py - Extract translatable strings from a WordPress plugin or theme.

Usage: python3 extract_strings.py <path> <textdomain> [--skip-dirs dir1,dir2]
Output: JSON array to stdout - [{msgid, file, line, type, plural?, context?}, ...]

Handles PHP: __() _e() esc_html__() esc_attr__() esc_html_e() esc_attr_e()
             _x() _ex() esc_html_x() esc_attr_x()
             _n() _nx() _n_noop() _nx_noop()
Handles JS:  __() _n() _x() _nx() (bare and wp.i18n.* prefixed)
"""
import sys
import os
import re
import json

# Dirs that are never WP plugin/theme source code
SKIP_DIRS_DEFAULT = {'node_modules', 'vendor', '.git', '__pycache__', '.github', '.svn'}

# PHP i18n functions where textdomain is the 2nd arg: func('string', 'textdomain')
PHP_FUNCS_2ARG = r'(?:__|_e|esc_html__|esc_attr__|esc_html_e|esc_attr_e)'

# PHP i18n functions where textdomain is the 3rd arg: func('string', 'context', 'textdomain')
PHP_FUNCS_3ARG = r'(?:_x|_ex|esc_html_x|esc_attr_x)'

# PHP plural functions: _n('singular', 'plural', $count, 'textdomain')
PHP_PLURAL_FUNCS = r'(?:_n|_n_noop)'

# PHP plural+context: _nx('singular', 'plural', $count, 'context', 'textdomain')
PHP_PLURAL_CONTEXT_FUNCS = r'(?:_nx|_nx_noop)'


def build_line_map(content):
    """Build list of byte offsets for each line start."""
    offsets = []
    pos = 0
    for line in content.split('\n'):
        offsets.append(pos)
        pos += len(line) + 1
    return offsets


def offset_to_line(offsets, offset):
    lo, hi = 0, len(offsets) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if offsets[mid] <= offset:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1


def decode_php(s):
    return (s.replace("\\'", "'")
             .replace('\\"', '"')
             .replace('\\\\', '\\')
             .replace('\\n', '\n')
             .replace('\\t', '\t'))


def q_str():
    """Regex fragment: single-or-double quoted string."""
    return r"""(?P<q{n}>['"])(?P<s{n}>(?:[^'"\\]|\\.)*)(?P={n})"""


def make_q(n):
    return rf"""(?P<q{n}>['"])(?P<s{n}>(?:[^'"\\]|\\.)*)(?P=q{n})"""


def extract_php(filepath, textdomain, line_offsets, content):
    results = []
    td = re.escape(textdomain)

    # 2-arg: func('string', 'textdomain')
    pat2 = re.compile(
        PHP_FUNCS_2ARG + r'\s*\(\s*' + make_q('A') + r"""\s*,\s*['"]""" + td + r"""['"]\s*""",
        re.DOTALL
    )
    for m in pat2.finditer(content):
        msgid = decode_php(m.group('sA'))
        if msgid.strip():
            results.append({
                'msgid': msgid,
                'file': filepath,
                'line': offset_to_line(line_offsets, m.start()),
                'type': 'php',
            })

    # 3-arg: func('string', 'context', 'textdomain')
    pat3 = re.compile(
        PHP_FUNCS_3ARG + r'\s*\(\s*' + make_q('A') +
        r"""\s*,\s*""" + make_q('B') + r"""\s*,\s*['"]""" + td + r"""['"]\s*""",
        re.DOTALL
    )
    for m in pat3.finditer(content):
        msgid = decode_php(m.group('sA'))
        ctx = decode_php(m.group('sB'))
        if msgid.strip():
            results.append({
                'msgid': msgid,
                'context': ctx,
                'file': filepath,
                'line': offset_to_line(line_offsets, m.start()),
                'type': 'php',
            })

    # Plural 4-arg: _n('singular', 'plural', $count, 'textdomain')
    pat_n = re.compile(
        PHP_PLURAL_FUNCS + r'\s*\(\s*' + make_q('A') +
        r'\s*,\s*' + make_q('B') +
        r"""\s*,\s*[^,)]+,\s*['"]""" + td + r"""['"]\s*""",
        re.DOTALL
    )
    for m in pat_n.finditer(content):
        singular = decode_php(m.group('sA'))
        plural = decode_php(m.group('sB'))
        if singular.strip():
            results.append({
                'msgid': singular,
                'plural': plural,
                'file': filepath,
                'line': offset_to_line(line_offsets, m.start()),
                'type': 'php',
            })

    # Plural+context 5-arg: _nx('singular', 'plural', $count, 'context', 'textdomain')
    pat_nx = re.compile(
        PHP_PLURAL_CONTEXT_FUNCS + r'\s*\(\s*' + make_q('A') +
        r'\s*,\s*' + make_q('B') +
        r'\s*,\s*[^,)]+,\s*' + make_q('C') +
        r"""\s*,\s*['"]""" + td + r"""['"]\s*""",
        re.DOTALL
    )
    for m in pat_nx.finditer(content):
        singular = decode_php(m.group('sA'))
        plural = decode_php(m.group('sB'))
        ctx = decode_php(m.group('sC'))
        if singular.strip():
            results.append({
                'msgid': singular,
                'plural': plural,
                'context': ctx,
                'file': filepath,
                'line': offset_to_line(line_offsets, m.start()),
                'type': 'php',
            })

    return results


def decode_js(s):
    return (s.replace("\\'", "'")
             .replace('\\"', '"')
             .replace('\\\\', '\\')
             .replace('\\n', '\n')
             .replace('\\t', '\t'))


def extract_js(filepath, textdomain, line_offsets, content):
    results = []
    td = re.escape(textdomain)
    prefix = r"""(?:wp\.i18n\.)?"""

    # __('string', 'textdomain')
    pat1 = re.compile(
        prefix + r"""__\s*\(\s*""" + make_q('A') + r"""\s*,\s*['"]""" + td + r"""['"]\s*""",
        re.DOTALL
    )
    for m in pat1.finditer(content):
        msgid = decode_js(m.group('sA'))
        if msgid.strip():
            results.append({
                'msgid': msgid,
                'file': filepath,
                'line': offset_to_line(line_offsets, m.start()),
                'type': 'js',
            })

    # _x('string', 'context', 'textdomain')
    pat_x = re.compile(
        prefix + r"""_x\s*\(\s*""" + make_q('A') +
        r"""\s*,\s*""" + make_q('B') +
        r"""\s*,\s*['"]""" + td + r"""['"]\s*""",
        re.DOTALL
    )
    for m in pat_x.finditer(content):
        msgid = decode_js(m.group('sA'))
        ctx = decode_js(m.group('sB'))
        if msgid.strip():
            results.append({
                'msgid': msgid,
                'context': ctx,
                'file': filepath,
                'line': offset_to_line(line_offsets, m.start()),
                'type': 'js',
            })

    # _n('singular', 'plural', count, 'textdomain')
    pat_n = re.compile(
        prefix + r"""_n\s*\(\s*""" + make_q('A') +
        r"""\s*,\s*""" + make_q('B') +
        r"""\s*,\s*[^,)]+,\s*['"]""" + td + r"""['"]\s*""",
        re.DOTALL
    )
    for m in pat_n.finditer(content):
        singular = decode_js(m.group('sA'))
        plural = decode_js(m.group('sB'))
        if singular.strip():
            results.append({
                'msgid': singular,
                'plural': plural,
                'file': filepath,
                'line': offset_to_line(line_offsets, m.start()),
                'type': 'js',
            })

    # _nx('singular', 'plural', count, 'context', 'textdomain')
    pat_nx = re.compile(
        prefix + r"""_nx\s*\(\s*""" + make_q('A') +
        r"""\s*,\s*""" + make_q('B') +
        r"""\s*,\s*[^,)]+,\s*""" + make_q('C') +
        r"""\s*,\s*['"]""" + td + r"""['"]\s*""",
        re.DOTALL
    )
    for m in pat_nx.finditer(content):
        singular = decode_js(m.group('sA'))
        plural = decode_js(m.group('sB'))
        ctx = decode_js(m.group('sC'))
        if singular.strip():
            results.append({
                'msgid': singular,
                'plural': plural,
                'context': ctx,
                'file': filepath,
                'line': offset_to_line(line_offsets, m.start()),
                'type': 'js',
            })

    return results


def walk_files(root, skip_dirs):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext == '.php':
                yield 'php', os.path.join(dirpath, fname)
            elif ext in ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'):
                yield 'js', os.path.join(dirpath, fname)


def main():
    if len(sys.argv) < 3:
        print('Usage: extract_strings.py <path> <textdomain> [--skip-dirs dir1,dir2]', file=sys.stderr)
        sys.exit(1)

    root = sys.argv[1]
    textdomain = sys.argv[2]

    skip_dirs = set(SKIP_DIRS_DEFAULT)
    for i, arg in enumerate(sys.argv[3:], 3):
        if arg == '--skip-dirs' and i + 1 < len(sys.argv):
            skip_dirs |= set(sys.argv[i + 1].split(','))

    if not os.path.isdir(root):
        print(f'Error: {root} is not a directory', file=sys.stderr)
        sys.exit(1)

    all_strings = []
    # Key: (msgid, plural_or_empty, context_or_empty) → index in all_strings
    seen = {}
    # Track all types (php/js) per key so strings used in both are marked for JSON sidecar
    seen_types = {}

    for ftype, filepath in walk_files(root, skip_dirs):
        try:
            with open(filepath, encoding='utf-8', errors='replace') as f:
                content = f.read()
        except OSError:
            continue

        line_offsets = build_line_map(content)

        if ftype == 'php':
            entries = extract_php(filepath, textdomain, line_offsets, content)
        else:
            entries = extract_js(filepath, textdomain, line_offsets, content)

        for entry in entries:
            key = (entry['msgid'], entry.get('plural', ''), entry.get('context', ''))
            if key not in seen:
                seen[key] = len(all_strings)
                seen_types[key] = {ftype}
                all_strings.append(entry)
            else:
                # String already seen - accumulate its type so PHP+JS strings get both
                seen_types[key].add(ftype)

    # Write accumulated types back; 'types' is a sorted list e.g. ['js','php'] or ['js']
    for key, idx in seen.items():
        all_strings[idx]['types'] = sorted(seen_types[key])
        # Keep legacy 'type' field as primary (prefer 'js' when both present for JSON filter)
        all_strings[idx]['type'] = 'js' if 'js' in seen_types[key] else 'php'

    # Make paths relative to root
    for entry in all_strings:
        try:
            entry['file'] = os.path.relpath(entry['file'], root)
        except ValueError:
            pass

    print(json.dumps(all_strings, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
