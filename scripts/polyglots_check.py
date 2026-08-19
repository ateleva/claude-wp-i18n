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


# =============================================================================
# LOCALE-SPECIFIC RULES (6e-6m)
#
# Everything below depends on the target language's conventions and is driven
# by data/locales/{LOCALE}.rules.json. A rule with no config entry does NOT
# run. That default is deliberate: applying one locale's conventions to
# another does not merely give generic advice, it tells the translator to
# BREAK their own rules. Real examples this design prevents:
#
#   de_DE  "Add-ons" is the German glossary's OWN documented plural
#          (Mehrzahl). The Italian no-English-plural rule flagged it as an
#          error and told the translator to write "Add-on".
#   de_DE  Italian's "use e instead of &" told a German translator to use
#          an Italian conjunction rather than "und".
#   fr_FR  "Voulez-vous vraiment ?" carries the space before "?" that French
#          typography REQUIRES. The Italian rule flagged it as a mistake.
#
# So a missing config means "we do not know this locale's rules", never
# "assume Italian".
# =============================================================================

LOCALE_NEUTRAL_RULES = ("6a", "6b", "6c", "6d")


def load_locale_rules(locale, data_dir):
    """Load data/locales/{LOCALE}.rules.json.

    Returns (rules_dict, status). status is 'configured' when a file exists,
    'neutral-only' when it does not, in which case rules_dict is empty and
    only the locale-neutral checks 6a-6d will run."""
    path = os.path.join(data_dir, "locales", f"{locale}.rules.json")
    if not os.path.isfile(path):
        return {}, "neutral-only"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("rules", {}), "configured"


def _rule(cfg, key):
    """Return the rule's config dict if it is enabled, else None."""
    r = cfg.get(key)
    if isinstance(r, dict) and r.get("enabled"):
        return r
    return None


def active_rule_ids(cfg):
    """Rule ids that will actually run for this locale, for the report."""
    active = list(LOCALE_NEUTRAL_RULES)
    active += sorted(k for k, v in cfg.items() if isinstance(v, dict) and v.get("enabled"))
    return active


def inactive_rule_ids(cfg):
    return sorted(k for k, v in cfg.items() if isinstance(v, dict) and not v.get("enabled"))


# --- 6e: apostrophe used instead of an accented vowel -------------------------

def check_6e(msgid, msgstr, cfg):
    r = _rule(cfg, "6e_apostrophe_accent")
    if not r:
        return None
    for bad, good in r.get("pairs", []):
        if re.search(r"\b" + re.escape(bad), msgstr):
            return Finding("6e", "ERROR", msgid, msgstr,
                           f"Uses {bad} instead of {good}")
    return None


# --- 6f: capitalization -------------------------------------------------------

def _is_sentence_initial(text, start):
    """True if the token at `start` opens the string or a new sentence.
    A function word is legitimately capitalised there ("... recupero. Il
    codice precedente ..."), so it must not count as Title Case. Ignoring
    this flagged 17 correct strings in the real free-plugin .po."""
    before = text[:start].rstrip()
    if not before:
        return True
    return before[-1] in ".?!:;\n" or before[-1] in "([{\"'«"


def check_6f_title_case(msgid, msgstr, cfg):
    """Flag a FUNCTION word capitalised mid-sentence.

    Counting "3 consecutive capitalised words" instead flagged ordinary
    strings full of acronyms and proper nouns ("PHP OpenSSL", "Google
    Authenticator, Authy", "Local by Flywheel"): 8 findings on the real
    free-plugin .po, all 8 false positives. Proper nouns never capitalise
    function words, so those are the real signal.

    The word list is per-locale because the words differ, and because some
    locales must not run this at all: German capitalises every noun, and its
    formal register capitalises the pronoun "Sie", so the heuristic does not
    transfer."""
    r = _rule(cfg, "6f_title_case")
    if not r:
        return None
    function_words = {w.lower() for w in r.get("function_words", [])}
    if not function_words:
        return None
    words = list(re.finditer(r"[^\W\d_]+", msgstr, re.UNICODE))
    if len(words) <= 3:
        return None
    offenders = [
        m.group(0) for m in words
        if m.group(0)[:1].isupper()
        and m.group(0) != m.group(0).upper()      # skip ALL-CAPS acronyms
        and m.group(0).lower() in function_words
        and not _is_sentence_initial(msgstr, m.start())
    ]
    if offenders:
        return Finding("6f", "WARNING", msgid, msgstr,
                       f"Possible Title Case: function word(s) capitalised "
                       f"mid-sentence {sorted(set(offenders))}. This locale uses "
                       f"sentence case.")
    return None


def check_6f_months(msgid, msgstr, cfg):
    """Flag a capitalised month name mid-sentence.

    Off for de_DE (months are nouns, so German capitalises them) and for
    en_GB (English capitalises them)."""
    r = _rule(cfg, "6f_lowercase_months")
    if not r:
        return None
    for month in r.get("months", []):
        if re.search(r"(?<=\s)" + re.escape(month.capitalize()) + r"\b", msgstr):
            return Finding("6f", "WARNING", msgid, msgstr,
                           f"Month name '{month.capitalize()}' capitalised "
                           f"mid-sentence, should be lowercase in this locale")
    return None


# --- 6g: punctuation ----------------------------------------------------------

def check_6g(msgid, msgstr, cfg):
    problems = []

    # French REQUIRES a space before ; : ! ? so this sub-rule is off there.
    r = _rule(cfg, "6g_space_before_punctuation")
    if r:
        marks = r.get("marks", ",.;:?!")
        if re.search(r"\s[" + re.escape(marks) + r"]", msgstr):
            problems.append("space before punctuation")

    if _rule(cfg, "6g_ellipsis"):
        if re.search(r"\.{4,}", msgstr):
            problems.append("ellipsis has 4+ dots (use the ellipsis character or exactly ...)")

    # Scoped to the conjunction ENDING A LIST, per the it_IT handbook: "la
    # virgola inserita prima della congiunzione che termina un elenco". A
    # comma before "e" joining two independent clauses is correct, so require
    # an earlier comma proving a list is in progress.
    r = _rule(cfg, "6g_oxford_comma")
    if r:
        conj = r.get("conjunctions", [])
        if conj:
            pattern = r",\s+(?:" + "|".join(re.escape(c) for c in conj) + r")\s"
            m_ox = re.search(pattern, msgstr)
            if m_ox and "," in msgstr[:m_ox.start()]:
                problems.append("serial comma before the final conjunction; this locale omits it")

    if _rule(cfg, "6g_paren_spacing"):
        if re.search(r"\(\s|\s\)", msgstr):
            problems.append("space just inside parentheses")

    if problems:
        return Finding("6g", "WARNING", msgid, msgstr, "; ".join(problems))
    return None


# --- 6h: & used as a conjunction ----------------------------------------------

def _has_bare_ampersand(s):
    return re.search(r"(?<!&)\s&\s(?!amp;)", s) is not None


def check_6h(msgid, msgstr, cfg):
    r = _rule(cfg, "6h_ampersand")
    if not r:
        return None
    conjunction = r.get("conjunction")
    if not conjunction:
        return None
    if _has_bare_ampersand(msgid) and _has_bare_ampersand(msgstr):
        return Finding("6h", "WARNING", msgid, msgstr,
                       f"Uses '&' as a conjunction; this locale should use "
                       f"'{conjunction}'")
    return None


# --- 6i: English loanword plurals, driven by the locale glossary --------------

def build_invariato_terms(entries):
    """Terms the LOCALE glossary keeps unchanged (target equals the English
    term). Generalises 6i beyond its original hardcoded plugins/themes/widgets
    list to every such loanword (~130 in it.csv: account, blog, editor, ...).

    Note this only identifies the terms. Whether an English -s plural on them
    is WRONG is a separate, per-locale question, gated by 6i_loanword_plural:
    Italian drops the -s, German does not ("Add-ons" is the German glossary's
    own documented plural)."""
    out = set()
    for key, entry_list in entries.items():
        if len(key) < 3:
            continue
        for e in entry_list:
            if e.source == "locale" and _norm(e.target) == key:
                out.add(key)
                break
    return out


def check_6i(msgid, msgstr, invariato_terms, cfg):
    if not _rule(cfg, "6i_loanword_plural"):
        return None
    hits = [t for t in invariato_terms
            if re.search(r"\b" + re.escape(t) + r"s\b", msgstr, re.IGNORECASE)]
    if hits:
        return Finding("6i", "WARNING", msgid, msgstr,
                       f"English loanword plural(s); this locale keeps the "
                       f"singular form: {sorted(hits)}")
    return None


# --- 6j: "Please" humanised ----------------------------------------------------

def check_6j(msgid, msgstr, cfg):
    r = _rule(cfg, "6j_please")
    if not r:
        return None
    humanizers = r.get("humanizers", [])
    if not humanizers:
        return None
    if re.match(r"^Please\b", msgid.strip(), re.IGNORECASE):
        for h in humanizers:
            if re.match(r"^" + re.escape(h) + r"\b", msgstr.strip(), re.IGNORECASE):
                return Finding("6j", "WARNING", msgid, msgstr,
                               f"Humanized 'Please' as '{h}'; this locale drops "
                               f"it from device messages")
    return None


# --- 6k: progressive/gerund marker ---------------------------------------------

def check_6k(msgid, msgstr, cfg):
    r = _rule(cfg, "6k_gerund")
    if not r:
        return None
    marker = r.get("marker")
    if not marker:
        return None
    if re.match(r"^[A-Z][a-z]*ing\b", msgid.strip()):
        if marker.lower() not in msgstr.lower():
            return Finding("6k", "INFO", msgid, msgstr,
                           f"Gerund without '{marker}'; this locale's convention "
                           f"adds it")
    return None


# --- 6l: 12-hour vs 24-hour clock in date-format strings ------------------------

DATE_FORMAT_HINT = re.compile(r"[gGhH]:i(:s)?\s*[Aa]?")


def check_6l(msgid, msgstr, cfg):
    """Off for en_GB, where 12-hour am/pm is legitimate."""
    if not _rule(cfg, "6l_clock_24h"):
        return None
    if DATE_FORMAT_HINT.search(msgid):
        if re.search(r"[gh]:i(:s)?\s*[Aa]\b", msgstr):
            return Finding("6l", "WARNING", msgid, msgstr,
                           "Keeps 12-hour AM/PM format; this locale uses 24h (H:i)")
    return None


# --- 6m: localized wordpress.org host ------------------------------------------

def check_6m(msgid, msgstr, cfg):
    r = _rule(cfg, "6m_localized_host")
    if not r:
        return None
    host = r.get("host")
    if not host:
        return None
    if re.search(r"https://wordpress\.org/", msgstr):
        return Finding("6m", "INFO", msgid, msgstr,
                       f"Bare wordpress.org URL; consider {host} where a "
                       f"localized page exists")
    return None


def check_entry(msgid, fields, invariato_terms, cfg):
    """Run the applicable rules against one entry.

    Only requires msgstr to be non-empty. Unlike the checks' original prose
    gate ("non-empty AND different from msgid"), msgstr == msgid is NOT
    skipped, matching the fix glossary.py's find_candidates already tests for
    (test_untranslated_entry_is_still_checked): an untranslated Dashboard
    left as "Dashboard" is a real finding. The one check where msgstr ==
    msgid is the CORRECT state (6a) encodes that in its own condition."""
    msgstr = fields["msgstr"]
    if not msgstr:
        return []

    findings = []
    # Locale-neutral: always run.
    for f in (check_6a(msgid, msgstr, fields["extracted_comments"]),
              check_6b(msgid, msgstr, fields["flags"]),
              check_6c(msgid, msgstr),
              check_6d(msgid, msgstr)):
        if f:
            findings.append(f)

    # Locale-specific: run only what this locale's config enables.
    for f in (check_6e(msgid, msgstr, cfg),
              check_6f_title_case(msgid, msgstr, cfg),
              check_6f_months(msgid, msgstr, cfg),
              check_6g(msgid, msgstr, cfg),
              check_6h(msgid, msgstr, cfg),
              check_6i(msgid, msgstr, invariato_terms, cfg),
              check_6j(msgid, msgstr, cfg),
              check_6k(msgid, msgstr, cfg),
              check_6l(msgid, msgstr, cfg),
              check_6m(msgid, msgstr, cfg)):
        if f:
            findings.append(f)

    return findings


def run_checks(po_path, slug, data_dir, overlay_path=None, locale=None):
    """Run the applicable checks against every translated entry in po_path.

    Returns (findings, glossary_findings, rule_status). rule_status describes
    which rules ran for this locale so callers can be explicit about coverage
    rather than implying every rule was applied.

    `locale` selects data/locales/{LOCALE}.rules.json. When it is None or has
    no config file, ONLY the locale-neutral rules 6a-6d run: no locale's
    conventions are ever assumed for another. Read-only throughout."""
    with open(po_path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    blocks = parse_po_blocks(content)
    entries = load_glossary(slug, data_dir, overlay_path=overlay_path)
    invariato_terms = build_invariato_terms(entries)

    cfg, status = ({}, "neutral-only") if locale is None else load_locale_rules(locale, data_dir)
    rule_status = {
        "locale": locale,
        "status": status,
        "active": active_rule_ids(cfg),
        "inactive": inactive_rule_ids(cfg),
    }

    findings = []
    glossary_findings = []
    for msgid, block in blocks:
        if msgid is None or is_po_header_block(block):
            continue
        fields = parse_entry_fields(block)
        msgstr = fields["msgstr"]
        if not msgstr:
            continue
        findings.extend(check_entry(msgid, fields, invariato_terms, cfg))
        for c in find_candidates(entries, msgid, msgstr):
            glossary_findings.append(_with_msgid(c, msgid, msgstr))

    return findings, glossary_findings, rule_status


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
    try:
        findings, glossary_findings, rule_status = run_checks(
            po_path, slug, args.data_dir, overlay_path=args.overlay, locale=args.locale)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)

    by_sev = {"ERROR": [], "WARNING": [], "INFO": []}
    for f in findings:
        by_sev[f.severity].append(f)

    print(f"wp-polyglots-check: {po_path}")
    print(f"  ERROR   : {len(by_sev['ERROR'])}")
    print(f"  WARNING : {len(by_sev['WARNING'])}")
    print(f"  INFO    : {len(by_sev['INFO'])}")
    print(f"  GLOSSARY: {len(glossary_findings)} (needs model adjudication)")

    # State coverage explicitly. Silence here would let a user assume every
    # rule ran for their locale when most may not be configured.
    print(f"\nRule coverage for {args.locale}: {rule_status['status']}")
    if rule_status["status"] == "neutral-only":
        print(f"  No data/locales/{args.locale}.rules.json, so ONLY the")
        print(f"  locale-neutral rules ran: {', '.join(LOCALE_NEUTRAL_RULES)}")
        print(f"  (must-not-translate, fuzzy, placeholders, HTML tags) plus the")
        print(f"  glossary check. No style rules from any other locale were")
        print(f"  applied. Add that file to enable style checks for {args.locale}.")
    else:
        print(f"  active  : {', '.join(rule_status['active'])}")
        if rule_status["inactive"]:
            print(f"  inactive: {', '.join(rule_status['inactive'])}")
            print(f"  (inactive means not configured or not applicable for this")
            print(f"   locale, never that the string passed the rule)")
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
            "rule_status": rule_status,
            "findings": [f._asdict() for f in findings],
            "glossary_findings": [g._asdict() for g in glossary_findings],
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    sys.exit(1 if (findings or glossary_findings) else 0)


if __name__ == "__main__":
    main()
