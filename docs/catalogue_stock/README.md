# Stock categories for governed requests

This test-only configuration opens the six imported categories 20–25 to **Item and
Service Requests**. It reuses those records and adds only the two missing leaves needed
by the Leroy Merlin exercise: workwear and small durable workshop tools.

## Test accounting choice

| Existing category | Catalogue family | Expense | Stock | Input / output |
| --- | --- | --- | --- | --- |
| 22 Construction Consumables | Construction material | 601000 | 311000 | 603100 |
| 20 Tool Accessories | Consumable or accessory | 602230 | 321000 | 603200 |
| 21 Tool Consumables | Consumable or accessory | 602230 | 321000 | 603200 |
| 23 Electrical Consumables | Consumable or accessory | 602230 | 321000 | 603200 |
| 24 Plumbing Consumables | Consumable or accessory | 602230 | 321000 | 603200 |
| 25 Spare Parts | Consumable or accessory | 602220 | 321000 | 603200 |
| Workwear & PPE | Consumable or accessory | 602230 | 321000 | 603200 |
| Tools & Workshop Equipment | Durable equipment | 606300 | manual valuation | — |

The material and consumable categories use average cost and automated valuation.
Accounts 311000 and 321000 are created if absent. Small durable tools use average cost,
manual valuation and immediate expense on 606300, so their accounting book value is
zero unless the accountant classifies the item as a fixed asset instead. This is a
configurable **test choice**, not an accountant's validation for production.

The activation refuses production, multiple companies, unexpected external IDs,
partial configurations and categories containing products. It defaults to a rollback.

## Controlled deployment on `artdubati_test`

After audit, use the ordinary platform check and verified backup. Deploy
`maintenance_shareholder_equipment` 18.0.5.2.4 with `docs/deploy_modules.sh`, including
the normal route comparison, then while `odoo_web` is stopped run:

```bash
bash /tmp/catalogue_stock/docs/catalogue_stock/run_activation.sh
bash /tmp/catalogue_stock/docs/catalogue_stock/run_activation.sh --apply
bash /tmp/catalogue_stock/docs/catalogue_stock/run_activation.sh
```

The first command must describe the intended changes, the second commits them, and the
last must end with `0 record(s) rolled back`. Restart Odoo and repeat the platform and
route checks.

## Acceptance

Create a new request for `AXTON adhesive 25 kg`:

- Family: **Construction material**;
- Product Category: **All / Construction Materials / 22 Construction Consumables**;
- Tracking: **By Quantity**;
- Supplier reference: `91952403`.

For the remaining specimen lines use **Workwear & PPE** for the trousers,
**20 Tool Accessories** for the Bosch set, and **Tools & Workshop Equipment** only for
a saw deliberately treated as non-capitalised. A capitalised saw belongs in the fixed
asset branch instead.

The first click on **Submit** must create a numbered request instead of returning
“This field is set by the request itself.” A different requester, state or request
number sent through the API must still be refused.
