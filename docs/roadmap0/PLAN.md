# ROADMAP section 0 – plan (revision 2, 11/10/2026, no code yet)

Basis: NOMENCLATURE.md (retained), REPORT.md (facts, anomalies), EXTRACT.md and data/.
Nothing runs on artdubati_test before the audit and the owner's go. Standard Odoo and
OCA first; changes by inheritance; no raw SQL writes.

Revision 2 answers the audit of c8d2d66: a persistent creation request instead of a
transient assistant (§2), no `product_family` and no `classification_pending` on the
product (§2.2), the complete data of the request (§2.3), no provisional mass move of
stored products (§3.2), guarded deletion of categories (§3.4), Mac Mini bill posted by
an accounting user only (§4), decisions D1 to D6 applied.

## Verified (code and database, read-only)
- `maintenance_ok` comes from `maintenance_product` (« Can be Maintenance »); our module
  depends on it.
- Two paths create equipment categories silently: `maintenance_account`
  (`account.move.line._set_equipment_category`) and our
  `equipment.operation.line._equipment_category`.
- `maintenance.equipment.category`: name translatable, no `active` field (deleted, never
  archived).
- Changing a stored product's category to another cost method or valuation empties and
  replenishes its stock at the current cost (`stock_account`); journal entries only in
  automatic valuation.
- OCA `contract.tag` in the server's `contract` 18.0.2.5.3. OCA `base_tier_validation`
  18.0.3.5.2 (server-ux, « Mature ») exists but is **not installed**.
- Our `product.category` already carries `is_fixed_asset_stock`,
  `default_warranty_status`, `default_insurance_status`.

## Hypotheses to check (local rehearsal or dry run)
- H1: the bill of P00381 links to the existing equipment 871 by its serial and fills
  `asset_id` (phase 1 behaviour, with this exact history).
- H2: an existing non-stock equipment (the lasers) can be brought into stock with a
  third-party owner by an operation that reuses the equipment and its contract.
- H3: origin of the table saw's 329 € (standard price) against its 15 € bill.
- H4: an existing untracked stock unit (Green cross laser 824) can become a serial item
  integrated as equipment by a controlled operation.

---

## 1. Label « Can be maintained »
Override of `maintenance_ok` in `maintenance_shareholder_equipment`: « Can be
maintained »; translations from `--i18n-export`: fr « Peut être maintenu », fa
« قابل تعمیر و نگهداری است ». Test: `fields_get` in en_US, fr_FR, fa_IR. Shipped with
item 2.

## 2. Product creation request (persistent document)

### 2.1 Document and workflow
Model `product.creation.request` (mail.thread, activities, attachments), sequence
PCR/YYYY/NNNN:
- states: draft → to approve → approved → done, plus refused and cancelled;
- requester (creator), responsible (who completes it), approver (who decided), dates;
- the approval freezes a signature of the request's decisive data; any change after
  approval sends it back to « to approve » with the list of changed values (same pattern
  as `equipment.operation`, phase 2f);
- execution (catalogue manager): creates the `product.template` (and its supplier
  line) through the ORM with every check, links it to the request, never creates or
  posts a bill, an order or a stock move;
- refusal and cancellation keep the reason; the chatter is the decision log.

Approval mechanism (decision D7): A) the phase 2 pattern of `equipment.operation`
(already audited, no new module, same users and screens) — proposed; B) OCA
`base_tier_validation` (configurable tiers, but a new module on the platform: platform
fingerprint, parity, route inventory, its own audit).

### 2.2 No family column on the product
Demonstration: from the standard fields, a product's family can be deduced except
between materials, consumables and goods for resale, which share type (storable),
tracking and `maintenance_ok`; only their **category** tells them apart:
- service: `type = service`;
- durable equipment: storable, serial tracking, `maintenance_ok`;
- intangible asset: not storable, category of the intangible branch;
- material / consumable / goods for resale: storable, not maintainable: by category.
So the family is **not** stored on the product: it is a choice of the request (which
filters the categories and the fields asked) and, afterwards, deduced from the
product's category **branch**. The branches are the product categories created by the
migration with an external ID per root (fixed assets, small durable equipment,
materials, consumables, goods for resale, intangible assets, services purchased,
sales); the checks read the root's external ID, not a new column. No
`classification_pending`: every product is classified at the end of the migration.

Checks on `product.template` (every path: form, import, quick create, API), per branch:
equipment = storable, serial, maintainable, equipment category mandatory and valid;
materials, consumables, goods = storable, not maintainable; services = service type;
intangible = not storable. `All`, the automatic equipment categories and « To classify »
are refused for any product created or edited after the migration.

### 2.3 Data of the request
Company; family; name, internal reference, barcode; unit and purchase unit; purchase /
sale; product category (filtered by the family); tracking (deduced, shown); equipment
category (equipment, mandatory, never « To classify »); supplier, supplier reference,
price (excl. tax), minimum quantity, lead time; purchase and sale taxes; sale price
(excl. tax) and initial cost (excl. tax); warranty and insurance defaults (from the
category, shown); photo and documents (attachments).
Shown read-only for the chosen company and category: effective income and expense
accounts, asset profile and « posting the bill will create a fixed asset » or the
expense account, cost method, valuation, stock accounts.
Duplicate detection (archived products included) on name (normalised), internal
reference, barcode and supplier reference: exact barcode or internal reference blocks
the approval; a similar name or supplier reference must be confirmed by the approver.

### 2.4 Rights and quick creation (D6)
- New group « Product Catalogue Manager » (own category): approves and executes requests,
  edits products.
- Requesters: Equipment Operator, Purchase User, Inventory User: create and follow
  their requests.
- Product creation outside a request is refused to everyone but catalogue managers
  (guard on `product.template` / `product.product` `create`, so quick create in purchase
  lines and imports are covered, with a message pointing to the request); `no_create`
  on the product fields of the purchase and operation lines for the others. The
  migration script runs as superuser.

### 2.5 Silent creation of equipment categories removed
`maintenance_account` and our receipt take the product's default equipment category
(`product.template.equipment_category_id`, a link, not a classification flag);
without one they refuse with a message naming the product, never create a category.

Tests: each family requested, approved, executed; re-approval after a change;
duplicates; refusals by family; quick create refused to a purchase user, allowed to a
catalogue manager; bill line and receipt without equipment category refused, no category
created; fr / fa translations; HTTP routes inventory (new module data only, no route).

## 3. Migration (setup script: dry run, audit, apply, control dry run)

### 3.1 Created
- Equipment tree (NOMENCLATURE.md §1) as module data of item 2 (external IDs,
  `noupdate`, translations in the .po files), « To classify » included (transitional).
- Product category branches with their accounts looked up by code and shown in the dry
  run, never guessed: only those whose treatment is decided now (fixed assets / IT with
  the test profile « Matériel informatique (test) », 3 years, one asset per item;
  services purchased and sales by nature; intangible assets). The material, consumable,
  goods and small-equipment branches wait for §3.2.
- Contract tags (NOMENCLATURE.md §5).

### 3.2 Stored products: no provisional move (audit point 4)
Only what does not depend on the stock accounts moves now: services (no stock), the Mac
Mini (fixed asset, manual valuation is its final treatment), the two lasers (third-party
owned: no company value whatever the category). The table saw, Green cross laser 824 and
TEST Cement bag stay in their category until the accountant's stock accounts (C25) and
the small-equipment answer (C24); they then move once, directly to the final
configuration. One revaluation, never two.

### 3.3 Products and equipment
- Equipment: moved to the tree and renamed (NOMENCLATURE.md §3).
- Lasers (D3): a controlled equipment operation reusing the equipment and their contracts
  EQOP/2026/0738-0739: internal serial, receipt into stock with Manager as quant owner,
  monitor location emptied; products 836 / 828 storable with serial (H2; if the existing
  receipt branches cannot reuse an equipment, a « regularisation into stock » operation
  type, planned and audited first).
- Green cross laser 824 (D5): integrated as a serial equipment by a controlled
  operation (H4), unless its explicit deletion as test data is decided.
- Computer 837 (D5): archived if it has no stock, document or use (checked in the dry
  run); duplicates and TEST products archived after the same check.
- Table saw (D4): nothing aligned automatically; the dry run reads its bill
  BILL/2026/10/0006 and the origin of the 329 € (valuation layers, product history); if
  15 € is the real total price, a controlled and traced revaluation afterwards.
- At the end no product is in `All` or « To classify » except those §3.2 keeps waiting,
  listed in the report.

### 3.4 Deleting equipment categories
Refused while a category is referenced by: an equipment (active or archived), a product
(default equipment category), a product category, a bill line
(`account.move.line.equipment_category_id`), or any other field pointing to
`maintenance.equipment.category` (found dynamically through `ir.model.fields`); defaults
and saved filters mentioning their ids are listed. Their `__import__.cat_*` external IDs
are deleted with them and listed in the report, with the old code → new category
correspondence.

## 4. Mac Mini (after §3, rehearsed locally first: H1)
1. Product into fixed assets / IT; equipment renamed « Mac Mini – 877790 », category
   IT & communications / Computers & servers.
2. Bill created **in draft** from P00381 (1 100 € excl. tax) by the flow.
3. Posted only by a user with accounting rights (Billing or Accountant group) named by
   the owner; the flow never posts it. Expected: draft fixed asset on 218300 with the
   test profile, `asset_id` on the equipment, cost final 1 100 € from the bill.

## 5. Supplier consignment
Separate plan, after characterising a change of owner in Odoo 18 (P4-1 step 2, C23).
`TEST Cement rental` closed there.

## Order and deployments
§1 + §2 one module update → §3 setup script (dry run, audit, apply, control) → §4 Mac
Mini → §5 own plan → the products waiting in §3.2 once C24 / C25 are answered.
Insurance and financing registers: standard / OCA search reported separately first.

## Decisions taken (audit of c8d2d66)
- D1: goods for resale apart from materials used on worksites; generic sales products
  are goods or services by nature.
- D2: « To classify » transitional only; no permanent flag.
- D3: lasers through a controlled equipment operation reusing equipment and contracts.
- D4: no automatic alignment of the table saw.
- D5: Computer 837 archived if without dependency; Green cross laser 824 integrated as
  serial equipment unless explicitly deleted.
- D6: group « Product Catalogue Manager »; requests by operators and buyers; quick
  creation refused to them.
- Mac Mini bill posted by an authorised accounting user only.

## Decision asked
- D7: approval mechanism of the request: phase 2 pattern (proposed) or OCA
  `base_tier_validation`.
