# French (fr_FR) - Polyglots style stub

Not a full handbook. This is a short stub covering only what
`typhography-rules.md` recorded, so a translator at least gets tone right
before someone writes the full ruleset. Expand from the official handbook
before relying on this for anything beyond tone and quoting.

## Source

Welcome to the fr_FR (langue française en France) glossary for WordPress!
Bienvenue dans le glossaire de WordPress pour la langue française en France
(fr_FR) !

Typography rules for translating WP into French:
[https://fr.wordpress.org/team/handbook/polyglots/les-regles-typographiques-utilisees-pour-la-traduction-de-wp-en-francais/](https://fr.wordpress.org/team/handbook/polyglots/les-regles-typographiques-utilisees-pour-la-traduction-de-wp-en-francais/)

## Glossary

`data/glossaries/fr.csv` - 603 terms, columns `en,fr,pos,description`.

## Not yet documented here

Tone (tu vs vous), capitalization rules, punctuation spacing (French uses a
non-breaking space before `; : ! ?`), date/number formats. Read the
typography rules page above before translating anything beyond single
glossary terms.

## Deterministic rule config

Machine-readable companion: `data/locales/fr_FR.rules.json` (status: **partial**, 8 rules active, 5 inactive).

That file decides which of the deterministic checks 6e-6m `polyglots_check.py` applies to fr_FR. Rules 6a-6d are locale-neutral and always run. A disabled rule records whether it is `not-applicable` (wrong for this locale) or `not-researched` (nobody has checked the handbook yet). Editing the prose here does not change what the script enforces; edit the JSON for that.
