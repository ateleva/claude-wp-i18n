# wp-i18n

A **Claude Code plugin** for the WordPress developer i18n workflow: generate translation files from your plugin or theme source, check them against the WordPress.org Polyglots glossary and locale style rules, and diagnose why a translated string is still rendering in English.

Three skills, one shared glossary and rules layer.

> **Not a content translation tool.** This generates `.pot` / `.po` / `.mo` / `.json` files from source code. It does not translate pages, posts, or WooCommerce products. For that, use Polylang or WPML.

> **Upgrading from `claude-wp-code-translate`?** This repo was a single skill installed into `~/.claude/skills/wp-code-translate/`. It is now a plugin bundling three skills. See [Migrating](#migrating-from-the-old-single-skill).

---

## The three skills

| Skill | What it does | Writes files? |
|-------|--------------|---------------|
| **`/wp-code-translate`** | Extracts strings, updates `.pot`/`.po`, compiles `.mo`, generates JS sidecars. Translates using the locale's glossary and tone. | Yes |
| **`/wp-polyglots-check`** | Checks a `.po` against Polyglots style rules and the glossary. Optionally fixes what it finds. | Only after you approve |
| **`/wp-i18n-doctor`** | Diagnoses why a translated string renders in English, walking all five stages from source call to the file WP core actually loads. | Never. Read-only by design |

They compose: translate, check, then verify the chain. The doctor is safe to run anywhere, including against a production plugin directory.

---

## Why the glossary layer exists

WordPress.org Polyglots teams maintain a per-locale glossary of binding term translations. A plugin author who wants their translations approved (or who is a PTE approving them) has to follow it.

Generic machine translation does not. Left to itself it will render `required` as *richiesta* when the Italian glossary says *necessario*, translate `Dashboard` as *Dashboard* when the glossary says *Bacheca*, and pick a formal register for locales whose Polyglots teams mandate the informal one.

This plugin makes the glossary and the locale style rules a first-class input to both translating and checking.

**Glossaries are fetched live** from `translate.wordpress.org` and cached, so they do not go stale as teams add terms:

```bash
python3 scripts/glossary.py fetch --slug it
```

Any GlotPress locale slug works, not just the six seeded here.

---

## Requirements

- [Claude Code](https://claude.ai/code)
- Python 3, standard library only. No pip packages
- GNU gettext (`msgfmt`). On macOS: `brew install gettext && brew link gettext --force`

---

## Installation

```
/plugin marketplace add ateleva/claude-wp-i18n
/plugin install wp-i18n
```

Then restart Claude Code. All three skills become available.

### Migrating from the old single skill

If you previously cloned this repo into `~/.claude/skills/wp-code-translate/`, remove or rename that directory first. A personal skill of the same name **shadows** the plugin's copy, so you would keep running the old glossary-unaware version:

```bash
mv ~/.claude/skills/wp-code-translate ~/.claude/skills/wp-code-translate.bak
```

---

## Usage

### Translate a plugin or theme

```
/wp-code-translate plugin <slug> <lang-codes>
/wp-code-translate theme  <slug> <lang-codes>
```

```
/wp-code-translate plugin my-plugin it
/wp-code-translate plugin my-plugin it,fr,de,es
/wp-code-translate theme  my-theme  it,fr
```

It shows a token estimate and waits for confirmation before translating. Answer `pot-only` to refresh the `.pot` without translating anything.

### Check translations for compliance

```
/wp-polyglots-check <locale> <slug>
/wp-polyglots-check it_IT my-plugin
/wp-polyglots-check it_IT my-plugin --fix auto
```

Read-only until it asks. Output looks like:

```
Deterministic   ERROR 0  WARNING 10  INFO 3
Glossary        47 candidates -> 12 real, 35 false positive
```

The deterministic findings are mechanical and final. The glossary candidates are extracted mechanically and then judged in context, because a glossary lemma is not a ready-made translation.

### Diagnose a string stuck in English

```
/wp-i18n-doctor plugin <slug> [locale]
/wp-i18n-doctor plugin my-plugin it_IT
```

Reports which of the five stages dropped the string: `NOT_IN_POT`, `NOT_IN_PO`, `EMPTY_MSGSTR`, `NOT_IN_SIDECAR`, `NO_SIDECAR`, `NO_HANDLE`.

---

## What gets generated

Inside `{plugin-or-theme}/languages/`:

| File | Description |
|------|-------------|
| `{textdomain}.pot` | Master template |
| `{textdomain}-{locale}.po` | Translation source, human-readable |
| `{textdomain}-{locale}.mo` | Compiled binary WordPress loads |
| `{textdomain}-{locale}-{hash}.json` | JS runtime translations, if the plugin calls `wp_set_script_translations()` |

A `.bak` is written before any existing `.po` is modified.

Editing a `.po` always triggers all three of: recompile `.mo`, regenerate the JS sidecar, re-run the doctor. Skipping the sidecar step is the single most common cause of "the `.po` is complete but the site shows English" and produces no error anywhere.

---

## Project glossary overlays

A locale glossary sometimes needs a project-specific ruling. GlotPress supports this with project glossaries that outrank the locale glossary, and so does this plugin.

Create `{your-plugin}/.i18n/glossary-{LOCALE}.csv`, same four columns as the WP.org export:

```csv
en,it,pos,description
"required plugin","plugin richiesto",expression,"Loanword noun keeps richiesto, not the bare lemma necessario."
"required plugins","plugin richiesti",expression,"Plural agreement for the above."
```

Both skills pick it up automatically. Overlay entries win over locale entries, and are labelled `overlay` in reports so you can tell which ruling applied.

---

## Italian morphology

The glossary gives a lemma. Italian needs agreement. Fixes are inflected to match the noun, never substituted blindly:

```
required          -> necessario / necessaria / necessari / necessarie
required plugin   -> plugin richiesto
required plugins  -> plugin richiesti
```

`Password is required.` becomes `La password è necessaria.`, agreeing with the feminine *password*.

When gender or number cannot be determined from the string, or the glossary offers multiple targets, or the part of speech does not match the usage, the skill stops and asks. That holds even in `--fix auto` mode.

---

## Repository layout

```
.claude-plugin/
  plugin.json            plugin manifest
  marketplace.json       marketplace entry
skills/
  wp-code-translate/     translate
  wp-polyglots-check/    check and fix
  wp-i18n-doctor/        diagnose, read-only
data/
  glossaries/            per-locale CSVs + fetch metadata
  locales/
    {LOCALE}.md          human-readable style rules and tone
    {LOCALE}.rules.json  which deterministic rules apply to that locale
  locale-map.md          locale code, plural forms, glossary slug
scripts/
  glossary.py            fetch / cache / lookup / candidate extraction
  polyglots_check.py     deterministic rules 6a-6m
  extract_strings.py     source string extraction
  pot_manager.py         .pot create / diff / update
  po_manager.py          .po create / update / dedup
  json_generator.py      JS sidecar generation
  i18n_doctor.py         five-stage chain diagnostic
tests/                   40 unit tests, stdlib unittest
```

Run the tests with:

```bash
python3 -m unittest discover -s tests
```

---

## Locale coverage

Glossaries are seeded for six locales and fetchable for any.

| Locale | Glossary | Style rules |
|--------|----------|-------------|
| `it_IT` | 520 terms | Full handbook |
| `fr_FR` | 603 terms | Stub, tone and handbook link |
| `de_DE` | 517 terms | Stub, informal `du` variant |
| `es_ES` | 474 terms | Stub, informal `tú`, angle quotes |
| `pt_PT` | 331 terms | Stub, handbook pointer only |
| `en_GB` | 390 terms | Stub, spelling variant locale |

Any other locale still works for extraction, `.pot`/`.po`/`.mo` generation, and sidecars. Fetch its glossary with `glossary.py fetch --slug <slug>`.

### Style rules are scoped per locale

Rules 6a-6d (must-not-translate, fuzzy, placeholders, HTML tags) are locale-neutral and always run. Everything else is language-specific and runs only where `data/locales/{LOCALE}.rules.json` enables it.

**A locale with no rule config gets the locale-neutral rules and the glossary check, nothing else,** and the report says so explicitly. No locale ever inherits another's conventions, because that does not produce vague advice, it tells the translator to break their own rules:

| Locale | What a one-size-fits-all Italian rule would do |
|--------|-----------------------------------------------|
| `de_DE` | Flag `Add-ons` and say to drop the `-s`. That is the German glossary's own documented plural (Mehrzahl). |
| `de_DE` | Tell a German translator to use `e` instead of `und`. |
| `fr_FR` | Flag `Voulez-vous vraiment ?`. French typography *requires* that space before `?`. |
| `en_GB` | Flag ordinary Title Case, capitalised months, `&`, and 12-hour clocks. |

Each config records why a rule is off, distinguishing **`not-applicable`** (wrong for this locale, leave off) from **`not-researched`** (nobody has read that handbook yet, safe to enable once someone does). Per-locale coverage is in the table above; see `skills/wp-polyglots-check/references/rules.md` for the format.

---

## Differences from similar tools

| Tool | Purpose |
|------|---------|
| **wp-i18n** | Generate, glossary-check, and debug translation files for your own plugin/theme code |
| Loco Translate | Translate already-installed plugins/themes via WP admin |
| WPML / Polylang | Translate site content: pages, posts, custom fields |
| WP-CLI i18n | Official CLI for `.pot` extraction. Requires WP-CLI |
| GlotDict | Browser extension adding glossary hints inside translate.wordpress.org |

---

## Credits

Glossary data is fetched from [translate.wordpress.org](https://translate.wordpress.org) and belongs to the respective WordPress Polyglots locale teams. The Italian style rules in `data/locales/it_IT.md` are reproduced from the [Italian Polyglots handbook](https://it.wordpress.org/team/handbook/polyglots/).

## License

MIT
