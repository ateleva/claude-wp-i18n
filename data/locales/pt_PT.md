# Portuguese (pt_PT) - Polyglots style stub

Not a full handbook. `typhography-rules.md` only recorded the handbook link
for this locale, no tone/style notes. This stub is a placeholder pointing at
the source, not a ruleset - do not assume any tone convention from this file
alone.

## Source

Polyglots handbook (Portuguese, Portugal team) - locate the current handbook
URL under [https://pt.wordpress.org/team/handbook/](https://pt.wordpress.org/team/handbook/)
before translating; it was not captured in the source material for this file.

## Glossary

`data/glossaries/pt.csv` - 331 terms, columns `en,pt,pos,description`.

## Not yet documented here

Everything: tone, quoting, capitalization, punctuation, date/number formats.
Read the handbook before translating anything beyond single glossary terms.

## Deterministic rule config

Machine-readable companion: `data/locales/pt_PT.rules.json` (status: **minimal**, 9 rules active, 4 inactive).

That file decides which of the deterministic checks 6e-6m `polyglots_check.py` applies to pt_PT. Rules 6a-6d are locale-neutral and always run. A disabled rule records whether it is `not-applicable` (wrong for this locale) or `not-researched` (nobody has checked the handbook yet). Editing the prose here does not change what the script enforces; edit the JSON for that.
