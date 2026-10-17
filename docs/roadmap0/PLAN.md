# ROADMAP section 0 – plan (revision 5, 11/10/2026; items 1 to 3 implemented and deployed on artdubati_test, code 5823e71, README.md)

Basis: NOMENCLATURE.md (retained), REPORT.md (facts, anomalies), EXTRACT.md and data/.
Nothing runs on artdubati_test before the audit and the owner's go. Standard Odoo and
OCA first; changes by inheritance; no raw SQL writes.

Revision 5 answers the audit of eb4b37e: variant guard narrowed to direct creation in
superuser mode and an explicit override of `_create_product_variant()` (§2.7);
accounting treatment recomputed and compared at execution (§2.8); structural fields
locked for everyone until the modification request, with a controlled and traced
correction (§2.4); canonical keys, non-empty partial indexes and a business message
for concurrent duplicates (§2.8); approved supporting documents frozen (§2.10).

Revision 4 answered the audit of ed0b50e: quick creation refused to everyone (§2.4,
tests), variants (H5 resolved, §2.7), locking, idempotence and concurrent duplicates
(§2.8), families executable only when their final configuration exists (§2.9), the
precise data rules (§2.10); D7 to D9 decided.

Revision 3 answered the audit of a811786: no direct creation for anyone (§2.4),
stored equipment wait for C24 / C25 (§3.2, §3.3), archiving instead of deleting
referenced equipment categories (§3.4), comparative characterisation of
`base_tier_validation` for D7 (§2.6), checks only on structural changes (§2.2).

Revision 2 answered the audit of c8d2d66: a persistent creation request instead of a
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
- H5 (resolved by reading Odoo 18, audit of ed0b50e): variants are created by
  `product.template._create_variant_ids()` in the current environment (template
  creation and changes of attribute lines) and by `_create_product_variant()` through
  `sudo()` (dynamic attributes, from a sale or purchase line). Handled in §2.7. Still to
  list in the dry run: products of artdubati_test with attribute lines (expected none).

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

Approval mechanism (D7, decided): the phase 2 pattern of `equipment.operation`, one level
(D8), with its own approver group; the approver is never the requester (D9, server
check); an approver who is also catalogue manager may then execute. A request may only
select categories and accounting treatments already configured (D8): creating a
category or changing its accounts is a separate operation, outside the request.

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

Checks on `product.template` (every path: form, import, quick create, API), **only when a
structural field is written** (category, type, storable, tracking, `maintenance_ok`,
default equipment category, units, accounts): an ordinary edit (name, price, picture,
description, supplier line) of a product still waiting in `All` (§3.2) is never
refused. Per branch:
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

### 2.4 Rights and creation (D6, audit of a811786)
- New group « Product Catalogue Manager » (own category, not the phase 2 groups): approves
  and executes requests, administers existing products. Proposed: the approver of a
  request is not its requester.
- Requesters: Equipment Operator, Purchase User, Inventory User (create and follow their
  requests).
- **Nobody creates a product directly, the catalogue manager included.** The guard on
  `product.template.create` and `product.product.create` (and therefore `copy`) refuses
  any call outside superuser mode (`env.su`): only the request's execution, which runs
  the creation in `sudo()` on the server after its own checks, and the migration script
  (Odoo shell, superuser) create products. No context key opens it: an RPC client cannot
  obtain superuser mode, whatever context it sends. Quick creation in purchase and
  operation lines and imports are refused with a message pointing to the request;
  `no_create` on those product fields for a clean interface.
- **Structural fields locked for everyone** (catalogue manager included) until the
  future modification request exists: product category, type, storable, tracking,
  `maintenance_ok`, units of measure, own income and expense accounts, default equipment
  category, attribute lines. A write of one of them outside superuser mode is refused.
  Not locked: the operational evolution of the cost (average cost computed by Odoo,
  revaluations of the standard tools), name, descriptions, prices, pictures, supplier
  lines.
- Exceptional corrections go through a small controlled assistant « Structural
  correction » (catalogue manager, mandatory reason, before / after values posted in the
  product's chatter and kept on a correction record, executed in `sudo()` after the same
  checks as a request) or through an audited script.

### 2.5 Silent creation of equipment categories removed
`maintenance_account` and our receipt take the product's default equipment category
(`product.template.equipment_category_id`, a link, not a classification flag);
without one they refuse with a message naming the product, never create a category.

### 2.6 Approval mechanism (D7): comparison
OCA `base_tier_validation` 18.0.3.5.2 (server-ux), read in its source:

| Need | base_tier_validation | Phase 2 pattern (`equipment.operation`) |
|---|---|---|
| Configurable approvers | yes: a user, a group or a field of the record, per company, with a domain | one approver group (new group here) |
| Several levels | yes (tiers with sequence, ordered approval optional) | no (one level) |
| History | `tier.review` (who, when, comment) **deleted** by `restart_validation` and by a return to draft or cancel; chatter notifications only if enabled | chatter tracking and approval snapshot kept |
| Change after approval → new approval | no: under validation the write is **refused**; after validation it is **allowed** unless « tier validation exceptions » are configured; no reset on change | yes: signature of the decisive data, any change returns to « to approve » with the changed values listed (2f) |
| Block before execution | yes (state transition refused until validated) | yes (execution only from « approved ») |
| Bypass | context keys `skip_validation_check` and `skip_check_state_condition`, readable from any RPC call | none (no context key) |
| Platform | new module: install, platform fingerprint and parity, JS assets (systray), audit; no HTTP route | already deployed and audited |

Covering the need with the OCA module would require: a reset on change (signature and
`restart_validation`), keeping the review history before each restart, and stripping
the two context keys from client calls. Those are significant workarounds of its design.
Proposal: the phase 2 pattern, with its own new approver group and one level; several
levels can be added later if the catalogue needs them (D8).

### 2.7 Variants (H5, audit of eb4b37e)
- Direct `product.template.create` and `product.product.create`: superuser mode only
  (the request's execution, the migration, module installations). No condition on
  attributes there: a module installed later that creates variants legitimately, or the
  migration taking over an old product with variants, keeps working.
- Creation requests never carry attribute lines.
- Any write of `attribute_line_ids` outside superuser mode is refused (§2.4).
- Explicit override of `product.template._create_product_variant()`: when the call
  would **create** a variant (dynamic attributes, no existing variant for the
  combination) and the calling environment is not superuser, it is refused **before**
  the core's own `Product.sudo().create()`. Returning an existing variant is unchanged.
- Tests: initial creation (one variant); adding an attribute line refused (manager
  included); duplication (`copy`) refused; dynamic variant from a purchase / sale line
  refused (a template with a dynamic attribute set up by the test in superuser mode);
  the same call in superuser mode allowed; migration in superuser mode unaffected.

### 2.8 Locking, idempotence, concurrency (phase 2 protections)
- `_lock()` (`SELECT … FOR UPDATE NOWAIT`) on the request before approval and before
  execution, then the state is read again: a second execution, or an execution racing
  another, raises « already executed or being executed » and changes nothing.
- **Accounting treatment recomputed at execution**: effective income, expense and stock
  accounts, asset profile, cost method, valuation, taxes and defaults (warranty,
  insurance) are computed again from the current configuration and compared with the
  approved signature; any difference (for example a category's account changed after
  the approval) sends the request back to « to approve » with the differences listed,
  and no product is created (same principle as the frozen treatment of phase 2f).
- Final duplicate check inside the execution's transaction, after the lock, against
  every existing product, active or archived, and every executed request.
- Odoo runs transactions in REPEATABLE READ: a search after the lock may not see a
  product committed meanwhile by another transaction. The guarantee is therefore a
  database one:
  - canonical keys **stored** on the request (internal reference, barcode, supplier +
    supplier reference: trimmed, inner spaces collapsed, upper case), used both by the
    duplicate search and by the indexes;
  - partial unique indexes per company on each key, only for executed requests and
    non-empty keys (`state = 'done' AND key IS NOT NULL AND key <> ''`), created by
    `init()`;
  - at execution the request's keys and state are flushed inside a savepoint before the
    product is created: of two concurrent executions with the same key, the second waits
    for the first and gets the unique violation, caught in the savepoint and turned into
    a business message naming the other request; nothing is created.
- Operational rule: the migration script and any other superuser creation run with
  `odoo_web` stopped (deployment procedure), never while requests are being executed.
- A request `done`, `refused` or `cancelled` is closed: any write other than the
  chatter and activities is refused; it never goes back into the circuit through an
  edit. A refused or cancelled request can be duplicated into a new draft.
- Tests: double execution; two concurrent executions with the same barcode, internal
  reference or supplier reference (two cursors: business message, one product); a
  duplicate of an archived product refused; a category account changed after approval
  sends the request back to approval at execution, no product; write on a closed request
  refused.

### 2.9 Families executable in the first deployment
A family is executable only when its final configuration exists. First deployment:
- executable: services (purchased and sold, their categories created by §3.1);
  durable equipment **capitalised** in a fixed-asset category whose expense account has
  an asset profile (IT, test profile 3 years; plant & tools, profile 5 years);
- refused with a message « waits for the accountant (C24 / C25) »: small durable
  equipment, materials, consumables, goods for resale; intangible assets (profile and
  duration not decided);
- never: `All`, « To classify », an archived or automatic equipment category.
The check is made on the server at approval and at execution (not only by the form's
domain).

### 2.10 Data rules
- Supplier price: in the supplier line's currency (field on the request, default the
  supplier's purchase currency, else the company's); labels « Price (excl. tax) » with
  the currency shown; sale price and initial cost in the company currency, « (excl.
  tax) ».
- Taxes: purchase taxes of type « purchase », sale taxes of type « sale », active, of the
  request's company (and its parents); checked on the server, not only by the domain.
- Duplicates: supplier reference compared per **supplier + reference**; internal
  reference and barcode per company; normalised name as a warning.
- Approval signature, exact fields: company; family; name; internal reference;
  barcode; product category; equipment category; deduced type, storable and tracking;
  unit and purchase unit; purchase / sale; supplier; supplier reference; currency;
  supplier price; minimum quantity; lead time; purchase taxes; sale taxes; sale price;
  initial cost; effective income, expense and stock accounts; asset profile; cost
  method and valuation; warranty and insurance defaults. Notes, photo and documents are
  not in the signature.
- Supporting documents (quotes, data sheets): their list and checksums are frozen at
  approval; deleting or replacing an approved document is refused, and execution checks
  the frozen list (a missing or changed document sends the request back to approval).
  Further documents may be added after approval. The photo stays outside the signature.
- At execution the photo becomes the product's image and the documents are copied as
  attachments of the product (the request keeps its own).
- Equipment category: refused on the server if archived, automatic or « To classify »,
  whatever the client sends.
- Multi-company: the request has a company; categories, taxes, supplier, accounts and
  the created product are checked against it; record rules on the company; a requester
  reads his own requests, catalogue managers and approvers the requests of their
  companies.

Tests: each **executable** family requested, approved, executed; the waiting families
refused with their message; re-approval after a change of a signature field; approver
= requester refused; duplicates; quick create and direct `create` refused to everyone,
catalogue manager included; §2.7 and §2.8 tests; bill line and receipt without equipment
category refused, no category created; fr / fa translations; HTTP routes inventory (new
module data only, no route).

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

### 3.2 Stored products: no provisional move (audits of c8d2d66 and a811786)
Only what does not depend on the stock accounts moves now: services (no stock) and the
Mac Mini (fixed asset, manual valuation is its final treatment). **Every other stored
item waits for C24 / C25**: the table saw, Green cross laser 824, the two lasers
836 / 828 and TEST Cement bag keep their product category, valuation and product
settings; their final product category, product transformation (storable, serial) and
stock entry happen once, directly into the final configuration. Their **equipment
category** (business tree) is corrected now: it has no accounting effect. Their
products get no default equipment category yet (a structural change refused while they
are in `All`); nothing is received for them in the meantime.

### 3.3 Products and equipment
- Equipment: moved to the tree and renamed (NOMENCLATURE.md §3).
- Lasers (D3), **after C24 / C25**: a controlled equipment operation reusing the
  equipment and their contracts EQOP/2026/0738-0739: internal serial, receipt into stock
  with Manager as quant owner, monitor location emptied, products 836 / 828 storable
  with serial (H2; if the existing receipt branches cannot reuse an equipment, a
  « regularisation into stock » operation type, planned and audited first). Now: only
  their equipment category (Measuring, inspection & setting-out); anomaly 1 stays open
  and listed.
- Green cross laser 824 (D5), **after C24 / C25**: integrated as a serial equipment by a
  controlled operation (H4), unless its explicit deletion as test data is decided.
- Computer 837 (D5): archived if it has no stock, document or use (checked in the dry
  run); duplicates and TEST products archived after the same check.
- Table saw (D4): nothing aligned automatically; the dry run reads its bill
  BILL/2026/10/0006 and the origin of the 329 € (valuation layers, product history); if
  15 € is the real total price, a controlled and traced revaluation afterwards.
- At the end of this migration no product is in « To classify »; the products §3.2
  keeps waiting stay in their current category and are listed in the report.

### 3.4 Old equipment categories: archive when referenced (audit of a811786)
- `active` added by inheritance to `maintenance.equipment.category` (standard archiving;
  archived categories leave the selection lists, references keep displaying them).
- The script moves the active equipment to the new tree, then for each old category
  (the 29 imported, `All` 89, `Fixed Assets` 481): **archives** it while anything
  references it, **deletes** it only when nothing does.
- References checked: equipment (active or archived), products (default equipment
  category), bill lines (`account.move.line.equipment_category_id`, any state), and any
  other field pointing to `maintenance.equipment.category` (found through
  `ir.model.fields`); defaults and saved filters mentioning their ids are listed.
  Expected: `All` (89) stays referenced by the posted bill line of the table saw
  (BILL/2026/10/0006) and is archived.
- **A posted accounting line is never modified** to allow a deletion.
- External IDs: kept for archived categories; deleted with the record only for a deleted
  category; both lists, with the old code → new category correspondence, in the report.

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

- Audit of a811786: no direct creation for anyone; stored equipment wait for C24 / C25
  (equipment category corrected now); referenced old categories archived; checks on
  structural changes only.

- Audit of eb4b37e: mechanism, one level, requester / approver separation, waiting
  families, migration and archiving validated; development authorised once the four
  corrections of revision 5 are integrated (variants, recomputation at execution,
  structural lock, concurrent duplicates) and the approved documents frozen.
- Audit of ed0b50e: D7 phase 2 mechanism; D8 one level, the request selects only
  configured categories and treatments; D9 approver different from the requester (who
  may then execute if catalogue manager). Archiving strategy, no change to posted
  entries and the stock moves deferred to C24 / C25 validated.

## Owner amendment — autonomous catalogue profile, 17/10/2026

The owner explicitly requested a special role for test users and superadministrators
who create and approve their own product requests. This supersedes the unconditional
requester/approver separation in D9 only for explicitly assigned members of
`group_product_catalogue_autonomous`. The ordinary manager rule stays unchanged.
The exception is a separate, unassigned-by-default level implying the catalogue
manager; it does not imply equipment or accounting privileges. No direct product
creation or validation bypass is introduced. Request actors and snapshots remain
unchanged. See DEFINITIONS.md and ADM-13; version 18.0.5.1.0 requires review and a
module update before this role exists or can take effect on artdubati_test.
