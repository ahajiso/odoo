# Définitions — manuel Odoo L'Art du Bâti

Document de référence à l'usage de Claude. Il rassemble tout ce qui est
*stable* : où vivent les trois documents du manuel, les codes de fiches, les
règles de rédaction, le vocabulaire par langue, le format du journal, et la
fiche technique de l'instance Odoo. La procédure elle-même (quand et comment
agir) est dans `maintenance-manuel-odoo.md`, à côté de ce fichier.

Dernière mise à jour : 03/10/2026 (ajout des conventions d'import en masse,
de capture d'écran et de publication par dépôt git).

## 1. Les trois documents

Claude Docs est la source unique du contenu ; les pages web sous
`lartdubati_manual/manual/<lang>/` sont **générées** à partir de lui et ne
doivent jamais être éditées directement (voir `maintenance-manuel-odoo.md`
§« Source de vérité »).

| Langue | Titre | Doc id (container) | URL |
| --- | --- | --- | --- |
| FR (référence) | Manuel Odoo – L'Art du Bâti (FR) | a7828da9-0a0c-4a7f-8cae-49f1c3d934ab | https://claude.ai/code/artifact/a7828da9-0a0c-4a7f-8cae-49f1c3d934ab |
| EN | Manuel Odoo – L'Art du Bâti (EN) | 3efc85ac-0f1e-4694-90e5-a3256b5d9cbc | https://claude.ai/code/artifact/3efc85ac-0f1e-4694-90e5-a3256b5d9cbc |
| FA | Manuel Odoo – L'Art du Bâti (FA) | c84b1427-c085-42b9-99ef-2565486b743c | https://claude.ai/code/artifact/c84b1427-c085-42b9-99ef-2565486b743c |

Ces trois documents sont liés au compte claude.ai de l'utilisateur. Une
session Claude Code peut les lire, les modifier et les exporter si elle
dispose des outils `mcp__Claude_Docs__*` (c'est le cas des sessions Claude
Code sur le web ouvertes avec ce compte). Sans ces outils, voir la section
« Ce qui n'existe que côté Claude Docs » tout en bas de ce fichier.

### Onglets

| Page web | FR : onglet · tab id · node | EN : onglet · tab id · node | FA : onglet · tab id · node | Codes |
| --- | --- | --- | --- | --- |
| index | Accueil · 05221feb-a132 · d1d291f9-609a | Home · 74e370d1-0795 · 30337180-15e6 | خانه · a79db514-d0c7 · 83d88cca-b426 | — (profils, gabarit, règles, journal) |
| reference | Référence · 47fe5456-87fd · db68ed44-17c1 | Reference · 4209b37f-fe2a · 18c4999b-763a | مرجع · 27b9226c-732c · 19fbef5b-1e02 | REF-01 à REF-10 |
| admin | Admin Odoo · 5b6a64e4-79ec · e9e520e4-6128 | Odoo Admin · aa096bb8-3386 · 7ec38d8c-7e79 | مدیر اودو · d55939d9-a7aa · 6f5f67be-42cd | ADM-01 à ADM-09 |
| parc | Responsable parc · 91901160-3123 · 80b1101f-ee7f | Fleet manager · 6b99ac29-c5ed · 369c8c02-7c72 | انباردار/امین اموال · c9615183-5878 · 7e7daaf3-4f51 | PARC-01 à PARC-09 |
| comptable | Comptable · 0e760d90-5bf2 · b259aee5-6ba6 | Accountant · 1911f8d6-30f8 · 732f18f9-2e73 | حسابدار · f7e2d130-575c · 805cfd89-b3a4 | CPT-01 à CPT-13 |
| chantier | Chantier · 02229e66-47d7 · 1ab14945-7ad7 | Site · 0454b652-a47f · d9ab7a8f-cb6d | کارگاه · ad9f5a05-6add · 1fd65ca3-9d78 | CH-01 à CH-03 |

Rôle « Responsable parc » : EN « Fleet Manager / Storekeeper », FA
« انباردار/امین اموال » (choix de l'utilisateur ; ne plus utiliser
« مسئول پارک » ni « مسئول ناوگان » — un ancien nom de fichier d'export,
`مسئول ناوگان.md`, a néanmoins été conservé comme nom de fichier attendu par
le générateur pour l'onglet FA « parc », voir `lartdubati_manual/tools/README.md`).

Les **ids de blocs** à l'intérieur d'un onglet (ceux qu'on cible avec
`{"kind":"blocks","ids":[...]}`) changent à chaque réécriture : ne jamais les
stocker dans ce fichier. Avant de modifier une fiche, lire l'outline de
l'onglet (`read` sur le node, payload `{"kind":"view","outline":true}`), ou
chercher (`{"kind":"search","text":"…"}` / `"pattern"`). Les **ids de doc**,
**de tab** et **de node** ci-dessus, eux, sont stables — c'est pour ça qu'ils
sont enregistrés ici.

## 2. Règles de rédaction

- Une fiche = une action, titre `## CODE Verbe à l'infinitif…`.
- Plan fixe, dans cet ordre, rubriques vides omises : **Qui · Quand**,
  **Prérequis**, **Étapes** (liste numérotée), **Vérification**,
  **Attention**, **Voir aussi**.
- Menus en gras avec flèches : **Maintenance → Équipement**.
- Menus et champs écrits exactement comme dans l'interface d'Odoo **dans la
  langue de la version** : FR = interface française, EN = interface
  anglaise, FA = interface persane (règle 5 de l'Accueil). Vérifier dans les
  fichiers de traduction officiels Odoo 18 (`addons/*/i18n/fr.po`, `fa.po` ;
  `msgid` = libellé anglais) et dans `lartdubati_manual` /
  `maintenance_shareholder_equipment` i18n pour les champs du module. Voir
  §5 pour les libellés courants.
- Données saisies en français dans Odoo (étiquettes de contact, emplacements
  WH/…, catégorie et produits « Frais généraux », noms d'exemple) : gardées
  telles quelles dans les trois langues, avec une glose si utile.
- Une information partagée vit dans Référence uniquement ; les autres fiches
  citent son code.
- Codes stables : jamais renumérotés ; nouvelle fiche = numéro suivant de
  l'onglet ; fiche supprimée = code retiré, jamais réutilisé.
- Français = référence. EN et FA reprennent les mêmes codes, le même nombre
  de fiches et d'étapes (vérifié par `check.py`, voir
  `lartdubati_manual/tools/README.md`).
- Comptes comptables : plan comptable général, toujours présentés comme « à
  valider par l'expert-comptable ».
- Renvoi vers un écran d'Odoo : **ne rien faire de particulier dans Claude
  Docs** — écrire le chemin de menu en gras comme d'habitude (**Maintenance →
  Équipement**), `build_site.py` le transforme en lien à la génération, dans
  les trois langues. Le dictionnaire `SCREENS` du script associe le libellé
  du dernier segment (par langue) à un XML ID d'action ; si le chemin se
  termine par une action (Nouveau) ou un nom d'enregistrement (L'Art du
  Bâti), le générateur remonte le chemin jusqu'au premier segment connu.
  Ajouter un écran = une ligne par langue dans `SCREENS`
  (`lartdubati_manual/tools/build_site.py`), jamais une URL dans le texte du
  manuel. Les contrôles d'interface (Favoris, Regrouper par) n'y figurent
  pas et restent non liés, c'est voulu.
- Lien écrit à la main dans le texte : réservé aux renvois explicites du type
  « liste complète : [Positions fiscales](…) », sur le même format d'URL.
- Format d'URL des écrans Odoo :
  `https://erp.lartdubati.com/odoo/action-<xml_id>` (le routeur d'Odoo 18
  accepte le XML ID aussi bien que l'identifiant numérique, cf.
  `addons/web/static/src/core/browser/router.js`). Toujours un XML ID,
  jamais un identifiant numérique, et jamais un lien vers un enregistrement
  précis : les ids diffèrent entre `artdubati` et `artdubati_test`. Un lien
  construit ainsi vaut pour les deux bases et survit aux refontes
  d'interface. XML ID déjà utilisés : `account.action_tax_form`,
  `account.action_account_form`, `account.action_move_out_invoice_type`,
  `account.action_move_in_invoice_type`,
  `account.action_account_fiscal_position_form`,
  `account.action_payment_term_form`.
- **Capture d'écran** : seulement quand le lien ne suffit pas à désigner la
  chose (une case parmi plusieurs identiques, un champ noyé dans un onglet
  dense, un bouton qui n'apparaît que dans un état donné, une capture d'un
  assistant qui n'est pas un écran de menu). Recadrée sur la zone concernée,
  jamais la fenêtre entière.
  - **Où les images vivent** : `lartdubati_manual/static/screenshots/<lang>/`
    (un sous-dossier par langue d'interface visible sur la capture — pas
    forcément la langue du texte du manuel qui la montre, voir ci-dessous).
    Servies directement par Odoo comme toute ressource statique d'un module
    (`/lartdubati_manual/static/screenshots/<lang>/<fichier>.png`), sans
    contrôleur dédié.
  - **Comment l'insérer dans Claude Docs** : un lien Markdown normal, dont le
    texte sert de légende et dont l'URL est l'**URL absolue et complète**
    (`https://erp.lartdubati.com/lartdubati_manual/static/screenshots/...`) —
    jamais un chemin relatif ou commençant par `/` seul. Claude Docs
    transforme silencieusement un lien à chemin relatif/host-relatif en texte
    brut (le lien disparaît) ; seule une URL absolue produit un vrai lien.
    Toujours relire le paragraphe après insertion
    (`{"kind":"view","parentId":"<id du bloc>"}`) pour vérifier qu'un
    `<link href="...">` a bien été créé.
  - **Comment ça devient une image à la publication** : `build_site.py`
    reconnaît ce motif exact (lien vers
    `.../lartdubati_manual/static/screenshots/....png|jpg|jpeg`) et le
    transforme en `<figure><img loading="lazy"><figcaption></figure>` — voir
    `IMG_RE` / `link_images()` dans
    `lartdubati_manual/tools/build_site.py`. Aucune image n'est stockée dans
    Claude Docs.
  - **Réutiliser une capture entre langues** : une capture ne montre qu'une
    seule interface (le plus souvent FR). Les fiches EN/FA peuvent pointer
    vers la même image FR tant que l'assistant Odoo concerné n'a pas de
    différence visuelle notable d'une langue à l'autre — ajouter alors une
    précision dans la légende (« French interface shown; the wizard is
    identical in English »). Ne produire une capture par langue que si
    l'interface diffère réellement (ex. RTL en FA).
  - **Prendre les captures sans bandeau de test** : le module
    `lartdubati_env_ribbon` affiche un bandeau rouge sur les bases de test
    (voir §5). Pour une capture propre sans toucher au serveur ni redéployer
    quoi que ce soit, injecter dans la page, avant la capture, via l'outil
    JavaScript du navigateur Claude :
    ```js
    const s = document.createElement('style');
    s.textContent = '.o_env_ribbon_test{display:none !important}';
    document.head.appendChild(s);
    ```
    Purement côté navigateur, pour l'onglet courant : aucun état persistant,
    rien à nettoyer, le bandeau réapparaît tout seul à la fermeture de
    l'onglet ou au rechargement.
- **Import de fichier (données en masse)** : documenté dans les fiches de
  création de catégories, produits et équipements (ADM-01, ADM-02, et la
  fiche PARC dédiée à la création d'équipements/de modèles) comme suit.
  - Chemin : depuis la vue liste du modèle concerné → icône ⚙ (ou menu
    Actions) → **Importer des enregistrements** → déposer le fichier →
    écran de correspondance des colonnes → **Tester** (valide sans créer
    d'enregistrement) → corriger les erreurs signalées → **Importer**.
    Toujours documenter l'usage de **Tester** avant **Importer**.
  - **Piège à toujours rappeler pour les champs de catégorie
    (`maintenance.equipment.category`, `product.category`)** : l'import
    recherche la valeur d'une colonne pointant vers un champ Many2one
    hiérarchique avec une correspondance exacte sur `complete_name` (le
    chemin complet depuis la racine), jamais sur le nom traduit affiché à
    l'écran. `complete_name` n'est **jamais traduit**, même en session
    FR/FA — seules les versions anglaises d'origine (voir REF-03/REF-04)
    fonctionnent dans la colonne du fichier d'import, quelle que soit la
    langue du fichier ou de l'utilisateur qui importe. L'écran « Voir les
    valeurs possibles » du wizard est trompeur : il affiche les noms traduits
    (langue de la session), qui ne correspondront *pas* à l'import. Exemple
    de valeur correcte à mettre dans le fichier, quelle que soit la langue :
    `Assets & Equipment / Power & Workshop Tools / 02 Corded Power Tools`.
    Vérifié par appel direct à l'ORM (`name_search`, `operator:"="`, context
    par défaut) : une recherche sur le nom traduit renvoie `[]`, une
    recherche sur le chemin anglais complet renvoie l'enregistrement.
  - **Fichiers modèles** : un fichier CSV d'exemple par formulaire d'import
    sujet à nos champs personnalisés, sous
    `lartdubati_manual/static/templates/` (mêmes règles de publication/lien
    que les captures d'écran : lien Markdown vers l'URL absolue
    `https://erp.lartdubati.com/lartdubati_manual/static/templates/<fichier>.csv`,
    texte du lien = libellé du fichier).
    - `import-equipements-modele.csv` — équipements
      (`maintenance.equipment`), colonnes alignées sur nos champs
      personnalisés (propriétaire, responsable/partenaire, statut de
      propriété, mode d'acquisition, localisation, etc.) — voir le fichier
      pour la liste exacte des colonnes et des valeurs attendues (libellés
      FR exacts de l'interface, catégories en chemin complet anglais).
    - `import-produits-modele.csv` — modèles/produits (fiches techniques
      d'équipement), colonnes Nom, Référence interne, Catégorie de
      produits (même règle de chemin complet anglais), Ventes, Achats,
      Type de produit, Suivre l'inventaire.
    - Chaque nouveau fichier modèle doit être validé au moins une fois dans
      l'assistant d'import d'`artdubati_test` (**Tester**, jamais
      **Importer**) avant d'être publié, pour garantir qu'il ne produit
      aucune erreur de correspondance.
- Phrases courtes, pas d'emoji.

### Journal des modifications (onglet Accueil)

Tableau `Date | Fiches | Modification`. Ajouter une ligne à chaque
modification, la plus récente en bas. Format date : JJ/MM/AAAA (chiffres
persans en FA).

## 3. Matrice d'impact : changement Odoo → fiches à revoir

| Changement dans Odoo | Fiches à mettre à jour |
| --- | --- |
| Nouvelle catégorie d'équipement, renommage, déplacement | REF-03 (arbre + prochain numéro libre), ADM-04 si procédure de contrôle change |
| Nouvelle catégorie de produit, modification comptable d'une catégorie | REF-04, ADM-02 si réglages changent |
| Nouvel emplacement / chantier, convention de nommage | REF-07 ; ADM-03 si procédure change |
| Nouvel entrepôt, changement de code d'entrepôt | REF-07, ADM-06 |
| Étiquettes de contact (Actionnaire, Loueur, Prêteur, Emprunteur, Partenaire…), filtre des partenaires dans le module | REF-09, REF-10, PARC-09, PARC-05/06/07, ADM-08 |
| Module lartdubati_manual ou procédure de publication | ADM-07, Accueil (ligne « Consultable… »), `maintenance-manuel-odoo.md` §« Publication » |
| Champ ajouté/modifié/supprimé dans maintenance_shareholder_equipment | REF-05, ADM-05 (version), + toute fiche citant le champ (chercher son libellé dans les trois docs) |
| Nouvelle valeur de Statut de propriété | REF-06, CPT-02, et PARC-08 / CPT-04 si liée à un incident |
| Nouvelle valeur de Mode d'acquisition | REF-01, REF-05, CPT-05, fiche PARC dédiée si nouveau cas |
| Installation d'un module d'immobilisations (OCA ou autre) | CPT-03 (remplacer « hors Odoo » par la procédure), CPT-06, REF-08, CPT-02 |
| Changement de plan comptable / comptes utilisés | CPT-02 à CPT-13 |
| Dépenses générales (nouveau type, nouveau compte) | CPT-07, REF-04 |
| Changement de droits d'accès / groupes | Rubrique Prérequis des fiches concernées ; tableau « Qui lit quoi » (Accueil) |
| Nouveau profil utilisateur | Nouvel onglet dans les trois docs + ligne dans « Qui lit quoi » + `UI[lang]["pages"]` de `build_site.py` |
| Montée de version Odoo | Toutes les fiches : vérifier menus et libellés dans les trois langues ; REF-08 (limites) ; ADM-05 |
| Limite levée (ex. traduction des catégories de produit) | REF-08 + fiches qui la citent (REF-04, ADM-02) |
| Nouveau formulaire d'import documenté / nouveau fichier modèle | La fiche ADM/PARC concernée + `lartdubati_manual/static/templates/` + ce fichier (§2, note sur l'import) si la règle générale change |

## 4. Référence technique Odoo

| Élément | Valeur |
| --- | --- |
| Instance | https://erp.lartdubati.com — Odoo 18.0 Community, Docker sur VPS |
| Base | artdubati (production) ; artdubati_test (base de test) |
| Conteneur | odoo_web |
| Modules sur mesure | `/opt/odoo/addons/custom` sur le serveur = clone de github.com/ahajiso/odoo |
| Module métier | maintenance_shareholder_equipment, version 18.0.1.0.2, dépend de maintenance et stock |
| Module facturation BTP | lartdubati_facturation 18.0.1.0.0 : taux réduits 10 %/5,5 % réactivés, taxes et position fiscale d'autoliquidation de sous-traitance (art. 283-2 nonies CGI), articles main-d'œuvre/matériaux/conseil avec comptes 704/707/706, mentions BTP sur res.company (onglet « Mentions BTP ») imprimées sur facture et devis, menu d'export FEC, conditions de paiement. Installé sur artdubati_test uniquement. |
| Module bandeau d'environnement | lartdubati_env_ribbon 18.0.1.0.0 : bandeau rouge quand le nom de la base se termine par `_test`, `_staging` ou `_dev`. Composant Owl purement client (`static/src/env_ribbon/env_ribbon.{js,xml,css}`), aucune donnée serveur. Pour le désactiver temporairement le temps d'une capture d'écran, voir §2 « Prendre les captures sans bandeau de test » — aucune modification du module ni du serveur. |
| Dépôts OCA ajoutés | server-ux-18 (date_range), account-reconcile-18 (account_reconcile_oca, account_statement_base), bank-statement-import-18 (OFX, CAMT) ; addons_path mis à jour dans `/opt/odoo/config/odoo.conf` |
| Module de publication | lartdubati_manual 18.0.1.0.0 : routes `/manuel`, `/manuel/<lang>/<page>` (auth user, langue de l'utilisateur par défaut) ; menu racine « Manuel » (act_url, nouvel onglet) traduit en « Manual » (en.po) et « راهنما » (fa_IR.po) ; pages lues depuis `lartdubati_manual/manual/<lang>/*.html` (contrôleur `controllers/main.py`, constante `MANUAL_DIR`) ; fichiers sous `lartdubati_manual/static/` (captures d'écran, fichiers modèles d'import) servis automatiquement par le mécanisme standard des modules Odoo, sans route dédiée. |
| OCA immobilisations | account_asset_management 18.0.1.1.11 (+ report_xlsx, report_xlsx_helper) installé sur artdubati_test (vérifié le 03/10/2026) ; catégories d'immobilisation en attente de l'expert-comptable ; non installé en production |
| Hiérarchie catégories équipement | module OCA maintenance_equipment_category_hierarchy |
| Langues | en_US (base), fr_FR, fa_IR |
| Application comptable | CE = « Facturation » (Invoicing / صدور فاکتور) ; pas de rapport compte de résultat en CE |

### Libellés Odoo 18 courants (EN / FR / FA)

| EN | FR | FA |
| --- | --- | --- |
| Maintenance → Equipment | Maintenance → Équipement | نگهداری ← تجهیزات |
| Product Information (onglet) | Informations sur le produit | اطلاعات محصول |
| Sales / Purchase (cases produit) | Ventes / Achat | فروش / خرید |
| Product Type : Goods / Service / Combo | Type de produit : Biens / Service / Combo | نوع محصول : کالاها / خدمت |
| Track Inventory | Suivre l'inventaire | ردیابی موجودی |
| Used in location (champ natif) | Lieu d'utilisation | استفاده شده در محل |
| Individual / Company (type de contact) | Individu (vérifier : fr.po officiel = « Particulier ») / Société | فردی / شرکت |
| Invoicing → Configuration → Accounting → Chart of Accounts | Facturation → Configuration → Comptabilité → Plan comptable | صدور فاکتور ← پیکربندی ← حسابداری ← جدول حساب ها |
| Invoicing → Vendors → Bills | Facturation → Fournisseurs → Factures fournisseurs | صدور فاکتور ← فروشندگان ← صورتحساب |
| Invoicing → Accounting → Journal Items | Facturation → Comptabilité → Écritures comptables | صدور فاکتور ← حسابداری ← آیتم های روزنامه |
| Group By → Add Custom Group | Regrouper par → Ajouter un groupe personnalisé | گروه‌بندی برمبنای ← افزودن گروه سفارشی |
| Favorites → Save current search · Shared | Favoris → Enregistrer la recherche actuelle · Partagé | علاقه‌مندی ها ← ذخیره سازی فایل فعلی · به اشتراک گذاشته شده |
| Import Records | Importer des enregistrements | درون‌ریزی گروهی / وارد کردن رکوردها |
| Test (assistant d'import) | Tester | آزمایش |
| Import (assistant d'import, bouton final) | Importer | درون‌ریزی |

### Champs du module (technique → FR / FA)

**maintenance.equipment** : `owner_type` → Type de propriété (Entreprise /
Actionnaire / Tiers) ; `owner_partner_id` → Propriétaire (tiers) / مالک
(شخص ثالث) ; `accounting_ownership` → Propriété comptable / مالکیت حسابداری ;
`ownership_state` → Statut de propriété / وضعیت مالکیت ; `handover_date` →
Date de remise ; `handover_value` → Valeur de remise ; `replacement_value` →
Valeur de remplacement / ارزش جایگزینی ; `initial_condition` → État initial ;
`return_obligation` → Obligation de restitution / تعهد بازگرداندن ;
`physical_wear_active` → Suivi de l'usure physique actif / ردیابی فرسودگی
فیزیکی فعال ; `accounting_depreciation_active` → Amortissement comptable
actif / استهلاک حسابداری فعال ; `current_location_id` (Many2one
stock.location, tracking) → Localisation actuelle / مکان فعلی ;
`acquisition_mode` → Mode d'acquisition / نحوه تحصیل (Achat / Location /
Emprunté à un tiers / Prêté à un tiers) ; `rental_counterparty_id` →
Partenaire de location / prêt / طرف مقابل اجاره/قرض ; `rental_end_date` →
Date de fin de location / prêt / تاریخ پایان اجاره/قرض.

Groupes de vue : « Propriété tierce (actionnaire) » / مالکیت شخص ثالث
(سهامدار), « Localisation » / مکان, « Gestion du parc (acquisition) » /
مدیریت ناوگان (نحوه تحصیل).

**maintenance.request** : `repair_cost` → Coût de réparation / هزینه تعمیر ;
`repairer` → Réparateur / تعمیرکار ; `repair_invoice_ref` → Référence facture
de réparation / شماره فاکتور تعمیر.

**Champs natifs produit utiles pour l'import** (Odoo 18, `fields_get`,
context `lang: fr_FR`) : `name` → Nom, `type` → Type de produit, `categ_id`
→ Catégorie de produits, `sale_ok` → Ventes, `purchase_ok` → Achats,
`default_code` → Référence interne, `is_storable` → Suivre l'inventaire.

**Champs attendus sur la colonne « Nom » lors de l'import d'équipements** :
l'assistant suggère le champ Odoo « Nom de l'équipement » (pas simplement
« Nom ») — utiliser cet intitulé exact en en-tête de colonne dans le fichier
d'import pour que la correspondance automatique fonctionne du premier coup.

### Pièges connus (à ne pas reproduire)

- `product.category.name` n'est pas traduisible en Odoo 18
  (`translate=False`) : noms de catégories produit identiques dans toutes
  les langues. Même règle, par construction du champ `complete_name`, pour
  `maintenance.equipment.category` (voir §2, note sur l'import).
- Import de masse sur un champ Many2one hiérarchique (catégories
  équipement/produit) : la correspondance se fait sur `complete_name`
  (chemin complet anglais), jamais sur le nom traduit affiché à l'écran —
  voir §2.
- Fichiers `.po` Odoo 18 : chaque entrée exige `#. module: <nom>` ET la
  référence exacte `#: model:ir.model.fields,field_description:…` /
  `…fields.selection,name:…` / `model_terms:ir.ui.view,arch_db:…` /
  `model:ir.ui.menu,name:…`. Toujours partir de
  `odoo -d artdubati --i18n-export=x.pot --modules=<module>
  --stop-after-init`, jamais d'un `.po` écrit de mémoire.
- `docker exec -i odoo_web … < fichier` lit le fichier sur l'hôte, pas dans
  le conteneur.
- Ne jamais deviner un external ID : le chercher et l'afficher avant d'agir.
- Odoo Community n'a pas de module Immobilisations (`account_asset` est
  Enterprise).
- Le champ natif « Lieu d'utilisation » (location, texte libre) n'est pas
  utilisé ; seule Localisation actuelle fait foi.
- Mise à jour module : `docker exec -i odoo_web odoo -d artdubati -u
  <module> --stop-after-init` puis `docker restart odoo_web`. Nécessaire
  quand le code, les vues, le menu ou les `.po` d'un module changent ; **pas**
  pour les seules pages HTML du manuel (`git pull` suffit, voir
  `maintenance-manuel-odoo.md` §« Publication »).
- Lien Markdown Claude Docs à chemin relatif (`/lartdubati_manual/...`) :
  silencieusement transformé en texte brut, pas en lien. Toujours une URL
  absolue (`https://erp.lartdubati.com/...`) — voir §2.

## 5. Ce qui n'existe que côté Claude Docs

Cette section ne concerne que les sessions **sans** les outils
`mcp__Claude_Docs__*` (voir §1). Une telle session ne peut
**ni lire ni modifier** le contenu des fiches — celui-ci vit exclusivement
dans les trois documents Claude Docs listés en §1, qui sont des documents
claude.ai liés au compte de l'utilisateur, pas des fichiers du dépôt. Ce que
le dépôt contient, c'est : le **résultat** de ce contenu (les pages HTML déjà
générées, sous `lartdubati_manual/manual/`), l'**outil** qui le régénère
(`lartdubati_manual/tools/`), et **cette documentation**. Concrètement, une
session Claude Code peut :

- régénérer les pages HTML si on lui fournit les exports Markdown à jour
  (soit en dossier déjà exporté, soit en les import-collant dans le dépôt) ;
- vérifier la cohérence FR/EN/FA des exports fournis (`check.py`) ;
- modifier le générateur lui-même (`build_site.py`, templates CSS/JS,
  correspondances d'écrans) ;
- mettre à jour cette documentation.

Elle ne peut pas, sans qu'on lui donne un export à jour : savoir ce que
contient une fiche, ajouter ou modifier une fiche, consulter le journal des
modifications, ou vérifier qu'une fiche correspond encore à l'état réel
d'Odoo. Si une tâche demande cela, la bonne réponse est de le dire
explicitement plutôt que de deviner à partir des pages HTML déjà publiées
(qui peuvent être en retard sur Claude Docs, ou — plus rarement — avoir été
régénérées depuis un export qui n'a pas encore été relu).
