# ROADMAP section 0 – four classifications (proposal, 11/10/2026)

Draft for the owner and the audit. **Nothing is changed in the database before the
read-only complement (`complement.py`) has run and this mapping is decided.** Every
proposal below is a proposal; accounts are the French chart (PCG) of the company and
must exist in it (checked by the complement, ACCOUNT lines); every accounting choice is
a test choice for the accountant (QUESTIONS_COMPTABLE.md).

The four classifications answer different questions and never copy each other:

| Classification | Question | Odoo object |
|---|---|---|
| Equipment categories | What physical good is it, what is it used for, how is it maintained? | `maintenance.equipment.category` (OCA hierarchy) |
| Product categories | How is a purchase or a sale booked and valued? | `product.category` (accounts, cost method, valuation, fixed-asset flag) |
| Contract natures | What kind of recurring commitment is it? | OCA `contract` (tags), plus `equipment_nature` on lines linked to an equipment |
| Business registers | Which business object must be followed over time? | dedicated models or modules (insurance, financing, fleet, worksites) |

No equipment category « Finance », « Insurance » or « Services »: those are services
(product categories), contracts and registers.

## 1. Equipment categories (physical goods that are maintained)

Proposal built from the 28 imported categories (first draft, 25/09): grouped by nature
and use, the numeric codes dropped (to confirm), the missing families added (IT,
vehicles, trailers, site installations). Disposable PPE and workwear are consumables
(product categories) and the future workwear register, not equipment; only durable,
inspected safety equipment (harnesses, extinguishers, gas detectors) is equipment.

| Proposed category | From the imported draft |
|---|---|
| IT & Office / Computers & servers | 18 Electronic and IT Equipment (split) |
| IT & Office / Network & telephony | new |
| IT & Office / Printers & peripherals | new |
| IT & Office / Office furniture | new |
| Tools / Cordless tools | 01 |
| Tools / Corded power tools | 02 |
| Tools / Hand tools (only tracked ones) | 03 |
| Tools / Batteries & chargers | 19 |
| Measuring & Inspection | 11 Measuring Equipment |
| Workshop machinery / Woodworking | 06 |
| Workshop machinery / Metalworking | 07 |
| Workshop machinery / Other | 17 Small Workshop Machinery |
| Trade equipment / Electrical | 04 |
| Trade equipment / Plumbing & MEP | 05 |
| Trade equipment / Painting & coating | 08 |
| Trade equipment / Masonry & tiling | 09 |
| Trade equipment / Plastering & drywall | 10 |
| Trade equipment / Demolition | 12 |
| Trade equipment / Cleaning | 13 Workshop Cleaning Equipment |
| Site machinery (mixers, compactors, generators, compressors, pumps) | 26 |
| Access & work at height (ladders, scaffolding, platforms) | 16 |
| Formwork & shoring | 28 |
| Handling & lifting | 15 Material Handling Equipment |
| Safety equipment (durable, inspected) | 14 Safety and PPE (narrowed) |
| Vehicles | 27 |
| Trailers | new |
| Site installations (cabins, containers, fences, lighting, temporary power) | new |
| Premises installations (heating, ventilation, alarm, fixed fittings) | new |

The intermediate parents of the draft (« Assets & Equipment », « Power & Workshop
Tools », « Trade & Site Equipment », « Logistics Safety & Access », « Site Machinery &
Vehicles », « Inspection & Measurement », « IT & Office Equipment ») are replaced by the
parents above. The two automatic categories `All` (89) and `Fixed Assets` (481) are
removed once their equipment is moved, and `maintenance_account` is prevented from
creating new ones (the equipment category comes from the product, plan of item 3).

### The four current equipment (provisional, to confirm with the complement)

| Equipment | Today | Proposed |
|---|---|---|
| 871 « Device 1 » (Mac Mini, serial 877790) | All | IT & Office / Computers & servers, renamed « Mac Mini 877790 » |
| 484 table saw (hypothesis: the second one in All) | All | Workshop machinery / Woodworking |
| the two equipment of `Fixed Assets` (hypothesis: the lasers) | Fixed Assets | Measuring & Inspection |

## 2. Product categories (booking and valuation)

| Branch | Content | Account (test choice) | Cost / valuation |
|---|---|---|---|
| Fixed assets / Plant, machinery & tools | existing id 19 | 215400, profile « Matériel et outillage » | average, manual |
| Fixed assets / IT equipment | Mac Mini, computers | 218300, own profile (3 years, test) | average, manual |
| Fixed assets / Vehicles & trailers | | 218200, own profile | average, manual |
| Fixed assets / Office furniture | | 218400, own profile | average, manual |
| Fixed assets / Site & premises installations | | 218100 (or 213500), own profile | average, manual |
| Intangible assets / Software acquired | perpetual licences | 205000, own profile | – |
| Small equipment (below the capitalisation threshold) | tools and devices not capitalised | 606300 | average, manual |
| Consumables & accessories / 20 to 25 | existing ids 12 to 17 | 602200 or 606xxx (accountant) | average, manual |
| Consumables / Disposable PPE & workwear | new | 606xxx (accountant) | average, manual |
| Construction materials | materials bought for worksites | 601000 / 602xxx (accountant) | average, manual |
| Goods for resale | | 607000 | average, manual |
| Services purchased / Maintenance & repair | | 615xxx | – |
| Services purchased / Insurance | premiums | 616xxx | – |
| Services purchased / Telecom & Internet | | 626000 | – |
| Services purchased / Software & SaaS subscriptions (ChatGPT…) | | 6xxx (accountant: 6135 / 6156 / 628) | – |
| Services purchased / Rentals | | 613500 | – |
| Services purchased / Leasing (crédit-bail) | | 612xxx | – |
| Services purchased / Fees & professional services | | 622600 | – |
| Services purchased / Subcontracting | | 604000 or 611000 (accountant) | – |
| Services purchased / Transport & logistics | | 624xxx | – |
| Services purchased / Energy & site utilities | | 606100 | – |
| Services purchased / Bank fees | | 627800 | – |
| Administrative supplies & overheads | existing « Frais généraux » | per product (606400, 626000…) | – |
| Sales / Works, services, rentals | existing service products | 704000, 706000, 708300 | – |

`All` keeps no product: every product goes to its real category (procedure of item 3).
Loans, interest and financing are not products: they belong to the financing register
(bank fees stay a service).

## 3. Contract natures (recurring commitments)

Today: `contract_type` (customer / supplier) and, on lines linked to an equipment,
`equipment_nature` (rental, free loan, insurance, maintenance). Proposal, standard
first: the OCA contract **tags** (`contract.tag`, already installed) carry the nature
of the whole contract: insurance, maintenance, rental, leasing, telecom & Internet,
software & SaaS, energy & utilities, other subscription. `equipment_nature` stays for
the link of a line to an equipment. A recurring contract has a service product of
section 2 (its accounts) and a tag (its nature).

## 4. Business registers (followed over time, not equipment)

| Register | Content | Where (ROADMAP) |
|---|---|---|
| Equipment | physical goods, ownership, maintenance | `maintenance.equipment` (done) |
| Recurring contracts | subscriptions, rentals, SaaS, telecom | OCA contract (A) |
| Insurance policies | policy, cover, deadlines, insured objects (equipment, vehicles, worksites), ten-year liability | new register (C) |
| Financing | loans, leasing, interest, schedules | new register (to add to the roadmap) |
| Fleet | vehicles and trailers: registration, mileage, fuel, inspections | Odoo Fleet, linked to the equipment (D) |
| Worksites | consumption, subcontracting, costs | project / analytic (E) |
| Workwear / PPE | allocation per person | (F) |

## Decisions asked
1. The equipment tree above (codes dropped or kept, the families added, the narrowed
   safety category).
2. The product category branches and their accounts (test choices, then accountant).
3. Contract natures as OCA tags.
4. A financing register added to the roadmap.
