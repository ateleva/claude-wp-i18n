#!/usr/bin/env python3
"""
po_manager.py - Create, update, and deduplicate WordPress .po files.

Commands:
  create <file.po> <locale> <textdomain> <plural_forms>
      Create a fresh .po file with proper header.

  update <file.po> <translations.json>
      Merge new msgid/msgstr pairs into existing .po; deduplicate.
      translations.json: {"source string": "translated string", ...}
      OR extended format: [{"msgid": "", "msgstr": "", "plural": "", "msgstr_plural": ["",""]}]

  dedup <file.po>
      Remove duplicate msgid entries (keep first occurrence).

  list_untranslated <file.po>
      Print JSON array of msgids with empty msgstr (need translation).
"""
import sys
import os
import json
import re
import shutil
from datetime import datetime, timezone


PLURAL_FORMS = {
    'it_IT': 'nplurals=2;plural=(n!=1);',
    'fr_FR': 'nplurals=2;plural=(n>1);',
    'de_DE': 'nplurals=2;plural=(n!=1);',
    'es_ES': 'nplurals=2;plural=(n!=1);',
    'pt_PT': 'nplurals=2;plural=(n!=1);',
    'pt_BR': 'nplurals=2;plural=(n>1);',
    'ar':    'nplurals=6;plural=(n==0?0:n==1?1:n==2?2:n%100>=3&&n%100<=10?3:n%100>=11&&n%100<=99?4:5);',
    'ja':    'nplurals=1;plural=0;',
    'zh_CN': 'nplurals=1;plural=0;',
    'zh_TW': 'nplurals=1;plural=0;',
    'nl_NL': 'nplurals=2;plural=(n!=1);',
    'ru_RU': 'nplurals=3;plural=(n%10==1&&n%100!=11?0:n%10>=2&&n%10<=4&&(n%100<10||n%100>=20)?1:2);',
    'pl_PL': 'nplurals=3;plural=(n==1?0:n%10>=2&&n%10<=4&&(n%100<10||n%100>=20)?1:2);',
    'cs_CZ': 'nplurals=3;plural=(n==1)?0:(n>=2&&n<=4)?1:2;',
    'ko_KR': 'nplurals=1;plural=0;',
    'tr_TR': 'nplurals=2;plural=(n>1);',
    'uk':    'nplurals=3;plural=(n%10==1&&n%100!=11?0:n%10>=2&&n%10<=4&&(n%100<10||n%100>=20)?1:2);',
}


def escape_po(s):
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    s = s.replace('\n', '\\n"\n"')
    s = s.replace('\t', '\\t')
    return s


def po_header(locale, textdomain):
    plural = PLURAL_FORMS.get(locale, 'nplurals=2;plural=(n!=1);')
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M%z')
    return f"""# {textdomain} {locale} translation.
# Copyright (C) {datetime.now().year}
msgid ""
msgstr ""
"Project-Id-Version: {textdomain}\\n"
"POT-Creation-Date: {now}\\n"
"PO-Revision-Date: {now}\\n"
"Language: {locale}\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Plural-Forms: {plural}\\n"
"X-Generator: wp-code-translate-skill\\n"
"""


def parse_po_blocks(content):
    """
    Parse a PO file into a list of raw block strings.
    Each block is separated by a blank line; the first block is the header.
    Returns list of (msgid, block_text) tuples. msgid=None for header.
    """
    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    raw_blocks = re.split(r'\n{2,}', content.strip())
    blocks = []
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        # Extract msgid
        m = re.search(r'^msgid\s+"((?:[^"\\]|\\.)*)"', block, re.MULTILINE)
        if m:
            msgid_val = m.group(1)
            # Handle multi-line: msgid "" followed by consecutive quoted
            # continuation lines. MUST stop at the first non-quoted line
            # (msgid_plural / msgstr) - a naive re.findall over the whole
            # remainder of the block also matches msgstr's OWN continuation
            # lines (since those are quoted too) and silently concatenates
            # the translation text onto the msgid. That bug produced 18
            # spurious "missing" msgids and near-duplicate PO entries in
            # Aug 2026 (see also the same bug class, already fixed, in
            # json_generator.py's parse_po_translations).
            if msgid_val == '':
                rest = block[m.end():]
                cont = []
                for line in rest.split('\n')[1:]:
                    line_m = re.match(r'^"((?:[^"\\]|\\.)*)"$', line.strip())
                    if not line_m:
                        break
                    cont.append(line_m.group(1))
                if cont:
                    msgid_val = ''.join(cont)
            if msgid_val == '':
                blocks.append((None, block))  # header
            else:
                decoded = (msgid_val.replace('\\"', '"').replace('\\\\', '\\')
                           .replace('\\n', '\n').replace('\\t', '\t'))
                blocks.append((decoded, block))
        else:
            blocks.append((None, block))
    return blocks


def dedup_po(po_path):
    """Remove duplicate msgid entries from a .po file, keeping first."""
    with open(po_path, encoding='utf-8', errors='replace') as f:
        content = f.read()
    blocks = parse_po_blocks(content)
    seen = set()
    kept = []
    for msgid, block in blocks:
        if msgid is None:
            kept.append(block)
            continue
        if msgid not in seen:
            seen.add(msgid)
            kept.append(block)
    new_content = '\n\n'.join(kept) + '\n'
    with open(po_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    removed = len(blocks) - len(kept)
    print(f'Dedup: removed {removed} duplicate(s) from {po_path}', file=sys.stderr)


def list_untranslated(po_path):
    with open(po_path, encoding='utf-8', errors='replace') as f:
        content = f.read()
    blocks = parse_po_blocks(content)
    untranslated = []
    for msgid, block in blocks:
        if msgid is None:
            continue
        # Check if msgstr is empty
        m = re.search(r'^msgstr\s+"((?:[^"\\]|\\.)*)"', block, re.MULTILINE)
        if m and m.group(1) == '':
            # Also check for continuation
            rest = block[m.end():]
            cont = re.findall(r'^"([^"]*)"', rest, re.MULTILINE)
            if not cont or ''.join(cont) == '':
                untranslated.append(msgid)
    print(json.dumps(untranslated, ensure_ascii=False, indent=2))


def format_entry(msgid, msgstr, plural=None, msgstr_plural=None, comment=None):
    lines = []
    if comment:
        lines.append(f'# {comment}')
    if plural:
        lines.append(f'msgid "{escape_po(msgid)}"')
        lines.append(f'msgid_plural "{escape_po(plural)}"')
        if msgstr_plural:
            for i, s in enumerate(msgstr_plural):
                lines.append(f'msgstr[{i}] "{escape_po(s)}"')
        else:
            lines.append('msgstr[0] ""')
            lines.append('msgstr[1] ""')
    else:
        lines.append(f'msgid "{escape_po(msgid)}"')
        lines.append(f'msgstr "{escape_po(msgstr or "")}"')
    return '\n'.join(lines)


def cmd_create(po_path, locale, textdomain, plural_forms=None):
    header = po_header(locale, textdomain)
    if plural_forms:
        header = re.sub(r'"Plural-Forms: [^"]+\\n"', f'"Plural-Forms: {plural_forms}\\n"', header)
    os.makedirs(os.path.dirname(po_path) or '.', exist_ok=True)
    with open(po_path, 'w', encoding='utf-8') as f:
        f.write(header)
    print(f'Created {po_path}', file=sys.stderr)


def cmd_update(po_path, translations_path):
    with open(translations_path, encoding='utf-8') as f:
        raw = json.load(f)

    # Normalise input: accept both dict and list formats
    if isinstance(raw, dict):
        entries = [{'msgid': k, 'msgstr': v} for k, v in raw.items()]
    else:
        entries = raw  # list of {msgid, msgstr, plural?, msgstr_plural?}

    # Backup existing
    if os.path.exists(po_path):
        shutil.copy2(po_path, po_path + '.bak')
        with open(po_path, encoding='utf-8', errors='replace') as f:
            content = f.read()
        existing_blocks = parse_po_blocks(content)
        existing_ids = {msgid for msgid, _ in existing_blocks if msgid is not None}
    else:
        existing_ids = set()
        content = ''

    new_entries = [e for e in entries if e.get('msgid') and e['msgid'] not in existing_ids]

    if not new_entries:
        print('PO up to date - no new entries.', file=sys.stderr)
        return

    with open(po_path, 'a', encoding='utf-8') as f:
        for e in new_entries:
            block = format_entry(
                e['msgid'],
                e.get('msgstr', ''),
                e.get('plural'),
                e.get('msgstr_plural'),
            )
            f.write('\n' + block + '\n')

    # Dedup just in case
    dedup_po(po_path)
    print(f'Added {len(new_entries)} new entry/entries to {po_path}', file=sys.stderr)


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'create' and len(sys.argv) >= 5:
        plural = sys.argv[5] if len(sys.argv) > 5 else None
        cmd_create(sys.argv[2], sys.argv[3], sys.argv[4], plural)
    elif cmd == 'update' and len(sys.argv) >= 4:
        cmd_update(sys.argv[2], sys.argv[3])
    elif cmd == 'dedup' and len(sys.argv) >= 3:
        dedup_po(sys.argv[2])
    elif cmd == 'list_untranslated' and len(sys.argv) >= 3:
        list_untranslated(sys.argv[2])
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
