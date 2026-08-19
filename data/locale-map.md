# WP Locale Map

Short ISO 639-1 code → WordPress locale code

`Glossary slug` is the GlotPress locale slug used in the glossary export URL
(`https://translate.wordpress.org/locale/{slug}/default/glossary/-export/?format=csv`)
and in `data/glossaries/{slug}.csv`. It is only filled in where it differs
unpredictably from `Short` (`en_GB` -> `en-gb`, not `en`) or where a glossary
file actually exists in this repo — most locales have neither yet.

| Short | WP Locale | Language | Plural forms | Glossary slug |
|-------|-----------|----------|--------------|----------------|
| it | it_IT | Italian | nplurals=2;plural=(n!=1); | it |
| fr | fr_FR | French | nplurals=2;plural=(n>1); | fr |
| de | de_DE | German | nplurals=2;plural=(n!=1); | de |
| es | es_ES | Spanish | nplurals=2;plural=(n!=1); | es |
| pt | pt_PT | Portuguese | nplurals=2;plural=(n!=1); | pt |
| en_GB | en_GB | English (UK) | nplurals=2;plural=(n!=1); | en-gb |
| pt_BR | pt_BR | Portuguese (Brazil) | nplurals=2;plural=(n>1); | pt-br |
| ar | ar | Arabic | nplurals=6;plural=(n==0?0:n==1?1:n==2?2:n%100>=3&&n%100<=10?3:n%100>=11&&n%100<=99?4:5); | |
| ja | ja | Japanese | nplurals=1;plural=0; | |
| zh | zh_CN | Chinese (Simplified) | nplurals=1;plural=0; | |
| zh_TW | zh_TW | Chinese (Traditional) | nplurals=1;plural=0; | |
| nl | nl_NL | Dutch | nplurals=2;plural=(n!=1); | |
| ru | ru_RU | Russian | nplurals=3;plural=(n%10==1&&n%100!=11?0:n%10>=2&&n%10<=4&&(n%100<10||n%100>=20)?1:2); |
| pl | pl_PL | Polish | nplurals=3;plural=(n==1?0:n%10>=2&&n%10<=4&&(n%100<10||n%100>=20)?1:2); |
| cs | cs_CZ | Czech | nplurals=3;plural=(n==1)?0:(n>=2&&n<=4)?1:2; |
| sv | sv_SE | Swedish | nplurals=2;plural=(n!=1); |
| da | da_DK | Danish | nplurals=2;plural=(n!=1); |
| fi | fi | Finnish | nplurals=2;plural=(n!=1); |
| nb | nb_NO | Norwegian Bokmål | nplurals=2;plural=(n!=1); |
| tr | tr_TR | Turkish | nplurals=2;plural=(n>1); |
| ko | ko_KR | Korean | nplurals=1;plural=0; |
| he | he_IL | Hebrew | nplurals=2;plural=(n!=1); |
| uk | uk | Ukrainian | nplurals=3;plural=(n%10==1&&n%100!=11?0:n%10>=2&&n%10<=4&&(n%100<10||n%100>=20)?1:2); |
| ro | ro_RO | Romanian | nplurals=3;plural=(n==1?0:(n==0||(n%100>0&&n%100<20))?1:2); |
| hu | hu_HU | Hungarian | nplurals=2;plural=(n!=1); |
| el | el | Greek | nplurals=2;plural=(n!=1); |
| bg | bg_BG | Bulgarian | nplurals=2;plural=(n!=1); |
| hr | hr | Croatian | nplurals=3;plural=(n%10==1&&n%100!=11?0:n%10>=2&&n%10<=4&&(n%100<10||n%100>=20)?1:2); |
| sk | sk_SK | Slovak | nplurals=3;plural=(n==1)?0:(n>=2&&n<=4)?1:2; |
| lt | lt_LT | Lithuanian | nplurals=3;plural=(n%10==1&&n%100!=11?0:n%10>=2&&(n%100<10||n%100>=20)?1:2); |
| lv | lv | Latvian | nplurals=3;plural=(n%10==1&&n%100!=11?0:n!=0?1:2); |
| et | et | Estonian | nplurals=2;plural=(n!=1); |
| id | id_ID | Indonesian | nplurals=1;plural=0; |
| th | th | Thai | nplurals=1;plural=0; |
| vi | vi | Vietnamese | nplurals=1;plural=0; |
