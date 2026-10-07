# Définitions — manuel Odoo L'Art du Bâti

Document de référence pour toute personne ou tout agent qui modifie Odoo ou
le manuel. Il rassemble tout ce qui est *stable* : où vivent les pages du
manuel, les codes de fiches, les
règles de rédaction, le vocabulaire par langue, le format du journal, et la
fiche technique de l'instance Odoo. La procédure elle-même (quand et comment
agir) est dans `maintenance-manuel-odoo.md`, à côté de ce fichier.

Dernière mise à jour : 07/10/2026 (les fiches s'éditent directement dans les
pages HTML du dépôt ; Claude Docs n'est plus utilisé).

## 1. Les pages du manuel

Les pages HTML du dépôt sont la source unique du contenu (voir
`maintenance-manuel-odoo.md` §« Source de vérité ») :
`lartdubati_manual/manual/<lang>/<page>.html`, servies sur
`https://erp.lartdubati.com/manuel/<lang>/<page>` (connexion requise). Balisage
d'une fiche et outils : `lartdubati_manual/tools/README.md`.

| Page (fichier) | FR | EN | FA | Codes |
| --- | --- | --- | --- | --- |
| index | Accueil | Home | خانه | — (profils, gabarit, règles, journal) |
| reference | Référence | Reference | مرجع | REF-01 à REF-10 |
| admin | Admin Odoo | Odoo Admin | مدیر اودو | ADM-01 à ADM-12 |
| parc | Responsable parc | Fleet manager | انباردار/امین اموال | PARC-01 à PARC-11 |
| comptable | Comptable | Accountant | حسابدار | CPT-01 à CPT-15 |
| chantier | Chantier | Site | کارگاه | CH-01 à CH-03 |
| investisseur | Investisseur | Investor | سرمایه‌گذار | INV-01 à INV-04 |

Les noms d'onglets affichés viennent de `UI[lang]["pages"]` dans
`lartdubati_manual/tools/build_site.py` ; les préfixes de codes et leur page,
de `CODE_PAGE` dans le même fichier.

Rôle « Responsable parc » : EN « Fleet Manager / Storekeeper », FA
« انباردار/امین اموال » (choix de l'utilisateur ; ne plus utiliser
« مسئول پارک » ni « مسئول ناوگان »).

Onglet FA « investisseur » : nom « سرمایه‌گذار » avec demi-espace (ZWNJ,
U+200C).

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
  §4 pour les libellés courants.
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
- Renvoi vers un écran d'Odoo : écrire le chemin de menu en gras comme
  d'habitude (**Maintenance → Équipement**, en HTML `<strong>…</strong>`) ;
  `refresh.py` le transforme en lien, dans les trois langues. Le dictionnaire `SCREENS` du script associe le libellé
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
  - **Comment l'insérer dans une fiche** : un lien dont le texte sert de
    légende et dont l'URL pointe vers le fichier
    (`<a href="/lartdubati_manual/static/screenshots/fr/x.png">Légende</a>`).
  - **Comment ça devient une image** : `refresh.py` reconnaît ce motif (lien
    vers `.../lartdubati_manual/static/screenshots/....png|jpg|jpeg`) et le
    transforme en `<figure><img loading="lazy"><figcaption></figure>` — voir
    `IMG_RE` / `link_images()` dans `lartdubati_manual/tools/build_site.py`.
  - **Réutiliser une capture entre langues** : une capture ne montre qu'une
    seule interface (le plus souvent FR). Les fiches EN/FA peuvent pointer
    vers la même image FR tant que l'assistant Odoo concerné n'a pas de
    différence visuelle notable d'une langue à l'autre — ajouter alors une
    précision dans la légende (« French interface shown; the wizard is
    identical in English »). Ne produire une capture par langue que si
    l'interface diffère réellement (ex. RTL en FA).
  - **Prendre les captures sans bandeau de test** : le module
    `lartdubati_env_ribbon` affiche un bandeau rouge sur les bases de test
    (voir §4). Pour une capture propre sans toucher au serveur ni redéployer
    quoi que ce soit, injecter dans la page, avant la capture, via l'outil
    console JavaScript du navigateur :
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
    que les captures d'écran : lien vers
    `/lartdubati_manual/static/templates/<fichier>.csv`, texte du lien =
    libellé du fichier).
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
| Nouveau profil utilisateur | Nouvelle page dans les trois langues + ligne dans « Qui lit quoi » + `UI[lang]["pages"]` et `CODE_PAGE` de `build_site.py` |
| Montée de version Odoo | Toutes les fiches : vérifier menus et libellés dans les trois langues ; REF-08 (limites) ; ADM-05 |
| Limite levée (ex. traduction des catégories de produit) | REF-08 + fiches qui la citent (REF-04, ADM-02) |
| Accès des investisseurs (profils d'accès aux stocks, groupe Investisseur, règles) — module lartdubati_investor_home | ADM-10, ADM-11, INV-02, INV-04, REF-08 |
| Écran d'accueil investisseur (web_quick_start_screen, `docs/investor_home/setup_investor_home.py`) | INV-01, ADM-10 |
| Colonnes, calculs ou réglages du moniteur de stock (bi_sql_editor, `docs/stock_monitor/`, Paramètres → Inventaire → Moniteur de stock) | INV-03, ADM-12, CPT-15, REF-08 |
| Type de lieu d'un emplacement (place_type), adresse d'entrepôt | ADM-06, REF-07, INV-03 |
| Contrats fournisseurs de location (OCA contract, maintenance_equipment_contract) | PARC-11, CPT-14, PARC-05 |
| Création d'équipement depuis facture fournisseur (OCA maintenance_account) | PARC-10, CPT-01 |
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
| Module investisseur | lartdubati_investor_home 18.0.1.4.0 : type de lieu des emplacements, profils d'accès aux stocks (res.users `stock_access_id`), groupe « Investisseur », règles globales, contrainte équipement actif ⇒ stock interne, réglages du moniteur de stock (Paramètres → Inventaire). Moniteur = 2 rapports OCA bi_sql_editor (`docs/stock_monitor/`) ; accueil = OCA web_quick_start_screen (`docs/investor_home/`). Installé sur artdubati_test uniquement. |
| Dépôts OCA (investisseur) | contract-18 (contract, maintenance_equipment_contract), reporting-engine-18 (bi_sql_editor), web-18 (web_quick_start_screen), server-ux-18 (base_menu_visibility_restriction) ; maintenance_account, base_maintenance |
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
| Import records | Importer des enregistrements | ورود رکورد |
| Test (assistant d'import) | Tester | تست |
| Import (assistant d'import, bouton final) | Importer | ورود |
| See possible values (assistant d'import) | Voir les valeurs possibles | مقادیر ممکن را مشاهده کنید. |
| Product (champ de l'équipement, module OCA maintenance_product) | Article | Product (non traduit en persan) |

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
- Éditer une page sans lancer `refresh.py` : le sommaire, la recherche des
  autres pages et les liens automatiques restent sur l'ancien état.
