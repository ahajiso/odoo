# ROADMAP section 0 – extract of the existing records (artdubati_test, 11/10/2026)

Facts only, no proposal. Source: inventory `roadmap0_inventory_2026-10-11_073438.txt`
(a9568ea, run once after the audit). The four equipment, the stock, the service products
with their contracts and the accounts come from the read-only complement
(`complement.py`, section « Complement » below, filled when it has run). One company:
Docteur Bain.

## Equipment categories (31)

29 imported on 25/09/2026 by f.t.1@lartdubati.com (external IDs `__import__.cat_*`),
no product category, **0 equipment** each: 1 root, 6 groups, 22 leaves coded 01 to 19
and 26 to 28 (codes 20 to 25 are product categories: consumables).

| id | Category | External ID |
|---|---|---|
| 59 | Assets & Equipment | cat_actif |
| 84 | Assets & Equipment / Inspection & Measurement | cat_measure |
| 85 | … / Inspection & Measurement / 11 Measuring Equipment | cat_11 |
| 86 | Assets & Equipment / IT & Office Equipment | cat_it_office |
| 87 | … / IT & Office Equipment / 18 Electronic and IT Equipment | cat_18 |
| 80 | Assets & Equipment / Logistics Safety & Access | cat_logistics |
| 81 | … / Logistics Safety & Access / 14 Safety and Personal Protective Equipment | cat_14 |
| 82 | … / Logistics Safety & Access / 15 Material Handling Equipment | cat_15 |
| 83 | … / Logistics Safety & Access / 16 Ladders Scaffolding and Work at Height | cat_16 |
| 60 | Assets & Equipment / Power & Workshop Tools | cat_power_tools |
| 61 | … / Power & Workshop Tools / 01 Cordless Tools | cat_01 |
| 62 | … / Power & Workshop Tools / 02 Corded Power Tools | cat_02 |
| 63 | … / Power & Workshop Tools / 03 Hand Tools | cat_03 |
| 64 | … / Power & Workshop Tools / 06 Woodworking Equipment | cat_06 |
| 65 | … / Power & Workshop Tools / 07 Metalworking Equipment | cat_07 |
| 66 | … / Power & Workshop Tools / 17 Small Workshop Machinery | cat_17 |
| 67 | … / Power & Workshop Tools / 19 Batteries and Chargers | cat_19 |
| 77 | Assets & Equipment / Site Machinery & Vehicles | cat_machinery |
| 78 | … / Site Machinery & Vehicles / 26 Site Machinery | cat_26 |
| 79 | … / Site Machinery & Vehicles / 27 Vehicles | cat_27 |
| 68 | Assets & Equipment / Trade & Site Equipment | cat_site_equip |
| 69 | … / Trade & Site Equipment / 04 Electrical Equipment | cat_04 |
| 70 | … / Trade & Site Equipment / 05 Plumbing and MEP Equipment | cat_05 |
| 71 | … / Trade & Site Equipment / 08 Painting and Coating Equipment | cat_08 |
| 72 | … / Trade & Site Equipment / 09 Masonry and Tiling Equipment | cat_09 |
| 73 | … / Trade & Site Equipment / 10 Plastering and Drywall Equipment | cat_10 |
| 74 | … / Trade & Site Equipment / 12 Demolition Equipment | cat_12 |
| 75 | … / Trade & Site Equipment / 13 Workshop Cleaning Equipment | cat_13 |
| 76 | … / Trade & Site Equipment / 28 Formwork and Shoring Equipment | cat_28 |

Created automatically (OCA `maintenance_account`, name and link of the product category),
no external ID:

| id | Category | Product category | Equipment | Created |
|---|---|---|---|---|
| 89 | All | All | 2 | 04/10/2026 by test@test.com |
| 481 | Fixed Assets | All / Fixed Assets | 2 | 10/10/2026 14:54 by f.i.1@febitmail.com |

## Product categories (12)

All in manual valuation (`manual_periodic`), no stock account; income 707000 everywhere.

| id | Category | Cost | Expense | Fixed-asset flag | Equipment category | Products | External ID |
|---|---|---|---|---|---|---|---|
| 1 | All | standard | 607000 | no | All (89) | 14 | product.product_category_all |
| 3 | All / Expenses | standard | 607000 | no | – | 0 | product.cat_expense |
| 11 | All / Expenses / Consumables & Accessories | average | 607000 | no | – | 0 | __import__.cat_consumables |
| 12 | … / 20 Tool Accessories | average | 607000 | no | – | 0 | __import__.cat_20 |
| 13 | … / 21 Tool Consumables | average | 607000 | no | – | 0 | __import__.cat_21 |
| 14 | … / 22 Construction Consumables | average | 607000 | no | – | 0 | __import__.cat_22 |
| 15 | … / 23 Electrical Consumables | average | 607000 | no | – | 0 | __import__.cat_23 |
| 16 | … / 24 Plumbing Consumables | average | 607000 | no | – | 0 | __import__.cat_24 |
| 17 | … / 25 Spare Parts | average | 607000 | no | – | 0 | __import__.cat_25 |
| 18 | All / Expenses / Frais généraux | standard | 607000 | no | – | 3 | – |
| 19 | All / Fixed Assets | average | 215400 (profile « Matériel et outillage (test) ») | yes | Fixed Assets (481) | 2 | – |
| 2 | All / Saleable | standard | 607000 | no | – | 0 | product.product_category_1 |

## Products (19, templates)

« Own » = account set on the product; otherwise the category's. No product has a stock
account; none other than those of category 19 has an asset profile.

| id | Product | Category | Type | Storable | Maintainable | Own income | Own expense |
|---|---|---|---|---|---|---|---|
| 8 | 1800W corded table saw, 254mm blade, with wheeled stand | All | goods | yes | yes | – | – |
| 837 | Computer | All | goods | no | no | – | – |
| 7 | Conseil / Prestation intellectuelle | All | service | – | no | 706000 | – |
| 824 | Green cross laser | All | goods | yes | no | – | – |
| 823 | Laser rangefinder | All | goods | yes | no | – | – |
| 127 | Location de matériel (facturée) | All | service | – | no | 708300 | – |
| 126 | Location de matériel (payée) | All | service | – | no | – | 613500 |
| 843 | Mac Mini ([MM1220], serial tracking) | All | goods | yes | yes | – | – |
| 5 | Main d'œuvre - Finition / Façade (horaire) | All | service | – | no | 704000 | – |
| 6 | Matériaux de construction (finition/façade) | All | goods | no | no | 707000 (= category) | – |
| 125 | Prêt de matériel | All | service | – | no | – | – |
| 13 | TEST Bought compressor | All | goods | no | yes | – | – |
| 10 | TEST Cement bag | All | goods | yes | no | – | – |
| 11 | TEST Scaffold rent | All | service | – | no | – | – |
| 3 | Abonnement téléphonique | All / Expenses / Frais généraux | service | – | no | – | 626000 |
| 4 | Frais administratifs | All / Expenses / Frais généraux | service | – | no | – | 606400 |
| 1 | Frais bancaires | All / Expenses / Frais généraux | service | – | no | – | 627800 |
| 836 | 360° green laser | All / Fixed Assets | goods | no | yes | – | – |
| 828 | Laser rangefinder | All / Fixed Assets | goods | no | yes | – | – |

Two products named « Laser rangefinder » (823 and 828).

## Complement (to fill from `complement.py`)
The four equipment, the stock with values, the history of P00381, the service products
with their contract lines, every contract line, the contract natures, the asset profiles
and assets, the accounts of classes 20, 21, 60, 61, 62, 66, 67 and their use.
