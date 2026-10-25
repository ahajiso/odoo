"""Reclassification entry of the DEXTER mitre saw: 606300 debit / 215400 credit.

Owner's test choice C28 (25/10/2026): the DEXTER mitre saw is expensed. Its bill line
(BILL/2026/10/0013, posted and paid) is on 215400; its draft fixed asset 462 is deleted
first by the accountant. A manual entry on 215400 would inherit the account's asset
profile and create an asset when posted (account_asset_management, action_post), and the
« Asset Profile » column is not offered on the entry lines: this script creates the
entry with no asset profile on either line, posts it and checks that no fixed asset was
created. Dry run by default; RECLASS_APPLY=1 commits. Refuses (nothing written) on any
unexpected state; a second run finds the posted entry and changes nothing.
"""
import os

APPLY = os.environ.get("RECLASS_APPLY") == "1"
SERVER_DB = "artdubati_test"
MODULE = "maintenance_shareholder_equipment"
EXPECTED_VERSION = "18.0.5.2.6"
BILL = "BILL/2026/10/0013"
TEMPLATE_ID = 2889          # DEXTER mitre saw
EQUIPMENT_ID = 2180         # DEXTER mitre saw – 55669982
DELETED_ASSET_ID = 462
AMOUNT = 88.22
DEBIT_CODE, CREDIT_CODE = "606300", "215400"
JOURNAL_CODE = "MISC"
REF = "BILL/2026/10/0013 – DEXTER mitre saw reclassified to expense (C28)"
LABEL = "Reclassement DEXTER mitre saw en charge (C28) – BILL/2026/10/0013"

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
company = env["res.company"].search([])
if len(company) != 1:
    raise SystemExit("REFUSED: expected one company")
env = env(context=dict(env.context, allowed_company_ids=company.ids))
out("START", f"database={env.cr.dbname}", "APPLY" if APPLY else "DRY RUN")

Move = env["account.move"]
done = Move.search([("ref", "=", REF), ("state", "=", "posted")])
if done:
    out("SKIP", f"entry already posted: {done.name}")
    env.cr.rollback()
    out("END", "dry run, 0 change(s) rolled back" if not APPLY else "applied, 0 change(s) committed")
    raise SystemExit(0)

accounts = {}
for code in (DEBIT_CODE, CREDIT_CODE):
    acc = env["account.account"].search([("code", "=", code), ("company_ids", "in", company.id)])
    if len(acc) != 1:
        error(f"account {code}: expected one, found {len(acc)}")
    accounts[code] = acc
journal = env["account.journal"].search([("code", "=", JOURNAL_CODE), ("company_id", "=", company.id)])
if len(journal) != 1 or journal.type != "general":
    error(f"journal {JOURNAL_CODE}: expected one miscellaneous journal, found {len(journal)}")
out("JOURNAL", journal.name, journal.code)

if env["account.asset"].browse(DELETED_ASSET_ID).exists():
    error(f"fixed asset {DELETED_ASSET_ID} still exists: delete it first (draft)")
equipment = env["maintenance.equipment"].browse(EQUIPMENT_ID).exists()
if not equipment or equipment.product_id.product_tmpl_id.id != TEMPLATE_ID:
    error(f"equipment {EQUIPMENT_ID} is not the DEXTER mitre saw")
elif equipment.asset_id:
    error(f"equipment {equipment.name} still has the fixed asset {equipment.asset_id.display_name}")
bill = Move.search([("name", "=", BILL), ("move_type", "=", "in_invoice")])
line = bill.invoice_line_ids.filtered(lambda l: l.product_id.product_tmpl_id.id == TEMPLATE_ID)
out("BILL", bill.name, f"state={bill.state}", f"payment={bill.payment_state}",
    f"line_account={line.account_id.code}", f"amount={line.price_subtotal}",
    f"asset={line.asset_id.id or '-'}")
if bill.state != "posted" or len(line) != 1:
    error(f"{BILL}: expected posted with one DEXTER line")
elif line.account_id.code != CREDIT_CODE or abs(line.price_subtotal - AMOUNT) > 0.001 \
        or line.asset_id:
    error(f"{BILL}: the DEXTER line is not {AMOUNT} on {CREDIT_CODE} without asset")
drafts = Move.search([("state", "=", "draft"), ("journal_id", "=", journal.id),
                      ("line_ids.account_id", "=", accounts[CREDIT_CODE].id)])
if drafts:
    error(f"draft entries on {CREDIT_CODE} in {JOURNAL_CODE}: {drafts.ids}; delete the "
          "draft created by hand first")

if errors:
    env.cr.rollback()
    out("END", f"{len(errors)} error(s); nothing written")
    raise SystemExit(1)

assets_before = env["account.asset"].search_count([])
move = Move.create({
    "move_type": "entry", "journal_id": journal.id, "date": bill.date, "ref": REF,
    "line_ids": [
        (0, 0, {"account_id": accounts[DEBIT_CODE].id, "name": LABEL, "debit": AMOUNT,
                "credit": 0.0, "asset_profile_id": False}),
        (0, 0, {"account_id": accounts[CREDIT_CODE].id, "name": LABEL, "debit": 0.0,
                "credit": AMOUNT, "asset_profile_id": False}),
    ],
})
for ml in move.line_ids:
    out("LINE", ml.account_id.code, f"debit={ml.debit}", f"credit={ml.credit}",
        f"profile={ml.asset_profile_id.name or '-'}")
    if ml.asset_profile_id:
        error(f"line {ml.account_id.code} kept an asset profile")
if not errors:
    move.action_post()
    move.message_post(body=f"{LABEL}. Bill {BILL}; draft fixed asset {DELETED_ASSET_ID} "
                           "deleted before (docs/asset_fix/reclass_entry.py).")
    equipment.message_post(body=f"Expensed (C28): entry {move.name}, {AMOUNT} from "
                                f"{CREDIT_CODE} to {DEBIT_CODE}.")
assets_after = env["account.asset"].search_count([])
out("POSTED", move.name, f"state={move.state}", f"date={move.date}",
    f"assets_before={assets_before}", f"assets_after={assets_after}")
if assets_after != assets_before or move.line_ids.asset_id:
    error("a fixed asset was created by the entry")

if errors:
    env.cr.rollback()
    out("END", f"{len(errors)} error(s); rolled back")
    raise SystemExit(1)
if APPLY:
    env.cr.commit()
    out("END", f"applied, entry {move.name} posted")
else:
    env.cr.rollback()
    out("END", "dry run, 1 entry rolled back")
