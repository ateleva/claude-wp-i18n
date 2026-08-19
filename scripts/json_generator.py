#!/usr/bin/env python3
"""
json_generator.py - Generate WP JS translation JSON sidecar file.

Usage:
  python3 json_generator.py <plugin_path> <textdomain> <locale> <po_path> [extracted_json]

  plugin_path    - root of plugin or theme
  textdomain     - text domain string
  locale         - WP locale (e.g. it_IT)
  po_path        - path to the compiled .po file
  extracted_json - optional; path to extract_strings.py output (to filter JS-only strings)

Output:
  Writes JSON file to <plugin_path>/languages/<textdomain>-<locale>-<hash>.json
  Prints the output path to stdout.

Hash formula: WordPress core uses md5(relative_script_path) where relative_script_path
is the script src relative to the plugin directory (e.g. "build/app.js").
This script detects it from wp_enqueue_script / wp_register_script calls.
If no src found, falls back to md5(handle), then to no-hash filename with a warning.
"""
import sys
import os
import re
import json
import hashlib
from datetime import datetime, timezone


PLURAL_FORMS = {
    'it_IT': 'nplurals=2; plural=(n!=1);',
    'fr_FR': 'nplurals=2; plural=(n>1);',
    'de_DE': 'nplurals=2; plural=(n!=1);',
    'es_ES': 'nplurals=2; plural=(n!=1);',
    'pt_PT': 'nplurals=2; plural=(n!=1);',
    'pt_BR': 'nplurals=2; plural=(n>1);',
    'nl_NL': 'nplurals=2; plural=(n!=1);',
    'ru_RU': 'nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);',
    'pl_PL': 'nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && (n%100<10||n%100>=20) ? 1 : 2);',
    'ja':    'nplurals=1; plural=0;',
    'zh_CN': 'nplurals=1; plural=0;',
    'zh_TW': 'nplurals=1; plural=0;',
    'ko_KR': 'nplurals=1; plural=0;',
    'tr_TR': 'nplurals=2; plural=(n>1);',
    'ar':    'nplurals=6; plural=(n==0 ? 0 : n==1 ? 1 : n==2 ? 2 : n%100>=3 && n%100<=10 ? 3 : n%100>=11 && n%100<=99 ? 4 : 5);',
    'uk':    'nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);',
}


def scan_php_files(plugin_path):
    """Yield (filepath, content) for all PHP files, skipping common junk dirs."""
    skip = {'node_modules', 'vendor', '.git', '__pycache__'}
    for dirpath, dirnames, filenames in os.walk(plugin_path):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fname in filenames:
            if not fname.endswith('.php'):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, encoding='utf-8', errors='replace') as f:
                    yield fpath, f.read()
            except OSError:
                continue


def find_script_handles(plugin_path, textdomain):
    """Scan PHP files for wp_set_script_translations() calls, return list of handles."""
    handles = []
    td_escaped = re.escape(textdomain)
    pattern = re.compile(
        r"""wp_set_script_translations\s*\(\s*['"]([^'"]+)['"]\s*,\s*['"]""" + td_escaped + r"""['"]""",
        re.IGNORECASE
    )
    for _, content in scan_php_files(plugin_path):
        for m in pattern.finditer(content):
            handle = m.group(1)
            if handle not in handles:
                handles.append(handle)
    return handles


def extract_js_path_from_expr(expr):
    """
    Given a PHP expression for a script src, extract the relative JS file path.

    Handles patterns like:
      plugin_dir_url(__FILE__) . 'build/app.js'
      plugins_url('assets/js/app.js', __FILE__)
      plugins_url('assets/js/app.js', PLUGIN_FILE)
      get_stylesheet_directory_uri() . '/js/main.js'
      get_template_directory_uri() . '/js/main.js'
      MY_PLUGIN_URL . 'js/app.js'
      $this->url . 'js/app.js'
      self::PLUGIN_URL . 'js/app.js'
      'https://example.com/wp-content/plugins/myplugin/build/app.js'  (full URL)

    Returns the path string (e.g. 'build/app.js') stripped of leading slashes, or None.
    """
    # A string literal that looks like a JS file path
    js_path_re = re.compile(r"""['"]([a-zA-Z0-9_/\-\.]+\.(?:js|jsx|mjs|cjs))['"]""")

    # plugins_url('path/file.js', ...) - first arg is the relative path
    pu_m = re.search(r"""plugins_url\s*\(\s*['"]([^'"]+\.(?:js|jsx|mjs|cjs))['"]""", expr, re.IGNORECASE)
    if pu_m:
        return pu_m.group(1).lstrip('/')

    # Any other expression: look for the last .js string literal (usually the path suffix)
    literals = js_path_re.findall(expr)
    if literals:
        # Pick the last match - in concatenations like URL_CONST . 'build/app.js'
        # the path is always the rightmost literal
        return literals[-1].lstrip('/')

    return None


def find_script_src_path(plugin_path, handle):
    """
    Find the relative script src path for a given handle.
    Scans wp_enqueue_script / wp_register_script calls in all PHP files.
    Returns the relative JS file path (e.g. 'build/app.js'), or None.

    WP core computes the JSON sidecar filename as:
      {textdomain}-{locale}-{md5(relative_src_path)}.json

    This function resolves the src expression in multiple steps:
    1. Inline literal or known function: extract path directly
    2. Variable assignment: trace $var = ... back to its definition
    3. Property/method: try to find assignment in the same file
    """
    h_escaped = re.escape(handle)
    # Capture the second argument (src) of wp_enqueue/register_script - up to the next comma
    # Allow multi-line since sometimes formatted with newlines
    enqueue_pat = re.compile(
        r"""wp_(?:enqueue|register)_script\s*\(\s*['"]""" + h_escaped +
        r"""['"]\s*,\s*((?:[^,)'"]*|'[^']*'|"[^"]*")*?)\s*,""",
        re.IGNORECASE | re.DOTALL
    )
    js_path_re = re.compile(r"""['"]([a-zA-Z0-9_/\-\.]+\.(?:js|jsx|mjs|cjs))['"]""")

    for fpath, content in scan_php_files(plugin_path):
        for m in enqueue_pat.finditer(content):
            src_expr = m.group(1).strip()

            # Case 1: expression contains a .js path directly (inline or via known functions)
            path = extract_js_path_from_expr(src_expr)
            if path:
                return path

            # Case 2: bare PHP variable $var_name - trace to its assignment in same file
            var_m = re.match(r'^\$(\w+)$', src_expr)
            if var_m:
                var_name = re.escape(var_m.group(1))
                assign_re = re.compile(r'\$' + var_name + r'\s*=\s*([^\n;]+)', re.IGNORECASE)
                for am in assign_re.finditer(content):
                    path = extract_js_path_from_expr(am.group(1))
                    if path:
                        return path

            # Case 3: property access $this->prop or self::CONST - look for assignment nearby
            prop_m = re.match(r'^\$?(?:this|self)\s*(?:->|::)\s*(\w+)', src_expr)
            if prop_m:
                prop = re.escape(prop_m.group(1))
                # Look for   $this->prop = ...   or   self::CONST = ...
                assign_re = re.compile(
                    r'(?:\$this\s*->\s*' + prop + r'|\bself\s*::\s*' + prop + r')\s*=\s*([^\n;]+)',
                    re.IGNORECASE
                )
                for am in assign_re.finditer(content):
                    path = extract_js_path_from_expr(am.group(1))
                    if path:
                        return path

    return None


def parse_po_translations(po_path):
    """
    Parse a .po file and return list of dicts:
    [{msgid, msgstr, plural?, msgstr_plural?}]
    Only entries with non-empty msgstr included.
    """
    with open(po_path, encoding='utf-8', errors='replace') as f:
        content = f.read()

    content = content.replace('\r\n', '\n').replace('\r', '\n')
    raw_blocks = re.split(r'\n{2,}', content.strip())

    entries = []
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue

        # Skip header (msgid "")
        msgid_m = re.search(r'^msgid\s+"((?:[^"\\]|\\.)*)"', block, re.MULTILINE)
        if not msgid_m:
            continue
        raw_msgid = msgid_m.group(1)
        if raw_msgid == '':
            # Check for continuation
            rest = block[msgid_m.end():]
            cont = re.findall(r'^"([^"]*)"', rest, re.MULTILINE)
            if not cont or ''.join(cont) == '':
                continue  # header block

        def decode_po_str(s):
            return s.replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n').replace('\\t', '\t')

        msgid = decode_po_str(raw_msgid)

        # Check for plural
        plural_m = re.search(r'^msgid_plural\s+"((?:[^"\\]|\\.)*)"', block, re.MULTILINE)

        if plural_m:
            plural = decode_po_str(plural_m.group(1))
            msgstr_plural = []
            for mm in re.finditer(r'^msgstr\[(\d+)\]\s+"((?:[^"\\]|\\.)*)"', block, re.MULTILINE):
                msgstr_plural.append(decode_po_str(mm.group(2)))
            if any(msgstr_plural):
                entries.append({'msgid': msgid, 'plural': plural, 'msgstr_plural': msgstr_plural})
        else:
            msgstr_m = re.search(r'^msgstr\s+"((?:[^"\\]|\\.)*)"', block, re.MULTILINE)
            if msgstr_m:
                msgstr = decode_po_str(msgstr_m.group(1))
                # Multi-line msgstr continuation
                rest = block[msgstr_m.end():]
                cont = re.findall(r'^"([^"]*)"', rest, re.MULTILINE)
                if cont:
                    msgstr = msgstr + ''.join(decode_po_str(c) for c in cont)
                if msgstr:
                    entries.append({'msgid': msgid, 'msgstr': msgstr})

    return entries


def load_js_msgids(extracted_json_path):
    """Return set of msgids that come from JS/JSX source files."""
    if not extracted_json_path or not os.path.exists(extracted_json_path):
        return None  # None means: include all strings
    with open(extracted_json_path, encoding='utf-8') as f:
        data = json.load(f)
    return {e['msgid'] for e in data if e.get('type') == 'js'}


def build_json(translations, locale, js_msgids=None):
    """Build WP locale_data JSON structure."""
    plural_forms = PLURAL_FORMS.get(locale, 'nplurals=2; plural=(n!=1);')
    lang = locale.split('_')[0] if '_' in locale else locale

    locale_data = {
        '': {
            'domain': 'messages',
            'plural-forms': plural_forms,
            'lang': lang,
        }
    }

    for entry in translations:
        msgid = entry['msgid']
        if js_msgids is not None and msgid not in js_msgids:
            continue  # Skip non-JS strings when we have the JS filter
        if 'plural' in entry:
            locale_data[msgid] = entry.get('msgstr_plural', ['', ''])
        else:
            locale_data[msgid] = [entry.get('msgstr', '')]

    return {
        'translation-revision-date': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S+00:00'),
        'generator': 'wp-code-translate-skill',
        'domain': 'messages',
        'locale_data': {
            'messages': locale_data,
        }
    }


def main():
    if len(sys.argv) < 5:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    plugin_path = sys.argv[1]
    textdomain = sys.argv[2]
    locale = sys.argv[3]
    po_path = sys.argv[4]
    extracted_json = sys.argv[5] if len(sys.argv) > 5 else None

    if not os.path.exists(po_path):
        print(f'Error: {po_path} not found', file=sys.stderr)
        sys.exit(1)

    # Detect script handles
    handles = find_script_handles(plugin_path, textdomain)

    # Parse translations from PO
    translations = parse_po_translations(po_path)

    # Load JS-only msgids filter
    js_msgids = load_js_msgids(extracted_json)

    lang_dir = os.path.join(plugin_path, 'languages')
    os.makedirs(lang_dir, exist_ok=True)

    output_paths = []

    # If no JS strings at all, skip JSON generation entirely
    if js_msgids is not None and len(js_msgids) == 0:
        print('No JS strings found - skipping JSON sidecar generation.', file=sys.stderr)
        print(json.dumps([]))
        return

    if handles:
        for handle in handles:
            src_path = find_script_src_path(plugin_path, handle)
            if src_path:
                hash_input = src_path
                print(f'Script src detected: {src_path} (handle: {handle})', file=sys.stderr)
            else:
                hash_input = handle
                print(f'WARNING: Could not detect script src for handle "{handle}", using md5(handle) as fallback.', file=sys.stderr)
                print(f'  If the JSON file is not loaded by WP, find the correct path with:', file=sys.stderr)
                print(f'  grep -r "wp_enqueue_script.*{handle}" /path/to/plugin/', file=sys.stderr)

            h = hashlib.md5(hash_input.encode('utf-8')).hexdigest()
            filename = f'{textdomain}-{locale}-{h}.json'
            out_path = os.path.join(lang_dir, filename)
            data = build_json(translations, locale, js_msgids)
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=None, separators=(',', ':'))
            output_paths.append(out_path)
            print(f'Wrote {out_path}', file=sys.stderr)
    else:
        # No wp_set_script_translations found - plugin may be PHP-only
        if js_msgids is None:
            # No extracted JSON provided; assume all strings might be JS
            print('WARNING: No wp_set_script_translations() found.', file=sys.stderr)
            print('  Skipping JSON sidecar. If this plugin loads JS translations, add', file=sys.stderr)
            print('  wp_set_script_translations() in your PHP and re-run.', file=sys.stderr)
        else:
            print('No wp_set_script_translations() calls found - no JSON sidecar written.', file=sys.stderr)
            print('  This is expected for PHP-only plugins.', file=sys.stderr)

    # Print output paths as JSON for skill to report back
    print(json.dumps(output_paths))


if __name__ == '__main__':
    main()
