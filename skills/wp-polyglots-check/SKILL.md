---
name: wp-polyglots-check
description: >
  Checks a WordPress plugin or theme's .po translation file against locale-specific
  Polyglots style guidelines. Parses each translated string and reports compliance
  issues (tone, accents, capitalization, punctuation, untranslated-must-stay strings,
  placeholders, HTML tags, date formats, etc.) using locale instruction files you
  maintain under locales/. Use when asked to "check locale compliance", "check
  translation compliance", "verify polyglots rules", "check it_IT translations",
  or invokes /wp-polyglots-check.
user-invokable: true
argument-hint: "<locale e.g. it_IT> <plugin-or-theme-slug>"
allowed-tools:
  - Read
  - Bash
  - Edit
  - Write
---

# wp-polyglots-check

Checks a WordPress plugin or theme `.po` file for compliance with locale-specific
Polyglots style guidelines. Locale instruction files are maintained by the user
in `~/.claude/skills/wp-polyglots-check/locales/`.

---

## Step 1 — Parse arguments

Extract from the invocation:
- `LOCALE` — WP locale code (e.g. `it_IT`, `fr_FR`, `de_DE`)
- `SLUG` — plugin or theme folder name (e.g. `eleva-crm-for-photographers`, `fotonic-pro`)

If either is missing, ask the user to provide them before continuing. Do not proceed.

---

## Step 2 — STOP CHECK: locale instructions must exist first

**Before doing anything else**, check whether the locale instructions file exists:

```
~/.claude/skills/wp-polyglots-check/locales/{LOCALE}.md
```

If the file **does not exist**, stop immediately and tell the user:

> "No locale instructions found for `{LOCALE}`. Before I can check compliance,
> you need to create the file:
> `~/.claude/skills/wp-polyglots-check/locales/{LOCALE}.md`
> with the Polyglots style guidelines for that locale.
> You can find official guidelines at https://make.wordpress.org/polyglots/handbook/"

Do **not** fall back to generic checks. The locale file is required.

If the file exists, read it fully — it will be the reference for all subsequent checks.

---

## Step 3 — STOP CHECK: find the plugin/theme and its .po file

**Before doing anything else with translations**, locate:

1. The plugin or theme folder. Search in order:
   - Walk up from the current working directory looking for `wp-content/`
   - `wp-content/plugins/{SLUG}/`
   - `wp-content/themes/{SLUG}/`

2. Inside that folder, find the `languages/` directory.

3. Inside `languages/`, find the `.po` file for the locale. Try these patterns:
   - `languages/{TEXTDOMAIN}-{LOCALE}.po`  (most common)
   - `languages/{SLUG}-{LOCALE}.po`
   - `languages/{LOCALE}.po`

   List all `.po` files in that directory and pick the one matching the locale.

Run these Bash checks:
```bash
# Find plugin folder
find . -type d -name "{SLUG}" 2>/dev/null | head -5

# Find languages dir and .po files
find . -path "*/{SLUG}/languages/*.po" 2>/dev/null
```

If the plugin/theme folder is **not found**, stop and ask the user:
> "I couldn't find the `{SLUG}` folder. What is the full path to the plugin or theme?"

If the `languages/` directory is **not found**, stop and tell the user:
> "Found `{SLUG}` but it has no `languages/` directory. No translations to check."

If no `.po` file for `{LOCALE}` is found, stop and tell the user:
> "No `{LOCALE}.po` file found in `{SLUG}/languages/`. The translation file may not
> exist yet. Create it first, then run this check again."

---

## Step 4 — Report what was found and ask for confirmation

Before running any checks, summarize to the user what was found:

```
Found:
  Locale instructions : ~/.claude/skills/wp-polyglots-check/locales/{LOCALE}.md
  Plugin/theme folder : {FULL_PATH_TO_SLUG}
  .po file            : {FULL_PATH_TO_PO_FILE}

I will now read and check the translations for compliance with the {LOCALE} guidelines.
Note: if I find issues you want me to fix, I will ask your permission before editing
any .po or .mo file.

Proceed? (yes/no)
```

Wait for user confirmation before continuing.

---

## Step 5 — Parse the .po file

Read the full `.po` file. Extract each translation block:

```
#  (translator comment)
#. (extracted comment — identifies string type: Plugin Name, Author, etc.)
#: (source reference)
#, (flags: fuzzy, php-format, etc.)
msgctxt "..."
msgid "..."
msgid_plural "..."
msgstr "..."
msgstr[0] "..."
msgstr[1] "..."
```

Build a list of entries with all fields. The `#.` extracted comments are critical —
they identify strings that must NOT be translated:
- `Plugin Name of the plugin` / `Plugin name of the plugin` / `Theme Name of the theme`
- `Author of the plugin` / `Author of the theme`
- `Found in changelog list item`

---

## Step 6 — Run compliance checks

For each entry where `msgstr` is non-empty and different from `msgid`, apply the
checks from the locale instructions file. For `it_IT`, apply these (derived from the
locale instructions):

### 6a — Strings that must NOT be translated (hard errors)

Check `#.` comment for:
- `Plugin Name` / `Theme Name` → `msgstr` must equal `msgid` (copy original)
- `Author of the plugin` / `Author of the theme` → must be left as-is
- `Found in changelog list item` → must be left as-is

Flag as **ERROR** if `msgstr` differs from `msgid` for these.

### 6b — Fuzzy strings

If the entry has `#, fuzzy` flag and `msgstr` is non-empty, flag as **WARNING**:
> "String is marked fuzzy — needs review/approval before it goes live."

### 6c — Placeholders intact

Check that all placeholders in `msgid` are present in `msgstr`:
- `%s`, `%d`, `%f`
- `%1$s`, `%2$s`, `%1$d`, etc. (numbered)
- `###PLACEHOLDER###`

Flag as **ERROR** if any placeholder from `msgid` is missing in `msgstr`, or if the
order of numbered placeholders changed without good reason.

### 6d — HTML tags intact

Check that all HTML tags present in `msgid` are present in `msgstr` with correct
structure. The text content between tags should be translated, but the tags themselves
(`<a href="%s">`, `</a>`, `<strong>`, `</strong>`, etc.) must remain intact.

Flag as **ERROR** if an opening/closing tag is missing or malformed in `msgstr`.

### 6e — Accent errors (it_IT)

Check for common Italian accent mistakes:
- `e'` or `E'` used instead of `è` / `È` → **ERROR**
- `a'` instead of `à` → **WARNING**
- Missing acute accents: `ne` where `né` expected, `se` where `sé` expected,
  `perche` instead of `perché` → **WARNING** (context-dependent)

```python
import re
# e' as accent substitute
if re.search(r"\be'|\bE'", msgstr):
    flag error
```

### 6f — Capitalization (it_IT)

- Title Case detected: if 3+ consecutive words each start with uppercase and the
  string is more than 3 words, flag as **WARNING** (Italian doesn't use Title Case)
- Month names with capital letter: gennaio, febbraio, marzo, etc. should be lowercase
  → **WARNING** if found capitalized inside a sentence

### 6g — Punctuation (it_IT)

- Space before punctuation: check for ` ,` ` .` ` ;` ` :` ` ?` ` !` → **WARNING**
- Ellipsis should be exactly `…` (U+2026) or `...` (3 dots). Four or more dots → **WARNING**
- Oxford comma: `uno, due, e tre` pattern → **WARNING** (should be `uno, due e tre`)
- No space after opening bracket or before closing: `( testo )` → **WARNING**

### 6h — `&` as conjunction (it_IT)

If `msgid` contains ` & ` and `msgstr` also contains ` & ` (not inside an HTML entity
like `&amp;`), flag as **WARNING**: Italian should use `e` instead of `&`.

### 6i — English loan word plurals (it_IT)

Common loan words should appear without English plural `-s` in Italian text:
- `plugins` → should be `plugin`
- `themes` → should be `tema` or `temi` (not `themes`)
- `widgets` → should be `widget`
- `templates` → acceptable (can stay) but flag `templates` as **INFO**

Check: if `msgstr` contains `\bplugins\b` or `\bthemes\b` (case-insensitive) →
**WARNING**.

### 6j — Umanizzazione (it_IT)

If `msgid` starts with `Please ` and `msgstr` starts with `Si prega` or `Per favore`,
flag as **WARNING**: Italian guidelines say not to humanize device messages — drop "Please".

### 6k — Verbs ending in -ing translated literally (it_IT)

If `msgid` contains a gerund pattern like `Loading X`, `Saving X`, `Updating X` and
`msgstr` does NOT contain `in corso` → flag as **INFO**: Italian convention adds
"in corso…" (e.g. "Caricamento delle impostazioni in corso…").

### 6l — Date format strings (it_IT)

If `msgid` contains PHP date format chars (M, j, Y, g, i, A, G, H in combination):
- English: `M j, Y g:i A` → Italian should be `j M Y H:i`
- Check that AM/PM indicator (`A` or `a`) is NOT present in `msgstr` for Italian dates
- Check that 24h format (`H` or `G`) is used in `msgstr`

Flag as **WARNING** if `msgstr` still contains `g:i A` or `h:i A` patterns.

### 6m — `wordpress.org` URLs (it_IT)

If `msgstr` contains a URL starting with `https://wordpress.org/` → flag as **INFO**:
Consider using `https://it.wordpress.org/` where an Italian page exists.

---

## Step 7 — Report findings

Output a structured compliance report:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WP Polyglots Compliance Report
  Locale  : {LOCALE}
  Plugin  : {SLUG}
  File    : {PO_FILE_PATH}
  Checked : {DATE}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Summary
  Total strings   : {N}
  Translated      : {N}
  Skipped (empty) : {N}
  ERRORs          : {N}
  WARNINGs        : {N}
  INFOs           : {N}

━━ ERRORS (must fix) ━━━━━━━━━━━━━━━━━━━

[E1] Must not be translated (Plugin Name / Author / Changelog)
  msgid  : "..."
  msgstr : "..."   ← should equal msgid
  Rule   : Strings with comment "Plugin Name of the plugin" must be copied verbatim.

...

━━ WARNINGS (should fix) ━━━━━━━━━━━━━━━

[W1] Accent error — apostrophe used instead of accented vowel
  msgid  : "..."
  msgstr : "...e'..."   ← should be "...è..."
  Rule   : Never use e' as a substitute for è.

...

━━ INFO (consider) ━━━━━━━━━━━━━━━━━━━━━

[I1] Date format may need Italian order
  msgid  : "M j, Y g:i A"
  msgstr : "M j, Y g:i A"   ← consider "j M Y H:i"
  Rule   : Italian dates use day-month-year, 24h clock, no AM/PM.

...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Step 8 — Offer to fix issues

After the report, ask the user:

> "Would you like me to fix the issues found?
> I will only edit the `.po` file (and recompile `.mo` if msgfmt is available).
> I will show you each change before applying it. Proceed?"

**Only start editing after the user explicitly says yes.**

When editing:
- Fix only what was flagged — do not change correct strings
- Use the Edit tool for `.po` file changes
- After `.po` edits, offer to compile the `.mo`:
  ```bash
  msgfmt {PO_FILE} -o {MO_FILE}
  ```
- Ask permission before running msgfmt.
