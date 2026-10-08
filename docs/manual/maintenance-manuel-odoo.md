# Maintenance du manuel Odoo – L'Art du Bâti

Document de procédure pour toute personne ou tout agent (Claude Code, Codex,
développeur) qui modifie Odoo ou le manuel. Il décrit où se trouve le manuel
utilisateur, comment le modifier et comment le publier. Les éléments stables
(pages et codes de fiches, règles de rédaction, vocabulaire, fiche technique
Odoo) sont dans `definitions-manuel.md`, à côté de ce fichier.

Dernière mise à jour : 07/10/2026 (les fiches s'éditent directement dans les
pages HTML du dépôt ; Claude Docs n'est plus utilisé).

## 1. Règle fondamentale

Tout changement dans Odoo (configuration, module, catégorie, emplacement,
champ, droit, procédure) doit être reporté dans le manuel **avant** que le
changement soit considéré comme terminé. Un changement n'est « fini » que
lorsque :

1. il fonctionne dans Odoo ;
2. les fiches impactées du manuel FR sont à jour ;
3. une ligne est ajoutée au journal des modifications (page Accueil, format en
   §« Journal » de `definitions-manuel.md`) ;
4. les versions EN et FA sont mises à jour avec les mêmes codes, ou le
   retard est noté dans le journal (« EN/FA à faire ») ;
5. les pages sont rafraîchies (`refresh.py`), vérifiées (`check.py`),
   commitées et poussées (§4) ; l'utilisateur n'a plus qu'à faire `git pull`
   sur le serveur.

Si rien dans le manuel n'est impacté, le dire explicitement (« aucune fiche
impactée ») plutôt que de passer l'étape sous silence.

Pour savoir quelles fiches sont concernées par un changement donné, voir la
matrice d'impact (`definitions-manuel.md` §3).

## 2. Source de vérité

**Les pages HTML du dépôt sont la source unique du contenu** :
`lartdubati_manual/manual/<lang>/<page>.html` (langues `fr`, `en`, `fa` ;
pages `index`, `reference`, `admin`, `parc`, `comptable`, `chantier`,
`investisseur`). Le module Odoo `lartdubati_manual` les sert telles quelles sur
`https://erp.lartdubati.com/manuel` (connexion requise). Il n'y a pas d'autre
copie : ni Claude Docs, ni projet Claude, ni fichier Markdown.

Dans une page, seul le **corps de la carte** s'édite à la main (tout ce qui
suit le sommaire, jusqu'à `</div></main>`). L'en-tête, les onglets, le
sommaire, l'index de recherche, le pied de page et les liens automatiques sont
réécrits par `lartdubati_manual/tools/refresh.py` (balisage attendu et détail :
`lartdubati_manual/tools/README.md`).

**EN et FA ne sont pas retraduits automatiquement.** Une nouvelle fiche FR est
répercutée en EN et FA avec les codes identiques et les libellés de
l'interface Odoo dans leur propre langue (`definitions-manuel.md` §2 et §4) :
la même information réécrite avec le vocabulaire de chaque interface, pas une
traduction mot à mot. Si le temps manque, le retard est noté dans le journal
(« EN/FA à faire ») plutôt que d'improviser une traduction non vérifiée.

## 3. Procédure de mise à jour d'une fiche

1. Identifier le changement Odoo et les fiches impactées
   (`definitions-manuel.md` §3). Retrouver une fiche : `grep -n "INV-03"
   lartdubati_manual/manual/fr/*.html`, ou la recherche du site.
2. Modifier uniquement les fiches concernées, dans le corps de la page FR.
3. Nouvelle fiche : à la fin de la page de l'onglet, code suivant de l'onglet
   (jamais un code réutilisé), gabarit de rédaction (`definitions-manuel.md`
   §2) et balisage du README des outils.
4. Ajouter la ligne au journal (page Accueil, dernier tableau) dans les trois
   langues.
5. Répercuter en EN/FA (§2 ci-dessus), ou noter « EN/FA à faire » dans le
   journal.
6. Rafraîchir et vérifier (§4).
7. Mettre à jour `definitions-manuel.md` si les pages, la version d'un module,
   les champs, les libellés ou la matrice d'impact changent ; mettre à jour ce
   document si la procédure elle-même change.
8. Dire à l'utilisateur quelles fiches ont changé et qu'il n'a rien d'autre à
   faire que `git pull` sur le serveur (§4).

Si le changement Odoo est préparé par un agent (module, script, config), la
mise à jour du manuel fait partie de la livraison : la faire dans le même
travail, avant de déclarer celui-ci terminé.

### Capture d'écran ou fichier modèle d'import

Conventions dans `definitions-manuel.md` §2 (quand faire une capture, où les
fichiers vivent, comment masquer le bandeau de test). Ajouter le fichier sous
`lartdubati_manual/static/screenshots/<lang>/` ou
`lartdubati_manual/static/templates/`, puis le lier depuis la fiche (le
README des outils donne le balisage) et le committer avec la page.

## 4. Rafraîchissement, vérification, publication

Chaîne complète : **édition de `lartdubati_manual/manual/<lang>/*.html` →
`refresh.py` → `check.py` → commit + push sur github.com/ahajiso/odoo →
`git pull` sur le serveur.**

1. Rafraîchir les pages modifiées et leurs voisines :
   ```bash
   cd lartdubati_manual/tools
   python3 refresh.py          # toutes les langues (ou : python3 refresh.py fr)
   ```
   Sans cette étape, le sommaire de l'onglet, la recherche des autres pages
   et les liens automatiques (codes, menus, captures) ne voient pas la
   modification.
2. Contrôler :
   - `python3 check.py` : cohérence FR/EN/FA (mêmes fiches, mêmes codes, mêmes
     renvois, mêmes nombres, même nombre d'étapes, aucun renvoi orphelin) ;
     toute différence restante doit être délibérée et notée au journal ;
   - `git diff` : seules les fiches voulues ont changé (le reste du diff doit
     se limiter à l'index de recherche et à la date du pied de page) ;
   - rendu visuel des pages touchées (bureau, mobile, RTL pour FA), dans un
     navigateur, pas seulement une relecture du HTML.
3. Commit + push sur `github.com/ahajiso/odoo`, avec dans le même commit les
   pages modifiées et tout nouveau fichier sous `lartdubati_manual/static/`
   (captures, modèles d'import) qu'elles référencent.
4. Publication : le dossier des modules sur mesure du serveur
   (`/opt/odoo/addons/custom`, voir `definitions-manuel.md` §4) **est** un
   clone de ce dépôt. Un `git pull` dans ce dossier suffit : aucun
   redémarrage, aucune commande `-u` (nécessaire seulement quand le code, les
   vues ou les `.po` d'un module changent, pas pour les pages du manuel).

### Historique : méthodes abandonnées

- Jusqu'au 07/10/2026, le contenu vivait dans trois documents Claude Docs
  (FR/EN/FA), exportés en Markdown puis convertis en HTML par
  `build_site.py`. Les pages actuelles du dépôt sont le dernier état de ces
  documents ; elles sont désormais la source. Les outils d'export Claude Docs
  (`extract_exports.py`, `helpers/`) ont été retirés.
- Avant le passage du dossier des modules à un clone git, la publication se
  faisait par archive zip copiée sur le serveur (`publier_manuel.sh`,
  `installer_module_manuel.sh`). Ces scripts ne sont plus d'actualité.

## 5. Ce que fait et ne fait pas cette documentation

- Elle décrit la procédure et les règles ; le texte des fiches est dans les
  pages HTML.
- `lartdubati_manual/tools/` contient le gabarit (CSS, JS, libellés, table
  `SCREENS`) et les outils `refresh.py` et `check.py` : il n'y a pas d'autre
  mise en forme à maintenir. Captures d'écran et fichiers modèles d'import
  sont des fichiers statiques ajoutés à la main.
- Si une étape de ce document ne correspond plus à la pratique (nom de
  fichier changé, nouvel outil), corriger ce document dans le même travail
  plutôt que de laisser la divergence s'installer.

## 6. Questions ouvertes (au 03/10/2026)

Les questions pour l'expert-comptable (comptes, TVA, immobilisations, devises) sont
regroupées dans `docs/QUESTIONS_COMPTABLE.md`, avec le choix arrêté et où le changer.

- Type de contact « Individu » (manuel FR) vs « Particulier » (traduction
  officielle Odoo 18 fr.po) : à vérifier dans l'interface réelle, puis
  aligner REF-09, REF-10, PARC-09.
- OCA immobilisations : dès que l'installation est confirmée, vérifier les
  menus (Facturation → Immobilisations ; Facturation → Configuration →
  Immobilisations → Catégories d'immobilisation) puis réécrire CPT-03 et
  CPT-06, ajuster CPT-02 (sortie via le bouton « Sortir »), REF-08
  (supprimer la ligne « aucun lien automatique… » ou la reformuler), ajouter
  une fiche ADM pour les catégories d'immobilisation (comptes
  2154/28154/6811, durée, linéaire, prorata — à valider par l'expert-
  comptable). Libellés FR du module : Immobilisation, Catégorie
  d'immobilisation, Compte d'immobilisation, Compte de dépréciation, Compte
  de dépréciation (charge), Méthode de calcul, Nombre d'années, Prorata
  temporis, Tableau des amortissements, Calcul des amortissements, Sortir,
  Valeur d'achat, Date d'activation. Droits : groupe Facturation suffit pour
  les immobilisations ; Administrateur pour les catégories.
- Filtre éventuel des champs Propriétaire (tiers) / Partenaire de location /
  prêt par étiquette (modification du module, non demandée à ce jour).
- Comptes comptables CPT-02 à CPT-08 : validation par l'expert-comptable.
- Partage du manuel aux utilisateurs : à faire par Ali.
- Facturation BTP : les taxes d'autoliquidation créées par
  lartdubati_facturation n'ont aucun tag de déclaration. Les cases exactes
  de la CA3 pour l'autoliquidation nationale (distincte de
  l'intracommunautaire) doivent être obtenues de l'expert-comptable, puis
  renseignées sur les lignes de répartition des 4 taxes. Tant que ce n'est
  pas fait, CPT-10 et CPT-11 portent l'avertissement correspondant.
- Régime de TVA : débits ou encaissements, non tranché. Les taxes « S »
  (encaissement) et « G » (débits) sont toutes actives ; CPT-09 le signale.
- Mise en production : toute la configuration de facturation est sur
  artdubati_test. Au passage en production, installer
  lartdubati_facturation et lartdubati_env_ribbon sur artdubati, puis
  relire CPT-09 à CPT-13 et ADM-09 pour retirer les mentions « base de
  test ».
- SIRET et assurance décennale en cours d'obtention : compléter la fiche
  société, l'onglet Mentions BTP (ADM-09) et prévoir l'inscription à la
  plateforme agréée (module l10n_fr_pdp).
