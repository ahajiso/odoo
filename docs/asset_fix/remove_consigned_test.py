"""Remove the consigned TEST cement bags of TBER/Stock (P4-1, owner 25/10/2026).

Quant 10 of TBER/Stock: 15 « TEST Cement bag » owned by « TEST Supplier (owner) », a
consumable held for a third party (monitor « Integrity » alert since 10/10/2026). The
owner confirmed these are test data with no physical goods: they are removed by the
standard Odoo inventory adjustment counted 0 (CHARACTERISATION.md S1: no valuation
layer, no journal item for goods that are not the company's).

Our phase 2 rule `_check_third_party_owner` refuses any stock line carrying a third
party owner on a consumable. It is relaxed **in this shell process only, for this quant
only** (same product, location and owner); the module's code is not changed and
odoo_web keeps the rule. Dry run by default; CONSIGNED_FIX_APPLY=1 commits. Refuses
(nothing written) on any unexpected state.
"""
import os

APPLY = os.environ.get("CONSIGNED_FIX_APPLY") == "1"
SERVER_DB = "artdubati_test"
MODULE = "maintenance_shareholder_equipment"
EXPECTED_VERSION = "18.0.5.2.6"
QUANT_ID = 10
PRODUCT_NAME = "TEST Cement bag"
LOCATION_NAME = "TBER/Stock"
OWNER_NAME = "TEST Supplier (owner)"
QUANTITY = 15.0
REASON = "TEST data removed: consigned cement bags, no physical goods (P4-1, owner 25/10/2026)"

env = env(context=dict(env.context, active_test=False, lang="en_US"))  # noqa: F821
errors = []


def out(section, *parts):
    print(" | ".join([section] + [str(p) for p in parts]))


def error(message):
    errors.append(message)
    out("ERROR", message)


if env.cr.dbname != SERVER_DB:
    raise SystemExit(f"REFUSED: {env.cr.dbname} is not {SERVER_DB}")
module = env["ir.module.module"].search([("name", "=", MODULE)])
if module.state != "installed" or module.latest_version != EXPECTED_VERSION:
    raise SystemExit(f"REFUSED: {MODULE} must be installed at {EXPECTED_VERSION}")
out("START", f"database={env.cr.dbname}", "APPLY" if APPLY else "DRY RUN")

quant = env["stock.quant"].browse(QUANT_ID).exists()
if not quant:
    if APPLY is False and env["stock.move.line"].search_count([("reference", "=", REASON)]):
        out("SKIP", "quant already removed")
        env.cr.rollback()
        out("END", "dry run, 0 change(s) rolled back")
        raise SystemExit(0)
    raise SystemExit(f"REFUSED: quant {QUANT_ID} not found")
product, location, owner = quant.product_id, quant.location_id, quant.owner_id
out("QUANT", quant.id, product.display_name, location.complete_name,
    f"owner={owner.display_name or '-'}", f"quantity={quant.quantity}",
    f"reserved={quant.reserved_quantity}", f"lot={quant.lot_id.name or '-'}")
if quant.quantity == 0 and owner:
    out("SKIP", "quant already at 0")
    env.cr.rollback()
    out("END", "dry run, 0 change(s) rolled back")
    raise SystemExit(0)
if product.name != PRODUCT_NAME or location.complete_name != LOCATION_NAME \
        or owner.name != OWNER_NAME or quant.quantity != QUANTITY:
    error("the quant is not the expected consigned TEST cement bags")
if quant.reserved_quantity or quant.lot_id:
    error("the quant is reserved or carries a lot")
if product.maintenance_ok or product.tracking != "none" or owner == env.company.partner_id:
    error("not a consumable held for a third party")

if errors:
    env.cr.rollback()
    out("END", f"{len(errors)} error(s); nothing written")
    raise SystemExit(1)

# the relaxation: this process only, this quant only
MoveLine = type(env["stock.move.line"])
original = MoveLine._check_third_party_owner


def _check_third_party_owner(self):
    others = self.filtered(lambda l: not (
        l.product_id == product and l.owner_id == owner and l.location_id == location))
    return original(others)


MoveLine._check_third_party_owner = _check_third_party_owner

layers_before = env["stock.valuation.layer"].search_count([])
entries_before = env["account.move"].search_count([])
quant = quant.with_context(inventory_name=REASON)
quant.inventory_quantity = 0
quant.inventory_quantity_set = True
quant.action_apply_inventory()
MoveLine._check_third_party_owner = original

lines = env["stock.move.line"].search([("reference", "=", REASON)])
for line in lines:
    out("MOVE", line.reference, f"{line.location_id.complete_name} -> {line.location_dest_id.complete_name}",
        f"qty={line.quantity}", f"owner={line.owner_id.display_name or '-'}", f"state={line.state}")
quant.invalidate_recordset()
layers_after = env["stock.valuation.layer"].search_count([])
entries_after = env["account.move"].search_count([])
out("RESULT", f"quant_quantity={quant.exists().quantity if quant.exists() else 0}",
    f"layers {layers_before}->{layers_after}", f"entries {entries_before}->{entries_after}")
if len(lines) != 1 or lines.state != "done" or lines.quantity != QUANTITY or lines.owner_id != owner:
    error("expected one done line of 15 carrying the owner")
if layers_after != layers_before or entries_after != entries_before:
    error("a valuation layer or a journal entry was created")
env.flush_all()
alerts = env["lartdubati.stock.monitor"].search([
    ("product_id", "=", product.id), ("stock_id.complete_name", "=", LOCATION_NAME)])
out("MONITOR", f"rows={len(alerts)}")

if errors:
    env.cr.rollback()
    out("END", f"{len(errors)} error(s); rolled back")
    raise SystemExit(1)
if APPLY:
    env.cr.commit()
    out("END", "applied, 1 quant removed")
else:
    env.cr.rollback()
    out("END", "dry run, 1 quant rolled back")
