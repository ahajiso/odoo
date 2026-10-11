# ROADMAP section 0 – plan (revision 1, 11/10/2026, no code yet)

Basis: NOMENCLATURE.md (retained by the audit), REPORT.md (facts and anomalies),
EXTRACT.md and data/ (read-only inventory and complement). Five items, each audited
before any code; nothing runs on artdubati_test before the audit and the owner's go.
Standard Odoo and OCA first; changes by inheritance; no raw SQL writes.

## Verified (code and database, read-only)
- `maintenance_ok` is defined by `maintenance_product` (« Can be Maintenance »); our
  module depends on it, so it can override the label.
- Equipment categories are created silently by **two** paths: `maintenance_account`
  (`account.move.line._set_equipment_category`, from a bill line) and our own
  `equipment.operation.line._equipment_category` (phase 2 receipts). Both copy the
  product category's name.
- `maintenance.equipment.category.name` is translatable; the model has no `active`
  field (a category is deleted, never archived).
- Changing the category of a stored product with another cost method or valuation
  empties and replenishes its stock at the current cost (`stock_account`
  `product.template.write`); journal entries only in automatic valuation (none today).
- OCA `contract.tag` exists in the server's `contract` 18.0.2.5.3.
- The accounts the matrix needs exist in the company's chart (218300, 205000, 606300,
  612200, 616xxx…); one asset profile only (215400, 5 years); no fixed asset.

## Not verified / hypotheses
- H1: posting the bill of P00381 links the bill line to the existing equipment 871 by
  its serial number and fills `asset_id` (phase 1 behaviour, to rehearse with this
  exact history: receipt done before any bill, price changed after the receipt).
- H2: an existing non-stock equipment can be brought into stock with a third-party
  quant owner without creating a second equipment (path to characterise, item 3).
- H3: the 15 € / 329 € difference of the table saw comes from a standard price typed
  by hand (product history to read in item 3's dry run).

---

## 1. Label « Can be maintained »
- Override in `maintenance_shareholder_equipment` (product.template):
  `maintenance_ok` string « Can be maintained ». Translations from `--i18n-export`
  only: fr « Peut être maintenu », fa « قابل تعمیر و نگهداری است » (audit's wording,
  owner may change it).
- Tests: `fields_get` in en_US, fr_FR, fa_IR returns the three labels.
- Smallest change of the section; shipped with item 2 (same module, one update), unless
  the owner wants it alone first.

## 2. Product creation assistant and default equipment category
Standard first: the product form stays; the assistant is the guided path, **model
constraints are the guarantee** (they apply to every path: form, import, quick create in
a purchase line, API).

Data model (maintenance_shareholder_equipment):
- `product.template.product_family` (selection): durable equipment, material or
  consumable, service, intangible asset (decision D1 on goods for resale and the generic
  sales products).
- `product.template.equipment_category_id`: default equipment category of the product,
  mandatory for durable equipment; refused if it is « To classify » or one of the
  automatic categories, except on products flagged as migrated (`classification_pending`,
  set only by the migration script).
- `product.category`: the family it accepts (a fixed-asset category only for durable
  equipment and intangible assets, a service category only for services…), checked
  against the product's family.
- Consistency checks per family: durable equipment = storable, serial tracking,
  maintainable, category with the fixed-asset flag or the small-equipment flag;
  material / consumable = storable, quantity (lot optional), not maintainable;
  service = service type; intangible = no stock.

Silent creation removed:
- `maintenance_account`: the line's equipment category comes from the product's
  `equipment_category_id`; `_set_equipment_category` refuses (clear message naming the
  product) instead of creating a category.
- Our `_equipment_category`: same rule.

Assistant (TransientModel, menu Inventory → Products → « New product (guided) »): step
1 the family; step 2 only the fields the family needs (name, equipment category for
equipment, product category filtered by family, purchase / sale, internal reference,
supplier); the deduced values are shown read-only (type, tracking, cost method,
valuation, accounts of the category, « posting the bill will create a fixed asset » or
« expensed on 606300 »); creates the product through the ORM (same constraints).
Rights: product creation stays with the existing Inventory / Purchase managers
(decision D6).

Tests: each family created by the assistant; each forbidden combination refused by the
constraints (form and quick-create paths); a bill line and a receipt of a product
without equipment category refused, no category created; translations fr / fa.

## 3. Migration of products and equipment
A setup script (`docs/roadmap0/setup_roadmap0.py`, Odoo shell), dry run by default,
`--apply` after the audit of the dry run, then a control dry run (phase 0 and 2
pattern). Backup first.

- Equipment tree: created as module data of item 2 (external IDs, `noupdate`,
  translations through the .po files), « To classify » included; then the script moves
  the equipment and deletes the 29 imported categories (no equipment) and the automatic
  `All` (89) and `Fixed Assets` (481) once empty. The correspondence of the old codes
  01 to 28 is written in the migration report.
- Product categories: created by the script (accounts are company properties, looked up
  by code and shown in the dry run, never guessed): fixed assets / IT (218300, new test
  profile « Matériel informatique (test) », 3 years, one asset per item), small durable
  equipment (606300; book value C24), measuring & inspection under it, services
  purchased by nature, sales by nature, overheads. **Cost average, valuation manual**
  everywhere for now: no switch to automatic before the accountant's stock accounts
  (C25).
- Products: moved per NOMENCLATURE.md §4 (the dry run lists each move, its cost-method
  change and the stock revaluation Odoo will do); duplicates and TEST products archived
  only after listing their dependencies (moves, bills, contracts, equipment); Computer
  837 and Green cross laser 824 per decision D5.
- Equipment: categories and names per §3.
- The two lasers (anomaly 1): products 836 / 828 made storable with serial tracking; an
  internal serial number per item; physical presence in stock with the third party
  Manager as quant owner; monitor location emptied; contracts EQOP/2026/0738-0739 kept.
  Path decided after characterisation on a local copy (decision D3): a borrowed /
  rented receipt operation reusing the existing equipment, or a standard inventory
  adjustment with owner.
- Table saw (anomaly 2): its product history read in the dry run; alignment decided
  (D4).
- Report: every record moved, created, deleted or archived, with before / after.

## 4. Mac Mini regularisation (after item 3)
1. Product in fixed assets / IT (storable, serial, average cost, manual valuation).
2. Equipment renamed « Mac Mini – 877790 », category IT / Computers & servers.
3. Bill created from P00381 (1 100 € excl. tax) and posted by the accountant or the
   owner: fixed asset created (draft, C4) on 218300 with the test profile, linked to the
   equipment (`asset_id`), equipment cost final 1 100 € from the bill.
Rehearsed first on a local copy with the same history (H1); checks: asset value 1 100,
`asset_id` filled, cost final, monitor rows (inventory value from the asset, stock
value 0 for a fixed-asset category).

## 5. Supplier consignment (separate plan)
Not mixed with items 1 to 4. First the characterisation of a change of owner in Odoo 18
(P4-1 step 2, C23), then its own plan (receipt with the supplier as owner, no value,
controlled consumption, bill at once or periodic, return, losses, exits refused).
`TEST Cement rental` closed there (anomaly 3).

## Order and deployments
1+2 one module update (code, tests, translations, equipment tree as data) → 3 setup
script (dry run, audit, apply, control) → 4 Mac Mini (rehearsal, then operations) → 5
own plan. Insurance and financing registers: a search of standard and OCA modules,
reported separately, before any proposal.

## Decisions asked
- D1: families: are goods for resale and the generic sales products (« Matériaux de
  construction », sales services) families of their own, or « material » / « service »?
- D2: constraints on existing products: only `classification_pending` products (set by
  the migration) may keep « To classify »; every new or edited product must be valid?
- D3: lasers: receipt operation reusing the equipment, or inventory adjustment with
  owner (DEFINITIONS.md: quant owners come from receipt move lines)?
- D4: table saw: align the product's standard price on the bill (15 €) or keep 329 €?
- D5: Computer 837 and Green cross laser 824: equipment or archived?
- D6: who may create products (assistant): the current Inventory / Purchase managers?
