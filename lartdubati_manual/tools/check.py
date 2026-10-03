"""Compare FR/EN/FA manual sources fiche by fiche."""
import re, os, collections
PAGES = {
    "fr": ["Accueil.md", "Référence.md", "Admin Odoo.md", "Responsable parc.md", "Comptable.md", "Chantier.md"],
    "en": ["Home.md", "Reference.md", "Odoo Admin.md", "Fleet manager.md", "Accountant.md", "Site.md"],
    "fa": ["خانه.md", "مرجع.md", "مدیر اودو.md", "انباردار امین اموال.md", "حسابدار.md", "کارگاه.md"],
}
FA_DIG = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
CODE = re.compile(r"\b(REF|ADM|PARC|CPT|CH)-(\d{2})\b")

def load(lang):
    data = {}
    for i, f in enumerate(PAGES[lang]):
        txt = open(f"s_{lang}/{f}", encoding="utf-8").read().translate(FA_DIG)
        secs = re.split(r"(?m)^## ", txt)
        for s in secs[1:]:
            head = s.split("\n", 1)[0]
            m = CODE.match(head)
            key = m.group(0) if m else f"p{i}:{head[:30]}"
            body = s.split("\n", 1)[1] if "\n" in s else ""
            data[key] = dict(page=i, head=head, refs=sorted(set(c.group(0) for c in CODE.finditer(body))),
                             nums=sorted(set(re.findall(r"(?<![\d.])\d{3,6}(?![\d.])", body))),
                             steps=len(re.findall(r"(?m)^\s*\d+\. ", body)))
    return data

D = {l: load(l) for l in PAGES}
codes = sorted(set().union(*[{k for k in D[l] if CODE.match(k)} for l in D]))
for c in codes:
    issues = []
    for l in ("en", "fa"):
        if c not in D[l]: issues.append(f"missing in {l}"); continue
        if c not in D["fr"]: issues.append(f"extra in {l}"); continue
        a, b = D["fr"][c], D[l][c]
        if a["page"] != b["page"]: issues.append(f"{l}: page {b['page']}≠{a['page']}")
        if a["refs"] != b["refs"]: issues.append(f"{l} refs Δ fr-only={sorted(set(a['refs'])-set(b['refs']))} {l}-only={sorted(set(b['refs'])-set(a['refs']))}")
        if a["nums"] != b["nums"]: issues.append(f"{l} nums Δ fr-only={sorted(set(a['nums'])-set(b['nums']))} {l}-only={sorted(set(b['nums'])-set(a['nums']))}")
        if a["steps"] != b["steps"]: issues.append(f"{l} steps {b['steps']}≠{a['steps']}")
    if issues: print(c, "|", "; ".join(issues))
# order per page
for l in D:
    order = collections.defaultdict(list)
    for k, v in D[l].items(): order[v["page"]].append(k)
    print(l, {p: len(v) for p, v in sorted(order.items())})
# dangling refs
for l in D:
    for k, v in D[l].items():
        for r in v["refs"]:
            if r not in D[l]: print("DANGLING", l, k, "->", r)
