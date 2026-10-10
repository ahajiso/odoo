# Roadmap after phase 4 (audits of 6063db1, 2071e6e and 86cf4ac..beacfeb, 10/10/2026)

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

## 0. Right after phase 4 (audit of 86cf4ac..beacfeb), before A to K

Not mixed with the phase 4 security deployment; each with its own plan and audit.

1. Label « Can be Maintenance » → « Can be Maintained » (FR « Peut être maintenu »,
   FA with the same verbal meaning): find which OCA module defines it, override the
   label with a minimal local inheritance (never edit the OCA repository), test
   `fields_get` in the three languages.
2. Product creation procedure, reworked.
3. Two separate classifications: the product category (accounting treatment) and the
   equipment category (business); default equipment category on the product.
4. Clean-up of the existing categories, in particular the misleading equipment category
   « Fixed Assets ».
5. Mac Mini to regularise: product category « All » and equipment category « All »
   wrong; no bill and no fixed asset; order now at 1 100 € (excl. tax) while the
   equipment keeps a provisional cost of 1 850 € (excl. tax).
6. Audit of the accounts of every product and equipment category (accountant,
   `QUESTIONS_COMPTABLE.md`).

Then the functional phases below, and the manual last.

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
« VT » means « vêtements de travail » (workwear), confirmed on 10/10/2026.

- employee or contractor; product and size; quantity given; date given;
- useful life or renewal date; return;
- mandatory PPE, certification and expiry;
- signature or proof of delivery.

`hr`, `hr_expense` and `project` are not installed.

## I. Operational maintenance
A maintenance contract (A) and a maintenance job are two different objects. Standard
`maintenance` (installed) and the OCA modules already there (`maintenance_request_repair`,
`maintenance_request_purchase`, `maintenance_equipment_usage`...) first. To cover:
- preventive and periodic maintenance; next due date and alerts;
- corrective requests and jobs;
- provider, parts, labour and duration;
- equipment downtime;
- bill and cost linked to the equipment;
- full history;
- job covered or not by the warranty (the equipment's warranty fields, phase 1).

## J. Supplier bill intake
Recurring bills (A) do not cover every entry. To cover:
- PDF upload or bills received by email;
- one-off bill without a contract;
- duplicate check (supplier, reference, amount, date);
- supplier, reference, dates, taxes, accounting and analytic distribution;
- order – receipt – bill matching where there is an order (phase 1 and 2 integration);
- approval circuit; handling of differences;
- link to a contract, equipment, vehicle, worksite or warehouse.

Target: a persistent controlled document, as for the other entries.

## K. One-off expenses and expenses paid by employees
- tolls, fuel, parking, small purchases;
- paid by an employee or with a company card;
- receipts and reimbursements;
- assignment to a worksite, vehicle or cost centre;
- bill without an order and without a contract.

Standard `hr_expense` first (not installed; it needs `hr`).

## Last. Manual
Rewrite of the three manuals (FR, then EN / FA) for all phases. The procedure is in
`docs/manual/maintenance-manuel-odoo.md`.
