# German (de_DE) - Polyglots style stub

Not a full handbook. This is a short stub covering only what
`typhography-rules.md` recorded, so a translator at least gets tone right
before someone writes the full ruleset. Expand from the official handbook
before relying on this for anything beyond tone and quoting.

## Tone

The **default** German glossary variant is the **informal `du`-Form**. A
separate **formal `Sie`-Form** glossary also exists on GlotPress - do not mix
the two within one plugin/theme. `data/glossaries/de.csv` in this repo is the
default (`du`) variant.

## Source

WordPress glossary for German (de_DE). Style guide (binding, uniform rules):
[https://de.wordpress.org/team/handbook/polyglots-team/style-guide/](https://de.wordpress.org/team/handbook/polyglots-team/style-guide/)

Introduction to the glossary:
[https://de.wordpress.org/team/handbook/polyglots-team/das-glossar/](https://de.wordpress.org/team/handbook/polyglots-team/das-glossar/)

Polyglots handbook:
[https://de.wordpress.org/team/handbook/polyglots-team/](https://de.wordpress.org/team/handbook/polyglots-team/)

## Glossary

`data/glossaries/de.csv` - 517 terms, columns `en,de,pos,description`.

## Not yet documented here

Capitalization (German capitalizes all nouns - this is grammar, not a style
choice, but edge cases around compound nouns and English loanwords are not
recorded here), punctuation, date/number formats. Read the style guide above
before translating anything beyond single glossary terms.

## Deterministic rule config

Machine-readable companion: `data/locales/de_DE.rules.json` (status: **partial**, 7 rules active, 6 inactive).

That file decides which of the deterministic checks 6e-6m `polyglots_check.py` applies to de_DE. Rules 6a-6d are locale-neutral and always run. A disabled rule records whether it is `not-applicable` (wrong for this locale) or `not-researched` (nobody has checked the handbook yet). Editing the prose here does not change what the script enforces; edit the JSON for that.
