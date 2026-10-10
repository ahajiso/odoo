# Phase 4 – plan (draft, items decided before the plan)

Scope (CLAUDE.md): home page and investor user setup, review of the existing
configuration (web_quick_start_screen versus a client action). The full plan is proposed
to the owner and audited before any code.

## Items already decided by the owner

### P4-1. Regularisation of third-party consumables (owner's decision, 10/10/2026)
Found by the stock monitor after the phase 3 deployment: quant 10 at TBER/Stock, 15
« TEST Cement bag » owned by « TEST Supplier (owner) » (consignment test of phase 0),
Integrity alert. Consumables are owned only in v1 (DEFINITIONS.md), and
`stock.move.line._check_third_party_owner` (phase 2) refuses every move line carrying an
owner other than the company unless it is the serial number of a borrowed or rented
equipment of that owner. Standard Odoo changes a quant owner only through a move (the
owner column of an existing quant is read-only), so such a leftover can neither leave
the stock nor become the company's.

To build (option 2 chosen by the owner):
- allow, for an untracked consumable (no serial, `maintenance_ok` false) whose
  existing quant belongs to a third party, only the two regularisations:
  1. its removal by an inventory adjustment (internal location → inventory loss
     location, line owner = the quant's owner);
  2. its passage to the company by an internal transfer on the same location with
     « Assign Owner » = the company (source line owner = the third party, destination
     quant without owner);
- everything else stays refused: a third-party consumable entering the stock, moving
  between locations, leaving to a customer or supplier;
- tests: both regularisations accepted, every other case still refused, the monitor's
  Integrity alert gone afterwards, the valuation of the passage to the company (average
  cost; entry if the category is in automated valuation) checked;
- to check during the plan: how Odoo 18 builds the move lines of an owner change (one
  internal line with `owner_id` = third party and the destination quant's owner from
  the picking's `owner_id`), and whether the passage to the company produces a
  valuation layer.

Then, on artdubati_test, the owner's choice for quant 10 (remove or pass to the company).

## Data cleaned after the phase 3 deployment (10/10/2026)
Bg/TEST Paris (id 21): its 40 « TEST Cement bag » moved to Bg/Stock by a standard
internal transfer (Bg/Stock now 46); « Outside Any Monitor Stock » alert gone; the
location to archive.
