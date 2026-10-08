# Phase 0 – configuration of artdubati_test

Revision 2 of `docs/DEFINITIONS.md`. Run by the owner on the server, in this order.
Already done before: consumable categories 11-17 at average cost; Consignment
(owner on stock) enabled.

## 1. OCA modules (server)

Only `stock_location_address` needs a new clone; the other modules come from OCA
repositories already cloned for installed modules (maintenance, contract).

```bash
cd /opt/odoo/addons
git clone --depth 1 -b 18.0 https://github.com/OCA/stock-logistics-transport.git stock-logistics-transport-18
ls maintenance-18/maintenance_equipment_usage maintenance-18/maintenance_request_purchase contract-18/contract_line_successor
```

If the `ls` fails, the folder name differs: look for the OCA maintenance and contract
clones with `grep addons_path /opt/odoo/config/odoo.conf` and adapt the path.

Add the new clone to `addons_path` in `/opt/odoo/config/odoo.conf`, using the path as
seen from inside the container (same form as the other OCA entries of that line), then:

```bash
docker restart odoo_web
docker exec -i odoo_web odoo -d artdubati_test -u base --stop-after-init 2>&1 | tail -3   # refreshes the module list
docker exec -i odoo_web odoo -d artdubati_test \
  -i contract_line_successor,maintenance_equipment_usage,maintenance_request_purchase,stock_location_address \
  --stop-after-init 2>&1 | grep -E " (ERROR|CRITICAL|WARNING) " | head -20
docker restart odoo_web
```

`maintenance_request_purchase` installs the Purchase application if it is not there
yet. `maintenance_equipment_contract` stays installed until phase 3 (the current stock
monitor reports use it).

## 2. Configuration script

From any machine with Python 3 (no dependency), with an administrator account of
artdubati_test:

```bash
cd docs/phase0
export ODOO_URL=https://erp.lartdubati.com ODOO_DB=artdubati_test ODOO_LOGIN=<admin login>
read -s ODOO_PASSWORD && export ODOO_PASSWORD
python3 setup_phase0.py            # dry run: shows what it found and would do
python3 setup_phase0.py --apply    # after checking the dry run output
```

The dry run stops with a clear message if an account code (exact codes of the Odoo 18
French chart: 215400, 281500, 681120), the miscellaneous journal
or the location `Chez tiers` is not found exactly once. Paste its output to Claude if
anything is unexpected.

## 3. Accounting choices (test only)

Chosen for artdubati_test so that development and integration tests can run. **They
are not validated by the accountant** and can be changed by the accountant at any
time; nothing in the code depends on the values below, only on their existence.

| Choice | Value for the test | Where to change it |
|---|---|---|
| Fixed-asset account (tools and equipment) | 215400 Matériels industriels | Constants `ASSET_ACCOUNT`, `DEPRECIATION_ACCOUNT`, `EXPENSE_ACCOUNT` of `setup_phase0.py` then rerun, or in Odoo the profile's accounts and the category's expense account (below) |
| Depreciation account | 281500 Amortissements installations, matériel et outillage industriels | Profile: **Compte de dépréciation** |
| Depreciation expense account | 681120 Dotations aux amortissements des immobilisations corporelles | Profile: **Compte de dépréciation (charge)** |
| Asset profile | « Matériel et outillage (test) », journal OD (opérations diverses) | **Facturation → Configuration → Immobilisations → Catégories d'immobilisation** |
| Depreciation method | Linear, 5 years, yearly lines, prorata temporis | Same profile: **Méthode de calcul**, **Nombre d'années**, **Prorata temporis** |
| Draft assets | Assets created from a bill stay in draft until confirmed | Same profile: **Sauter l'état brouillon** (tick to confirm automatically) |
| One asset per unit | Enabled (required by the design: one asset per serial number) | Same profile: **Créer une immobilisation par article** (keep ticked) |
| Profile on the account | Account 215400 carries the profile, so a bill line on it creates an asset | **Facturation → Configuration → Comptabilité → Plan comptable**, account 215400, field **Catégorie d'immobilisation** |
| Product category for stock-tracked fixed assets | « All / Fixed Assets »: average cost, manual valuation, expense account 215400 | **Inventaire → Configuration → Catégories de produits** → Fixed Assets: **Méthode de coût**, **Valorisation d'inventaire**, **Compte de charges** |
| Equipment rental expense account | 613500 Locations mobilières | Used from phase 1 (posting lock on rent bills); it will be a company setting with this default |

Another depreciation duration per kind of equipment = another profile on another
class 21 account (for example 215500 Outillage industriel), and another product category
pointing to it. The script only creates the first one.

## 4. Third-party location

The existing `WH/Chez tiers` is a child of the warehouse view location `WH`, not of
`WH/Stock`, so ordinary deliveries do not reserve what is there: it already meets the
design and no new location tree is created. The script only checks it. One child
location per third party (e.g. `WH/Chez tiers/Client A`) is created when needed, with
its address (field from `stock_location_address`, phase 1).
