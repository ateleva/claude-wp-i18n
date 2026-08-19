# Spanish (es_ES) - Polyglots style stub

Not a full handbook. This is a short stub covering only what
`typhography-rules.md` recorded, so a translator at least gets tone right
before someone writes the full ruleset. Expand from the official handbook
before relying on this for anything beyond tone and quoting.

## Tone and typography

- Always informal (**de "tú"**, never "usted").
- Always use **Spanish angle quotes**: `«comillas españolas»`
  (Windows: Alt+174 / Alt+175 - Mac: Shift+Alt+{ / Shift+Alt+}).
- No mid-sentence capitalization, except proper nouns and exceptions accepted
  by the RAE (Real Academia Española).
- Font proper names are not translated, **except** "System Fonts" ->
  "Fuentes del sistema" (that one is a setting label, not a proper name).

## Source

Glossary agreed for some es_ES (Spanish, Spain) translations.
Translators' guide:
[https://es.wordpress.org/team/handbook/traducciones/guia/](https://es.wordpress.org/team/handbook/traducciones/guia/)

Slack: #polyglots-es channel on Make WordPress Slack
([join instructions](https://es.wordpress.org/team/handbook/manuales/slack/)).

## Glossary

`data/glossaries/es.csv` - 474 terms, columns `en,es,pos,description`.

## Not yet documented here

Punctuation beyond quoting, date/number formats, capitalization edge cases
beyond the RAE-exception rule above. Read the translators' guide before
translating anything beyond single glossary terms.

## Deterministic rule config

Machine-readable companion: `data/locales/es_ES.rules.json` (status: **partial**, 9 rules active, 4 inactive).

That file decides which of the deterministic checks 6e-6m `polyglots_check.py` applies to es_ES. Rules 6a-6d are locale-neutral and always run. A disabled rule records whether it is `not-applicable` (wrong for this locale) or `not-researched` (nobody has checked the handbook yet). Editing the prose here does not change what the script enforces; edit the JSON for that.
