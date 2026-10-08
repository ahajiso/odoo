"""Compare les pages FR/EN/FA du manuel fiche par fiche.

Lit lartdubati_manual/manual/<lang>/*.html (les fiches s'éditent dans ces
fichiers) et signale : fiche manquante ou en trop, fiche sur une autre page,
renvois REF-xx… différents, nombres différents (comptes comptables… ; les dates
JJ/MM/AAAA sont ignorées), nombre d'étapes différent, renvoi vers un code
inexistant. Le français fait référence. Code de sortie 1 s'il reste un écart.

Usage : python3 check.py
"""
import collections
import sys
import html
import os
import re

MANUAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manual")
PAGES = ["index", "reference", "admin", "parc", "comptable", "chantier", "investisseur"]
LANGS = ("fr", "en", "fa")
FA_DIG = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
CODE = re.compile(r"\b(REF|ADM|PARC|CPT|CH|INV)-(\d{2})\b")


def text(fragment):
    return html.unescape(re.sub(r"<[^>]+>", " ", fragment)).translate(FA_DIG)


def load(lang):
    data = {}
    for i, page in enumerate(PAGES):
        path = os.path.join(MANUAL, lang, page + ".html")
        if not os.path.exists(path):
            continue
        src = open(path, encoding="utf-8").read()
        body = src.split('<main><div class="card">', 1)[1].split("</div></main>", 1)[0]
        for sec in re.split(r'(?=<h2 id=")', body)[1:]:
            head_html, rest = sec.split("</h2>", 1)
            head = text(head_html).strip()
            m = CODE.search(head)
            key = m.group(0) if m else f"p{i}:{head[:30]}"
            plain = text(rest)
            dates = re.sub(r"\b\d{1,2}/\d{1,2}/\d{4}\b", " ", plain)  # dates differ by language
            data[key] = dict(page=i, refs=sorted(set(c.group(0) for c in CODE.finditer(plain))),
                             nums=sorted(set(re.findall(r"(?<![\d.])\d{3,6}(?![\d.])", dates))),
                             steps=len(re.findall(r"<li\b", "".join(re.findall(r"<ol>.*?</ol>", rest, re.S)))))
    return data


D = {l: load(l) for l in LANGS}
problems = 0
codes = sorted(set().union(*[{k for k in D[l] if CODE.match(k)} for l in D]))
for c in codes:
    issues = []
    for l in ("en", "fa"):
        if c not in D[l]:
            issues.append(f"missing in {l}")
            continue
        if c not in D["fr"]:
            issues.append(f"extra in {l}")
            continue
        a, b = D["fr"][c], D[l][c]
        if a["page"] != b["page"]:
            issues.append(f"{l}: page {PAGES[b['page']]}≠{PAGES[a['page']]}")
        if a["refs"] != b["refs"]:
            issues.append(f"{l} refs Δ fr-only={sorted(set(a['refs']) - set(b['refs']))} {l}-only={sorted(set(b['refs']) - set(a['refs']))}")
        if a["nums"] != b["nums"]:
            issues.append(f"{l} nums Δ fr-only={sorted(set(a['nums']) - set(b['nums']))} {l}-only={sorted(set(b['nums']) - set(a['nums']))}")
        if a["steps"] != b["steps"]:
            issues.append(f"{l} steps {b['steps']}≠{a['steps']}")
    if issues:
        problems += 1
        print(c, "|", "; ".join(issues))
for l in D:
    order = collections.defaultdict(list)
    for k, v in D[l].items():
        order[v["page"]].append(k)
    print(l, {PAGES[p]: len(v) for p, v in sorted(order.items())})
for l in D:
    for k, v in D[l].items():
        for r in v["refs"]:
            if r not in D[l]:
                problems += 1
                print("DANGLING", l, k, "->", r)
print("OK: no difference" if not problems else f"{problems} problem(s)")
sys.exit(1 if problems else 0)
