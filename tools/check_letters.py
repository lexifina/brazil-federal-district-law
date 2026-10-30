"""Independent letters-and-digits check of every version against its SINJ-DF text file (regex tokenizer, no HTML
parser).

    python -X utf8 check_letters.py [part.json ...]

For each version: the page body (no head, scripts, styles or comments) with every text run under a strike-through
(s, strike, del, line-through) left out, the notes left out (any element of class "link_vide", any paragraph with a
ch_norma_info attribute; SINJ leaves <p> unclosed, so a paragraph runs to the next paragraph, heading or block), the
lines "Texto Compilado", "Legislação correlata - ..." and "Este texto não substitui o publicado no DODF ..." left out,
reduced to letters and digits, must equal the version's unit files reduced the same way, each unit found at its place
in document order.
"""
import hashlib, html, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from br_lib import letters_check  # noqa: E402

TOKEN = re.compile(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)((?:[^>"\']|"[^"]*"|\'[^\']*\')*)>|([^<]+)', re.S)
VOIDS = ('br', 'img', 'meta', 'link', 'hr', 'input', 'col', 'area', 'base', 'wbr')
BREAKS = ('p', 'div', 'br', 'tr', 'li', 'table', 'tbody', 'thead', 'ul', 'ol', 'center', 'blockquote', 'h1', 'h2', 'h3',
          'h4', 'h5', 'h6')
ENDS_P = ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'ul', 'ol', 'blockquote', 'center', 'pre', 'hr')
DROP = re.compile(r'(?im)^\s*(?:Texto Compilado|Texto Original|Este texto n[ãa]o substitui o publicado no DODF\b.*|'
                  r'Legisla[çc][ãa]o correlata\s*-.*)\s*$')


def page_text(b):
    s = b.decode('utf-8', 'replace')
    s = re.sub(r'(?is)<script.*?</script>|<style.*?</style>|<!--.*?-->|<head\b.*?</head>', '', s)
    # Older files: plain text in <div id="div_texto">, one paragraph a line, no tags: a newline there is a break.
    d = s.find('<div id="div_texto">')
    if d >= 0:
        e = s.find('</div>', d)
        inner = s[d + 20:e]
        if '<' not in inner:
            s = s[:d + 20] + inner.replace('\n', '<br>') + s[e:]
    i = s.lower().find('<body')
    s = s[s.index('>', i) + 1:] if i >= 0 else s
    open_, out = [], []
    for t in TOKEN.finditer(s):
        close, tag, a, text = t.group(1), (t.group(2) or '').lower(), t.group(3) or '', t.group(4)
        if text is not None:
            if not any(o[1] for o in open_):
                out.append(re.sub(r'\s+', ' ', html.unescape(text)))
            continue
        if not close and tag in ENDS_P:
            for k in range(len(open_) - 1, -1, -1):
                if open_[k][0] == 'p':
                    del open_[k:]
                    break
        if tag in BREAKS:
            out.append('\n')
        if close:
            for k in range(len(open_) - 1, -1, -1):
                if open_[k][0] == tag:
                    del open_[k:]
                    break
        elif tag not in VOIDS:
            low = a.lower()
            m = re.search(r'class\s*=\s*["\']([^"\']*)', low)
            drop = (tag in ('s', 'strike', 'del') or 'line-through' in low or 'ch_norma_info' in low
                    or bool(m and 'link_vide' in m.group(1).split()))
            open_.append((tag, drop))
    return DROP.sub('', '\n'.join(l.strip() for l in ''.join(out).split('\n')))


def main(paths):
    vs = []
    for p in paths:
        for a in json.load(open(p, encoding='utf-8'))['acts']:
            for v in a['versions']:
                raw = (HERE / '.cache' / 'raw' / hashlib.sha256(v['source_url'].encode()).hexdigest()).read_bytes()
                assert hashlib.sha256(raw).hexdigest() == v['sha256'], (a['slug'], 'sha256')
                vs.append((f"{a['slug']} {v['from']}", v['units'], page_text(raw)))
    bad = letters_check(vs, None)
    for b in bad:
        print(b)
    print(f'{len(vs)} versions checked, {len(bad)} mismatches')
    return len(bad)


if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1:] or sorted(str(p) for p in (HERE / 'corpus.d').glob('*.json'))) else 0)
