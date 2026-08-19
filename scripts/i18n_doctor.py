#!/usr/bin/env python3
"""
i18n_doctor.py - Read-only audit: which strings will actually render in
English despite "the .po is complete", and why.

A WP script translation depends on a five-stage chain, and every stage can
silently drop a string with no error anywhere:

  source (__()/_e() calls)
    -> extracted (needs the literal 2-arg form; a hardcoded-domain wrapper
       makes the 1-arg form look correct while being invisible to extraction)
    -> .pot (needs `pot_manager.py update` to have actually run)
    -> .po (needs a real, non-empty msgstr)
    -> compiled JSON sidecar (needs regenerating after every .po change,
       and a JS-filter regen against an under-extracted source silently
       drops any string the extractor missed)
    -> the EXACT filename WP core resolves for the enqueued script handle
       (handle-based name checked first, md5-hashed name as fallback -
       shipping the wrong one means the sidecar that exists is never loaded)

This is exactly the audit that would have caught the Aug 2026 regression:
a sidecar regenerated with the JS filter dropped from 325 keys to 103,
silently reverting 263 already-translated Fotonic Pro strings to English,
because 517 source calls across 19 files used the 1-arg form and were
invisible to the extractor the whole time.

Usage:
  python3 i18n_doctor.py <plugin_path> <textdomain> <locale> [--handle <handle>]

  --handle <handle>  the script handle actually registered via
                      wp_set_script_translations() for this plugin's JS.
                      Skips auto-detection and checks the handle-based
                      sidecar filename directly (use when the plugin's PHP
                      enqueues via a non-literal src expression the
                      auto-detector can't resolve, or to match a plugin's
                      known convention e.g. Fotonic Pro's fotonic-pro-js).

Exit code: 0 if every source JS string has a real, loadable translation.
           1 if anything would render in English, with a full breakdown.
"""
import sys
import os
import json
import subprocess
import hashlib
import re
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_script(*args):
    return subprocess.run([sys.executable] + list(args), capture_output=True, text=True)


def po_translation_map(po_path):
    """msgid -> True/False (has a real, non-empty translation)."""
    sys.path.insert(0, SCRIPT_DIR)
    import po_manager
    if not os.path.exists(po_path):
        return {}
    content = open(po_path, encoding='utf-8').read()
    blocks = po_manager.parse_po_blocks(content)
    out = {}
    for msgid, block in blocks:
        if msgid is None:
            continue
        m = re.search(r'^msgstr\s+"((?:[^"\\]|\\.)*)"', block, re.MULTILINE)
        has_text = False
        if m:
            if m.group(1):
                has_text = True
            else:
                rest = block[m.end():]
                cont = []
                for line in rest.split('\n')[1:]:
                    lm = re.match(r'^"((?:[^"\\]|\\.)*)"$', line.strip())
                    if not lm:
                        break
                    cont.append(lm.group(1))
                has_text = bool(''.join(cont))
        out[msgid] = has_text
    return out


def resolve_sidecar_path(plugin_path, textdomain, locale, lang_dir, handle_override):
    if handle_override:
        return os.path.join(lang_dir, f'{textdomain}-{locale}-{handle_override}.json'), handle_override

    sys.path.insert(0, SCRIPT_DIR)
    import json_generator as jg
    handles = jg.find_script_handles(plugin_path, textdomain)
    if not handles:
        return None, None
    handle = handles[0]
    src_path = jg.find_script_src_path(plugin_path, handle)
    hash_input = src_path or handle
    hashed = hashlib.md5(hash_input.encode('utf-8')).hexdigest()
    return os.path.join(lang_dir, f'{textdomain}-{locale}-{hashed}.json'), handle


def main():
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    plugin_path = os.path.abspath(sys.argv[1])
    textdomain = sys.argv[2]
    locale = sys.argv[3]
    rest = sys.argv[4:]
    handle_override = rest[rest.index('--handle') + 1] if '--handle' in rest else None

    lang_dir = os.path.join(plugin_path, 'languages')
    pot_path = os.path.join(lang_dir, f'{textdomain}.pot')
    po_path = os.path.join(lang_dir, f'{textdomain}-{locale}.po')

    problems = []

    # 1. Extract from source (also surfaces unextractable 1-arg/dynamic calls on stderr)
    r = run_script(os.path.join(SCRIPT_DIR, 'extract_strings.py'), plugin_path, textdomain)
    if r.returncode != 0:
        print('extract_strings.py failed:\n' + r.stderr, file=sys.stderr)
        sys.exit(2)
    if r.stderr.strip():
        print(r.stderr, file=sys.stderr)
    extracted = json.loads(r.stdout)
    js_msgids = {e['msgid'] for e in extracted if e['type'] == 'js'}

    # 2. Diff against POT
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(extracted, f)
        extracted_tmp = f.name
    try:
        r = run_script(os.path.join(SCRIPT_DIR, 'pot_manager.py'), 'diff', extracted_tmp, pot_path)
        diff = json.loads(r.stdout) if r.returncode == 0 else {'new_entries': []}
    finally:
        os.unlink(extracted_tmp)
    not_in_pot = {e['msgid'] for e in diff.get('new_entries', [])} & js_msgids
    for m in sorted(not_in_pot):
        problems.append(('NOT_IN_POT', m, 'source string was never added to the .pot template'))

    # 3. Check PO translations
    po_map = po_translation_map(po_path)
    for m in sorted(js_msgids):
        if m not in po_map:
            problems.append(('NOT_IN_PO', m, 'in POT but never added to the .po file'))
        elif not po_map[m]:
            problems.append(('EMPTY_MSGSTR', m, 'in .po but translation is empty'))

    # 4. Resolve the sidecar WP will actually load, and check its contents
    sidecar_path, handle = resolve_sidecar_path(plugin_path, textdomain, locale, lang_dir, handle_override)
    sidecar_keys = set()
    if sidecar_path is None:
        problems.append(('NO_HANDLE', '(n/a)', 'no wp_set_script_translations() call found for this textdomain - pass --handle if the enqueue uses a non-literal src'))
    elif os.path.exists(sidecar_path):
        data = json.load(open(sidecar_path, encoding='utf-8'))
        sidecar_keys = set(data.get('locale_data', {}).get('messages', {}).keys())
    else:
        problems.append(('NO_SIDECAR', sidecar_path, 'expected sidecar file does not exist - run the pipeline'))

    for m in sorted(js_msgids):
        if po_map.get(m) and m not in sidecar_keys:
            problems.append(('NOT_IN_SIDECAR', m, 'translated in .po but missing from the compiled sidecar the browser actually loads - regenerate it'))

    # Report
    if not problems:
        print(f'OK - {len(js_msgids)} JS strings, all translated and present in the sidecar WP will load.')
        if sidecar_path:
            print(f'Sidecar: {sidecar_path} ({len(sidecar_keys)} keys, handle={handle})')
        return 0

    by_kind = {}
    for kind, msgid, reason in problems:
        by_kind.setdefault(kind, []).append((msgid, reason))

    print(f'\n{len(problems)} problem(s) - these will render in English on a {locale} site:\n', file=sys.stderr)
    for kind, items in by_kind.items():
        print(f'--- {kind} ({len(items)}) ---', file=sys.stderr)
        for msgid, reason in items[:25]:
            print(f'  {msgid[:90]!r}  [{reason}]', file=sys.stderr)
        if len(items) > 25:
            print(f'  ... and {len(items) - 25} more', file=sys.stderr)
        print(file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
