# Deterministic rule reference (6a-6m)

Human reference for the checks implemented in `scripts/polyglots_check.py`.
The script is the source of truth; this file explains what each rule means
and why, for when you need to justify a finding to a translator.

Rule ids are kept from the pre-plugin version of this skill, where these
lived as prose in SKILL.md Step 6, so older reports stay comparable.

| Rule | Severity | What it catches |
|------|----------|-----------------|
| 6a | ERROR | Plugin Name / Theme Name / Author / changelog string was translated. These come from the plugin header or readme and must be copied verbatim. |
| 6b | WARNING | Entry flagged `fuzzy` but has content. Needs human review before it goes live. |
| 6c | ERROR | A `%s`, `%d`, `%1$s`, or `###PLACEHOLDER###` present in msgid is missing from msgstr, or numbered placeholders were reordered. |
| 6d | ERROR | An HTML tag present in msgid is missing or malformed in msgstr. |
| 6e | ERROR | `e'` / `E'` typed instead of `è` / `È`. |
| 6f | WARNING | Title Case, or a month name capitalised mid-sentence. Italian uses sentence case. |
| 6g | WARNING | Space before punctuation, space inside parentheses, 4+ dot ellipsis, or an Oxford comma before `e`. |
| 6h | WARNING | `&` used as a conjunction. Italian uses `e`. Ignores `&amp;`. |
| 6i | WARNING | English `-s` plural on a loanword the glossary marks invariato. |
| 6j | WARNING | `Please` humanised as "Si prega" / "Per favore". Italian device messages drop it. |
| 6k | INFO | English gerund rendered without "in corso". |
| 6l | WARNING | Date format keeps 12-hour AM/PM. Italian uses 24-hour `H:i`. |
| 6m | INFO | Bare `wordpress.org` URL where an `it.wordpress.org` page exists. |

## Notes on two rules that changed when they moved into code

**6i was generalised.** The prose version hardcoded three loanwords
(`plugins`, `themes`, `widgets`). The script now derives the list from the
locale glossary itself: every term whose translation equals the English term
(roughly 130 entries in `it.csv` - `account`, `blog`, `editor`, `backend`,
`breadcrumb`, and so on). Adding a term to the glossary now extends this
rule automatically.

**6a was tightened.** Matching "plugin name" as a bare substring anywhere in
a `#.` comment produced a false positive against a developer's own
translators note (`#. translators: 1: Plugin name "Eleva CRM Pro" 2: ...`).
The rule now requires the comment to *start with* one of WP.org's canonical
marker phrases, which is how its own POT generator emits them.

## Locale scope

**6a-6d are locale-neutral** and always run: they check WP.org structural
markers, the fuzzy flag, placeholders, and HTML tags. None depends on the
target language.

**6e-6m are locale-specific** and run only where
`data/locales/{LOCALE}.rules.json` enables them. A locale with no config
file gets the locale-neutral rules and the glossary check, nothing else.

That default is deliberate. Applying one locale's conventions to another
does not give generic advice, it instructs the translator to break their own
rules. Every one of these was a real defect before the config existed:

| Locale | What the Italian rule did |
|--------|---------------------------|
| `de_DE` | Flagged `Add-ons` as an error and said to drop the `-s`. That is the German glossary's OWN documented plural (`add-ons -> Add-ons`, Mehrzahl). |
| `de_DE` | Told a German translator to replace `&` with the Italian `e` rather than `und`. |
| `de_DE` | Would flag every correctly capitalised German noun and month as Title Case. |
| `fr_FR` | Flagged `Voulez-vous vraiment ?` as "space before punctuation". French typography REQUIRES that space. |
| `en_GB` | Would flag ordinary English Title Case, capitalised months, `&`, and 12-hour am/pm clocks, none of which are errors in English. |

### Rule config format

`data/locales/{LOCALE}.rules.json`:

```json
{
  "locale": "it_IT",
  "_status": "complete",
  "rules": {
    "6h_ampersand": { "enabled": true, "conjunction": "e" },
    "6i_loanword_plural": { "enabled": false, "_why": "not-applicable: ..." }
  }
}
```

Every disabled rule must carry a `_why` (a test enforces this), and the
wording distinguishes two very different states:

- **`not-applicable`** - the rule is wrong for this locale and should stay
  off permanently. German loanword plurals, French punctuation spacing.
- **`not-researched`** - the rule might well apply, but nobody has checked
  that locale's handbook yet. Safe to investigate and enable.

`_status` is `complete`, `partial`, or `minimal`, describing how far the
locale has actually been verified against its own handbook. Only `it_IT` and
`en_GB` are `complete`, and `en_GB` only because almost nothing applies to it.
