# Phase 0 – configuration of artdubati_test

Revision 2 of `docs/DEFINITIONS.md`. Run by the owner on the server, in this order.
Already done before: consumable categories 11-17 at average cost; Consignment
(owner on stock) enabled.

Order: backup, OCA modules, dry run without error, `--apply`, control dry run.
Run the shell blocks with bash; `set -o pipefail` makes a failed Odoo command fail
the pipeline instead of being hidden by `tee`, and the full logs stay in
`/opt/odoo/logs/`.

## 1. Backup of artdubati_test (server)

```bash
set -o pipefail
mkdir -p /opt/odoo/backups /opt/odoo/logs
docker exec odoo_db pg_dump -U odoo -Fc artdubati_test \
  > /opt/odoo/backups/artdubati_test_$(date +%F_%H%M)_phase0.dump && echo BACKUP OK
ls -lh /opt/odoo/backups | tail -3
```

Restore if needed (database only; the test filestore is not touched by phase 0):
`docker exec -i odoo_db pg_restore -U odoo -d artdubati_test --clean --if-exists < <file>.dump`
with Odoo stopped (`docker stop odoo_web`, then `docker start odoo_web`).

## 2. OCA modules (server)

State observed on artdubati_test: `purchase` installed; `contract_line_successor`,
`maintenance_equipment_usage`, `maintenance_request_purchase` available, not
installed; `stock_location_address` not in the module list (new repository needed);
`maintenance_equipment_contract` installed, kept until phase 3 (the current stock
monitor reports use it).

```bash
set -o pipefail
cd /opt/odoo/addons
git clone --depth 1 -b 18.0 https://github.com/OCA/stock-logistics-transport.git stock-logistics-transport-18
ls -d stock-logistics-transport-18/stock_location_address
```

Add the new clone to `addons_path`. The container reads `/etc/odoo/odoo.conf` and sees
`/opt/odoo/addons/<folder>` as `/mnt/extra-addons/<folder>` (log line "addons paths"
of the install below). Check, then add the entry:

```bash
docker inspect odoo_web --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
docker exec odoo_web ls -d /mnt/extra-addons/stock-logistics-transport-18/stock_location_address
grep -n '^addons_path' /opt/odoo/config/odoo.conf
sed -i '/^addons_path/ s|$|,/mnt/extra-addons/stock-logistics-transport-18|' /opt/odoo/config/odoo.conf
docker exec odoo_web grep -n '^addons_path' /etc/odoo/odoo.conf   # must end with the new entry
```

Use `sed` only if the `inspect` line shows `/opt/odoo/addons -> /mnt/extra-addons` and
`/opt/odoo/config -> /etc/odoo`, and the `ls` succeeds; otherwise ask Claude.

```bash
set -o pipefail
LOG=/opt/odoo/logs/phase0_install_$(date +%F_%H%M).log
docker exec -i odoo_web odoo -d artdubati_test \
     -i contract_line_successor,maintenance_equipment_usage,maintenance_request_purchase,stock_location_address \
     --stop-after-init 2>&1 | tee "$LOG" \
  && echo "INSTALL COMMAND OK"
grep -E " (ERROR|CRITICAL) |invalid module names" "$LOG" && echo "PROBLEM FOUND: do not continue" || echo "no ERROR/CRITICAL/invalid module line"
docker restart odoo_web
```

With `-i`, Odoo refreshes the module list itself (no `-u base`, which would update
every installed module). A module missing from `addons_path` only gives a WARNING
"invalid module names, ignored", hence the `grep` on it. Then check in the database:

```bash
docker exec -i odoo_db psql -U odoo -d artdubati_test -c "SELECT name, state, latest_version FROM ir_module_module WHERE name IN ('contract_line_successor','maintenance_equipment_usage','maintenance_request_purchase','stock_location_address') ORDER BY name;"
docker exec -i odoo_db psql -U odoo -d artdubati_test -c "SELECT name FROM ir_model_fields WHERE model = 'stock.location' AND name IN ('address_id','real_address_id');"
```

Continue only with four rows in state `installed` and the two fields listed.

## 3. Configuration script

From any machine with Python 3 (no dependency), with an administrator account of
artdubati_test that is **not** in the group « Stock Monitor Investor » (the global rule
of lartdubati_investor_home hides internal locations from that group, administrators
included; the script refuses such an account):

```bash
cd docs/phase0
export ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test ODOO_LOGIN=<admin login>
read -s ODOO_PASSWORD && export ODOO_PASSWORD
python3 setup_phase0.py            # dry run: must end without error
python3 setup_phase0.py --apply    # only after a clean dry run
python3 setup_phase0.py            # control: everything found, nothing left to do
```

- `--apply` refuses any database other than artdubati_test.
- An existing asset profile, category or account link is never changed (shown as
  KEEP), so a rerun does not undo the accountant's changes. Its structural values
  (accounts, journal, method, one asset per unit, valuation, cost method) are compared
  with the test choices and each difference is shown as DIFF, with a summary at the
  end. To reset them to the values of the script: `--apply --force-update`.
- Before any write, the script proves it can read the warehouse root and stock
  locations, and checks that an existing `Chez tiers` is internal, active and directly
  under the warehouse root.
- The dry run stops with a clear message if an account code (exact codes of the Odoo
  18 French chart: 215400, 281500, 681120), the miscellaneous journal (code `OD` or
  `MISC`), the warehouse (`Bg`, « Bougival 1 ») or a single `Chez tiers` location
  cannot be found, or if a duplicate exists. `Chez tiers` is created under the
  warehouse root if it does not exist.

## 4. Accounting choices (test only)

Chosen for artdubati_test so that development and integration tests can run. **They
are not validated by the accountant** and can be changed by the accountant at any
time; nothing in the code depends on the values below, only on their existence.

| Choice | Value for the test | Where to change it |
|---|---|---|
| Fixed-asset account (tools and equipment) | 215400 Matériels industriels | Constants `ASSET_ACCOUNT`, `DEPRECIATION_ACCOUNT`, `EXPENSE_ACCOUNT` of `setup_phase0.py` then rerun, or in Odoo the profile's accounts and the category's expense account (below) |
| Depreciation account | 281500 Amortissements installations, matériel et outillage industriels | Profile: **Compte de dépréciation** |
| Depreciation expense account | 681120 Dotations aux amortissements des immobilisations corporelles | Profile: **Compte de dépréciation (charge)** |
| Asset profile | « Matériel et outillage (test) », journal MISC (opérations diverses) | **Facturation → Configuration → Immobilisations → Catégories d'immobilisation** |
| Depreciation method | Linear, 5 years, yearly lines, prorata temporis | Same profile: **Méthode de calcul**, **Nombre d'années**, **Prorata temporis** |
| Draft assets | Assets created from a bill stay in draft until confirmed | Same profile: **Sauter l'état brouillon** (tick to confirm automatically) |
| One asset per unit | Enabled (required by the design: one asset per serial number) | Same profile: **Créer une immobilisation par article** (keep ticked) |
| Profile on the account | Account 215400 carries the profile, so a bill line on it creates an asset | **Facturation → Configuration → Comptabilité → Plan comptable**, account 215400, field **Catégorie d'immobilisation** |
| Product category for stock-tracked fixed assets | « All / Fixed Assets »: average cost, manual valuation, expense account 215400 | **Inventaire → Configuration → Catégories de produits** → Fixed Assets: **Méthode de coût**, **Valorisation d'inventaire**, **Compte de charges** |
| Equipment rental expense account | 613500 Locations mobilières | Used from phase 1 (posting lock on rent bills); it will be a company setting with this default |

Another depreciation duration per kind of equipment = another profile on another
class 21 account (for example 215500 Outillage industriel), and another product category
pointing to it. The script only creates the first one.

## 5. Third-party location

`Chez tiers` must be a child of the warehouse root location (shown as `WH`, warehouse
« Bougival 1 », code `Bg`), not of its stock location `Bg/Stock`, so that ordinary
deliveries never reserve what is there. The script checks it and creates it there if
it does not exist; no other location tree is created. One child location per third
party is created when needed, with its address (field from `stock_location_address`,
phase 1).
