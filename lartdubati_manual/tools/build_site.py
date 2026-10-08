"""Gabarit des pages web du manuel (/manuel) et import ponctuel depuis Markdown.

Les fiches s'éditent directement dans lartdubati_manual/manual/<lang>/*.html ;
refresh.py reconstruit ensuite sommaires, index de recherche et liens à partir
de ces pages, avec le gabarit (CSS, JS, libellés, SCREENS) défini ici.

Usage ponctuel (créer un onglet entier depuis des fichiers Markdown) :
python3 build_site.py --lang fr --src src --out ../manual
Produit <out>/<lang>/<page>.html, autonomes (CSS et JS inclus), sans ressource externe.
"""
import argparse
import datetime
import html
import json
import os
import re


UI = {
    "fr": {
        "dir": "ltr", "title": "Manuel Odoo – L'Art du Bâti", "search": "Rechercher une fiche (code, mot-clé)…",
        "toc": "Fiches de cet onglet", "noresult": "Aucune fiche trouvée", "generated": "Mis à jour le",
        "source": "",
        "print": "Imprimer",
        "pages": [
            ("index", "Accueil.md", "Accueil"),
            ("reference", "Référence.md", "Référence"),
            ("admin", "Admin Odoo.md", "Admin Odoo"),
            ("parc", "Responsable parc.md", "Responsable parc"),
            ("comptable", "Comptable.md", "Comptable"),
            ("chantier", "Chantier.md", "Chantier"),
            ("investisseur", "Investisseur.md", "Investisseur"),
        ],
    },
    "en": {
        "dir": "ltr", "title": "Odoo Manual – L'Art du Bâti", "search": "Search a sheet (code, keyword)…",
        "toc": "Sheets in this tab", "noresult": "No sheet found", "generated": "Updated on",
        "source": "",
        "print": "Print",
        "pages": [
            ("index", "Home.md", "Home"), ("reference", "Reference.md", "Reference"),
            ("admin", "Odoo Admin.md", "Odoo Admin"), ("parc", "Fleet manager.md", "Fleet manager"),
            ("comptable", "Accountant.md", "Accountant"), ("chantier", "Site.md", "Site"),
            ("investisseur", "Investor.md", "Investor"),
        ],
    },
    "fa": {
        "dir": "rtl", "title": "راهنمای اودو – L'Art du Bâti", "search": "جستجوی برگه (کد، کلیدواژه)…",
        "toc": "برگه‌های این بخش", "noresult": "برگه‌ای یافت نشد", "generated": "تاریخ به‌روزرسانی",
        "source": "",
        "print": "چاپ",
        "pages": [
            ("index", "خانه.md", "خانه"), ("reference", "مرجع.md", "مرجع"),
            ("admin", "مدیر اودو.md", "مدیر اودو"), ("parc", "انباردار امین اموال.md", "انباردار/امین اموال"),
            ("comptable", "حسابدار.md", "حسابدار"), ("chantier", "کارگاه.md", "کارگاه"),
            ("investisseur", "سرمایه\u200cگذار.md", "سرمایه\u200cگذار"),
        ],
    },
}
LANG_LABELS = {"fr": "FR", "en": "EN", "fa": "FA"}
CODE_PAGE = {"REF": "reference", "ADM": "admin", "PARC": "parc", "CPT": "comptable", "CH": "chantier", "INV": "investisseur"}
CODE_RE = re.compile(r"\b(REF|ADM|PARC|CPT|CH|INV)-(\d{2})\b")
BYLINE_RE = re.compile(r"^(?:[A-Z][a-z]{2} \d{1,2}, \d{4}|[\d۰-۹]{2}/[\d۰-۹]{2}/[\d۰-۹]{4}) · @?\S.*$", re.M)


# --- Liens profonds vers les écrans d'Odoo -----------------------------------
# Le routeur d'Odoo 18 accepte le XML ID d'une action aussi bien que son
# identifiant numérique (addons/web/static/src/core/browser/router.js) : une URL
# construite sur le XML ID vaut donc pour artdubati comme pour artdubati_test, et
# survit aux refontes d'interface. Les chemins de menus cités dans les fiches sont
# transformés en liens automatiquement, langue par langue.
ODOO_BASE = "https://erp.lartdubati.com/odoo/action-"

# Le dernier segment du chemin suffit à identifier l'écran ; la clé est écrite en
# minuscules, sans espaces superflus. Un chemin plus long tombe sur la même entrée.
SCREENS = {
    "fr": {
        "équipement": "maintenance.hr_equipment_action",
        "catégories d'équipement": "maintenance.hr_equipment_category_action",
        "emplacements": "stock.action_location_form",
        "entrepôts": "stock.action_warehouse_form",
        "catégories de produits": "product.product_category_action_form",
        "produits": "product.product_template_action",
        "contacts": "contacts.action_contacts",
        "étiquettes de contact": "base.action_partner_category_form",
        "sociétés": "base.action_res_company_form",
        "plan comptable": "account.action_account_form",
        "écritures comptables": "account.action_account_moves_all",
        "factures fournisseurs": "account.action_move_in_invoice_type",
        "factures clients": "account.action_move_out_invoice_type",
        "positions fiscales": "account.action_account_fiscal_position_form",
        "conditions de paiement": "account.action_payment_term_form",
        "taxes": "account.action_tax_form",
        "param\u00e8tres": "stock.action_stock_config_settings",
        "export fec": "lartdubati_facturation.action_l10n_fr_fec_export_wizard",
        "utilisateurs": "base.action_res_users",
        "profils d'accès aux stocks": "lartdubati_investor_home.action_stock_access",
        "contrats d'achats": "contract.action_supplier_contract",
        "réceptions": "stock.method_action_picking_tree_incoming",
    },
    "en": {
        "equipment": "maintenance.hr_equipment_action",
        "equipment categories": "maintenance.hr_equipment_category_action",
        "locations": "stock.action_location_form",
        "warehouses": "stock.action_warehouse_form",
        "product categories": "product.product_category_action_form",
        "products": "product.product_template_action",
        "contacts": "contacts.action_contacts",
        "contact tags": "base.action_partner_category_form",
        "companies": "base.action_res_company_form",
        "chart of accounts": "account.action_account_form",
        "journal items": "account.action_account_moves_all",
        "bills": "account.action_move_in_invoice_type",
        "customer invoices": "account.action_move_out_invoice_type",
        "fiscal positions": "account.action_account_fiscal_position_form",
        "payment terms": "account.action_payment_term_form",
        "taxes": "account.action_tax_form",
        "settings": "stock.action_stock_config_settings",
        "export fec": "lartdubati_facturation.action_l10n_fr_fec_export_wizard",
        "users": "base.action_res_users",
        "stock access profiles": "lartdubati_investor_home.action_stock_access",
        "supplier contracts": "contract.action_supplier_contract",
        "receipts": "stock.method_action_picking_tree_incoming",
    },
    "fa": {
        "تجهیزات": "maintenance.hr_equipment_action",
        "دسته\u200cبندی تجهیزات": "maintenance.hr_equipment_category_action",
        "دسته\u200cبندی\u200cهای تجهیزات": "maintenance.hr_equipment_category_action",
        "مکان\u200cها": "stock.action_location_form",
        "انبارها": "stock.action_warehouse_form",
        "دسته\u200cبندی محصولات": "product.product_category_action_form",
        "دسته\u200cبندی\u200cهای محصول": "product.product_category_action_form",
        "محصولات": "product.product_template_action",
        "مخاطبان": "contacts.action_contacts",
        "شرکت ها": "base.action_res_company_form",
        "جدول حساب ها": "account.action_account_form",
        "آیتم های روزنامه": "account.action_account_moves_all",
        "صورتحساب فروشندگان": "account.action_move_in_invoice_type",
        "فاکتورهای مشتری": "account.action_move_out_invoice_type",
        "موقعیت های مالی": "account.action_account_fiscal_position_form",
        "شرایط پرداخت": "account.action_payment_term_form",
        "مالیات ها": "account.action_tax_form",
        "برچسب‌های مخاطبان": "base.action_partner_category_form",
        "تنظیمات": "stock.action_stock_config_settings",
        "صورتحساب": "account.action_move_in_invoice_type",
        "export fec": "lartdubati_facturation.action_l10n_fr_fec_export_wizard",
        "کاربران": "base.action_res_users",
        "پروفایل\u200cهای دسترسی انبار": "lartdubati_investor_home.action_stock_access",
        "supplier contracts": "contract.action_supplier_contract",
        "رسیدها": "stock.method_action_picking_tree_incoming",
    },
}
# Séparateurs de chemin : flèche latine et flèche RTL du persan.
ARROWS = ("\u2192", "\u2190")

CSS = """
:root{--bg:#f7f6f3;--card:#fff;--ink:#1f2328;--muted:#5d6570;--line:#e3e1dc;--accent:#6b3f5c;--accent-soft:#f3ebf0;--code:#f1efe9}
@media (prefers-color-scheme:dark){:root{--bg:#16181b;--card:#1f2226;--ink:#e8e6e3;--muted:#a3a9b1;--line:#33373d;--accent:#d9a5c6;--accent-soft:#2c2229;--code:#2a2d31}}
*{box-sizing:border-box}html{scroll-padding-top:120px}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,"Vazirmatn",Tahoma,sans-serif}
header{position:sticky;top:0;z-index:10;background:var(--card);border-bottom:1px solid var(--line)}
.bar{max-width:1040px;margin:0 auto;padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.brand{font-weight:700;color:var(--accent);text-decoration:none;margin-inline-end:auto}
.langs a{color:var(--muted);text-decoration:none;font-size:13px;padding:2px 6px;border-radius:4px}
.langs a.on{background:var(--accent-soft);color:var(--accent);font-weight:600}
#q{flex:1 1 260px;min-width:0;padding:7px 10px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink);font-size:14px}
nav.tabs{max-width:1040px;margin:0 auto;padding:0 8px;display:flex;overflow-x:auto;gap:2px}
nav.tabs a{white-space:nowrap;padding:8px 12px;color:var(--muted);text-decoration:none;border-bottom:3px solid transparent;font-size:15px}
nav.tabs a.on{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}
#results{max-width:1040px;margin:0 auto;padding:0 16px}
#results ul{list-style:none;margin:8px 0;padding:8px;background:var(--card);border:1px solid var(--line);border-radius:8px;max-height:50vh;overflow:auto}
#results li a{display:block;padding:6px 8px;border-radius:4px;color:var(--ink);text-decoration:none}
#results li a:hover{background:var(--accent-soft)}#results small{color:var(--muted)}
main{max-width:1040px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 24px 24px}
h1{font-size:28px;margin:18px 0 8px}h2{font-size:21px;margin:36px 0 10px;padding-top:14px;border-top:1px solid var(--line)}
h2 .code{display:inline-block;font-size:13px;font-weight:700;color:var(--accent);background:var(--accent-soft);padding:2px 8px;border-radius:4px;margin-inline-end:8px;vertical-align:3px}
.toc{background:var(--accent-soft);border-radius:8px;padding:10px 16px;margin:12px 0}
.toc strong{font-size:14px}.toc ul{margin:6px 0 0;padding-inline-start:18px;columns:2;column-gap:28px}
.toc a{color:var(--ink);text-decoration:none}.toc a:hover{text-decoration:underline}
a{color:var(--accent)}
a.screen{color:inherit;text-decoration:none;border-bottom:1px dotted var(--accent)}
a.screen:hover{color:var(--accent);border-bottom-style:solid}
a.ref{font-weight:600;text-decoration:none;white-space:nowrap}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14.5px;display:block;overflow-x:auto}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:start;vertical-align:top}
th{background:var(--accent-soft)}
code{background:var(--code);padding:1px 5px;border-radius:4px;font-size:13.5px;word-break:break-all}
ol,ul{padding-inline-start:26px}li{margin:3px 0}
footer{max-width:1040px;margin:0 auto;padding:16px;color:var(--muted);font-size:13px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
footer button{background:none;border:1px solid var(--line);color:var(--muted);border-radius:6px;padding:4px 10px;cursor:pointer}
figure.shot{margin:16px 0;text-align:center}
figure.shot img{max-width:100%;border:1px solid var(--line);border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.08)}
figure.shot figcaption{margin-top:6px;font-size:13px;color:var(--muted)}
@media (max-width:640px){.card{padding:4px 14px 16px}.toc ul{columns:1}h1{font-size:24px}}
@media print{header,footer button,.toc,#results{display:none}body{background:#fff}.card{border:0}}
"""

JS = """
const IDX=__INDEX__;const q=document.getElementById('q'),r=document.getElementById('results');
const norm=s=>s.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,'');
q.addEventListener('input',()=>{const t=norm(q.value.trim());if(t.length<2){r.innerHTML='';return}
const words=t.split(/\\s+/);const hits=IDX.filter(f=>words.every(w=>f.s.includes(w))).slice(0,30);
r.innerHTML='<ul>'+(hits.length?hits.map(f=>`<li><a href="${f.u}"><b>${f.c}</b> ${f.t} <small>· ${f.p}</small></a></li>`).join(''):`<li><small>__NORES__</small></li>`)+'</ul>'});
document.addEventListener('keydown',e=>{if(e.key==='/'&&document.activeElement!==q){e.preventDefault();q.focus()}if(e.key==='Escape'){q.value='';r.innerHTML=''}});
"""


def slug(text):
    s = re.sub(r"[^\w]+", "-", text.lower(), flags=re.U).strip("-")
    return s or "section"


def fix_indent(md):
    """Normalise les listes imbriquées (indentation à 2 ou 3 espaces) pour CommonMark."""
    out = []
    for line in md.split("\n"):
        m = re.match(r"^( +)([-*]|\d+\.) ", line)
        if m:
            n = len(m.group(1))
            level = max(1, round(n / 2)) if n < 4 else n // 4 if n % 4 == 0 else round(n / 2)
            line = "    " * level + line[n:]
        out.append(line)
    return "\n".join(out)


def link_codes(fragment, page_ids):
    parts = re.split(r"(<[^>]+>)", fragment)
    depth = {"a": 0, "h2": 0, "code": 0}
    for i, part in enumerate(parts):
        if part.startswith("<"):
            m = re.match(r"<(/?)(a|h2|code)\b", part)
            if m:
                depth[m.group(2)] += -1 if m.group(1) else 1
            continue
        if any(depth.values()):
            continue

        def repl(m):
            code = f"{m.group(1)}-{m.group(2)}"
            page = CODE_PAGE[m.group(1)]
            return f'<a class="ref" href="{page}#{code.lower()}">{code}</a>'

        parts[i] = CODE_RE.sub(repl, part)
    return "".join(parts)


IMG_RE = re.compile(
    r'<a href="(?:https?://[^"/]+)?(/lartdubati_manual/static/screenshots/[^"]+\.(?:png|jpe?g))">(.*?)</a>',
    re.S,
)


def link_images(fragment):
    """Transforme les liens vers des captures d'écran en <figure><img>.

    Dans une fiche, on écrit un lien normal dont l'URL pointe vers le
    fichier statique servi par le module (ex.
    /lartdubati_manual/static/screenshots/fr/import-equipement.png) et dont le
    texte du lien sert de légende. Cette fonction convertit ce lien en image.
    """

    def repl(m):
        src, caption = m.group(1), m.group(2)
        cap = plain(caption).strip()
        return (f'<figure class="shot"><img src="{src}" alt="{html.escape(cap)}" loading="lazy">'
                f'<figcaption>{caption}</figcaption></figure>')

    return IMG_RE.sub(repl, fragment)


def link_menus(fragment, lang):
    """Transforme les chemins de menus en gras en liens vers l'écran d'Odoo.

    Le texte du manuel reste propre : aucune URL n'y figure, le lien est posé
    à la génération. Un chemin sans écran connu est laissé tel quel.
    """
    screens = SCREENS.get(lang, {})
    if not screens:
        return fragment

    def repl(m):
        inner = m.group(1)
        if "<" in inner:  # déjà balisé (lien, code…) : ne rien toucher
            return m.group(0)
        plain = html.unescape(inner)
        if not any(a in plain for a in ARROWS):
            return m.group(0)
        # On remonte le chemin depuis la fin : le dernier segment est souvent
        # une action (Nouveau) ou un nom d'enregistrement (L'Art du Bâti), et
        # l'écran visé est alors le segment au-dessus.
        segments = [x.strip().strip(".:,;").lower()
                    for x in re.split(r"[\u2192\u2190]", plain)]
        xmlid = next((screens[x] for x in reversed(segments) if x in screens), None)
        if not xmlid:
            return m.group(0)
        # Le gras est conservé : la règle du manuel veut les menus en gras,
        # le lien vient par-dessus.
        return (f'<a class="screen" href="{ODOO_BASE}{xmlid}" target="_blank"'
                f' rel="noopener"><strong>{inner}</strong></a>')

    # (?<!…) : un menu déjà relié (page éditée puis rafraîchie) n'est pas relié deux fois.
    return re.sub(r'(?<!rel="noopener">)<strong>(.*?)</strong>', repl, fragment, flags=re.S)


def render(md_text):
    from markdown_it import MarkdownIt  # seulement pour l'import depuis Markdown

    md_text = BYLINE_RE.sub("", md_text)
    md = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")
    tokens = md.parse(md_text)
    title, fiches = None, []
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open":
            text = tokens[i + 1].content
            if tok.tag == "h1" and title is None:
                title = text
            elif tok.tag == "h2":
                m = re.match(r"^((?:REF|ADM|PARC|CPT|CH|INV)-\d{2})\s+(.*)$", text)
                hid = m.group(1).lower() if m else slug(text)
                tok.attrSet("id", hid)
                fiches.append({"id": hid, "code": m.group(1) if m else "", "title": m.group(2) if m else text})
    body = md.renderer.render(tokens, md.options, {})
    # remove h1 (rendered in page header) and decorate h2 codes
    body = re.sub(r"<h1>.*?</h1>\n?", "", body, count=1, flags=re.S)
    body = re.sub(r'(<h2 id="[^"]+">)((?:REF|ADM|PARC|CPT|CH|INV)-\d{2})\s', r'\1<span class="code">\2</span>', body)
    return title, fiches, body


def plain(html_text):
    return html.unescape(re.sub(r"<[^>]+>", " ", html_text))


def index_entries(key, label, body):
    """Entrées de l'index de recherche d'une page : une par titre h2."""
    entries = []
    for sec in re.split(r'(?=<h2 id=")', body):
        m = re.match(r'<h2 id="([^"]+)">(.*?)</h2>', sec, re.S)
        if not m:
            continue
        htxt = plain(m.group(2)).strip()
        cm = re.match(r"^((?:REF|ADM|PARC|CPT|CH|INV)-\d{2})\s*(.*)$", htxt)
        entries.append({
            "c": cm.group(1) if cm else "", "t": html.escape(cm.group(2) if cm else htxt), "p": html.escape(label),
            "u": f"{key}#{m.group(1)}",
            "s": re.sub(r"\s+", " ", _norm(plain(sec))),
        })
    return entries


def write_pages(lang, out, rendered):
    """Écrit <out>/<lang>/<page>.html. rendered[key] = (titre, fiches, corps, libellé)."""
    ui = UI[lang]
    index = []
    for key, (title, fiches, body, label) in rendered.items():
        index += index_entries(key, label, body)
    langs_here = sorted(d for d in os.listdir(out) if os.path.isdir(os.path.join(out, d))) if os.path.isdir(out) else []
    langs_here = sorted(set(langs_here) | {lang})
    today = datetime.date.today().strftime("%d/%m/%Y")
    os.makedirs(os.path.join(out, lang), exist_ok=True)
    js = JS.replace("__INDEX__", json.dumps(index, ensure_ascii=False)).replace("__NORES__", ui["noresult"])
    footer_src = f" · {html.escape(ui['source'])}" if ui["source"] else ""
    for key, (title, fiches, body, label) in rendered.items():
        tabs = "".join(
            f'<a href="{k}"{" class=on" if k == key else ""}>{html.escape(rendered[k][3])}</a>' for k in rendered
        )
        langs = "".join(
            f'<a href="/manuel/{l}/{key}"{" class=on" if l == lang else ""}>{LANG_LABELS.get(l, l.upper())}</a>'
            for l in langs_here
        )
        toc = ""
        if len(fiches) > 1:
            items = "".join(
                f'<li><a href="#{f["id"]}">{(f["code"] + " ") if f["code"] else ""}{html.escape(f["title"])}</a></li>'
                for f in fiches
            )
            toc = f'<div class="toc"><strong>{ui["toc"]}</strong><ul>{items}</ul></div>'
        body_linked = link_images(link_menus(link_codes(body, None), lang))
        page = f"""<!doctype html>
<html lang="{lang}" dir="{ui['dir']}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>{html.escape(label)} · {html.escape(ui['title'])}</title><style>{CSS}</style></head>
<body><header><div class="bar"><a class="brand" href="index">{html.escape(ui['title'])}</a>
<input id="q" type="search" placeholder="{html.escape(ui['search'])}" autocomplete="off">
<span class="langs">{langs}</span></div><nav class="tabs">{tabs}</nav><div id="results"></div></header>
<main><div class="card"><h1>{html.escape(title)}</h1>{toc}{body_linked}</div></main>
<footer><span>{ui['generated']} {today}{footer_src}</span><button onclick="print()">{ui['print']}</button></footer>
<script>{js}</script></body></html>"""
        with open(os.path.join(out, lang, key + ".html"), "w", encoding="utf-8") as f:
            f.write(page)
        print(f"{lang}/{key}.html  {len(fiches)} sections")


def build(lang, src, out):
    ui = UI[lang]
    rendered = {}
    available = [p for p in ui["pages"] if os.path.exists(os.path.join(src, p[1]))]
    if not available:
        raise SystemExit(f"Aucune page source trouvée pour {lang} dans {src}")
    for key, fname, label in available:
        with open(os.path.join(src, fname), encoding="utf-8") as f:
            title, fiches, body = render(f.read())
        rendered[key] = (title or label, fiches, body, label)
    write_pages(lang, out, rendered)


def _norm(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="fr")
    ap.add_argument("--src", default="src")
    ap.add_argument("--out", default="manual")
    a = ap.parse_args()
    build(a.lang, a.src, a.out)
