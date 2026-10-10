# Roadmap after phase 4 (proposed by the audit of 6063db1, 10/10/2026)

Functional needs found by the audit, **not part of phase 4** (security). Each one becomes
its own phase, with a plan audited before any code. The order is for the owner to set.
The manual stays the very last phase: its rewrite covers every phase before it. This
moves to the end the rewrite planned for phase 5 (owner's decision of 08/10/2026:
rewrite once, at the end of the last phase).

Rules carried by each phase:
- every entry goes through a persistent, controlled document (as the equipment
  operations of phase 2): approval separated from execution; standard Odoo / OCA
  objects created or completed, not copied;
- standard Odoo and OCA modules first (Fleet, Project, HR...), links rather than double
  records;
- accounting questions go to `docs/QUESTIONS_COMPTABLE.md` (test choice, configurable);
- investor accounts: a new investor screen needs, explicitly, its action, models,
  methods, routes, menu, fields and tests (`docs/phase4/ROUTES.md`); without them,
  nothing new is visible to investors;
- every module installed comes with the inventory of its routes (`docs/phase4/routes.py`).

## A. Recurring expenses and contracts
A persistent document creating or completing the contract (OCA `contract`) and its
bills:
- type: subscription, insurance, maintenance, rental, energy, telecom, software, other;
- supplier; requester, responsible and approver; company, site, warehouse or worksite;
- service product and account; analytic distribution;
- amount (excl. tax), taxes, currency, indexation;
- periodicity; start date, end date or open-ended;
- notice, tacit or manual renewal;
- supplier reference and contract reference; documents without limit;
- payment method and term;
- previous / successor contract (`contract_line_successor`);
- bills generated, posted and paid.

The approval comes before the contract or the commitment. Recurring bills stay draft for
review.

Covers telephone, internet and ChatGPT (E):
- the product « Abonnement téléphonique » exists on 626000;
- the internet product is still to create;
- the ChatGPT product and its account are to confirm with the accountant;
- no real contract is configured yet.

## B. Paying bills
The current flow stops at posting and a manual payment. Missing:
- supplier payment methods;
- payment schedule and payment batches;
- SEPA files where needed;
- payment approval separated from the payment;
- bank statement import and bank reconciliation;
- follow-up of each bill: generated → approved → due → paid;
- direct debits.

## C. Insurance register
The equipment contract model is not enough. Insured objects: equipment, vehicle or
trailer, warehouse / site, company, worksite or building, ten-year liability (D).

Fields:
- insurer and broker; policy;
- nature of the cover; insured object; activities and areas covered;
- deductible and limits; effective and expiry dates; notice and renewal;
- premium and periodicity;
- certificates and specific conditions;
- alerts; compliant / not compliant.

An equipment is « insured » only with an active policy or a justified waiver.

## D. Ten-year liability insurance (décennale)
A cover of the company and its activities, not of a piece of equipment. For each
worksite or installation, it must prove:
- which policy was active on the date of the works;
- whether the activity was covered;
- which certificate was given to the customer, and its validity dates.

A copy (snapshot) of the applicable certificate is attached to the worksite, the quote or
the customer invoice.

## F. Vans and trailers
Standard `fleet` (not installed), with unique links
`fleet.vehicle ↔ maintenance.equipment ↔ account.asset`. To cover:
- registration, VIN and registration document;
- driver / responsible;
- mileage; fuel and charging;
- insurance (C);
- maintenance and repairs; technical inspection; tyres and consumables;
- fixed asset;
- assignment and cost per worksite.

A trailer is a vehicle or an equipment depending on its administrative status, never two
independent records.

## G. Worksite materials and consumables
Receipt exists (phase 2); consumption per worksite does not. Gaps:
- `project` is not installed;
- the product « Matériaux de construction » is not storable;
- consumable categories 11 to 17 are empty.

**To settle first (accountant): the valuation of consumables.** `docs/DEFINITIONS.md`
says automated valuation at average cost. The audit reads the categories as manual
valuation. To check on artdubati_test with a query, then decide and document.

Then a worksite exit / consumption document:
- worksite and destination location; requester and operator;
- product, quantity, unit; lots where needed; cost; analytic account;
- return of surplus; scrap / loss with a reason; supporting documents.

## H. Workwear and PPE (« VT/EPI ») of the workers
- employee or contractor; product and size; quantity given; date given;
- useful life or renewal date; return;
- mandatory PPE, certification and expiry;
- signature or proof of delivery.

`hr`, `hr_expense` and `project` are not installed.

## Last. Manual
Rewrite of the three manuals (FR, then EN / FA) for all phases. The procedure is in
`docs/manual/maintenance-manuel-odoo.md`.
