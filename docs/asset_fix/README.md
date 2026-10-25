# Asset alerts of the stock monitor (owner's choice of 25/10/2026, C28)

Read-only inventory of 25/10/2026 (`inventory.py`): five alerts.

| Equipment | Order / bill | Category | Decision |
|---|---|---|---|
| Mac Mini – 877790 (871) | P00381 Apple, 1 100 € excl. tax, received, not billed | IT Equipment (218300, profile « Matériel informatique (test) ») | capitalised: bill from P00381 |
| EVOLUTION table saw – 133887888 (2179) | P01144 Leroy Merlyn, 519.97 €, received, not billed | Plant & Tools (215400, « Matériel et outillage (test) ») | capitalised: bill of P01144 |
| DEXTER mitre saw – 55669982 (2180) | P01144, 88.22 €, not billed | Plant & Tools | **expensed**: category → Tools & Workshop Equipment (606300) before the bill |
| BOSCH set, 68 piece – 998877 (2181) | P01144, 23.12 €, not billed | « TEST – Installations temporaires » (606300) | filed with the tools (same account); equipment category corrected by the owner |
| Scie sur table – 1234 (484) | BILL/2026/10/0006 posted on 607000 | All | stays expensed (C19); informative alert |

`recategorise.py`: the DEXTER and the BOSCH to « All / Small Durable Equipment / Tools &
Workshop Equipment » (`catalogue_stock.categ_small_tools`). The screen refuses a category
change on purpose (structural lock); the script runs as superuser, refuses any
unexpected state (database, version 18.0.5.2.6, names, serials, current categories, a
bill line or fixed asset already there, a valuation change) and posts the reason on the
product and the equipment. Must run **before** the bill of P01144 is created (a bill
line takes its account from the product category). Rehearsed locally on a copy named
artdubati_test with a local stand-in: refusal on a billed product (nothing written), dry
run 1, apply 1, control 0; the monitor row goes from « Fixed Asset Missing » to « No
Fixed Asset (Expensed) ». Self-audited by Claude (no external audit available).

## Steps (one at a time)

1. Mac Mini: Purchase → P00381 → Create Bill; check 1 100.00 € excl. tax on 218300,
   taxes, date, supplier reference; post (accounting user). Expected: fixed asset
   « Mac Mini », equipment asset linked, cost 1 100 € final, monitor net book value.
2. Backup, then the script's dry run (send the output), apply and control:

```bash
cd /opt/odoo/addons/custom
C=<commit announced>
git fetch origin claude/clever-rubin-z76iba
rm -rf /tmp/assetfix && mkdir -p /tmp/assetfix
git archive "$C" docs/backup_db.sh docs/restore_db.sh docs/asset_fix | tar -x -C /tmp/assetfix
bash /tmp/assetfix/docs/backup_db.sh assetfix                         # BACKUP OK
docker exec -i odoo_web odoo shell -d artdubati_test --no-http \
  < /tmp/assetfix/docs/asset_fix/recategorise.py 2>&1 \
  | grep -E "^(START|TARGET|ITEM|ERROR|SKIP|CHANGE|MONITOR|END|REFUSED)"   # dry run: 2 change(s)
docker exec -i -e CATEGORY_FIX_APPLY=1 odoo_web odoo shell -d artdubati_test --no-http \
  < /tmp/assetfix/docs/asset_fix/recategorise.py 2>&1 \
  | grep -E "^(ERROR|CHANGE|MONITOR|END|REFUSED)"                        # applied, 2
docker exec -i odoo_web odoo shell -d artdubati_test --no-http \
  < /tmp/assetfix/docs/asset_fix/recategorise.py 2>&1 \
  | grep -E "^(ERROR|SKIP|CHANGE|END|REFUSED)"                          # dry run, 0
```

   On an ERROR or REFUSED: nothing was written; send the output. Rollback after a wrong
   apply: `bash /tmp/assetfix/docs/restore_db.sh assetfix`.
3. BOSCH equipment category: Product Catalogue → Structural Corrections → the BOSCH set,
   a « Tools » equipment category instead of « Formwork & Shoring », with the reason.
4. P01144: Create Bill; before posting check EVOLUTION on 215400, DEXTER and BOSCH on
   606300, the other lines on their own accounts; post. Expected: one fixed asset (the
   EVOLUTION), costs final, no « Fixed Asset Missing » left; three informative
   « No Fixed Asset (Expensed) » (Scie 1234, DEXTER, BOSCH).
5. Read-only control: `inventory.py` again.

## Situation after the first dry run (25/10/2026)

The dry run refused (nothing written): P01144 had already been billed and paid
(BILL/2026/10/0013, posted, paid) before the script. Mac Mini billed too
(BILL/2026/10/0012, posted, paid). Fixed assets created, all **draft**, no depreciation
posted (only their creation line): 460 Mac Mini 1 100.00, 461 EVOLUTION 519.97, 462 DEXTER
88.22. The BOSCH line is on 606300 (no asset). No « Fixed Asset Missing » left; yellow:
Scie 1234 and BOSCH.

The script now lists bill lines instead of refusing them (an equipment that still has a
fixed asset is still refused) and reports a refused category change as an ERROR
(savepoint) instead of a traceback; rehearsed locally (constraint refusal reported,
control run 0).

Option A (DEXTER stays capitalised): confirm the draft assets 460, 461, 462; the script
runs for the BOSCH only. Option B (DEXTER expensed, owner's choice C28): accounting user
deletes the draft asset 462 (allowed by account_asset_management for a draft asset
without posted depreciation; the bill line's and the equipment's links are cleared),
posts a miscellaneous entry 606300 debit / 215400 credit 88.22 dated as the bill, then
the script moves the DEXTER and the BOSCH; assets 460 and 461 are confirmed.
