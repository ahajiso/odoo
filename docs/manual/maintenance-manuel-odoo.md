# Maintenance du manuel Odoo – L'Art du Bâti

Document technique à l'usage de Claude. Il décrit où se trouve le manuel
utilisateur, comment il est construit et comment le tenir à jour. Les
éléments stables (ids, codes de fiches, règles de rédaction, vocabulaire,
fiche technique Odoo) sont dans `definitions-manuel.md`, à côté de ce
fichier — ce document-ci couvre la procédure : quand agir, dans quel ordre,
avec quels outils.

Dernière mise à jour : 03/10/2026 (publication par dépôt git plutôt que par
archive copiée sur le serveur ; ajout de la documentation sur l'import de
fichier et des captures d'écran).

## 1. Règle fondamentale

Tout changement dans Odoo (configuration, module, catégorie, emplacement,
champ, droit, procédure) doit être reporté dans le manuel **avant** que le
changement soit considéré comme terminé. Un changement n'est « fini » que
lorsque :

1. il fonctionne dans Odoo ;
2. les fiches impactées du manuel FR sont à jour ;
3. une ligne est ajoutée au journal des modifications (onglet Accueil,
   format en §« Journal » de `definitions-manuel.md`) ;
4. les versions EN et FA sont mises à jour avec les mêmes codes, ou le
   retard est noté dans le journal (« EN/FA à faire ») ;
5. le site `/manuel` est régénéré et poussé sur GitHub (§4) ; l'utilisateur
   n'a plus qu'à faire `git pull` sur le serveur.

Si rien dans le manuel n'est impacté, le dire explicitement à l'utilisateur
(« aucune fiche impactée ») plutôt que de passer l'étape sous silence.

Pour savoir quelles fiches sont concernées par un changement donné, voir la
matrice d'impact (`definitions-manuel.md` §3).

## 2. Source de vérité

**Claude Docs est la source unique du contenu.** Les trois documents listés
dans `definitions-manuel.md` §1 (Manuel Odoo – L'Art du Bâti, FR/EN/FA) sont
l'endroit où une fiche se crée, se corrige, se complète. Les pages HTML sous
`lartdubati_manual/manual/<lang>/*.html`, dans ce dépôt, sont un **résultat
généré** : elles ne doivent jamais être éditées à la main. Toute édition
faite directement sur un fichier `.html` serait écrasée à la prochaine
régénération, sans avertissement.

**EN et FA ne sont pas retraduits automatiquement à chaque changement.** Ce
sont des documents Claude Docs vivants, tenus en parallèle du FR : une
nouvelle fiche FR est répercutée en EN et FA à la main (ou par Claude), avec
les codes identiques et les libellés de l'interface Odoo dans leur propre
langue (`definitions-manuel.md` §2) — ce n'est pas une traduction mot à mot
automatisée du texte FR, mais la même information réécrite avec le
vocabulaire correct de chaque interface. Si le temps manque, le retard est
noté dans le journal (« EN/FA à faire ») plutôt que d'improviser une
traduction non vérifiée.

Le site publié (`lartdubati_manual/manual/`) peut donc légitimement être en
retard de quelques minutes ou heures sur Claude Docs, le temps de régénérer
et pousser — mais jamais en avance, et jamais divergent sur le fond.

## 3. Procédure de mise à jour d'une fiche

1. Identifier le changement Odoo et les fiches impactées
   (`definitions-manuel.md` §3).
2. Lire l'outline des onglets concernés (FR, puis EN, FA) — jamais à partir
   d'ids de blocs mémorisés, qui changent à chaque réécriture
   (`definitions-manuel.md` §1).
3. Modifier uniquement les fiches concernées : `update` sur le node de
   l'onglet (engine prose), `replace` d'un bloc (guard `ifHash`, ou `ifRev`
   sur ses propres écritures), ou cible `{"kind":"find","text":"…"}` (texte
   sans `**` ; `"nth":1` si plusieurs occurrences ; `with` en `"as":"text"`
   pour garder la mise en forme, `"as":"markdown"` pour ajouter du gras).
4. Nouvelle fiche : `insert` après la dernière fiche de l'onglet, code
   suivant, gabarit de rédaction (`definitions-manuel.md` §2). Nouvelle
   ligne de tableau : `insert` `"as":"blocks"` en `"side":"end"` sur l'id du
   tableau.
5. Ajouter la ligne au journal (Accueil, dernier tableau) dans les trois
   langues.
6. Répercuter en EN/FA avec les libellés de leur interface (§2 ci-dessus,
   `definitions-manuel.md` §2 et §4), ou noter « EN/FA à faire » dans le
   journal.
7. Régénérer et publier (§4 ci-dessous).
8. Mettre à jour `definitions-manuel.md` si les ids, la version du module,
   les champs, les libellés ou la matrice d'impact changent ; mettre à jour
   ce document si la procédure elle-même change.
9. Dire à l'utilisateur quelles fiches ont changé et confirmer qu'il n'a
   rien d'autre à faire que `git pull` sur le serveur (§4).

Si le changement Odoo est préparé par Claude (module, script, config), la
mise à jour du manuel fait partie de la livraison : la proposer dans la même
réponse, avant de déclarer le travail terminé.

### Capture d'écran ou fichier modèle d'import

Si la fiche a besoin d'une capture d'écran ou d'un nouveau fichier modèle
d'import, voir `definitions-manuel.md` §2 pour les conventions (où les
fichiers vivent, comment les lier depuis Claude Docs, comment désactiver le
bandeau de test le temps de la capture). Ajouter le fichier sous
`lartdubati_manual/static/screenshots/<lang>/` ou
`lartdubati_manual/static/templates/`, le committer avec le reste (§4), puis
seulement ensuite écrire le lien Markdown dans la fiche.

## 4. Génération et publication

Chaîne complète : **Claude Docs (source, 3 documents) → export Markdown par
onglet → pages HTML (`lartdubati_manual/tools/build_site.py`) → commit +
push dans `lartdubati_manual/manual/<lang>/` du dépôt
github.com/ahajiso/odoo → `git pull` sur le serveur.**

Le serveur n'a plus d'étape de copie d'archive : le dossier des modules sur
mesure du serveur (`/opt/odoo/addons/custom`, voir
`definitions-manuel.md` §4) **est** un clone de ce dépôt. Publier une mise à
jour du manuel se résume, côté serveur, à `git pull` — aucun redémarrage,
aucune commande `-u` (ça, c'est uniquement nécessaire quand le code, les
vues ou les fichiers `.po` d'un module changent, pas pour les pages HTML du
manuel, cf. `definitions-manuel.md` §« Pièges connus »).

Étapes, côté session Claude qui a accès à Claude Docs :

1. Exporter chaque onglet des trois documents avec
   `mcp__Claude_Docs__export` (voir `lartdubati_manual/tools/README.md` pour
   le détail exact de l'appel et des noms de fichiers attendus).
2. Récupérer les fichiers exportés dans des dossiers source
   (`python3 extract_exports.py …`, voir le même README).
3. Générer : pour chaque langue,
   `python3 build_site.py --lang <lang> --src <dossier_src_lang> --out
   ../manual` depuis `lartdubati_manual/tools/` (détail complet, dépendances
   et options dans `lartdubati_manual/tools/README.md`).
4. Contrôler avant de committer :
   - cohérence FR/EN/FA avec `check.py` (mêmes fiches, mêmes codes, mêmes
     renvois, même nombre d'étapes — voir le README des outils) ;
   - liens `page#code` et ancres valides ;
   - rendu visuel (desktop + mobile, RTL pour FA) — par une capture rapide
     des pages générées dans le navigateur, pas seulement une relecture du
     HTML.
5. Commit + push sur `github.com/ahajiso/odoo`, avec les lignes
   d'attribution Claude en fin de message (voir le rappel système de la
   session en cours pour le format exact). Inclure dans le même commit :
   les pages `lartdubati_manual/manual/<lang>/*.html` régénérées, et tout
   fichier nouveau sous `lartdubati_manual/static/` (captures, modèles
   d'import) référencé par les fiches qui viennent d'être modifiées.
6. Dire à l'utilisateur qu'un `git pull` sur le serveur (dans
   `/opt/odoo/addons/custom`) suffit à publier — aucun redémarrage d'Odoo.

### Historique : ancienne méthode par archive (abandonnée)

Avant le passage du dossier des modules sur mesure du serveur à un clone git
(voir `definitions-manuel.md` §4), la publication se faisait par archive
zip copiée sur le serveur (`publier_manuel.sh`) et nécessitait un script
séparé pour l'installation initiale du module
(`installer_module_manuel.sh`). Ces deux scripts ne sont plus d'actualité et
n'ont pas été repris dans ce dépôt — seule la méthode par `git pull` ci-dessus
s'applique désormais. Si un serveur devait un jour revenir à un déploiement
par archive (nouvel environnement non cloné depuis ce dépôt, par exemple),
réécrire un script équivalent plutôt que d'aller chercher l'ancien : il
copiait `lartdubati_manual/manual/<lang>/` dans un dossier détecté par
inspection du point de montage Docker, ce qui n'a plus de sens une fois le
dossier suivi par git.

## 5. Ce que fait et ne fait pas cette documentation

- Elle décrit la procédure et les règles ; elle ne contient jamais le texte
  des fiches lui-même (celui-ci n'existe que dans Claude Docs, voir
  `definitions-manuel.md` §5).
- `lartdubati_manual/tools/` contient tout le code du générateur : il n'y a
  pas, par ailleurs, d'étape manuelle de mise en forme HTML, de CSS ou de JS
  en dehors de ce que `build_site.py` produit. Toute capture d'écran ou
  fichier modèle d'import, en revanche, est bien un fichier statique ajouté
  à la main (§3 ci-dessus) — ce n'est pas généré.
- Si une étape de ce document ne correspond plus à ce que fait réellement
  une session Claude (nom de fichier changé, nouvel outil, nouvelle
  contrainte de l'API Claude Docs), corriger ce document dans la même
  session plutôt que de laisser la divergence s'installer.

## 6. Questions ouvertes (au 03/10/2026)

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
- Documentation de l'import en masse (ADM-01, ADM-02, fiche PARC dédiée) :
  ajoutée en FR/EN/FA le 03/10/2026 avec deux captures d'écran et deux
  fichiers modèles (`definitions-manuel.md` §2) ; export, régénération et
  publication (§4 de ce document) restent à faire pour que le site
  `/manuel` reflète ces fiches.
