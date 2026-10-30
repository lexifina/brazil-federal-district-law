# Distrito Federal: law history in git

The law of the Federal District (Distrito Federal) (Brazil) as a git history: one file per Artigo, one paragraph per line, so `git blame`, `git log` and `git diff` work line by line. The text is Portuguese, the only official language.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law).

## What this repository holds

| Folder | Act | Versions |
| --- | --- | ---: |
| `lc-<year>-<number>/` | the Leis Complementares SINJ-DF lists as "Sem Revogação Expressa", "Alterado" or "Suspenso" (revoked, void and unconstitutional ones are left out) | 1 each |

**Partial:** the Lei Orgânica do Distrito Federal (the DF's constitution) and ordinary Leis are not in yet. An act SINJ-DF shows no alteration for is given **as enacted**, credited to the act itself. An altered act is given **only as its text in force**, credited to SINJ-DF as the oldest version available: the wordings in between are not reconstructed yet, so no earlier version is shown rather than a wrong one.

## Source

[SINJ-DF](https://www.sinj.df.gov.br/sinj/), published by the Sistema Integrado de Normas Jurídicas do Distrito Federal (SINJ-DF). Each version names the page it was taken from and that page's sha256, in `data/versions.json`.

## Dates

An unaltered act is dated by its publication in the Diário Oficial do Distrito Federal (DODF) as the text's closing line names it ("Este texto não substitui o publicado no DODF nº ..., de <date>"), or by its signature when there is none. An altered act's text in force is dated by the latest date among the alterations SINJ-DF's notes cite ("(Artigo alterado(a) pelo(a) Lei Complementar 783 de 30/10/2008)"); "Vide" and "Legislação correlata" notes do not date a version. Commits are at noon in Brasília.

## How it is built

Lexifina reads the sources listed here and records each act's dated versions, and the laws that made each change, in one corpus file. `tools/build.py` writes this repository from that file, and the same corpus always gives the same commit hashes; `REPRODUCE.md` gives the details and the checks. A model (Claude) wrote Lexifina's code; it wrote no legal text, and no model runs when the history is built.

Each compiled text becomes one file per Art. ("Art. 4°-A" is its own file); headings of the Títulos, Capítulos and Seções stand above the first article under them; `000-titulo.md` holds the title, the ementa and the preamble. For the text in force, the earlier wordings the compiled text strikes through, the alteration notes, the "Legislação correlata" links, the heading "Texto Compilado" and the closing DODF notice are left out. Older files that are plain text (one paragraph a line) are split at their line breaks.

## How it is checked

Every version is read back from git on the day it took effect (`tools/check_repo.py`) and must match the corpus; an independent letters-and-digits comparison of every version against the source page must show no difference. Results are in `REPRODUCE.md`.

## What "author" means

The author of each commit is the law that made the text, or, for a consolidated text, the publisher, with an e-mail address that cannot exist; the committer is always Lexifina.

## Limits

Not a complete history: an altered act starts at its text in force; an altered act whose notes cite no date is left out. The text is not the official version: only the DODF is authoritative. Text after the last article (place, date, signatures, annexes) stays in the last article's file.

## Licence

See [LICENSE](LICENSE): Brazilian law texts are not protected by copyright (Lei 9.610/1998, art. 8, IV). Fonte: SINJ-DF, Sistema Integrado de Normas Jurídicas do Distrito Federal (SINJ-DF).
