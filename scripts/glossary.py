#!/usr/bin/env python3
"""
glossary.py - Fetch, cache, and query WordPress.org Polyglots glossaries.

Commands:
  fetch --slug SLUG [--data-dir DIR]
      Download the glossary CSV for SLUG from translate.wordpress.org and
      cache it at DIR/glossaries/SLUG.csv, updating .meta.json. On network
      failure, warns on stderr and leaves the existing cached copy in place.

  lookup --slug SLUG --term TERM [--data-dir DIR] [--overlay PATH]
      Print the glossary entries (JSON) matching TERM (accent/case
      insensitive), overlay entries first if present.

  candidates --po PO_FILE --slug SLUG [--data-dir DIR] [--overlay PATH] [--json OUT]
      Run every translated entry in PO_FILE through find_candidates() and
      print a human-readable report (and optionally JSON to OUT).

Run with -h/--help on any subcommand for its exact flags.
"""
import argparse
import csv
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from collections import namedtuple
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from po_manager import parse_po_blocks  # noqa: E402


GlossaryEntry = namedtuple("GlossaryEntry", "en target pos description source")
Candidate = namedtuple("Candidate", "term expected pos description reason source")

GLOTPRESS_EXPORT_URL = (
    "https://translate.wordpress.org/locale/{slug}/default/glossary/-export/?format=csv"
)

# Content words shorter than this, or on this stopword list, don't carry
# enough signal to be used as a match stem (mirrors function words that
# would otherwise match almost any Italian sentence).
STEM_LEN = 5
STOPWORDS = {
    "non", "del", "della", "dei", "delle", "con", "per", "una", "uno",
    "gli", "che", "sei", "alla", "allo", "agli", "alle", "dal", "dallo",
}


def _norm(s):
    """Accent-insensitive, case-insensitive normalisation."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _stem_words(text):
    """Content-word stems for one glossary target option (space-separated
    phrase). Excludes stopwords; each surviving word contributes its first
    STEM_LEN normalised characters."""
    out = []
    for w in re.findall(r"[^\W\d_]+", text, flags=re.UNICODE):
        wn = _norm(w)
        if len(wn) < 3 or wn in STOPWORDS:
            continue
        out.append(wn[:STEM_LEN])
    return out


def _is_meta_instruction(target):
    """A multi-word, fully-uppercase target is an instruction to the
    translator (e.g. 'NON SI TRADUCE' = drop this word), not literal text
    that should appear in msgstr. Single-word all-caps targets (AJAX, FAQ)
    are real invariato terms and are not affected by this check."""
    words = target.split()
    return len(words) > 1 and target == target.upper() and any(c.isalpha() for c in target)


def _read_glossary_csv(path, source):
    """Read a glossary CSV by column INDEX, not name - column 2's header is
    the locale slug (en/it/de/...) and varies per file."""
    entries = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if len(row) < 2 or not row[0].strip():
                continue
            en = row[0].strip()
            target = row[1].strip()
            pos = row[2].strip() if len(row) > 2 else ""
            description = row[3].strip() if len(row) > 3 else ""
            entries.append(GlossaryEntry(en, target, pos, description, source))
    return entries


def load_glossary(slug, data_dir, overlay_path=None):
    """Load the locale glossary for `slug` (plus an optional project overlay)
    into {normalised_term: [GlossaryEntry, ...]}. Multiple entries under one
    key are alternatives (different POS senses, or comma/slash-separated
    translation options) - find_candidates() decides precedence between
    overlay and locale entries at lookup time, not here."""
    path = os.path.join(data_dir, "glossaries", f"{slug}.csv")
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"No cached glossary for locale '{slug}' at {path}. "
            f"Run: python3 glossary.py fetch --slug {slug}"
        )
    entries = {}
    for e in _read_glossary_csv(path, source="locale"):
        entries.setdefault(_norm(e.en), []).append(e)
    if overlay_path and os.path.isfile(overlay_path):
        for e in _read_glossary_csv(overlay_path, source="overlay"):
            entries.setdefault(_norm(e.en), []).append(e)
    return entries


def fetch_glossary(slug, data_dir):
    """Download the live glossary for `slug`, cache it, update .meta.json.
    Returns (bytes_written, path). On network failure, warns on stderr and
    returns the cached file's existing size/path unchanged if one exists;
    re-raises if there is no cache to fall back to."""
    glossaries_dir = os.path.join(data_dir, "glossaries")
    os.makedirs(glossaries_dir, exist_ok=True)
    path = os.path.join(glossaries_dir, f"{slug}.csv")
    url = GLOTPRESS_EXPORT_URL.format(slug=slug)
    meta_path = os.path.join(glossaries_dir, ".meta.json")

    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            content = resp.read()
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        if os.path.isfile(path):
            print(
                f"warning: fetch failed for '{slug}' ({exc}); using cached copy at {path}",
                file=sys.stderr,
            )
            return os.path.getsize(path), path
        raise RuntimeError(
            f"fetch failed for '{slug}' ({exc}) and no cached copy exists at {path}"
        ) from exc

    with open(path, "wb") as f:
        f.write(content)

    meta = {}
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    meta[slug] = {
        "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "bytes": len(content),
        "source_url": url,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")

    return len(content), path


_PO_HEADER_SHAPE = re.compile(r'^msgid\s+""\s*\nmsgstr\s+""\s*$', re.MULTILINE)


def is_po_header_block(block):
    """True for the .po file header block specifically.

    po_manager.parse_po_blocks() is supposed to return msgid=None for the
    header, but its continuation-line scan for an empty msgid doesn't stop
    before the following msgstr line, so it walks straight into msgstr's OWN
    continuation lines and returns their joined text as if it were msgid's
    continuation -- the header comes back as a normal, non-None "entry"
    whose fake msgid is literally the Project-Id-Version/Report-Msgid-Bugs
    metadata block. That's an existing bug in po_manager.py (left unchanged
    per the plan), so every caller here defends against it directly instead
    of trusting msgid is None for headers. The header's real, distinguishing
    shape is msgid "" immediately followed by msgstr "" on the next line --
    no real translatable entry has both a literally empty msgid AND msgstr."""
    return _PO_HEADER_SHAPE.search(block) is not None


def parse_entry_fields(block):
    """Extract the fields Phase 2/3 checks need from one raw .po block (as
    returned by po_manager.parse_po_blocks: msgid already decoded, block is
    the untouched raw text). Not a second .po parser -- it's a field
    accessor over a block parse_po_blocks already split out, the same
    technique po_manager.list_untranslated uses inline for msgstr alone;
    this just makes it reusable and adds the two fields (#. comments, #,
    flags) list_untranslated didn't need."""
    msgstr = ""
    m = re.search(r'^msgstr\s+"((?:[^"\\]|\\.)*)"', block, re.MULTILINE)
    if m:
        msgstr = m.group(1)
        rest = block[m.end():]
        cont = re.findall(r'^"([^"]*)"', rest, re.MULTILINE)
        if cont:
            msgstr += "".join(cont)
        msgstr = msgstr.replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n")

    extracted_comments = re.findall(r"^#\.\s?(.*)$", block, re.MULTILINE)
    flags = set()
    for fline in re.findall(r"^#,\s?(.*)$", block, re.MULTILINE):
        flags.update(x.strip() for x in fline.split(","))

    return {"msgstr": msgstr, "extracted_comments": extracted_comments, "flags": flags}


def _strip_allcaps_literals(text):
    """Drop tokens the user types or sees verbatim (RESET, OTP codes) so
    they can't accidentally match a same-spelled lowercase glossary term."""
    return re.sub(r"\b[A-Z]{3,}\b", " ", text)


def _entry_satisfied(entry, key_norm, tgt_norm):
    """True/False whether msgstr appears to use this one glossary entry's
    translation. None means 'not applicable' (meta-instruction entries are
    handled by the caller, not scored here)."""
    if _is_meta_instruction(entry.target):
        return None
    target_norm = _norm(entry.target)
    if target_norm == key_norm:
        # Invariato: the term is its own translation: check literal presence.
        return re.search(r"\b" + re.escape(target_norm) + r"\b", tgt_norm) is not None
    # Translated phrase: every content word must show up (a lone shared
    # loanword, e.g. "plugin" inside "plugin richiesto", isn't enough on
    # its own to prove the REST of the phrase was translated correctly).
    stems = _stem_words(entry.target)
    if not stems:
        return None
    return all(s in tgt_norm for s in stems)


def find_candidates(entries, msgid, msgstr):
    """Check one msgid/msgstr pair against a loaded glossary dict. Returns a
    list of Candidate - empty if nothing looks wrong. Longer (multi-word)
    keys are checked before shorter ones, and a key whose match span is
    already covered by a longer match is skipped, so an overlay phrase like
    'required plugin' claims its span before the bare 'required' term is
    independently (and redundantly) flagged."""
    msgstr = msgstr or ""
    src_norm = _norm(_strip_allcaps_literals(msgid))
    tgt_norm = _norm(msgstr)

    keys = sorted(entries.keys(), key=lambda k: (-k.count(" "), -len(k)))
    claimed = []
    candidates = []

    for key in keys:
        if len(key) < 3:
            continue
        m = re.search(r"\b" + re.escape(key) + r"\b", src_norm)
        if not m:
            continue
        span = m.span()
        if any(s0 <= span[0] and span[1] <= s1 for s0, s1 in claimed):
            continue
        claimed.append(span)

        entry_list = entries[key]
        overlay_entries = [e for e in entry_list if e.source == "overlay"]
        active = overlay_entries or entry_list

        results = [_entry_satisfied(e, key, tgt_norm) for e in active]
        scored = [r for r in results if r is not None]
        if scored and any(scored):
            continue  # at least one applicable entry is satisfied

        meta_entries = [e for e, r in zip(active, results) if r is None and _is_meta_instruction(e.target)]
        if meta_entries and not scored:
            # Every entry for this key is a meta-instruction (e.g. "drop
            # this word", it glossary's Please -> NON SI TRADUCE). The only
            # thing a generic accent/stem matcher can honestly verify here
            # is whether the literal source word survived untranslated -
            # e.g. "Please" left in place. Recognising a HUMANIZED
            # translation of the dropped word ("si prega", "per favore")
            # needs locale-specific phrasing knowledge this engine doesn't
            # have; that's polyglots_check.py's rule 6j, layered on top.
            if re.search(r"\b" + re.escape(key) + r"\b", tgt_norm):
                best = meta_entries[0]
                candidates.append(Candidate(
                    term=key,
                    expected="(drop; do not translate)",
                    pos=best.pos,
                    description=best.description,
                    reason="meta-instruction not followed: term left untranslated",
                    source=best.source,
                ))
            continue

        if not scored:
            continue  # nothing applicable (shouldn't normally happen)

        best = active[0]
        expected = "/".join(e.target for e in active)
        candidates.append(Candidate(
            term=key,
            expected=expected,
            pos=best.pos,
            description=best.description,
            reason="glossary translation absent",
            source=best.source,
        ))

    return candidates


# --- CLI -------------------------------------------------------------------

def _default_data_dir():
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))


def _cmd_fetch(args):
    n, path = fetch_glossary(args.slug, args.data_dir)
    print(f"{path}: {n} bytes")


def _cmd_lookup(args):
    entries = load_glossary(args.slug, args.data_dir, overlay_path=args.overlay)
    key = _norm(args.term)
    matches = entries.get(key, [])
    print(json.dumps([m._asdict() for m in matches], indent=2, ensure_ascii=False))


def _cmd_candidates(args):
    with open(args.po, encoding="utf-8", errors="replace") as f:
        content = f.read()
    blocks = parse_po_blocks(content)
    entries = load_glossary(args.slug, args.data_dir, overlay_path=args.overlay)

    report = []
    for msgid, block in blocks:
        if msgid is None or is_po_header_block(block):
            continue
        msgstr_val = parse_entry_fields(block)["msgstr"]
        if not msgstr_val:
            continue  # untranslated: not this script's concern

        for c in find_candidates(entries, msgid, msgstr_val):
            report.append({
                "msgid": msgid,
                "msgstr": msgstr_val,
                "term": c.term,
                "expected": c.expected,
                "pos": c.pos,
                "description": c.description,
                "reason": c.reason,
                "source": c.source,
            })

    for r in report:
        print(f"[{r['source']}] {r['term']!r} -> expect {r['expected']!r}  ({r['reason']})")
        print(f"    msgid : {r['msgid'][:70]}")
        print(f"    msgstr: {r['msgstr'][:70]}")
    print(f"\n{len(report)} candidate(s) from {args.po}", file=sys.stderr)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    sys.exit(1 if report else 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="download and cache a locale's glossary")
    p_fetch.add_argument("--slug", required=True)
    p_fetch.add_argument("--data-dir", default=_default_data_dir())
    p_fetch.set_defaults(func=_cmd_fetch)

    p_lookup = sub.add_parser("lookup", help="print glossary entries for one term")
    p_lookup.add_argument("--slug", required=True)
    p_lookup.add_argument("--term", required=True)
    p_lookup.add_argument("--data-dir", default=_default_data_dir())
    p_lookup.add_argument("--overlay", default=None)
    p_lookup.set_defaults(func=_cmd_lookup)

    p_cand = sub.add_parser("candidates", help="check a .po file's translations against the glossary")
    p_cand.add_argument("--po", required=True)
    p_cand.add_argument("--slug", required=True)
    p_cand.add_argument("--data-dir", default=_default_data_dir())
    p_cand.add_argument("--overlay", default=None)
    p_cand.add_argument("--json", default=None, help="also write the report as JSON to this path")
    p_cand.set_defaults(func=_cmd_candidates)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
