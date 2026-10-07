# Générateur du manuel (lartdubati_manual/tools/)

Transforme les trois documents Claude Docs du manuel utilisateur
(« Manuel Odoo – L'Art du Bâti », FR/EN/FA) en pages HTML statiques, servies
par le module Odoo `lartdubati_manual` depuis `lartdubati_manual/manual/<lang>/*.html`.

Pour la procédure complète (quand régénérer, comment éditer les fiches avant,
comment publier après), voir `docs/manual/maintenance-manuel-odoo.md`. Ce
fichier-ci ne documente que l'outil.

## Fichiers

- `build_site.py` — le générateur. Transforme un dossier de fichiers Markdown
  (un par onglet) en pages HTML autonomes (CSS et JS inclus dans chaque page,
  aucune ressource externe). Contient aussi :
  - `SCREENS` : la table **chemin de menu (dernier segment, par langue) → XML
    ID d'action Odoo**. C'est la source unique de cette correspondance — ne
    pas la dupliquer ailleurs. L'ajouter dans le dict de la langue concernée
    pour faire pointer un nouveau chemin de menu vers un écran.
  - `link_codes()` : transforme les codes `REF-xx`, `ADM-xx`, `PARC-xx`,
    `CPT-xx`, `CH-xx` en liens internes `page#code`.
  - `link_menus()` : transforme les chemins de menu en gras (`**Maintenance →
    Équipement**`) en liens cliquables vers l'écran Odoo correspondant, via
    `SCREENS` et `ODOO_BASE` (`https://erp.lartdubati.com/odoo/action-<xml_id>`).
  - `link_images()` : transforme un lien Markdown dont l'URL pointe vers un
    fichier sous `/lartdubati_manual/static/screenshots/...` en
    `<figure><img></figure>`, avec le texte du lien comme légende.
- `extract_exports.py` — récupère les exports Markdown de Claude Docs
  (encodés en base64 dans les résultats d'outil) depuis le transcript JSONL
  de la session Claude Code, et écrit un fichier `.md` par onglet.
- `check.py` — vérifie la cohérence FR/EN/FA : mêmes codes de fiches, même
  page, mêmes renvois internes, mêmes nombres (comptes comptables, etc.),
  même nombre d'étapes, pas de renvoi vers un code qui n'existe pas.
- `requirements.txt` — dépendance Python du générateur.
- `helpers/` — scripts ponctuels utilisés pour construire des payloads
  `mcp__Claude_Docs__update` par script plutôt qu'à la main (utile pour de
  grosses séries de remplacements identiques). Non requis pour l'usage
  courant (une fiche à la fois) ; voir leur en-tête pour l'usage. Pas
  garantis à jour avec le format exact de l'API Claude Docs du moment — à
  adapter si l'outil renvoie une erreur de format.

## Entrées et sortie

**Entrée** : un dossier par langue contenant un fichier Markdown par onglet,
exporté depuis Claude Docs. Noms de fichiers attendus (clé `pages` de `UI`
dans `build_site.py`) :

| Langue | Fichiers attendus |
| --- | --- |
| fr | `Accueil.md`, `Référence.md`, `Admin Odoo.md`, `Responsable parc.md`, `Comptable.md`, `Chantier.md`, `Investisseur.md` |
| en | `Home.md`, `Reference.md`, `Odoo Admin.md`, `Fleet manager.md`, `Accountant.md`, `Site.md`, `Investor.md` |
| fa | `خانه.md`, `مرجع.md`, `مدیر اودو.md`, `انباردار امین اموال.md`, `حسابدار.md`, `کارگاه.md`, `سرمایه‌گذار.md` (avec ZWNJ) |

Un onglet absent du dossier source est simplement omis de la sortie (pas
d'erreur), sauf si le dossier est entièrement vide pour la langue.

**Sortie** : `<out>/<lang>/<page>.html` — une page HTML autonome par onglet et
par langue (`index`, `reference`, `admin`, `parc`, `comptable`, `chantier`, `investisseur`).

## Comment l'obtenir (export Claude Docs)

Depuis une session Claude Code qui a accès aux trois projets Claude Docs du
manuel (ids dans `docs/manual/definitions-manuel.md`, §« Les trois
documents ») :

1. Pour chaque onglet de chaque langue, appeler `mcp__Claude_Docs__export`
   avec `container` = l'id du document (projet) et `file` = l'id de l'onglet,
   `format: "markdown"`. Le résultat contient le contenu encodé en base64.
2. Récupérer les fichiers sans recopie manuelle :
   ```bash
   python3 extract_exports.py <transcript.jsonl> <dossier_src_lang>
   ```
   `<transcript.jsonl>` est le fichier de la session courante, sous
   `/root/.claude/projects/<projet>/*.jsonl` (le script prend par défaut le
   plus récent de `/root/.claude/projects/-home-claude/*.jsonl` — préciser le
   chemin explicitement si la session tourne ailleurs). Le script lit le
   dernier export de chaque onglet présent dans le transcript et écrit
   `<Nom de l'onglet>.md` dans `<dossier_src_lang>`.
3. Si le nom de fichier exporté ne correspond pas exactement aux noms attendus
   ci-dessus (onglet renommé), renommer le fichier avant de lancer le
   générateur, ou mettre à jour `UI[lang]["pages"]` dans `build_site.py`.

## Commande

```bash
cd lartdubati_manual/tools
pip install -r requirements.txt   # markdown-it-py ; une fois par environnement

for l in fr en fa; do
  python3 build_site.py --lang "$l" --src "src_$l" --out "../manual"
done
```

- `--lang` : `fr`, `en` ou `fa`.
- `--src` : dossier contenant les `.md` exportés pour cette langue (voir
  tableau ci-dessus).
- `--out` : dossier de sortie. Utiliser `../manual` pour écrire directement
  dans `lartdubati_manual/manual/`, le dossier lu par le module Odoo
  (`lartdubati_manual/controllers/main.py`, constante `MANUAL_DIR`).

Lancer les trois langues l'une après l'autre dans la même sortie (`--out`) :
chaque passage ajoute sa langue au sélecteur FR/EN/FA de toutes les pages déjà
présentes dans ce dossier (le générateur liste les sous-dossiers de langue
existants dans `--out` avant d'écrire).

## Vérifier avant de publier

```bash
python3 check.py
```
À lancer depuis un dossier contenant `s_fr/`, `s_en/`, `s_fa/` (les dossiers
source des trois langues — adapter les noms de dossiers au script si besoin,
voir son en-tête `PAGES`). Il signale : fiche manquante ou en trop dans une
langue, fiche sur la mauvaise page, renvois internes (`REF-xx` etc.) qui
diffèrent entre langues, nombres (comptes comptables) qui diffèrent, nombre
d'étapes différent, renvoi vers un code qui n'existe nulle part dans sa propre
langue.

Un désaccord trouvé par `check.py` n'est pas forcément une erreur (une fiche
peut légitimement exister dans une langue et pas encore dans une autre, noté
« EN/FA à faire » dans le journal) — mais toute différence doit être
délibérée, jamais une omission.

## Dépendances

- Python 3 (celui de l'image Odoo ou tout Python 3.9+ équivalent).
- `markdown-it-py` (voir `requirements.txt`) — seule dépendance externe de
  `build_site.py`. `check.py` et `extract_exports.py` n'utilisent que la
  bibliothèque standard.
- Accès à Claude Docs (outil `mcp__Claude_Docs__export`) pour produire les
  fichiers Markdown d'entrée — le générateur lui-même n'a besoin que de ces
  fichiers, pas d'un accès réseau à Claude Docs.
