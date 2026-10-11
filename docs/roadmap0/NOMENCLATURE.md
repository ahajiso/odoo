# ROADMAP section 0 – classifications (working document, NOT validated)

Status (11/10/2026): working material for the audit, which prepares the final matrix
(per family: stored or not, serial or quantity, maintainable, capitalised or expensed,
bought / rented / borrowed / consigned, recurring contract, Odoo object, accounting
treatment) and the mapping of the existing records. **Nothing is changed in the
database before that matrix and mapping are validated.** Facts come from
`REPORT.md` and `EXTRACT.md` (inventory and read-only complement).

## Principles retained by the audit (11/10/2026)
- Separate classifications: equipment categories (physical goods that are maintained),
  product categories (booking and valuation of purchases and sales, services included),
  contract natures, business registers. None copies another.
- Equipment categories: **the physical nature is the only axis**. Trades (plumbing,
  electricity, tiling, painting) never make a second, competing branch; if needed later,
  they are carried by tags or another usage field. The codes 01 to 28 leave the labels;
  their historical correspondence stays in the migration document.
- No equipment category « Finance », « Insurance » or « Services ».
- Supplier-owned stock is an **ownership mode** (third-party owner on the quants), never
  a category.
- Bank fees: a service only. Loans, interest, guarantees and partners' current accounts
  are never products.
- A « new register » is not a new custom model: standard Odoo and OCA modules are
  searched first (financing, insurance).
- Migration: `All` may stay the technical root of product categories, with no active
  product directly in it in the end; the automatic equipment categories `All` and
  `Fixed Assets` disappear after reclassification; a transitional category « To
  classify » rather than a silent automatic creation for historical products; the final
  creation assistant refuses « To classify ».

## 1. Equipment categories (physical nature)

| Category | Sub-categories |
|---|---|
| IT & communications | computers & servers; phones & tablets; network & telephony; printers & peripherals |
| Tools | cordless power tools; corded power tools; hand tools tracked individually; batteries & chargers tracked individually |
| Measuring, inspection & setting-out | |
| Workshop machinery | wood; metal; other |
| Site machinery & equipment | |
| Access & work at height | |
| Formwork & shoring | |
| Handling & lifting | |
| Cleaning & extraction | |
| Durable, inspected safety equipment | |
| Vehicles | |
| Trailers | |
| Temporary site installations | |
| Premises & warehouse installations | |
| Furniture tracked individually | |

Correspondence with the imported draft (25/09), for the migration document: 01 → Tools /
cordless; 02 → Tools / corded; 03 → Tools / hand tools; 19 → Tools / batteries & chargers;
11 → Measuring; 06 → Workshop / wood; 07 → Workshop / metal; 17 → Workshop / other;
18 → IT & communications (split); 26 → Site machinery; 16 → Access & work at height;
28 → Formwork & shoring; 15 → Handling & lifting; 13 → Cleaning & extraction; 14 →
Safety (durable, inspected only; disposable PPE is a consumable); 27 → Vehicles;
04, 05, 08, 09, 10, 12 (trade branches: electrical, plumbing, painting, tiling,
plastering, demolition) → no category of their own: their equipment goes to its
physical nature (tools, site machinery…).

## 2. Product categories (booking and valuation)

Test values before the accountant (C24, C25): accounts are hypotheses only.

| Family | Cost | Valuation |
|---|---|---|
| Fixed assets kept in stock | average | manual |
| Consumables owned by the company | average | automatic (DEFINITIONS.md) |
| Construction materials owned by the company | average | automatic |
| Goods for resale | average | automatic |
| Supplier-owned stock | not valued for the company | third-party owner on the quants |
| Services | – | no stock |
| Small durable equipment expensed | open question C24 | open question C24 |

Branches to cover (accounts: hypotheses, C25): fixed assets by nature (plant & tools,
IT, vehicles & trailers, furniture, installations, software acquired); small equipment;
consumables; construction materials; goods for resale; services purchased (maintenance
& repair, insurance, telecom & Internet, software & SaaS, rentals, leasing, fees,
subcontracting, transport & logistics, energy & premises charges, cleaning & waste, bank
fees); overheads; sales (works, services, rentals).

## 3. Contract natures
OCA `contract.tag` (installed with `contract`) for the nature of the whole contract;
`equipment_nature` stays for a line linked to an equipment (rental, free loan,
insurance, maintenance).

## 4. Registers
Equipment (done), recurring contracts (OCA contract), insurance policies, financing,
fleet (Odoo Fleet), worksites, workwear / PPE. Insurance and financing: standard / OCA
modules to search before any proposal.
