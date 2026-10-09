# Stock monitor (obsolete OCA bi_sql_editor reports)

Since phase 3 the stock monitor is the model `lartdubati.stock.monitor` of module
`lartdubati_investor_home` (one SQL view) with its OWL dashboard (action
`lartdubati_investor_home.action_stock_monitor`) and the standard views (action
`lartdubati_investor_home.action_stock_monitor_analysis`). Definitions:
`docs/DEFINITIONS.md`; plan: `docs/phase3/PLAN.md`; deployment: `docs/phase3/README.md`.

The two bi_sql_editor reports (`stock_monitor`, `stock_monitor_full`) are deleted at the
phase 3 deployment (step 0b of its README). Their queries and configuration are in the
git history of this folder (before phase 3).
