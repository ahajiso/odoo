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

### Audit of PR #3 (20/10/2026, Claude)

- **The bug was not fixed by PR #3.** Reproduced in a browser (local copy of the
  server's code and data, catalogue manager): the first save sends
  `similar_confirmed: false`, a field shown to catalogue managers only. `name`, `state`
  and `requester_id` are readonly in the model, so the web client never sends them
  (`web/static/src/views/fields/field.js`, `record.js` `_getChanges`). With PR #3 alone
  (18.0.5.2.4 of d7e1335) the same click still gives « This field is set by the
  request itself. ».
- Correction (2b9762d): `similar_confirmed` readonly in the form before approval (same
  rule as the write check) and an exact `False` accepted on create (`True` still
  refused); test replaying the captured payload through `web_save`. PR #3's three
  accepted defaults stay (harmless, for other clients).
- Browser check after the correction: a service request and the AXTON request (material,
  category 22) are saved and submitted on the first click; the payload no longer
  carries `similar_confirmed`.
- Suites of both modules on the server's code and data, updated from 18.0.5.2.3:
  **310 tests, 0 failed** locally (309 on the server: the real websocket class is
  skipped there). No route added.
- Activation script rehearsed on a local copy renamed `artdubati_test` (only the six
  expected ids adapted to the local ones): dry run 9 changes, `--apply` 9, control run
  0; the six categories at automated valuation with the stock journal STJ; the two
  leaves created. `request_ready` is traced to the system user (shell run as
  superuser), not to a person. The server ids 12 to 17 come from PR #3, not verified
  by Claude: the dry run refuses any difference before writing.

### First window (20/10/2026, b4648bd): stopped by the tests, rolled back

PLATFORM OK (before); BACKUP OK (`catstock`, 584 files, 0 missing, COUNTS `9 28 9 18 17
743`, code 1740e6b); CODE OK b4648bd; UPDATE OK; **1 failed of 309**:
`TestCreationRequest.test_waiting_family_refused` assumed that no material category is
open to requests, false on artdubati_test (one already is) and after any activation
(category 22). Reproduced locally on an activated copy; the test now closes them in its
own transaction; full suites on that copy: 310, 0 failed. Activation not run. Rolled
back with `restore_db.sh catstock`.

### Deployment record (20/10/2026, second window `catstock2`, code 877a30d)

Rollback of the first window confirmed (RESTORE OK, REGISTRY OK 122, code 1740e6b,
PLATFORM OK). Before the second window the owner unticked « Available for requests » on
12 and 13 (ticked by hand that afternoon, refused by the script as partial) and on the
root 507 « Construction Materials » (no stock accounts); no request used them.
PLATFORM OK (before); BACKUP OK (`catstock2`, 584 files, 0 missing, code 1740e6b); CODE
OK 877a30d; UPDATE OK; **309 tests, 0 failed**; odoo_web left stopped; activation dry
run 9 (categories 12 to 17 in their original state, 311000 to create, 321000 id 188
reused, 8 READY), `--apply` **9 changed**, control run **0**; start, HEALTH OK;
PLATFORM OK (after); routes identical to routes_after_18.0.5.2.3.txt. Kept until the
acceptance: backups `catstock`, `catstock2`, copies `*_before_restore_20261020_150943`.
Next: acceptance by the owner (below). C29 stays a test choice for the accountant.

### Procedure (one command at a time, after the audit)

```bash
cd /opt/odoo/addons/custom
COMMIT=<commit announced after the audit>
git fetch origin +refs/heads/main:refs/remotes/origin/main
git log -1 --oneline origin/main                       # $COMMIT
rm -rf /tmp/catstock && mkdir -p /tmp/catstock
git archive origin/main docs/phase4 docs/catalogue_stock docs/deploy_modules.sh \
  docs/backup_db.sh docs/restore_db.sh docs/one_off_rental/routes_after_18.0.5.2.3.txt \
  | tar -x -C /tmp/catstock
git status --short | head                              # nothing
bash /tmp/catstock/docs/phase4/check_modules.sh before # PLATFORM OK (before)
bash /tmp/catstock/docs/backup_db.sh catstock          # BACKUP OK
BACKUP=$(sed -n 's/^DUMP=//p' /opt/odoo/logs/catstock_backup)
KEEP_STOPPED=1 ARTDUBATI_DISPOSABLE=reset-before-production \
  bash /tmp/catstock/docs/deploy_modules.sh "$BACKUP" 309 catstock "$COMMIT"
                                       # TESTS OK … 309, « odoo_web left STOPPED »
bash /tmp/catstock/docs/catalogue_stock/run_activation.sh          # CATALOGUE STOCK OK (dryrun)
bash /tmp/catstock/docs/catalogue_stock/run_activation.sh --apply  # END | applied, N record(s) changed
bash /tmp/catstock/docs/catalogue_stock/run_activation.sh          # END | dry run, 0 record(s) rolled back
docker start odoo_web
docker exec odoo_web python3 -c "import urllib.request,time
for _ in range(30):
    try: urllib.request.urlopen('http://localhost:8069/web/health', timeout=3); print('HEALTH OK'); break
    except Exception: time.sleep(3)
else: print('HEALTH FAILED')"
bash /tmp/catstock/docs/phase4/check_modules.sh after  # PLATFORM OK (after)
docker exec -i odoo_web odoo shell -d artdubati_test --no-http \
  < /tmp/catstock/docs/phase4/routes.py > /opt/odoo/logs/catstock_routes.txt
diff /tmp/catstock/docs/one_off_rental/routes_after_18.0.5.2.3.txt \
  /opt/odoo/logs/catstock_routes.txt && echo "ROUTES IDENTIQUES"
```

Send the dry run's output before `--apply` if it shows any `ERROR` (nothing is written
then). On any FAILED, an `ERROR`, a count other than 309 or a control run other than
0: stop, odoo_web stays stopped, then `bash /tmp/catstock/docs/restore_db.sh catstock`
(database, filestore and code of the backup).

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
“This field is set by the request itself.”, for a catalogue manager too. A different
requester, state, request number or `similar_confirmed: true` sent through the API
must still be refused.
