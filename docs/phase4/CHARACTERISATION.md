# P4-1 step 1: characterisation of consigned consumables (10/10/2026)

Plan: docs/phase4/PLAN.md §5. Question to the accountant: C23
(docs/QUESTIONS_COMPTABLE.md). Script: `characterise_consignment.py` (odoo shell,
rolled back at the end).

## Environment

Local, not artdubati_test: Odoo 18.0 community (commit 6d58dc84 of 08/10/2026),
PostgreSQL 16, Python 3.12, French chart of accounts.
- **Standard**: database with `stock_account`, `purchase_stock` and `l10n_fr` only,
  none of our modules.
- **Ours**: the test database with `maintenance_shareholder_equipment` and
  `lartdubati_investor_home` (phase 3 code). Our rules refuse a consigned receipt,
  so the starting stock is written directly there.

Product: storable consumable, category AVCO with automated valuation, cost 5.00.
Starting stock in WH/Stock: 10 owned, received at 5.00; 15 owned by « Consignor »,
received with « Assign Owner ».

## Results: standard Odoo 18

```
Odoo 18.0.1.3 | modules: l10n_fr, purchase_stock, stock_account

## S0 starting stock: 10 owned received at 5.00, then 15 received with « Assign Owner » = consignor
  move line: Partners/Vendors -> WH/Stock qty 10.0 owner - state done [WH/IN/00011]
  move line: Partners/Vendors -> WH/Stock qty 15.0 owner Consignor (charac) state done [WH/IN/00012]
  quant: WH/Stock qty 10.0 owner -
  quant: WH/Stock qty 15.0 owner Consignor (charac)
  valuation layer: qty 10.0 value 50.0 unit 5.0 (WH/IN/00011 - Cement bag (charac))
  journal item: STJ 110200 Stock Interim (Received) D 0.0 C 50.0 (posted)
  journal item: STJ 110100 Stock Valuation D 50.0 C 0.0 (posted)
  product: qty_available 10.0 average cost 5.0

==============================================================================

## S1 consigned quant counted 0 (inventory adjustment)
  move line: WH/Stock -> Virtual Locations/Inventory adjustment qty 15.0 owner Consignor (charac) state done [Product Quantity Updated, inventory]
  quant: WH/Stock qty 10.0 owner -
  quant: WH/Stock qty 0.0 owner Consignor (charac)
  product: qty_available 10.0 average cost 5.0

==============================================================================

## S2 consigned goods delivered back to the consignor (owner on the delivery)
  move line: WH/Stock -> Partners/Customers qty 10.0 owner Consignor (charac) state done [WH/OUT/00003]
  move line: WH/Stock -> Partners/Customers qty 5.0 owner Consignor (charac) state done [WH/OUT/00003]
  quant: WH/Stock qty 10.0 owner -
  quant: WH/Stock qty 0.0 owner Consignor (charac)
  product: qty_available 10.0 average cost 5.0

==============================================================================

## S3 internal transfer on the same location, « Assign Owner » = company
  move line: WH/Stock -> WH/Stock qty 10.0 owner My Company state done [WH/INT/00003]
  move line: WH/Stock -> WH/Stock qty 5.0 owner My Company state done [WH/INT/00003]
  quant: WH/Stock qty 10.0 owner -
  quant: WH/Stock qty 15.0 owner Consignor (charac)
  quant: WH/Stock qty 0.0 owner My Company
  product: qty_available 10.0 average cost 5.0

==============================================================================

## S4 purchase from the consignor (order 15 at 6.00, receipt, bill), then S1
  move line: Partners/Vendors -> WH/Stock qty 15.0 owner - state done [WH/IN/00013]
  move line: WH/Stock -> Virtual Locations/Inventory adjustment qty 15.0 owner Consignor (charac) state done [Product Quantity Updated, inventory]
  quant: WH/Stock qty 25.0 owner -
  quant: WH/Stock qty 0.0 owner Consignor (charac)
  valuation layer: qty 15.0 value 90.0 unit 6.0 (WH/IN/00013 - Cement bag (charac))
  journal item: STJ 110200 Stock Interim (Received) D 0.0 C 90.0 (posted)
  journal item: STJ 110100 Stock Valuation D 90.0 C 0.0 (posted)
  journal item: BILL 110200 Stock Interim (Received) D 90.0 C 0.0 (posted)
  product: qty_available 25.0 average cost 5.6

==============================================================================

## S5 inventory adjustment adding 15 owned units (no owner)
  move line: Virtual Locations/Inventory adjustment -> WH/Stock qty 15.0 owner - state done [Product Quantity Updated, inventory]
  quant: WH/Stock qty 25.0 owner -
  quant: WH/Stock qty 15.0 owner Consignor (charac)
  quant: WH/Stock qty 0.0 owner -
  valuation layer: qty 15.0 value 75.0 unit 5.0 (Product Quantity Updated - Cement bag (charac))
  journal item: STJ 110200 Stock Interim (Received) D 0.0 C 75.0 (posted)
  journal item: STJ 110100 Stock Valuation D 75.0 C 0.0 (posted)
  product: qty_available 25.0 average cost 5.0
```

## Results: with our modules

```
Odoo 18.0.1.3 | modules: l10n_fr, lartdubati_investor_home, maintenance_shareholder_equipment, purchase_stock, stock_account

==============================================================================

## S0' standard consigned receipt with our modules
  REFUSED: ValidationError: Cement bag (charac) : receipts from suppliers and acquisitions go through an equipment operation (Receipt).

## S0 starting stock written directly: 10 owned, 15 owned by the consignor
  quant: WH/Stock qty 10.0 owner -
  quant: WH/Stock qty 15.0 owner Consignor (charac)
  product: qty_available 10.0 average cost 5.0

==============================================================================

## S1 consigned quant counted 0 (inventory adjustment)
  REFUSED: ValidationError: Cement bag (charac) : an owner other than the company is only allowed for a serial number of a borrowed or rented equipment of that owner (Consignor (charac)).

==============================================================================

## S2 consigned goods delivered back to the consignor (owner on the delivery)
  REFUSED: ValidationError: Cement bag (charac) : an owner other than the company is only allowed for a serial number of a borrowed or rented equipment of that owner (Consignor (charac)).

==============================================================================

## S3 internal transfer on the same location, « Assign Owner » = company
  REFUSED: ValidationError: Cement bag (charac) : an owner other than the company is only allowed for a serial number of a borrowed or rented equipment of that owner (My Company).

==============================================================================

## S4 purchase from the consignor (order 15 at 6.00, receipt, bill), then S1
  REFUSED: ValidationError: Cement bag (charac) : receipts from suppliers and acquisitions go through an equipment operation (Receipt).

==============================================================================

## S5 inventory adjustment adding 15 owned units (no owner)
  move line: Virtual Locations/Inventory adjustment -> WH/Stock qty 15.0 owner - state done [Product Quantity Updated, inventory]
  quant: WH/Stock qty 25.0 owner -
  quant: WH/Stock qty 15.0 owner Consignor (charac)
  quant: WH/Stock qty 0.0 owner -
  valuation layer: qty 15.0 value 75.0 unit 5.0 (Product Quantity Updated - Cement bag (charac))
  journal item: STJ 110200 Stock Interim (Received) D 0.0 C 75.0 (posted)
  journal item: STJ 110100 Stock Valuation D 75.0 C 0.0 (posted)
  product: qty_available 25.0 average cost 5.0
```

## Conclusions

1. **Consigned goods are never valued.** Receipt (S0), removal by adjustment (S1) and
   delivery back to the consignor (S2) create **no valuation layer and no journal
   item**: `stock_account` excludes every move whose owner is not the company
   (`_should_exclude_for_valuation`).
2. **Removal**: the standard ways are an inventory adjustment counted 0 (S1, consigned
   quant → inventory loss) or a delivery to the consignor carrying the owner (S2). Both
   are refused by our phase 2 rule `_check_third_party_owner`.
3. **« Assign Owner » does not change the owner of goods** (S3, the audit was right).
   The transfer moved 15 units « owned by the company » from a quant that did not
   exist (a 0-quant « My Company » appears) and left the consigned quant intact.
   Nothing is valued. The move line owner is the owner of the goods at both ends.
   Not usable; our rule also refuses it (it refuses any owner on a line, even the
   company's partner).
4. **Becoming the company's = buying from the consignor + removing the consigned
   quant** (S4).
   - The purchase receipt creates an owned quant valued at the purchase price (layer
     15 × 6.00; entry stock valuation / stock interim). The average cost moves from
     5.00 to 5.60. The bill clears the interim account.
   - The consigned quant must then be removed (S1).
   - In the end, 25 owned units; the goods are counted once.
   - With our modules, the purchase receipt goes through the existing Receipt
     operation (phase 2). The standard receipt is refused (S4 ours).
5. **Adding owned units by an inventory adjustment (S5)** values them at the current
   average cost, against the inventory adjustment's counterpart (here the stock
   interim account, 110200), **without any supplier document**. That is an acquisition
   without purchase: phase 2 already has a controlled operation for it (Acquisition,
   question C17). It is not to be used to « convert » consigned goods.

## Proposal for step 2 (separate plan, after C23)

- **Removal of consigned goods**: a business action « Consigned stock regularisation ».
  - Reason required, approval separated from execution, history in the chatter, like
    `equipment.operation`.
  - Its execution makes the standard S1 move (adjustment counted 0, no valuation) or
    the S2 move (delivery back to the consignor, if the goods physically leave).
  - Our rule is relaxed only inside that execution: `running` context, untracked
    consumables only, owner = the quant's owner.
- **Passage to the company**: no new mechanism. A purchase from the consignor through
  the existing Receipt operation (valued at the purchase price, bill), then the removal
  above for the consigned quant. Accounting counterpart: the bill (hypothesis of C23,
  to confirm by the accountant).
- **Quant 10 of TBER/Stock** (15 TEST Cement bag, consignor « TEST Supplier (owner) »):
  the owner chooses removal only (test data) or purchase plus removal.
