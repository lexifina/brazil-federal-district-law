"""Builds corpus.d parts for the Distrito Federal from the retrieved SINJ-DF text files (no network).

    python -X utf8 parse.py --today YYYY-MM-DD [--part-size 50] [--dry]

SINJ-DF (Sistema Integrado de Normas Jurídicas do DF) keeps each act's compiled text ("Texto Compilado"): earlier
wordings struck through (<s>, in paragraphs marked replaced_by), each alteration noted by a link of class "link_vide"
("(Artigo alterado(a) pelo(a) Lei Complementar 783 de 30/10/2008)"), "Legislação correlata" links in paragraphs that
carry a ch_norma_info attribute, and a closing line "Este texto não substitui o publicado no DODF nº ..., de <date>".
An act with no alteration note and nothing struck through is given as enacted, credited to the act itself and dated by
that DODF date; an altered act only as its text in force, credited to SINJ-DF as the oldest version available, dated
by the latest date its alteration notes cite.
"""
import argparse, html, json, re, sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from br_lib import lines_of, units_of, write_part, sha, norm  # noqa: E402

CACHE = HERE / '.cache'
BLOCK = {'p', 'div', 'br', 'tr', 'li', 'table', 'tbody', 'thead', 'ul', 'ol', 'center', 'blockquote', 'h1', 'h2', 'h3',
         'h4', 'h5', 'h6'}
VOID = {'br', 'img', 'meta', 'link', 'hr', 'input', 'col', 'area', 'base', 'wbr'}
BOILER = re.compile(r'^(?:Texto Compilado|Texto Original|Este texto n[ãa]o substitui o publicado no DODF\b.*|'
                    r'Legisla[çc][ãa]o correlata\s*-.*)$', re.I)
P_CLOSERS = {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'ul', 'ol', 'blockquote', 'center', 'pre', 'hr'}
DODF = re.compile(r'Este texto n[ãa]o substitui o publicado no DODF\b[^\n]*?(\d{1,2}/\d{1,2}/\d{4})', re.I)


class Split(HTMLParser):
    """Text as shown, without struck-through runs (old), link_vide notes and ch_norma_info paragraphs (notes). A <p>
    start tag ends an open <p>, as in a browser (SINJ leaves paragraphs unclosed)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.kept, self.old, self.notes = [], [], [], []

    def state(self):
        if any(e[1] == 'old' for e in self.stack):
            return 'old'
        if any(e[1] == 'note' for e in self.stack):
            return 'note'
        return None

    def handle_starttag(self, tag, attrs):
        if tag in P_CLOSERS:  # these start tags end an open <p>, as in a browser
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == 'p':
                    del self.stack[i:]
                    break
        if tag in BLOCK:
            self.kept.append('<br>')
            self.notes.append('\n')
        if tag in VOID:
            return
        a = dict(attrs)
        st = (a.get('style') or '').lower()
        cls = (a.get('class') or '').split()
        if tag in ('s', 'strike', 'del') or 'line-through' in st:
            c = 'old'
        elif 'link_vide' in cls or 'ch_norma_info' in a:
            c = 'note'
        else:
            c = None
        self.stack.append((tag, c))

    def handle_endtag(self, tag):
        if tag in BLOCK:
            self.kept.append('<br>')
            self.notes.append('\n')
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, d):
        st = self.state()
        if st == 'old':
            self.old.append(d)
        elif st == 'note':
            self.notes.append(d)
        else:
            self.kept.append(html.escape(d, quote=False))


def plain_breaks(h):
    """Older SINJ files (TextoArquivoNorma.aspx) hold plain text in <div id="div_texto"> with a newline between
    paragraphs and no tags: there a newline is a paragraph break."""
    m = re.search(r'(?is)<div id="div_texto">(.*?)</div>', h)
    if m and not re.search(r'(?i)<(p|br|h\d)\b', m.group(1)):
        h = h[:m.start(1)] + m.group(1).replace('\n', '<br>') + h[m.end(1):]
    return h


def body(h):
    h = re.sub(r'(?is)<script.*?</script>|<style.*?</style>|<!--.*?-->|<head\b.*?</head>', '', h)
    h = plain_breaks(h)
    i = h.lower().find('<body')
    return h[h.index('>', i) + 1:] if i >= 0 else h


def split(h):
    p = Split()
    p.feed(body(h))
    p.close()
    lines, dodf = [], []
    for kind, l in lines_of(''.join(p.kept)):
        m = DODF.search(l)
        if m:
            dodf.append(m.group(1))
        if BOILER.match(l):
            continue
        lines.append((kind, l))
    notes = [norm(n) for n in ''.join(p.notes).split('\n') if norm(n)]
    return lines, notes, norm(''.join(p.old)), dodf


DMY = re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b')


def dates(s):
    return [f'{int(y):04d}-{int(mo):02d}-{int(d):02d}' for d, mo, y in DMY.findall(s) if 1 <= int(mo) <= 12 and 1 <= int(d) <= 31]


ALTER = re.compile(r'(?i)\b(alterad|acrescid|revogad|inclu[íi]d|renumerad|suprimid|declarad|suspens|nova reda|reda[çc][ãa]o dada|'
                   r'acrescentad|transformad|prorrogad|substitu[íi]d|modificad|repristinad|retificad)')


def is_alteration(n):
    return bool(ALTER.search(n)) and not n.lower().startswith('legisla')


COUNTRY = {
    'code': 'BR-DF', 'name': 'Distrito Federal', 'slug': 'brazil-federal-district', 'lang': 'pt', 'tz': 'America/Sao_Paulo',
    'future_branch': 'futuro',
    'publisher': {'name': 'Sistema Integrado de Normas Jurídicas do Distrito Federal (SINJ-DF)',
                  'email': 'sinj@sinj.df.gov.br.invalid'},
    'default_in_force_rule': {
        'text': 'Decreto-Lei 4.657/1942 (LINDB) art. 1: unless it says otherwise, a law takes effect 45 days after its '
                'official publication. Distrito Federal laws almost always say "Esta Lei Complementar entra em vigor na '
                'data de sua publicação"; this record dates each act as enacted by its publication in the Diário '
                'Oficial do Distrito Federal (DODF), as the text\'s closing line names it.',
        'source': 'https://www.planalto.gov.br/ccivil_03/decreto-lei/del4657compilado.htm'},
    'licence_note': 'Texts: SINJ-DF, Sistema Integrado de Normas Jurídicas do Distrito Federal, www.sinj.df.gov.br. '
                    'Lei 9.610/1998 art. 8 IV: the texts of laws and other official acts are not protected by '
                    'copyright. Non-official text ("Este texto não substitui o publicado no DODF"): only the Diário '
                    'Oficial do Distrito Federal is authoritative.',
}
DECISIONS = [
    'An act SINJ-DF shows no alteration for (no alteration note, nothing struck through) is given as enacted, credited '
    'to the act itself and dated by its publication in the DODF as the text\'s closing line names it (the date of '
    'signature when there is none). An altered act is given only as its text in force, credited to SINJ-DF as the '
    'oldest version available and dated by the latest date its alteration notes cite. The wordings in between (struck '
    'through in the compiled text) are not reconstructed yet, so no earlier version is given rather than a wrong one.',
    'The text in force leaves out what the compiled text strikes through, the alteration notes (links such as "(Artigo '
    'alterado(a) pelo(a) Lei Complementar 783 de 30/10/2008)"), the "Legislação correlata" links above the text, the '
    'heading "Texto Compilado" and the closing notice "Este texto não substitui o publicado no DODF ...". "Vide" and '
    '"Legislação correlata" notes do not date a version.',
    'One file per Art.; headings of the Títulos, Capítulos and Seções stand above the first article under them; '
    '"000-titulo" holds the title, the ementa and the preamble. Text after the last article (place, date, signatures, '
    'annexes) stays with the last article. Tables are one line per row, cells separated by " | "; images are left out.',
]
AI = ["Claude Code (claude-opus-5-5) wrote Lexifina's code and chose the sources. No model output is used as legal "
      "text or dates: every word comes from the SINJ-DF texts."]


def raw(url):
    p = CACHE / 'raw' / sha(url.encode())
    return p.read_bytes() if p.exists() else None


def iso(d):
    m = DMY.search(d or '')
    return f'{int(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}' if m else None


def act_of(s):
    url = s['_text_url']
    b = raw(url)
    if b is None:
        return None, {}, 'not fetched'
    lines, notes, old, dodf = split(b.decode('utf-8', 'replace'))
    n = int(re.sub(r'\D', '', s.get('nr_norma') or '0') or 0)
    enacted = iso(s.get('dt_assinatura'))
    if not enacted or not n:
        return None, {}, 'no date or number'
    published = iso(dodf[0]) if dodf else None
    if published and published < enacted:
        published = None
    y = enacted[:4]
    slug = law_key = f'lc-{y}-{n:04d}'
    label = f'Lei Complementar nº {n}, de {enacted[8:10]}/{enacted[5:7]}/{y}'
    first = published or enacted
    alts = [x for x in notes if is_alteration(x)]
    alter = sorted(d for x in alts for d in dates(x) if d > first)
    if (old or alts) and not alter:
        return None, {}, 'altered, no dated note'
    units = units_of(lines, adt=False)
    if not units or list(units) == ['000-titulo']:
        return None, {}, 'no text'
    ementa = norm(s.get('ds_ementa') or '')
    page = f"https://www.sinj.df.gov.br/sinj/DetalhesDeNorma.aspx?id_norma={s['ch_norma']}"
    laws = {law_key: {'label': label, 'title': ementa or label, 'kind': 'law', 'enacted': enacted, 'published': published,
                      'url': page, 'temporary_until': None, 'restores': None, 'note': None}}
    v = {'from': alter[-1] if alter else first, 'source_url': url, 'sha256': sha(b), 'units': units}
    if alter:
        v['note'] = (f'Text in force as compiled by SINJ-DF; {label} was altered on {len(set(alter))} date(s) its notes '
                     f'cite, the latest {alter[-1]}.')
    act = {'slug': slug, 'short': f'LC {n}/{y}', 'title': label + (f' ({ementa})' if ementa and len(ementa) < 160 else ''),
           'url': page, 'first_law': None if alter else law_key, 'earlier_laws': [law_key] if alter else [],
           'versions': [v]}
    return act, laws, 'ok'


def part(name, acts, laws, today):
    c = {'country': COUNTRY,
         'sources': [{'name': 'SINJ-DF (Sistema Integrado de Normas Jurídicas do Distrito Federal): the compiled text of '
                              'each Lei Complementar', 'url': 'https://www.sinj.df.gov.br/sinj/', 'retrieved': today,
                      'licence': COUNTRY['licence_note'], 'notes': f'{len(acts)} acts in this part.'}],
         'laws': laws, 'acts': acts, 'applies': [], 'decisions': DECISIONS, 'ai_use': AI}
    return write_part(HERE / 'corpus.d', name, c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--today', required=True)
    ap.add_argument('--part-size', type=int, default=50)
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    idx = json.loads((CACHE / 'lc-index.json').read_text(encoding='utf-8'))
    keep = [s for s in idx if s.get('_text_url') and not re.match(r'(?i)revogad|anulad|sem efeito|inconstitucional',
                                                                    s.get('nm_situacao') or '')]
    keep.sort(key=lambda s: (iso(s.get('dt_assinatura')) or '9999', int(re.sub(r'\D', '', s.get('nr_norma') or '0') or 0)))
    why = {}
    for i in range(0, len(keep), a.part_size):
        chunk = keep[i:i + a.part_size]
        if any(raw(s['_text_url']) is None for s in chunk):
            why['part not complete'] = why.get('part not complete', 0) + 1
            continue  # a part is written only once every act in it is fetched, so a published part never changes
        acts, laws, seen = [], {}, set()
        for s in chunk:
            act, l, w = act_of(s)
            why[w] = why.get(w, 0) + 1
            if act and act['slug'] not in seen:
                seen.add(act['slug']); acts.append(act); laws.update(l)
        if not a.dry:
            print(part(f'20-lc-{i // a.part_size + 1:02d}', acts, laws, a.today), len(acts))
    print(len(keep), 'kept of', len(idx), why)


if __name__ == '__main__':
    main()
