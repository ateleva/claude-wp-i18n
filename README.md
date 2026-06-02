# wp-code-translate

A Claude Code skill that automates the full WordPress i18n pipeline for **plugins and themes**.

> **Not a content translation tool.** This skill generates `.pot` / `.po` / `.mo` / `.json` translation files from your plugin or theme source code — the developer workflow. It does not translate pages, posts, or WooCommerce products. For that, use Polylang or WPML.

---

## What it does

Given a plugin or theme slug and a list of target languages, it:

1. Scans all `.php`, `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs` files for translatable strings
2. Diffs against existing `.pot` to find new strings only
3. Shows a token cost estimate and asks for confirmation before translating
4. Translates new strings using Claude (batched, validated)
5. Creates or updates `.po` files per locale
6. Compiles `.mo` binaries via `msgfmt`
7. Generates WP JS JSON sidecars (for `wp_set_script_translations()`)

No wp-cli. No Poedit. No manual `.pot` editing. Pure Python 3 + GNU gettext.

---

## Requirements

- [Claude Code](https://claude.ai/code) — the CLI tool
- Python 3 (`python3 --version`)
- GNU gettext / msgfmt — install on macOS: `brew install gettext && brew link gettext --force`

---

## Installation

Clone into your Claude Code skills directory:

```bash
git clone https://github.com/ateleva/claude-wp-code-translate ~/.claude/skills/wp-code-translate
```

No additional config needed. Claude Code picks up skills automatically from `~/.claude/skills/`.

---

## Usage

```
/wp-code-translate plugin <slug> <lang-codes>
/wp-code-translate theme  <slug> <lang-codes>
```

### Examples

```
# Translate a plugin to Italian
/wp-code-translate plugin my-plugin it

# Translate a plugin to multiple languages
/wp-code-translate plugin my-plugin it,fr,de,es

# Translate a theme
/wp-code-translate theme my-theme it,fr
```

Lang codes are ISO 639-1 short codes (see [supported languages](#supported-languages)).

---

## What gets generated

For each locale, inside `{plugin-or-theme}/languages/`:

| File | Description |
|------|-------------|
| `{textdomain}.pot` | Master translation template |
| `{textdomain}-{locale}.po` | Translation source (human-readable) |
| `{textdomain}-{locale}.mo` | Compiled binary loaded by WordPress |
| `{textdomain}-{locale}-{hash}.json` | JS runtime translations (if plugin uses `wp_set_script_translations()`) |

A `.bak` backup is created before any existing `.po` is modified.

---

## How it works

### String extraction

Extracts all standard WP i18n function calls from PHP and JS/TS source files:

**PHP:** `__()`, `_e()`, `_n()`, `_x()`, `_nx()`, `esc_html__()`, `esc_html_e()`, `esc_attr__()`, `esc_attr_e()`, `_n_noop()`, `_nx_noop()`

**JS/TS:** `__()`, `_n()`, `_x()`, `_nx()`, `sprintf()`

Skips `node_modules/`, `vendor/`, `.git/`. Does **not** skip `build/` or `dist/` by default (some plugins serve JS directly from those dirs).

### Text domain detection

Auto-detects from plugin header (`Text Domain:` in main plugin file) or theme `style.css`. Warns and confirms if it can't be found.

### JS JSON sidecars

Detects `wp_set_script_translations()` calls, maps each handle back to its enqueued script src, computes `md5(relative_src_path)` for the correct filename. PHP-only plugins get no JSON file (`.mo` is sufficient).

---

## Supported languages

| Code | Locale | Language |
|------|--------|----------|
| `it` | it_IT | Italian |
| `fr` | fr_FR | French |
| `de` | de_DE | German |
| `es` | es_ES | Spanish |
| `pt` | pt_PT | Portuguese |
| `pt_BR` | pt_BR | Portuguese (Brazil) |
| `nl` | nl_NL | Dutch |
| `ru` | ru_RU | Russian |
| `pl` | pl_PL | Polish |
| `cs` | cs_CZ | Czech |
| `sv` | sv_SE | Swedish |
| `da` | da_DK | Danish |
| `fi` | fi | Finnish |
| `nb` | nb_NO | Norwegian Bokmål |
| `tr` | tr_TR | Turkish |
| `ko` | ko_KR | Korean |
| `he` | he_IL | Hebrew |
| `uk` | uk | Ukrainian |
| `ro` | ro_RO | Romanian |
| `hu` | hu_HU | Hungarian |
| `el` | el | Greek |
| `bg` | bg_BG | Bulgarian |
| `hr` | hr | Croatian |
| `sk` | sk_SK | Slovak |
| `lt` | lt_LT | Lithuanian |
| `lv` | lv | Latvian |
| `et` | et | Estonian |
| `id` | id_ID | Indonesian |
| `th` | th | Thai |
| `vi` | vi | Vietnamese |
| `ar` | ar | Arabic |
| `ja` | ja | Japanese |
| `zh` | zh_CN | Chinese (Simplified) |
| `zh_TW` | zh_TW | Chinese (Traditional) |

---

## Differences from similar tools

| Tool | Purpose |
|------|---------|
| **wp-code-translate** | Generate translation files for your own plugin/theme code |
| Loco Translate | Translate strings in already-installed plugins/themes via WP admin |
| WPML / Polylang | Translate site content (pages, posts, custom fields) |
| WP-CLI i18n | Official CLI for `.pot` extraction — requires WP-CLI installed |

---

## License

MIT
