# Outils du manuel (lartdubati_manual/tools/)

Les fiches du manuel s'éditent **directement** dans les pages HTML servies par le
module Odoo `lartdubati_manual` : `lartdubati_manual/manual/<lang>/<page>.html`
(langues `fr`, `en`, `fa` ; pages `index`, `reference`, `admin`, `parc`,
`comptable`, `chantier`, `investisseur`). Ces outils maintiennent ce qui ne doit
pas être tenu à la main.

Pour la procédure complète (quand mettre à jour, quelles fiches, comment
publier), voir `docs/manual/maintenance-manuel-odoo.md`. Ce fichier-ci ne
documente que les outils.

## Fichiers

- `refresh.py` — à lancer après chaque édition. Relit le titre et le corps de
  chaque page, puis réécrit toutes les pages de la langue avec le gabarit de
  `build_site.py` :
  - sommaire « Fiches de cet onglet » (à partir des titres `<h2>`) ;
  - index de recherche, commun à toutes les pages d'une langue (chaque page en
    embarque une copie : sans `refresh.py`, une fiche ajoutée n'est pas
    trouvée par la recherche des autres pages) ;
  - onglets, sélecteur de langue, date « Mis à jour le » du pied de page ;
  - liens automatiques : codes `REF-xx`, `ADM-xx`, `PARC-xx`, `CPT-xx`,
    `CH-xx`, `INV-xx` → `page#code` ; chemins de menus en gras →
    écran d'Odoo (table `SCREENS`) ; lien vers une capture d'écran → image.

  Il est idempotent : le relancer sans édition ne change que la date.
- `check.py` — vérifie la cohérence FR/EN/FA directement sur les pages : mêmes
  codes de fiches, même page, mêmes renvois internes, mêmes nombres (comptes
  comptables, etc.), même nombre d'étapes, pas de renvoi vers un code qui
  n'existe pas.
- `build_site.py` — le gabarit commun (CSS, JS de recherche, libellés `UI` par
  langue, `SCREENS`, fonctions de liens), utilisé par `refresh.py`. Il peut
  aussi créer un onglet entier à partir de fichiers Markdown (usage ponctuel,
  voir plus bas).
- `requirements.txt` — dépendance de l'import Markdown uniquement
  (`refresh.py` et `check.py` n'utilisent que la bibliothèque standard).

## Écrire dans une page

Le contenu éditable d'une page est le corps de la carte : tout ce qui suit le
sommaire (`<div class="toc">…</div>`) jusqu'à `</div></main>`. Ne pas modifier
l'en-tête, le sommaire, le pied de page ni le `<script>` : `refresh.py` les
réécrit.

Une fiche :

```html
<h2 id="inv-05"><span class="code">INV-05</span>Titre à l'infinitif</h2>
<p><strong>Qui · Quand</strong> : …</p>
<p><strong>Prérequis</strong> : …</p>
<p><strong>Étapes</strong></p>
<ol>
<li>Ouvrir <strong>Maintenance → Équipement</strong>.</li>
<li>…</li>
</ol>
<p><strong>Vérification</strong> : …</p>
<p><strong>Voir aussi</strong> : ADM-11, INV-02.</p>
```

- `id` du `<h2>` = code en minuscules ; titre sans le code (la balise
  `<span class="code">` porte le code).
- Renvoi vers une autre fiche : écrire le code en texte (`ADM-11`) ;
  `refresh.py` pose le lien.
- Chemin de menu : en gras (`<strong>Maintenance → Équipement</strong>`) ;
  `refresh.py` le transforme en lien vers l'écran si le dernier segment connu
  du chemin figure dans `SCREENS` (par langue). Ajouter un écran = une ligne
  par langue dans `SCREENS`, jamais une URL écrite dans la fiche.
- Capture d'écran : `<a href="/lartdubati_manual/static/screenshots/fr/x.png">Légende</a>` ;
  `refresh.py` la transforme en `<figure>`.
- Section sans code (Accueil) : `<h2 id="slug-du-titre">Titre</h2>`.
- FA : page en `dir="rtl"` ; écrire le texte persan normalement, chiffres
  persans dans les dates du journal.

## Commandes

```bash
cd lartdubati_manual/tools
python3 refresh.py          # toutes les langues ; ou : python3 refresh.py fr
python3 check.py            # cohérence FR/EN/FA
```

Un désaccord trouvé par `check.py` n'est pas forcément une erreur (une fiche
peut exister en FR avant EN/FA, noté « EN/FA à faire » dans le journal), mais
toute différence doit être délibérée, jamais une omission.

## Créer un onglet entier depuis Markdown (ponctuel)

Pour un nouvel onglet long, on peut le rédiger en Markdown (un fichier par
onglet, noms attendus dans `UI[lang]["pages"]` de `build_site.py`) puis :

```bash
pip install -r requirements.txt   # markdown-it-py
python3 build_site.py --lang fr --src <dossier_md> --out ../manual
python3 refresh.py
```

Attention : `build_site.py` réécrit **toutes** les pages de la langue à partir
du dossier Markdown, et omet celles qui n'y sont pas. Pour un seul onglet, le
générer dans un dossier temporaire (`--out /tmp/x`) puis recopier son corps
dans la page du dépôt, et lancer `refresh.py`.

Nouvel onglet (nouveau profil) : ajouter la page dans `UI[lang]["pages"]` des
trois langues et dans `CODE_PAGE` si elle a un nouveau préfixe de code.
