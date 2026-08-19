# English, UK (en_GB) - Polyglots style stub

Different in kind from the other five: en_GB is a **spelling-variant**
locale, not a foreign-language translation. There is no tone (tu/vous, formal
register) question - the source and target are both English. The glossary
itself carries most of what matters (British spelling: `colour` not `color`,
`organise` not `organize`, `licence`/`license` noun/verb distinction, etc.)
and correct capitalization of WordPress-specific UI terms.

## Glossary

`data/glossaries/en-gb.csv` - 390 terms, columns `en,en-gb,pos,description`.
Note the glossary slug is `en-gb` (hyphenated), not `en_gb` or `en`.

## Not yet documented here

Any en_GB-specific punctuation or date-format convention beyond standard
British English usage. No handbook link was captured in the source material
for this file - locate the current one under
[https://make.wordpress.org/polyglots/handbook/](https://make.wordpress.org/polyglots/handbook/)
before relying on more than the glossary.

## Deterministic rule config

Machine-readable companion: `data/locales/en_GB.rules.json` (status: **complete**, 4 rules active, 9 inactive).

That file decides which of the deterministic checks 6e-6m `polyglots_check.py` applies to en_GB. Rules 6a-6d are locale-neutral and always run. A disabled rule records whether it is `not-applicable` (wrong for this locale) or `not-researched` (nobody has checked the handbook yet). Editing the prose here does not change what the script enforces; edit the JSON for that.
