#!/usr/bin/env python3
"""
polyglots_check.py - Deterministic WordPress.org Polyglots compliance checks
for a .po file.

Ports wp-polyglots-check/SKILL.md Step 6 (rules 6a-6m) from prose into code,
plus a GLOSSARY category from scripts/glossary.py's find_candidates(). Rule
6i (English loanword plurals) is generalised beyond its original hardcoded
plugins/themes/widgets list: it now flags an English -s plural of ANY term
the locale glossary marks invariato (target text equal to the English term).

Usage:
  python3 polyglots_check.py PLUGIN_PATH TEXTDOMAIN LOCALE [--overlay PATH] [--json OUT]

Exit 0 = nothing found. Exit 1 = findings exist (deterministic and/or
GLOSSARY). Only the GLOSSARY category needs model adjudication -- the
deterministic 6a-6m findings are final as reported.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, namedtuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from po_manager import parse_po_blocks  # noqa: E402
from glossary import (  # noqa: E402
    load_glossary, find_candidates, parse_entry_fields, is_po_header_block, _norm,
)


Finding = namedtuple("Finding", "rule severity msgid msgstr message")


# --- 6a: strings that must not be translated --------------------------------

NOTRANSLATE_MARKERS = (
    "plugin name", "theme name", "author of the", "found in changelog list item",
)


def _is_notranslate_comment(comment):
    """WP.org's own POT generator emits these as the ENTIRE #. comment text
    for metadata pulled from the plugin/theme header or readme.txt (e.g. the
    literal line '#. Plugin Name of the plugin'). A developer's own
    '#. translators: ...' note can freely mention 'plugin name' mid-sentence
    without meaning any of this -- e.g. Fotonic Pro's real
    '#. translators: 1: Plugin name "Eleva CRM Pro" 2: ...' comment, which a
    bare substring-anywhere match wrongly flagged. Requiring the comment to
    START WITH the marker (after stripping any leading label WP.org itself
    sometimes prefixes) distinguishes the two."""
    c = comment.strip().lower()
    return any(c.startswith(marker) for marker in NOTRANSLATE_MARKERS)


def check_6a(msgid, msgstr, comments):
    if any(_is_notranslate_comment(c) for c in comments):
        if msgstr and msgstr != msgid:
            return Finding("6a", "ERROR", msgid, msgstr,
                            "Must not be translated (Plugin/Theme Name, Author, or "
                            "changelog) -- msgstr should equal msgid verbatim")
    return None


# --- 6b: fuzzy flag -----------------------------------------------------------

def check_6b(msgid, msgstr, flags):
    if "fuzzy" in flags and msgstr:
        return Finding("6b", "WARNING", msgid, msgstr,
                        "Marked fuzzy -- needs review/approval before it goes live")
    return None


# --- 6c: placeholders intact ---------------------------------------------------

PLACEHOLDER_RE = re.compile(r"%\d+\$[sdf]|%[sdf]|###[A-Z0-9_]+###")
NUMBERED_RE = re.compile(r"^%\d+\$")


def check_6c(msgid, msgstr):
    src = PLACEHOLDER_RE.findall(msgid)
    if not src:
        return None
    tgt = PLACEHOLDER_RE.findall(msgstr)
    missing = [p for p in src if p not in tgt]
    if missing:
        return Finding("6c", "ERROR", msgid, msgstr,
                        f"Placeholder(s) missing in msgstr: {missing}")
    src_numbered = [p for p in src if NUMBERED_RE.match(p)]
    tgt_numbered = [p for p in tgt if NUMBERED_RE.match(p)]
    if src_numbered and src_numbered != tgt_numbered and sorted(src_numbered) == sorted(tgt_numbered):
        return Finding("6c", "ERROR", msgid, msgstr,
                        f"Numbered placeholders reordered: {src_numbered} -> {tgt_numbered}")
    return None


# --- 6d: HTML tags intact -------------------------------------------------------

HTML_TAG_RE = re.compile(r"<[^>]+>")


def check_6d(msgid, msgstr):
    src_tags = HTML_TAG_RE.findall(msgid)
    if not src_tags:
        return None
    src_c, tgt_c = Counter(src_tags), Counter(HTML_TAG_RE.findall(msgstr))
    missing = [tag for tag, n in src_c.items() if tgt_c.get(tag, 0) < n]
    if missing:
        return Finding("6d", "ERROR", msgid, msgstr,
                        f"HTML tag(s) missing or malformed in msgstr: {missing}")
    return None


# --- 6e: accent errors (it_IT) ---------------------------------------------------

def check_6e(msgid, msgstr):
    if re.search(r"\be'|\bE'", msgstr):
        return Finding("6e", "ERROR", msgid, msgstr, "Uses e'/E' instead of è/È")
    return None


# --- 6f: capitalization (it_IT) --------------------------------------------------

ITALIAN_MONTHS = (
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
    "agosto", "settembre", "ottobre", "novembre", "dicembre",
)

# Italian function words. A capitalised one MID-SENTENCE is the actual signal
# for Title Case, because proper nouns and acronyms never capitalise these.
# Counting "3 consecutive capitalised words" instead flagged ordinary strings
# like "PHP OpenSSL", "Google Authenticator, Authy" and "Local by Flywheel":
# measured against the real free-plugin .po, that heuristic produced 8
# findings, all 8 false positives.
ITALIAN_FUNCTION_WORDS = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "a", "da",
    "in", "con", "su", "per", "tra", "fra", "e", "o", "ma", "che", "se",
    "del", "dello", "della", "dei", "degli", "delle", "dal", "dallo",
    "dalla", "dai", "dagli", "dalle", "al", "allo", "alla", "ai", "agli",
    "alle", "nel", "nello", "nella", "nei", "negli", "nelle", "sul",
    "sullo", "sulla", "sui", "sugli", "sulle", "come", "non", "anche",
    "quando", "dove", "questo", "questa", "sono", "essere",
}


def _is_sentence_initial(text, start):
    """True if the token at `start` opens the string or a new sentence.
    A function word is legitimately capitalised there ("... recupero. Il
    codice precedente ..."), so it must not count as Title Case. Ignoring
    this flagged 17 correct strings in the real free-plugin .po."""
    before = text[:start].rstrip()
    if not before:
        return True
    return before[-1] in ".?!:;\n" or before[-1] in "([{\"'«"


def check_6f(msgid, msgstr):
    words = list(re.finditer(r"[A-Za-zÀ-ÿ']+", msgstr))
    if len(words) > 3:
        # ALL-CAPS acronyms (PHP, PDF, MB) carry no case information, and a
        # function word opening a sentence is correct, so neither counts.
        offenders = [
            m.group(0) for m in words
            if m.group(0)[:1].isupper()
            and m.group(0) != m.group(0).upper()
            and m.group(0).lower() in ITALIAN_FUNCTION_WORDS
            and not _is_sentence_initial(msgstr, m.start())
        ]
        if offenders:
            return Finding("6f", "WARNING", msgid, msgstr,
                           f"Possible Title Case: function word(s) capitalised "
                           f"mid-sentence {sorted(set(offenders))}. Italian uses "
                           f"sentence case.")
    # month name capitalised mid-sentence (not the first word of msgstr)
    tail = msgstr[1:] if msgstr else ""
    for month in ITALIAN_MONTHS:
        if re.search(r"(?<=\s)" + month.capitalize() + r"\b", tail):
            return Finding("6f", "WARNING", msgid, msgstr,
                            f"Month name '{month.capitalize()}' capitalised mid-sentence "
                            "-- should be lowercase")
    return None


# --- 6g: punctuation (it_IT) -----------------------------------------------------

def check_6g(msgid, msgstr):
    problems = []
    if re.search(r"\s[,.;:?!]", msgstr):
        problems.append("space before punctuation")
    if re.search(r"\.{4,}", msgstr):
        problems.append("ellipsis has 4+ dots (use … or exactly ...)")
    # Oxford comma: per the it_IT handbook this is specifically "la virgola
    # inserita prima della congiunzione che TERMINA UN ELENCO" ("uno, due, e
    # tre"). A comma before "e" joining two independent clauses is ordinary
    # correct Italian, so require an earlier comma proving a list is in
    # progress. Without that, real strings like "... Sodium e Zip, e questo
    # server non le ha" were flagged wrongly.
    m_ox = re.search(r",\s+[eo]\s", msgstr)
    if m_ox and "," in msgstr[:m_ox.start()]:
        problems.append("Oxford comma ending a list (Italian omits it: 'uno, due e tre')")
    if re.search(r"\(\s|\s\)", msgstr):
        problems.append("space just inside parentheses")
    if problems:
        return Finding("6g", "WARNING", msgid, msgstr, "; ".join(problems))
    return None


# --- 6h: & as conjunction (it_IT) ------------------------------------------------

def _has_bare_ampersand(s):
    return re.search(r"(?<!&)\s&\s(?!amp;)", s) is not None


def check_6h(msgid, msgstr):
    if _has_bare_ampersand(msgid) and _has_bare_ampersand(msgstr):
        return Finding("6h", "WARNING", msgid, msgstr,
                        "Uses '&' as conjunction -- Italian should use 'e'")
    return None


# --- 6i: English loanword plurals (it_IT), generalised from the glossary --------

def build_invariato_terms(entries):
    """Terms the LOCALE glossary keeps unchanged (target text equals the
    English term itself) -- generalises rule 6i beyond its original
    hardcoded plugins/themes/widgets list to every such loanword (~130 in
    it.csv: account, blog, editor, ...)."""
    out = set()
    for key, entry_list in entries.items():
        if len(key) < 3:
            continue
        for e in entry_list:
            if e.source == "locale" and _norm(e.target) == key:
                out.add(key)
                break
    return out


def check_6i(msgid, msgstr, invariato_terms):
    hits = [t for t in invariato_terms if re.search(r"\b" + re.escape(t) + r"s\b", msgstr, re.IGNORECASE)]
    if hits:
        return Finding("6i", "WARNING", msgid, msgstr,
                        f"English loanword plural(s) should drop the 's' in Italian: {sorted(hits)}")
    return None


# --- 6j: "Please" humanised (it_IT) -----------------------------------------------

def check_6j(msgid, msgstr):
    if re.match(r"^Please\b", msgid.strip()):
        if re.match(r"^(Si prega|Per favore)\b", msgstr.strip(), re.IGNORECASE):
            return Finding("6j", "WARNING", msgid, msgstr,
                            "Humanized 'Please' as Si prega/Per favore -- Italian "
                            "device messages should drop it entirely")
    return None


# --- 6k: gerund without "in corso" (it_IT) ----------------------------------------

def check_6k(msgid, msgstr):
    if re.match(r"^[A-Z][a-z]*ing\b", msgid.strip()):
        if "in corso" not in msgstr.lower():
            return Finding("6k", "INFO", msgid, msgstr,
                            "Gerund without 'in corso' -- Italian convention adds it "
                            "(e.g. 'Caricamento impostazioni in corso...')")
    return None


# --- 6l: date format (it_IT) ------------------------------------------------------

DATE_FORMAT_HINT = re.compile(r"[gGhH]:i(:s)?\s*[Aa]?")


def check_6l(msgid, msgstr):
    if DATE_FORMAT_HINT.search(msgid):
        if re.search(r"[gh]:i(:s)?\s*[Aa]\b", msgstr):
            return Finding("6l", "WARNING", msgid, msgstr,
                            "Keeps 12-hour AM/PM format -- Italian dates use 24h (H:i), no AM/PM")
    return None


# --- 6m: wordpress.org URL (it_IT) ------------------------------------------------

def check_6m(msgid, msgstr):
    if re.search(r"https://wordpress\.org/", msgstr):
        return Finding("6m", "INFO", msgid, msgstr,
                        "Bare wordpress.org URL -- consider it.wordpress.org where "
                        "an Italian page exists")
    return None


DETERMINISTIC_CHECKS_SIMPLE = (
    check_6c, check_6d, check_6e, check_6f, check_6g, check_6h,
    check_6j, check_6k, check_6l, check_6m,
)


def check_entry(msgid, fields, invariato_terms):
    """Run every deterministic rule (6a-6m) against one entry. Only requires
    msgstr to be non-empty -- unlike the checks' original prose gate
    ("non-empty AND different from msgid"), msgstr == msgid is NOT
    skipped here, matching the fix glossary.py's find_candidates already
    tests for (test_untranslated_entry_is_still_checked): an untranslated
    Dashboard left as "Dashboard" is a real finding, not a no-op. The only
    checks where msgstr == msgid is itself the CORRECT state (6a) encode
    that in their own condition rather than as a blanket skip."""
    msgstr = fields["msgstr"]
    if not msgstr:
        return []

    findings = []
    f = check_6a(msgid, msgstr, fields["extracted_comments"])
    if f:
        findings.append(f)
    f = check_6b(msgid, msgstr, fields["flags"])
    if f:
        findings.append(f)
    for check in DETERMINISTIC_CHECKS_SIMPLE:
        f = check(msgid, msgstr)
        if f:
            findings.append(f)
    f = check_6i(msgid, msgstr, invariato_terms)
    if f:
        findings.append(f)
    return findings


def run_checks(po_path, slug, data_dir, overlay_path=None):
    """Run every check against every translated entry in po_path. Returns
    (findings: list[Finding], glossary_findings: list[glossary.Candidate]).
    Read-only: never writes to po_path or anything else."""
    with open(po_path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    blocks = parse_po_blocks(content)
    entries = load_glossary(slug, data_dir, overlay_path=overlay_path)
    invariato_terms = build_invariato_terms(entries)

    findings = []
    glossary_findings = []
    for msgid, block in blocks:
        if msgid is None or is_po_header_block(block):
            continue
        fields = parse_entry_fields(block)
        msgstr = fields["msgstr"]
        if not msgstr:
            continue
        findings.extend(check_entry(msgid, fields, invariato_terms))
        for c in find_candidates(entries, msgid, msgstr):
            glossary_findings.append(_with_msgid(c, msgid, msgstr))

    return findings, glossary_findings


GlossaryFinding = namedtuple(
    "GlossaryFinding", "msgid msgstr term expected pos description reason source"
)


def _with_msgid(candidate, msgid, msgstr):
    return GlossaryFinding(
        msgid=msgid, msgstr=msgstr, term=candidate.term, expected=candidate.expected,
        pos=candidate.pos, description=candidate.description, reason=candidate.reason,
        source=candidate.source,
    )


# --- CLI -----------------------------------------------------------------------

def _default_data_dir():
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))


def _glossary_slug_for_locale(locale, data_dir):
    """Resolve a WP locale (it_IT) to its GlotPress glossary slug (it) via
    data/locale-map.md's Glossary slug column -- needed because the mapping
    isn't always the obvious lowercase prefix (en_GB -> en-gb)."""
    map_path = os.path.join(data_dir, "locale-map.md")
    if os.path.isfile(map_path):
        with open(map_path, encoding="utf-8") as f:
            for line in f:
                if not line.startswith("|"):
                    continue
                cols = [c.strip() for c in line.strip("|\n").split("|")]
                if len(cols) >= 5 and cols[1] == locale and cols[4]:
                    return cols[4]
    return locale.split("_")[0].lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("plugin_path")
    parser.add_argument("textdomain")
    parser.add_argument("locale")
    parser.add_argument("--overlay", default=None)
    parser.add_argument("--json", default=None)
    parser.add_argument("--data-dir", default=_default_data_dir())
    args = parser.parse_args()

    po_path = os.path.join(args.plugin_path, "languages", f"{args.textdomain}-{args.locale}.po")
    if not os.path.isfile(po_path):
        print(f"error: no .po file at {po_path}", file=sys.stderr)
        sys.exit(2)

    slug = _glossary_slug_for_locale(args.locale, args.data_dir)
    findings, glossary_findings = run_checks(po_path, slug, args.data_dir, overlay_path=args.overlay)

    by_sev = {"ERROR": [], "WARNING": [], "INFO": []}
    for f in findings:
        by_sev[f.severity].append(f)

    print(f"wp-polyglots-check: {po_path}")
    print(f"  ERROR   : {len(by_sev['ERROR'])}")
    print(f"  WARNING : {len(by_sev['WARNING'])}")
    print(f"  INFO    : {len(by_sev['INFO'])}")
    print(f"  GLOSSARY: {len(glossary_findings)} (needs model adjudication)")
    for sev in ("ERROR", "WARNING", "INFO"):
        for f in by_sev[sev]:
            print(f"\n[{f.rule} {f.severity}] {f.message}")
            print(f"    msgid : {f.msgid[:70]}")
            print(f"    msgstr: {f.msgstr[:70]}")
    for g in glossary_findings:
        print(f"\n[GLOSSARY {g.source}] {g.term!r} -> expect {g.expected!r} ({g.reason})")
        print(f"    msgid : {g.msgid[:70]}")
        print(f"    msgstr: {g.msgstr[:70]}")

    if args.json:
        payload = {
            "po_path": po_path,
            "findings": [f._asdict() for f in findings],
            "glossary_findings": [g._asdict() for g in glossary_findings],
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    sys.exit(1 if (findings or glossary_findings) else 0)


if __name__ == "__main__":
    main()
