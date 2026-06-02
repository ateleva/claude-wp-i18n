#!/usr/bin/env python3
"""
pot_manager.py - Generate, diff, and update WordPress .pot files.

Commands:
  diff   <extracted.json> <file.pot>   → print JSON: {existing, new, total}
  update <file.pot> <extracted.json>   → update (or create) .pot with new entries
  create <file.pot> <extracted.json> <slug> <textdomain>  → create fresh .pot
"""
import sys
import os
import json
import re
from datetime import datetime, timezone


def parse_pot(pot_path):
    """Return set of msgids already in the POT file."""
    if not os.path.exists(pot_path):
        return set()
    with open(pot_path, encoding='utf-8', errors='replace') as f:
        content = f.read()
    msgids = set()
    for m in re.finditer(r'^msgid\s+"((?:[^"\\]|\\.)*)"', content, re.MULTILINE):
        val = m.group(1)
        if val:  # skip header (empty msgid)
            msgids.add(val.replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n'))
    # Handle multi-line msgids
    for m in re.finditer(r'^msgid\s+""\s*\n((?:"[^"]*"\s*\n)+)', content, re.MULTILINE):
        parts = re.findall(r'"([^"]*)"', m.group(0))
        full = ''.join(parts)
        if full:
            msgids.add(full)
    return msgids


def escape_po(s):
    """Escape a string for use in a PO file msgid/msgstr value."""
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    s = s.replace('\n', '\\n"\n"')
    s = s.replace('\t', '\\t')
    return s


def format_entry(entry):
    """Format a single extracted string as a POT entry block."""
    lines = []
    rel_file = entry.get('file', '')
    lineno = entry.get('line', '')
    if rel_file:
        lines.append(f'#: {rel_file}:{lineno}')
    if 'plural' in entry:
        lines.append(f'msgid "{escape_po(entry["msgid"])}"')
        lines.append(f'msgid_plural "{escape_po(entry["plural"])}"')
        lines.append('msgstr[0] ""')
        lines.append('msgstr[1] ""')
    else:
        lines.append(f'msgid "{escape_po(entry["msgid"])}"')
        lines.append('msgstr ""')
    return '\n'.join(lines)


def pot_header(slug, textdomain):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M%z')
    return f"""# {slug} translation template.
# Copyright (C) {datetime.now().year}
# This file is distributed under the same license as the {slug} package.
msgid ""
msgstr ""
"Project-Id-Version: {slug}\\n"
"Report-Msgid-Bugs-To: \\n"
"POT-Creation-Date: {now}\\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\\n"
"Language-Team: LANGUAGE <LL@li.org>\\n"
"Language: \\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"X-Generator: wp-code-translate-skill\\n"
"""


def cmd_diff(extracted_path, pot_path):
    with open(extracted_path, encoding='utf-8') as f:
        extracted = json.load(f)
    existing_ids = parse_pot(pot_path)
    new_entries = [e for e in extracted if e['msgid'] not in existing_ids]
    result = {
        'total': len(extracted),
        'existing': len(extracted) - len(new_entries),
        'new': len(new_entries),
        'new_entries': new_entries,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_update(pot_path, extracted_path):
    with open(extracted_path, encoding='utf-8') as f:
        extracted = json.load(f)

    existing_ids = parse_pot(pot_path)
    new_entries = [e for e in extracted if e['msgid'] not in existing_ids]

    if not new_entries:
        print(f'POT up to date — no new strings.', file=sys.stderr)
        return

    if not os.path.exists(pot_path):
        # Create fresh header
        slug = os.path.splitext(os.path.basename(pot_path))[0]
        header = pot_header(slug, slug)
        with open(pot_path, 'w', encoding='utf-8') as f:
            f.write(header)

    with open(pot_path, 'a', encoding='utf-8') as f:
        for entry in new_entries:
            f.write('\n' + format_entry(entry) + '\n')

    print(f'Added {len(new_entries)} new string(s) to {pot_path}', file=sys.stderr)
    print(json.dumps({'added': len(new_entries), 'new_entries': new_entries}, ensure_ascii=False))


def cmd_create(pot_path, extracted_path, slug, textdomain):
    with open(extracted_path, encoding='utf-8') as f:
        extracted = json.load(f)

    header = pot_header(slug, textdomain)
    entries = '\n'.join(format_entry(e) for e in extracted)

    os.makedirs(os.path.dirname(pot_path) or '.', exist_ok=True)
    with open(pot_path, 'w', encoding='utf-8') as f:
        f.write(header)
        f.write('\n')
        f.write(entries)
        f.write('\n')

    print(f'Created {pot_path} with {len(extracted)} string(s)', file=sys.stderr)


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'diff' and len(sys.argv) >= 4:
        cmd_diff(sys.argv[2], sys.argv[3])
    elif cmd == 'update' and len(sys.argv) >= 4:
        cmd_update(sys.argv[2], sys.argv[3])
    elif cmd == 'create' and len(sys.argv) >= 6:
        cmd_create(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
