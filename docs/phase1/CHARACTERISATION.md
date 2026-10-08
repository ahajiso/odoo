# Characterisations (phase 1)

## 1. Supplier refunds on a fixed-asset bill

First mandatory proof of phase 1 (audit of 08/10/2026), before any treatment or
documentation of refunds.

### Environment

Local, not artdubati_test: Odoo 18.0 community (commit 6d58dc84 of 08/10/2026), OCA
18.0 heads of the same day (maintenance, contract, stock-logistics-transport),
`account_asset_management` of this repository, PostgreSQL 16, Python 3.12. French
company with the `fr` chart of accounts. Script: `characterise_refund.py` (rolled back
at the end). Versions installed on artdubati_test may differ slightly; the behaviour
will be checked again by the module's integration tests on artdubati_test.

### Scenario and measured result

Asset profile on 215400 / 281500 / 681120, linear 5 years, « one asset per unit »;
product `maintenance_ok`; supplier bill of 2 units at 1000 on account 215400.

| Step | Measured |
|---|---|
| Profile created | account 215400 gets the profile automatically |
| Bill line of 2 units created | split into 2 lines of 1 unit (`asset_product_item`) |
| Bill posted | 2 assets in draft, 1000 each; 2 equipment created by `maintenance_account`, each linked to its line |
| « Extourner » (standard wizard), refund draft | each refund line already lists the **original equipment** in `equipment_ids` (copied), carries the asset profile, no `asset_id` |
| Refund posted | 2 new assets of **-1000** in draft; the 2 original assets **remain**; no new equipment (lines already had equipment); the 2 equipment stay linked to both the bill lines and the refund lines |
| Manual refund of 300 on 215400 posted | 1 new asset of **-300** in draft |

### Conclusions

- The static reading is confirmed: Odoo 18 does not call `_reverse_move_vals()`, so a
  reversal does not remove the original asset and creates negative assets; a manual
  refund on a fixed-asset account creates a negative asset.
- The reversal copies `equipment_ids` to the refund lines (field without
  `copy=False`): confirmed; our module redeclares it with `copy=False`.
- Test choice kept (question C8): supplier refunds on accounts carrying an asset
  profile are refused by default (company setting). The proper treatment (reduce the
  original value, cancel, dispose) waits for the accountant's answer to C8.

## 2. Purchase order billed on a fixed-asset account (hypothesis 2 of CLAUDE.md)

Same environment. Script: `characterise_purchase_split.py`. Product storable, serial
tracking, `maintenance_ok`, category « Fixed Assets » (average cost, manual valuation,
expense account 215400); purchase order of 3 units, received with 3 serial numbers,
bill created from the order.

| Step | Measured |
|---|---|
| Bill created from the order | 3 lines of 1 unit (split by `asset_product_item`); **only the first keeps `purchase_line_id`** |
| Order after posting | invoiced quantity **1** of 3, still « to invoice » for 2 |
| Assets / equipment | 3 assets, 3 equipment (created by `maintenance_account`) |
| Stock valuation layers | value 300 (they exist even with manual valuation, as expected) |

Cause: `_expand_asset_line()` of `account_asset_management` copies the line with
`copy()`; Odoo copies `purchase_line_id` only with the context
`include_business_fields` (`_copy_data_extend_business_fields`).

With that context (variant of the script): the 3 lines keep `purchase_line_id`, the
order shows 3 invoiced, status « invoiced ».

Conclusion: hypothesis 2 is **false** in the standard combination. Our module
overrides `_expand_asset_line()` to run it with `include_business_fields=True`; an
integration test checks the invoiced quantity of the order.
