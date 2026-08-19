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
# 'dist' excluded: translatable strings must come from SOURCE only, never
# compiled/minified output - build tools rename identifiers (a local __()
# wrapper becomes some minifier-assigned short name), which produces both
# false negatives (real calls no longer match the __(/_e( pattern) and false
# positives (an unrelated minified function that happens to be named _e/__
# gets flagged as an unextractable i18n call).
SKIP_DIRS_DEFAULT = {'node_modules', 'vendor', '.git', '__pycache__', '.github', '.svn', 'dist'}

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


def detect_unextractable_js(filepath, line_offsets, content):
    """
    Find JS/JSX __() / _e() calls with fewer than 2 args (no textdomain literal).
    These are INVISIBLE to extract_js() above and silently drop out of POT/PO/JSON
    with no error anywhere in the pipeline - this exact pattern caused 517 Pro
    strings (296 unique) to go untranslatable in Aug 2026, because a local i18n
    wrapper hardcoded the domain so `__('text')` felt natural to write but the
    extractor requires the literal 2-arg form. Reported loudly instead of skipped
    silently, so a plugin's own build/lint step can catch new instances of this.
    """
    warnings = []
    one_arg_single = re.compile(r"\b(__|_e)\(\s*'(?:[^'\\]|\\.)*'\s*\)")
    one_arg_double = re.compile(r'\b(__|_e)\(\s*"(?:[^"\\]|\\.)*"\s*\)')
    # bare variable/expression arg with no literal at all, e.g. __(d), __(t.label)
    dynamic_arg = re.compile(r"\b(__|_e)\(\s*[A-Za-z_$][\w$.\[\]'\"]*\s*\)")
    for pat, kind in ((one_arg_single, 'literal'), (one_arg_double, 'literal'), (dynamic_arg, 'dynamic')):
        for m in pat.finditer(content):
            fn = m.group(1)
            line = offset_to_line(line_offsets, m.start())
            warnings.append((filepath, line, fn, kind, m.group(0)[:60]))
    return warnings


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
    unextractable = []

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
            unextractable.extend(detect_unextractable_js(filepath, line_offsets, content))

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

    if unextractable:
        print(f'\nWARNING: {len(unextractable)} JS/JSX call(s) will NEVER be extracted '
              f'(missing textdomain arg or dynamic argument):', file=sys.stderr)
        for filepath, line, fn, kind, snippet in sorted(unextractable):
            rel = os.path.relpath(filepath, root)
            reason = 'no 2nd (textdomain) arg' if kind == 'literal' else 'non-literal argument, cannot auto-extract at all'
            print(f'  {rel}:{line}  {fn}(...)  [{reason}]  {snippet}', file=sys.stderr)
        print('These strings are silently absent from every POT/PO/JSON generated below.\n', file=sys.stderr)

    print(json.dumps(all_strings, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
