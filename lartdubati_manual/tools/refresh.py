"""Rafraîchit les pages du manuel après une édition directe des fichiers HTML.

Les fiches s'éditent dans lartdubati_manual/manual/<lang>/*.html, entre le
sommaire et la fin de la carte (<div class="card">). Ce script relit le titre
et le corps de chaque page, puis réécrit toutes les pages de la langue avec le
gabarit de build_site.py : sommaire de l'onglet, index de recherche commun à
toutes les pages, onglets, sélecteur de langue, date de mise à jour, liens
automatiques (codes REF-xx…, chemins de menus en gras, captures d'écran).

Usage : python3 refresh.py [fr en fa]   (par défaut : toutes les langues présentes)
"""
import html
import os
import re
import sys

from build_site import UI, link_menus, plain, write_pages

MANUAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manual")
CARD_RE = re.compile(r'<div class="card"><h1>(.*?)</h1>(?:<div class="toc">.*?</div>)?(.*)</div></main>', re.S)
H2_RE = re.compile(r'<h2 id="([^"]+)">(.*?)</h2>', re.S)
CODE_H2_RE = re.compile(r'^<span class="code">((?:REF|ADM|PARC|CPT|CH|INV)-\d{2})</span>(.*)$', re.S)
SCREEN_LINK_RE = re.compile(r'<a class="screen"[^>]*>.*?</a>', re.S)


def read_page(path):
    with open(path, encoding="utf-8") as f:
        m = CARD_RE.search(f.read())
    if not m:
        raise SystemExit(f"{path} : structure inattendue (carte <div class=\"card\"><h1> introuvable)")
    title, body = html.unescape(m.group(1)), m.group(2)
    fiches = []
    for hid, inner in H2_RE.findall(body):
        cm = CODE_H2_RE.match(inner.strip())
        if cm:
            fiches.append({"id": hid, "code": cm.group(1), "title": plain(cm.group(2)).strip()})
        else:
            fiches.append({"id": hid, "code": "", "title": plain(inner).strip()})
    return title, fiches, body


def protect_screen_links(body):
    """Évite que link_menus ne relie une seconde fois un menu déjà lié."""
    saved = []

    def keep(m):
        saved.append(m.group(0))
        return f"\x00{len(saved) - 1}\x00"

    body = SCREEN_LINK_RE.sub(keep, body)
    return body, saved


def refresh(lang):
    rendered = {}
    for key, _src, label in UI[lang]["pages"]:
        path = os.path.join(MANUAL, lang, key + ".html")
        if not os.path.exists(path):
            continue
        title, fiches, body = read_page(path)
        rendered[key] = (title, fiches, body, label)
    if not rendered:
        raise SystemExit(f"Aucune page trouvée pour {lang} dans {MANUAL}")
    # link_menus est appliqué par write_pages : on masque les liens existants
    # pendant l'écriture puis on les remet en place.
    saved_per_key = {}
    for key, (title, fiches, body, label) in list(rendered.items()):
        body, saved = protect_screen_links(body)
        saved_per_key[key] = saved
        rendered[key] = (title, fiches, body, label)
    write_pages(lang, MANUAL, rendered)
    for key, saved in saved_per_key.items():
        path = os.path.join(MANUAL, lang, key + ".html")
        with open(path, encoding="utf-8") as f:
            page = f.read()
        page = re.sub("\x00(\\d+)\x00", lambda m: saved[int(m.group(1))], page)
        with open(path, "w", encoding="utf-8") as f:
            f.write(page)


if __name__ == "__main__":
    langs = sys.argv[1:] or sorted(d for d in os.listdir(MANUAL) if d in UI)
    for lang in langs:
        refresh(lang)
