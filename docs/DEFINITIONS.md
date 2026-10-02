# Definitions: Investor Home and Stock Monitor

Status: validated by the owner on 03/10/2026, except the two points marked "to confirm".

## Stock
A stock is a stock.location (physical now, virtual later). Attributes:
place type (physical / lent-out / virtual), address (country, state, city; inherited
from the warehouse partner, overridable), currency (default: company currency).
A "lent-out" stock is the designated stock an item returns to when it comes back.

## Item families
- Asset: maintenance.equipment (unique item, no quantity tracking; quantity = 1).
- Consumable: goods product with Track Inventory, quantity from stock.quant.

## Ownership status (one explicit field, both families)
owned | borrowed | rented | lent_out
- owned: company property, in its stock.
- borrowed: belongs to a third party, we hold it for free.
- rented: belongs to a third party, we pay rent.
- lent_out: company property, held by a third party; it has a designated stock.
Existing owner_type and acquisition_mode stay as secondary data and are mapped to this field.

## Measures (per stock, in the stock's currency)
1. Quantity: number of assets, quantity on hand of consumables.
2. Inventory value (audience: store responsible): everything physically assumed to be
   in the stock, whoever owns it. Basis: acquisition cost for owned and lent_out items
   (consumables: average cost); replacement value for borrowed and rented items
   (to confirm).
3. Accounting value (audience: accountant): net book value of company property only.
   - owned and lent_out: acquisition value minus accumulated depreciation (assets);
     average-cost valuation (consumables).
   - borrowed and rented: 0.
   - Depreciation comes from the OCA module account_asset_management.
4. Cost (rented items only): rent amount per period, period, start date, and
   cumulative rent paid to date. Not applicable to other statuses.

Costing method for consumables: average cost (AVCO), changeable later.

## Currency
Each stock is reported in its own currency. Totals are only ever summed within one
currency and shown grouped by currency. No consolidation in this version.
Conversion from the company currency is done at entry (to confirm with the accountant).

## Access
Per user, any combination of: allowed countries, allowed stocks, allowed ownership
statuses, allowed families. Empty list = no restriction on that dimension.
A user with no access profile sees nothing. Enforced by record rules on every model the
monitor reads, including the unified reporting model.
Accounting value and cost are visible only to users with the matching right
(accounting group / store group respectively).
