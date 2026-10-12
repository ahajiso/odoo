# ROADMAP section 0 – « Item and Service Requests » menu: plan (revision 1, 12/10/2026, no code yet)

Owner's proposal after the deployment of 5823e71 (README.md, « Open after the
deployment »): the creation requests sit under Inventory → Products → Product Requests,
a path nobody looks in for a service or a subscription. Nothing runs on artdubati_test
before the audit and the owner's go.

## 1. Facts (code and Odoo 18 sources, read)

- Action `maintenance_shareholder_equipment.action_product_creation_request`
  (« Product Requests », model `product.creation.request`, list and form).
- Its only menu: `maintenance_shareholder_equipment.menu_product_creation_request`,
  parent `stock.menu_stock_inventory_control` (Inventory → Products), sequence 90,
  groups: Equipment Operator, `purchase.group_purchase_user`,
  `stock.group_stock_user`, Product Catalogue Manager. Structural Corrections next to
  it (catalogue managers only).
- Rights on `product.creation.request` (ir.model.access.csv): the same four groups;
  record rules: own requests for operators, buyers and inventory users, all for
  catalogue managers, multi-company.
- Odoo 18 parents found in the sources (no guessed external ID):
  `purchase.menu_purchase_products` (« Products », parent `purchase.menu_purchase_root`,
  sequence 5); `account.menu_finance_payables` (« Vendors », Invoicing).
- The current name appears in: the action, the form and list titles, the group of the
  product category form, the field label « Available for Product Requests », two
  guard messages (« … Inventory → Products → Product Requests), never directly. »,
  product_catalogue.py) and README.md. French « Demandes de produit », Persian
  « درخواست‌های محصول ».
- The investor accounts see only the Stock Monitor menu
  (`lartdubati_investor_home` test on `load_menus`): a new menu restricted to staff
  groups stays invisible to them, and that test runs again.

## 2. Proposal

1. **Rename** the action, form, list and category group: « Item and Service Requests »
   (fr « Demandes d'articles et services », fa « درخواست‌های کالا و خدمات »; Odoo's
   French already says « Article » for Product). The form title « Item or Service
   Request ». The guard messages give both new paths.
2. **Second menu, same action**, under Purchase → Products
   (`purchase.menu_purchase_products`), groups `purchase.group_purchase_user` and
   Product Catalogue Manager. No new action, model, right or rule: the buyer already
   has the rights and sees his own requests.
3. The Inventory menu stays (operators and inventory users), renamed.
4. Unchanged: technical names (model, external IDs, sequence « PCR/ »), the workflow,
   the guards, the rights and rules.
5. Not in the request: the real subscription (supplier, amount, period, renewal,
   documents, bills) belongs to phase A (recurring expenses and contracts). The menu's
   help text says it in one line: « To create a product or a service, not to record a
   contract or a bill. »

## 3. Decisions for the owner

- **D1 – names**: « Item and Service Requests » / « Demandes d'articles et services » /
  « درخواست‌های کالا و خدمات » (Persian to confirm), or another wording.
- **D2 – Invoicing → Vendors**: proposed **not now**. The accounting users (Billing,
  Accountant) have no right on `product.creation.request`: a menu there would need a new
  access line and an « own requests » rule for `account.group_account_invoice`, that is
  a security change with its own tests. Taken only if the owner wants accountants to
  request items themselves; otherwise they ask a buyer.
- **D3 – field label**: « Available for Product Requests » → « Available for Item and
  Service Requests » (only the label; the column `request_ready` is unchanged). Proposed
  yes, for one vocabulary.

## 4. Implementation (after the go)

- `views/product_catalogue_views.xml`: names, help text, second `menuitem`
  (`menu_product_creation_request_purchase`, sequence after Purchase's own Products
  menus).
- `models/product_catalogue.py`: field label (D3), the two guard messages.
- Version **18.0.5.0.1** (views and labels only, no column, no data migration).
- Translations: `odoo --i18n-export` of the module, then the French and Persian
  strings filled in the exported files (never written by hand from scratch).
- Docs: README.md (paths), CLAUDE.md, platform_expected.txt (AFTER line recomputed with
  platform.py on the final code).

## 5. Tests

- The two menus exist, point to the same action, with their parents and groups (by
  external ID).
- A buyer without Inventory rights sees the Purchase menu and opens the list; an
  inventory user without Purchase rights sees the Inventory menu only; an accountant
  without these groups sees neither (D2 not taken).
- The names in en_US, fr_FR and fa_IR (`with_context(lang=…)` on the action and menus;
  the tests set their language explicitly).
- The guard message names the new paths.
- The investor test on `load_menus` unchanged and passing (Stock Monitor only).
- Full suites of both modules on a clean checkout, log versioned; HTTP routes inventory
  (`docs/phase4/routes.py`): no route added (no controller), compared with the previous
  output.

## 6. Deployment (one ordinary update, no migration)

Standard window of the phases (`docs/phase4/check_modules.sh before`, `backup_db.sh`,
`deploy_modules.sh <backup> <tests> <label> <commit>` without `KEEP_STOPPED`,
`check_modules.sh after`), expected test count stated with the proof. Rollback:
`restore_db.sh` (permissions restored by 5823e71). The tooling proposal 061aaa1 (platform
check never silent, registry loaded after a restore) can ride along if audited.
Interface checks: a buyer finds « Item and Service Requests » under Purchase → Products,
fr and fa labels, the investor's menus unchanged.

## 7. Open points, not part of this change

- A catalogue manager to name, then the acceptance of the requests (README.md).
- Pre-filled family per menu (e.g. « service » from Purchase): possible later with a
  context default on a second action; not proposed now (one action, no duplication).
