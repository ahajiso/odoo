# ROADMAP section 0 – inventory of artdubati_test (11/10/2026)

Source: `run_inventory.sh` at a9568ea, run once by the owner after the audit's go
(`/opt/odoo/logs/roadmap0_inventory_2026-10-11_073438.txt`, 77 lines, END present).
Read-only, rolled back. One company: « Docteur Bain » (the company's name in the
database).

## 1. Product categories (12)
- Every category uses **manual valuation** (`manual_periodic`). Correction (audit of
  f19873d): manual does not mean « not valued ». Odoo still values every storable
  product (valuation layers, quantity × cost, the value the monitor shows); it only
  posts no journal entry at receipt or delivery, so the stock input, output and
  valuation accounts are not used, hence empty everywhere. The stock value is then not
  in the general ledger: it is booked by hand at closing (accountant).
- The cost method decides that value: `All` is at **standard** cost, the consumable
  categories 20 to 25 at **average** cost (phase 0). The storable products that are not
  equipment (TEST Cement bag, Green cross laser, Laser rangefinder 823; quantities not
  listed by the inventory) sit in `All`: their value is the standard price typed on the
  product, not the purchase cost. The phase 0 choice
  (average cost for consumables) does not apply to any product today.
- `All` (id 1): standard cost, expense 607000, **14 products**, linked to the
  equipment category `All`.
- `All / Expenses / Consumables & Accessories` and its six children 20 to 25 (ids 11
  to 17, imported 25/09, average cost, expense 607000): **0 products**. The
  consumables (cement bags) sit in `All`.
- `All / Expenses / Frais généraux` (id 18): 3 service products, each with its own
  expense account (626000, 606400, 627800): legitimate overrides.
- `All / Fixed Assets` (id 19, phase 0): expense 215400 with profile « Matériel et
  outillage (test) », fixed-asset flag on, average cost, **2 products** (360° green
  laser, Laser rangefinder 828), both non-storable.
- No category has an income or expense account inherited from a parent: each one
  holds its own (Odoo copies the default when a category is created).

## 2. Products (19), what matters
- **Mac Mini** (template 843) in `All`: expense 607000, no asset profile.
- Table saw (8) in `All`, storable, maintenance_ok: its bill was posted on 607000
  (test choice C19).
- **Duplicate « Laser rangefinder »**: 823 in `All` (storable, not maintainable) and
  828 in `All / Fixed Assets` (non-storable, maintainable).
- Green cross laser (824), Computer (837) in `All`; TEST products (compressor, cement
  bag, scaffold rent) still present.
- Overrides found only on services (income 704000 / 706000 / 708300, expense 613500,
  626000, 606400, 627800): coherent with their nature.

## 3. Equipment categories (31)
- **28 imported business categories** (`Assets & Equipment / …`, codes 01 to 28,
  25/09, by f.t.1): no product category, **0 equipment**.
- `All` (id 89): created 04/10 by test@test.com, linked to product category `All`,
  **2 equipment**.
- `Fixed Assets` (id 481): created **10/10 14:54** by f.i.1@febitmail.com, linked to
  product category `All / Fixed Assets`, **2 equipment**.
- `All` and `Fixed Assets` match exactly what `maintenance_account` creates when a
  product category has no equipment category (`_prepare_equipment_category_vals`: the
  product category's name and link, created in sudo). So every real equipment sits in an
  automatic category named after the accounting category, and the business tree is
  unused.

## 4. Label
`maintenance_ok` is defined by `maintenance_product`: en_US « Can be Maintenance »,
fr_FR « Peut être en maintenance », fa_IR « Can be Maintenance » (no Persian
translation). Wanted: « Can be maintained », « Peut être maintenu », Persian equivalent.

## 5. Mac Mini
- Product [MM1220] Mac Mini (variant 811), category `All`, storable, serial tracking,
  standard price 0.
- Purchase **P00381**, confirmed 10/10: 1 × **1 100 € HT**, received 1, **invoiced 0**
  (to invoice). **No bill exists.**
- Receipt Bg/IN/00006 done into Bg/Stock, serial 877790, through operation
  EQOP/2026/0740 (receipt, done).
- Equipment 871 « **Device 1** », category `All`, owned, integrated, cost **1 850 € HT
  provisional** (source: order, P00381), no fixed asset, no bill line.
- Why no fixed asset: (1) no bill was ever posted (the asset is created when the bill is
  posted); (2) even with a bill, the category `All` sends it to 607000, which has no
  asset profile: no asset would be created. At the approval of EQOP/2026/0740 the
  planned treatment was therefore « account 607000, no fixed asset ».
- 1 850 vs 1 100: the equipment cost was taken from the order at receipt; the order
  line now says 1 100. Hypothesis: the price was changed on the order after the
  receipt (to check in the order's history).
- The operation is done: its frozen treatment no longer blocks a change of category or
  the bill (the snapshot only applies to approved, not yet executed operations).

## 6. Third-party stock
- « Owner on stock » enabled (group: 5 users).
- One real quant: 15 TEST Cement bags in TBER/Stock owned by « TEST Supplier (owner) »
  (P4-1, quant 10); the −15 in Inventory adjustment is its counterpart.

## Owner's decisions (11/10/2026)
- The company name « Docteur Bain » is right.
- The 28 imported equipment categories are a first draft: they may be renamed, merged,
  removed or completed; unused ones are not kept only because they were imported. The
  equipment tree describes the nature and use of physical goods, never the accounting
  treatment.
- Four classifications kept apart: equipment categories, product categories, contract
  natures, business registers (docs/roadmap0/NOMENCLATURE.md).
- Persian label proposed by the audit: « قابل تعمیر و نگهداری است ».
- Before any data change: the read-only complement (complement.py), then the mapping.

## Proposed order (each item: its own plan and audit)
1. **Label** (independent, small): local inheritance of `maintenance_ok` string,
   translations exported, `fields_get` tested in three languages. Owner: Persian
   wording.
2. **Read-only complement**: the four equipment of `All` / `Fixed Assets` and the
   history of P00381's price.
3. **Two classifications and product creation** (0.2, 0.3, 0.4): the business tree as
   the equipment classification; a default equipment category on the product; no
   automatic category from `maintenance_account` (refused with a clear message when
   the product has none); move the 4 equipment, then remove `All` and `Fixed Assets`
   (equipment); duplicates and TEST products; consumables into categories 20 to 25.
   Owner: mapping of each product and equipment.
4. **Mac Mini** (0.5): test choice: IT fixed asset (1 100 € HT), new product category
   `All / Fixed Assets / IT equipment` on 218300 with its own profile (3 years, test),
   to confirm by the accountant; equipment category 18, name, then the bill from
   P00381 (1 100 € HT): asset created at posting, cost final from the bill.
   Rehearsed locally first.
5. **Accountant** (0.6): questions added to QUESTIONS_COMPTABLE.md (IT account and
   duration, capitalisation threshold, table saw C19, consumables in `All`).
6. **Supplier consignment** (0.7): separate plan after characterising the change of
   owner.
