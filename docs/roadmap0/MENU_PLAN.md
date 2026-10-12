# ROADMAP section 0 – « Item and Service Requests » menu (revision 2, 12/10/2026)

Revision 2 answers the audit of fa06f62 / 061aaa1 (D1, D2, D3 accepted by the owner;
development and ordinary deployment authorised once the corrections below are made).
Module `maintenance_shareholder_equipment` 18.0.5.0.0 → **18.0.5.0.1** (views, labels,
messages, one migration script reloading the translations; no column, no data change).

## 1. Facts (code and Odoo 18 sources, read)

- One action `maintenance_shareholder_equipment.action_product_creation_request`;
  rights on `product.creation.request`: Equipment Operator, `purchase.group_purchase_user`,
  `stock.group_stock_user`, Product Catalogue Manager; rules: own requests, all for the
  catalogue managers, multi-company. Unchanged.
- A menu is shown only when all its parents are (`ir.ui.menu._visible_menu_ids`). The
  root of Inventory (`stock.menu_stock_root`) needs `stock.group_stock_user` or
  `stock.group_stock_manager`; the root of Purchase (`purchase.menu_purchase_root`) needs
  `purchase.group_purchase_user` or `purchase.group_purchase_manager`. **A user with
  only « Product Catalogue Manager » saw neither path** (audit point 1, confirmed).
  His data rights were already enough: the existing tests approve and execute with
  `cat_manager2` (internal user + catalogue manager only).
- On a module **update**, a `menuitem`'s `groups` are only added (`convert.py`), never
  removed; its name, when taken from the action, is written in English only; and the
  update keeps the French and Persian values of every record whose English source
  changed. Found by the update test below: without the corrections of §2 the Inventory
  menu kept the buyer and manager groups and everything read « Demandes de produit » /
  « درخواست‌های محصول » after the update.

## 2. What is done (decisions D1 to D3 of the owner; D4 below to confirm)

1. Names (D1): « Item and Service Requests » / « Demandes d'articles et services » /
   « درخواست‌های کالا و خدمات »; form « Item or Service Request »; field label (D3)
   « Available for Item and Service Requests ». No menu under Invoicing (D2).
2. **D4 – the catalogue managers' entry point (to confirm)**: their own application
   « Product Catalogue » (« Catalogue produits », « کاتالوگ محصولات »; product icon),
   holding Item and Service Requests and Structural Corrections, visible to the
   catalogue managers only. **No Inventory nor Purchase right is given** to show a menu
   (the alternative, refused here, was to require Inventory/User or Purchase/User for
   every catalogue manager). One entry per application:

   | Menu | Parent | Groups |
   |---|---|---|
   | `menu_product_creation_request` | Inventory → Products (`stock.menu_stock_inventory_control`) | Equipment Operator, Inventory/User |
   | `menu_product_creation_request_purchase` | Purchase → Products (`purchase.menu_purchase_products`) | Purchase/User |
   | `menu_product_catalogue_root` → `menu_product_catalogue_requests`, `menu_product_structural_correction` | own application | Product Catalogue Manager |

   The Inventory menu removes, with `-group`, the groups it had in 18.0.5.0.0 (buyer,
   catalogue manager). A catalogue manager who is also a buyer sees two applications
   (Purchase and Product Catalogue), never two entries in one; same action, no domain:
   the record rules decide what each one sees.
3. **Scope always visible** (audit point 2): an information banner at the top of the
   request form: « This request creates an item or a service in the catalogue. It does
   not record a contract, a subscription or a bill. » (fr, fa); the empty-list help says
   it too.
4. The refused direct creation names the three paths « according to your access
   rights » (one message, `env._` so that it is translated from a plain function).
5. Migration script `migrations/18.0.5.0.1/post-migrate.py`: reloads this module's own
   .po files with overwrite (`ir.module.module._update_translations(overwrite=True)`,
   no SQL), just before Odoo's own load without overwrite. A translation edited by hand
   in the interface for one of this module's terms would be replaced by the file's.
6. Translations: `--i18n-export` (fr_FR, fa_IR, .pot) from a database updated to the new
   code; the unchanged terms keep the versioned translations, the 7 new or changed
   terms translated; no empty entry.

## 3. Tests (`tests/test_request_menus.py`, 11 tests, language set by the tests)

- one action, three entries, their parents and exact groups; the corrections under
  the catalogue application only;
- names of the action and the three menus and the field label in en_US, fr_FR, fa_IR;
- **catalogue manager alone** (internal user + Product Catalogue Manager, no Inventory
  nor Purchase right, asserted): sees his application, requests and corrections, and
  neither Inventory nor Purchase entry; opens the list and the form as the web client
  does (`get_views`, `web_search_read`, `web_read` with the form's fields), approves and
  executes another user's request; opens the structural corrections;
- buyer only → Purchase entry only; inventory user only → Inventory entry only;
  accountant (Billing) → no entry, no catalogue application;
- **manager + buyer** → Purchase and Product Catalogue entries, one per application;
- banner in the form, in English and French;
- through the action: a buyer sees his own requests only; a catalogue manager (alone or
  buyer too) sees all; a request of another company is invisible to a manager until
  that company is his;
- the requester still cannot approve his own request (catalogue manager alone);
- the direct creation message names the three paths and « According to your access
  rights »;
- the investor's menus: the `lartdubati_investor_home` test on `load_menus` (Stock
  Monitor only) runs unchanged.

## 4. Proof (local, 12/10/2026)

- Update rehearsed on a copy of the migrated rehearsal database (server's code and
  inventory data, 18.0.5.0.0, fr and fa loaded) → 18.0.5.0.1: no error; afterwards the
  action and the three menus read « Demandes d'articles et services » /
  « درخواست‌های کالا و خدمات », the field label is translated, the Inventory menu has
  only Equipment Operator and Inventory/User, the Purchase menu Purchase/User.
- Full suites of both modules on that database: **282 tests, 0 failed** (271 + 11) after
  the last test correction (the first run found one error in the new test itself, a
  request without its mandatory category). On the server: **281** (the real websocket
  class is skipped there). Clean-checkout run: test_logs/.
- HTTP routes (`docs/phase4/routes.py`) before and after the update: identical (319
  lines); no controller added.

## 5. Tooling (audit of 061aaa1)

- `restore_db.sh`: the registry check writes the Odoo shell's stdout and stderr to
  temporary files, checks the shell's exit code, then the `REGISTRY OK` marker, shows
  the last lines of the diagnostic on failure; the files are in the `trap`. Tested with
  a fake `docker`: success, shell failure, no marker.
- `check_modules.sh`: `RAWP` and `ERRP` created with the others and removed by the
  `trap`; tested on both paths, no temporary file left.

## 6. Deployment (ordinary update, after the audit)

```bash
cd /opt/odoo/addons/custom
COMMIT=<commit announced after the audit>
git fetch origin +refs/heads/main:refs/remotes/origin/main
git log -1 --oneline origin/main                       # $COMMIT
rm -rf /tmp/menu && mkdir -p /tmp/menu
git archive origin/main docs/phase4 docs/deploy_modules.sh docs/backup_db.sh \
  docs/restore_db.sh | tar -x -C /tmp/menu
git status --short | head                              # nothing
bash /tmp/menu/docs/phase4/check_modules.sh before     # PLATFORM OK (before)
bash /tmp/menu/docs/backup_db.sh menu                  # BACKUP OK
BACKUP=$(sed -n 's/^DUMP=//p' /opt/odoo/logs/menu_backup)
bash /tmp/menu/docs/deploy_modules.sh "$BACKUP" 281 menu "$COMMIT"
bash /tmp/menu/docs/phase4/check_modules.sh after      # PLATFORM OK (after)
docker exec -i odoo_web odoo shell -d artdubati_test --no-http \
  < /tmp/menu/docs/phase4/routes.py > /opt/odoo/logs/menu_routes.txt   # compared by Claude
```

One command at a time; any FAILED or a test count other than 281: stop, then
`bash /tmp/menu/docs/restore_db.sh menu`. Interface checks: a buyer finds « Demandes
d'articles et services » under Achats → Produits, the banner in the form; once a
catalogue manager is named, the « Catalogue produits » application with the requests
and the structural corrections; the investor's menus unchanged.

## 7. Not part of this change

- Naming the catalogue manager(s) and the acceptance of the requests (README.md).
- A pre-filled family per entry (e.g. « service » from Purchase): later, if wanted.
