# ROADMAP section 0 – functional nomenclature (retained by the audit, 11/10/2026)

Retained by the audit after the complement (b77b2ad). Accounts and durations are test
choices for the accountant (QUESTIONS_COMPTABLE.md C24, C25). **The database is not
changed before the plan (PLAN.md) is audited and authorised.** Facts: REPORT.md,
EXTRACT.md, data/.

## 1. Equipment tree (physical nature only)

- IT & communications (Informatique et communications)
  - Computers & servers
  - Phones & tablets
  - Network & telephony
  - Printers & peripherals
- Tools (Outillage)
  - Cordless power tools
  - Corded power tools
  - Hand tools tracked individually
  - Batteries & chargers tracked individually
- Measuring, inspection & setting-out (Mesure, contrôle et implantation)
- Workshop machinery (Machines d'atelier)
  - Wood
  - Metal
  - Other
- Site machinery & equipment (Machines et équipements de chantier)
- Access & work at height (Accès et travail en hauteur)
- Formwork & shoring (Coffrage et étaiement)
- Handling & lifting (Manutention et levage)
- Cleaning & extraction (Nettoyage et extraction)
- Durable, inspected safety equipment (Sécurité durable et contrôlée)
- Vehicles (Véhicules)
- Trailers (Remorques)
- Temporary site installations (Installations temporaires de chantier)
- Premises & warehouse installations (Installations des locaux et entrepôts)
- Furniture tracked individually (Mobilier suivi individuellement)
- To classify (À classifier): migration only, refused by the final creation assistant

Trades (plumbing, electricity, tiling, painting) are not branches: they overlap the
physical nature; usage tags later if the need is confirmed. Codes 01 to 28 leave the
labels; their correspondence stays in the migration document (PLAN.md, item 3).

## 2. Functional matrix

| Family | Stock | Tracking | Maintainable | Test treatment | Contract / register |
|---|---|---|---|---|---|
| Physical fixed asset | yes | serial mandatory | yes | average cost, manual valuation, class 21 | equipment + fixed asset |
| Small durable equipment expensed | yes | serial if tracked individually | yes | expense 606300, book value to confirm (C24) | equipment |
| Construction materials owned by the company | yes | quantity, lot if needed | no | average cost, automatic valuation | worksite consumption |
| Consumables & accessories | yes | quantity / lot | no | average cost, automatic valuation | stock |
| Goods entrusted by a supplier | yes | serial or quantity per product | per nature | no asset and no company value before consumption | consignment |
| Rented or borrowed equipment | yes | serial mandatory | yes | no company fixed asset | contract + equipment |
| Services purchased | no | none | no | expense account of the category | contract if any |
| Services sold | no | none | no | income account | sale / contract |
| Software acquired and capitalised | no | licence | no | 205000, profile to define | intangible asset |
| SaaS and subscriptions | no | none | no | periodic expense | recurring contract |
| Registered vehicles / trailers | yes | VIN / registration | yes | 218200 if capitalised | Fleet + equipment + asset |
| Insurance | no | policy | no | 616xxx | insurance register |

Automatic valuation needs the stock accounts of the accountant: **no category switches
to automatic before they are configured.** Owned, rented, borrowed or entrusted is never
a product category: it is carried by the operation, the quant owner and the contract.

## 3. The four equipment

| Equipment | Equipment category | Target product category | Action |
|---|---|---|---|
| Table saw 484 | Workshop machinery / Wood | Small durable equipment expensed | rename « Scie sur table – 1234 »; explain 15 € (bill) vs 329 € (stock) |
| Mac Mini 871 | IT & communications / Computers & servers | Fixed assets / IT | rename « Mac Mini – 877790 »; test account 218300, test profile 3 years |
| 360° green laser 869, rented | Measuring, inspection & setting-out | Small equipment / Measuring & inspection | out of `Fixed Assets`; storable, serial, quant owner Manager |
| Laser rangefinder 870, borrowed | Measuring, inspection & setting-out | Small equipment / Measuring & inspection | same; no company asset |

## 4. The 19 products

| Product | Destination |
|---|---|
| Table saw | Small durable equipment / Workshop machinery |
| Mac Mini | Fixed assets / IT |
| Computer (837) | merge into the IT family or archive if unused |
| Green cross laser (824) | Measuring & inspection; serial equipment or archived (decision) |
| Laser rangefinder (823) | duplicate without equipment: archive after checking |
| 360° green laser (836) | Small equipment / Measuring & inspection |
| Laser rangefinder (828) | Small equipment / Measuring & inspection |
| Conseil / prestation intellectuelle | Sales / Consulting |
| Main-d'œuvre finition / façade | Sales / Works |
| Location de matériel (facturée) | Sales / Rentals |
| Location de matériel (payée) | Services purchased / Rentals |
| Prêt de matériel | free operational service, never invoiced |
| Matériaux de construction | Sales / Materials (generic commercial product, not a stock product) |
| Abonnement téléphonique | Services purchased / Telecom & Internet |
| Frais administratifs | Overheads / Administrative supplies |
| Frais bancaires | Services purchased / Bank services |
| TEST Bought compressor | archive after checking dependencies |
| TEST Scaffold rent | archive with its TEST contract |
| TEST Cement bag | kept until the consignment phase, then replaced by a real material family |

`TEST Cement rental` is functionally wrong: entrusted consumables are not a rental; it
is replaced by the future consignment flow.

## 5. Contracts and registers
OCA contract tags to prepare: Insurance, Maintenance, Rental, Leasing, Telecom &
Internet, Software & SaaS, Energy & charges, Other subscription.
Registers to plan: insurance, financing, fleet, worksites, workwear & PPE. Standard and
OCA modules are searched before any specific development (insurance, financing).

## 6. Product creation assistant (rules)
First question: the family (durable equipment, material or consumable, service,
intangible asset). Deduced and checked: storable / service, serial or quantity,
maintainable, equipment category (mandatory for equipment), product category, cost
method and valuation, purchase / sale, contractual treatment. No equipment validated
with `All`, `Fixed Assets` or `To classify`; no equipment category ever created
silently.
